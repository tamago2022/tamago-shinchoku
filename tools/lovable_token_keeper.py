#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lovableの鍵を期限が切れる前に自動で更新し、失敗しても鍵を消さない（2026-10-04・Codex #580 助言）。

決まり：
  ・期限の5分前から更新を試みる（expires_in と保存時刻 _saved_at から計算）。
  ・invalid_grant（鍵そのものが無効＝人の同意が要る）と、通信障害・サーバ側の一時不調（やり直せば直る）を区別する。
      invalid_grant → 鍵ファイルは**消さない**。状態に『同意のやり直しが必要』と記録するだけ。
      通信障害など  → 何も壊さず、次の回にやり直す。
  ・書き込みは一時ファイル→置き換え。成功したら .last_good にも残す。
  ・最後に成功した時刻・最後の失敗の種類を ~/.tamago/lovable_keeper_state.json に残す（中身の鍵は書かない）。
心臓から lovable_auth_keeper.run() 経由で呼ばれる（15秒おき。ここで60秒に1回へ絞る）。

【31756番・2026-10-06・Single-flightガード】
  ★実測で見つけた穴：`tools/heartbeat.sh` は `top_status.py` を**待たずに**15秒おき起動する
    （`tick_every` の間引き無し・`&` でバックグラウンド投げっぱなし）。`top_status.py` は
    import時に `lovable_auth_keeper.run()` → この `ensure_fresh()` を呼ぶ。1回の実行が
    15秒を超えて重なると、**複数プロセスが同時に `ensure_fresh()` に入ってくる**。
    旧実装は「`lastTryTs` を読んで60秒以内ならやめる」という check-then-act だけで、
    読む→書くの間に鍔(つば)が無かった（TOCTOU）。ほぼ同時に2プロセスが「60秒経った」と
    判定すると、**同じ refresh_token を使って2本同時にLovableへ投げる**ことになる。
    OAuthのrefresh_tokenは使い捨て（ローテーション）なので、1本は成功しもう1本は
    `invalid_grant`（＝人の同意が要る誤判定）を引く恐れがあり、トークンファイルの
    書き込み自体も鍔無しで競合する。
  ★直し方：実際に更新処理へ入れるのを**1プロセスだけ**にする（シングルフライト）。
    `~/.tamago/.lovable_token_keeper.lock` を `fcntl.flock` の非ブロッキング排他で取り、
    取れなかった側は待たずに `"skipped"` を返して即終わる（次の心臓周回でまた来るので
    待つ必要が無い。`queue_store.queue_lock` と同じ fcntl パターンを流用）。
"""
import fcntl
import io
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.path.expanduser("~/.tamago/lovable_oauth.json")
STATE = os.path.expanduser("~/.tamago/lovable_keeper_state.json")
LOCK = os.path.expanduser("~/.tamago/.lovable_token_keeper.lock")  # ★31756番：単独飛行ガード
TOKEN_URL = "https://lovable.dev/oauth/token"
SKEW = 300  # 期限の5分前から更新
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _read(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _state(**kw):
    s = _read(STATE)
    s.update(kw)
    s["checkedAt"] = time.strftime("%F %T")
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)
    os.replace(tmp, STATE)


def _write_token(tok):
    tmp = TOKEN + ".tmp%d" % os.getpid()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tok, f)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(TOKEN) and os.path.getsize(TOKEN) > 2:
        shutil.copyfile(TOKEN, TOKEN + ".prev")
        os.chmod(TOKEN + ".prev", 0o600)
    os.replace(tmp, TOKEN)
    shutil.copyfile(TOKEN, TOKEN + ".last_good")
    os.chmod(TOKEN + ".last_good", 0o600)


def ensure_fresh(force=False):
    """戻り値: 'fresh'（まだ有効）/ 'refreshed' / 'transient'（通信不調・次回やり直し）/
    'need_consent'（人の同意が要る）/ 'nokey' / 'skipped'（★他のプロセスが同時に更新中。
    1本に絞るためこちらは何もせず譲った。次の心臓周回でまた来る）。

    ★31756番：実際の更新処理（下の _ensure_fresh_locked）に入れるのは常に1プロセスだけ。
    `fcntl.flock` の非ブロッキング排他で鍔を取り、取れなければ待たずに 'skipped' を返す。
    待たない理由：ここは15秒おきの心臓から呼ばれるので、次の周回で自然にリトライされる。
    ブロッキング待ちにすると、重なった分のプロセスが鍵待ちで積み重なってしまう。
    """
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            return "skipped"
        try:
            return _ensure_fresh_locked(force)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
    finally:
        os.close(fd)


def _ensure_fresh_locked(force=False):
    """★鍔（ensure_fresh）の中でだけ呼ばれる。ここが実際の更新処理の本体。"""
    tok = _read(TOKEN) or _read(TOKEN + ".last_good")
    rt = tok.get("refresh_token")
    if not rt:
        return "nokey"
    st = _read(STATE)
    if not force and time.time() - st.get("lastTryTs", 0) < 60:
        return "fresh"
    exp = (tok.get("_saved_at") or 0) + (tok.get("expires_in") or 0)
    if not force and tok.get("expires_in") and tok.get("_saved_at") and time.time() < exp - SKEW:
        return "fresh"
    _state(lastTryTs=time.time())
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": rt,
        "client_id": tok.get("_client_id") or "6d465f583e1e4ce5801b1616f735670c"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            new = json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8", "ignore")).get("error", "")
        except Exception:
            err = ""
        if e.code in (400, 401) and err == "invalid_grant":
            _state(lastFailure="invalid_grant", needConsent=True)
            return "need_consent"          # ★鍵は消さない
        _state(lastFailure="http_%s" % e.code)
        return "transient"
    except Exception as e:
        _state(lastFailure="network:%s" % type(e).__name__)
        return "transient"
    if not new.get("access_token"):
        _state(lastFailure="no_access_token")
        return "transient"
    tok.update(new)                          # 新しい refresh_token が返らなければ古いのを残す
    tok["_saved_at"] = time.time()
    _write_token(tok)
    _state(lastOkAt=time.strftime("%F %T"), lastFailure="", needConsent=False, expiresIn=new.get("expires_in"))
    return "refreshed"


if __name__ == "__main__":
    print(ensure_fresh(force=True))
