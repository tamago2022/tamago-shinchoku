#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWAの「リモコン」ボタンから来たコマンドを実行する（2026-09-03）。

流れ:
  PWA（スマホ）でボタンをタップ → obsidian://new が Vault に
  `AI出力/_ルール/コマンド_受信/<id>.md`（JSON）を作る → iCloudでMacに届く
  → このスクリプト（30秒おきのlaunchdから呼ばれる）が未処理の受信ファイルを読んで実行
     → status/commands.json に結果を追記してpush（PWAが読んで「実行しました」を表示）

対応アクション:
  resume    : 止まっているセッションを claude -p --resume で再開
  stop      : 指定pidを終了（Claudeプロセスであることを確認してから。SIGTERM）
  handoff   : 詰まっているセッションに簡易引き継ぎメッセージ付きの新セッションを立てる
  close_app : 重いアプリを終了（除外リスト＝Brave・Chromeは絶対に実行しない。未保存書類は失敗扱い）
  queue_ok    : 進捗表「たまごさんの確認待ち」で✅OKを押した番号を status/queue.json で done にする
  queue_redo  : 同じくやり直しを押した番号を waiting に戻し、items配列の先頭へ移動する（次に発車の一番手にする）
  queue_add   : 進捗表の入力欄に書いた1行（+優先度1-5）を status/queue.json の末尾へ waiting として新規追加する
                （2026-09-04追加。スマホから直接発車待ちへ積めるようにした。これまでDispatch経由でしか積めなかった）

  2026-09-04 queue_ok/queue_redo 追加：進捗表の確認ボタンは、これまで押した結果が端末内
  （localStorage）にしか残らず、Mac側の status/queue.json には一切反映されていなかった
  （index.html側コメントに「Obsidian経由でMac側へ渡す」と書かれていたが実装が無かった）。
  優先度（priority_ingest.py）・リモコン（resume/stop/handoff/close_app）と同じ
  「obsidian://new → Vault → このingest → status/queue.json」の道に乗せて実装した。

受信ファイルは消さない（記録として残す）。commands.jsonに書いたidは二重実行しない。
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
INBOX_DIR = os.path.join(VAULT, "AI出力", "_ルール", "コマンド_受信")
OUT = os.path.join(REPO, "status", "commands.json")
QUEUE = os.path.join(REPO, "status", "queue.json")
CLAUDE = os.environ.get("CLAUDE_BIN") or (os.path.expanduser("~/.local/bin/claude")
        if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

# 2026-09-03 たまごさん指定：絶対に閉じない（Chromeを含めるのは『Happy Place Station | Lovable』の
# ウィンドウを巻き込まないため。プロセス単位のquitではウィンドウ単位の除外ができないので全体を除外する）
EXCLUDED_APPS = {"Brave Browser", "Google Chrome"}


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def close_app(app):
    if not app:
        return "failed", "対象アプリ名が無い"
    if app in EXCLUDED_APPS:
        return "skipped", "%s は除外対象のため実行しません" % app
    check = run(["pgrep", "-f", app])
    if not check or not check.stdout.strip():
        return "skipped", "%s は起動していません" % app
    r = run(["osascript", "-e", 'tell application "%s" to quit' % app.replace('"', '\\"')], timeout=8)
    if r is None:
        return "failed", "タイムアウト（保存待ちの可能性）"
    time.sleep(2)
    check2 = run(["pgrep", "-f", app])
    if check2 and check2.stdout.strip():
        return "failed", "保存待ちで閉じられませんでした（未保存の書類がある可能性）"
    return "done", "%s を閉じました" % app


def resume(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    log = os.path.join(REPO, "status", "cmd-resume-%s.log" % cli[:8])
    cmd = [CLAUDE, "-p", "--resume", cli, "--permission-mode", "auto", "--output-format", "json",
           "【PWAリモコン】たまごさんがスマホから再開を指示。止まっていた続きを最後までやって。"]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s resume ===\n" % time.strftime("%Y-%m-%d %H:%M:%S")).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        return "done", "再開コマンドを送りました"
    except Exception as e:
        return "failed", str(e)


def stop(pid):
    try:
        pid = int(pid)
    except Exception:
        return "failed", "pidが不正"
    check = run(["ps", "-p", str(pid), "-o", "command="])
    if not check or not (check.stdout or "").strip():
        return "skipped", "既に終了しています"
    if "claude" not in check.stdout.lower():
        return "failed", "Claudeのプロセスではないため安全のため止めません"
    try:
        os.kill(pid, 15)  # SIGTERM。強制終了(-9)はしない
        return "done", "止めました"
    except Exception as e:
        return "failed", str(e)


def handoff(cli):
    if not cli:
        return "failed", "対象セッションIDが無い"
    new_id = str(uuid.uuid4())
    log = os.path.join(REPO, "status", "cmd-handoff-%s.log" % new_id[:8])
    prompt = ("【PWAリモコン・引き継ぎ】たまごさんがスマホから引き継ぎを指示。前のセッション（%s）が詰まっている。"
              "止まらない工場のホワイトボード（python3 /Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py next）"
              "を見て、担当を引き取り、続きを進めて。tamago-unyou-osスキルの前提に従うこと。" % cli[:8])
    cmd = [CLAUDE, "-p", "--session-id", new_id, "--permission-mode", "auto", "--output-format", "json", prompt]
    try:
        with open(log, "ab") as f:
            f.write(("\n=== %s handoff from %s ===\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), cli[:8])).encode())
            subprocess.Popen(cmd, cwd=os.path.expanduser("~"), stdout=f, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=True)
        return "done", "新セッション %s を起動しました" % new_id[:8]
    except Exception as e:
        return "failed", str(e)


# ---- 台帳の鍵（2026-09-05）----
# たまごさん「完了に入ったものもあれば、反応しないものもあります」の原因。
# 押したボタンの処理と、心臓（着火・回収）が同時に台帳を読み書きしていたため、
# 片方が古い内容で上書きして押した結果が消えていた（lost update）。
# 読む→書くの間ずっと鍵をかける（auto_launcher.py と同じ鍵ファイル）。
import fcntl
from contextlib import contextmanager

QUEUE_LOCK = os.path.join(REPO, "status", ".queue.lock")


@contextmanager
def queue_lock(timeout=10.0):
    f = open(QUEUE_LOCK, "a+")
    t0 = time.time()
    while True:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except Exception:
            if time.time() - t0 > timeout:
                break
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def _load_queue():
    return load_json(QUEUE, {"items": []})


def _save_queue(q):
    save_json(QUEUE, q)


def _find_item(items, n):
    for it in items:
        if it.get("n") == n:
            return it
    return None


def queue_add(text, priority=None):
    """進捗表の「＋発車待ちに追加」→ status/queue.json の末尾（n=最大+1）へ
    waiting状態の新規項目を追加する。2026-09-04：いままでDispatch経由でしか積めなかった
    発車待ちの列に、スマホから直接1行で積めるようにした。

    優先度（1=今すぐ…5=後回し）はitem自身の"priority"フィールドに書く。
    auto_launcher.pyのrank()はこのフィールドを最優先で見る（priority.jsonのQキー方式より単純で確実）。"""
    text = (text or "").strip()
    if not text:
        return "failed", "本文が空です"
    text = text[:400]
    try:
        p = int(priority)
    except Exception:
        p = None
    if p is not None and (p < 1 or p > 5):
        p = None
    q = _load_queue()
    items = q.get("items") or []
    next_n = (max([int(it.get("n") or 0) for it in items], default=0)) + 1
    item = {
        "n": next_n,
        "title": text[:120],
        "why": "スマホから追加",
        "what": text,
        "status": "waiting",
        "limitMin": 180,
        "model": "claude-sonnet-5",
    }
    if p is not None:
        item["priority"] = p
    items.append(item)
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番として発車待ちに追加しました（P%s）" % (next_n, p if p else "-")


def queue_ok(target):
    """進捗表「✅OK・完了にする」→ status/queue.json の該当番号を done にする。"""
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    it = _find_item(items, n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") == "done":
        return "skipped", "%d番はすでに完了です" % n
    it["status"] = "done"
    it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を完了にしました" % n


def queue_redo(target):
    """進捗表「↩︎やり直し」→ status/queue.json の該当番号を waiting に戻し、
    items配列の先頭へ移す（＝次に発車の一番手。auto_launcher.pyが次サイクルで拾う）。
    走行の残骸（sessionId/pid/startedAt/finishedAt/result/urls）は消し、新規のwaiting項目と同じ形に戻す。"""
    # 2026-09-04 たまごさん「やり直しも、今すぐやり直せないのか、急ぎのやつもある。
    #   順番待ちの後に並んでいいよ、っていうのもある」
    #   → target は "12"（今まで通り＝先頭）か "12:5"（優先度つき）で受ける。
    #     優先度が付いていれば、先頭へ割り込ませず item.priority に書いて列の順番に任せる。
    prio = None
    if ":" in str(target):
        target, _p = str(target).split(":", 1)
        try:
            prio = int(_p)
        except Exception:
            prio = None
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    idx = None
    for i, it in enumerate(items):
        if it.get("n") == n:
            idx = i
            break
    if idx is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    it = items.pop(idx)
    it["status"] = "waiting"
    it["checkedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for k in ("finishedAt", "result", "urls", "sessionId", "pid", "startedAt"):
        it.pop(k, None)
    if prio:
        it["priority"] = prio
        items.append(it)          # 順番待ちの後ろへ。優先度で拾われる
        where = "P%d で列に戻しました（急がない）" % prio
    else:
        it.pop("priority", None)
        it["priority"] = 1
        items.insert(0, it)       # 今すぐ＝先頭へ割り込ませる
        where = "列の先頭（次に発車）へ戻しました"
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を%s" % (n, where)


def queue_later(target):
    """「🟡 とりあえずOK（あとで直す）」を押したとき。

    2026-09-04 たまごさんの言葉：「70点だけど、今急ぎじゃないからいいや、っていうのもあるわけよ。
    完全には治ってないけど、まあここまでだったらとりあえずいいや、という状態がある。
    完全にオッケーじゃないんだけどね。とりあえずオッケー、だけど時間あるとき直そうね、っていうこと。
    結構俺の中では優先順位中ぐらいなのに、70点を85点に持っていくのに時間はかけたくない。」

    → **いったん完了として片づける**（確認待ちの列から外す）。
      そのうえで「あとで直す」1件を **P5（後回し）** で発車待ちの末尾に積む。
      列が空いてきたときに勝手に拾われるので、たまごさんは何もしなくてよい。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    src = None
    for it in items:
        if it.get("n") == n:
            src = it
            break
    if src is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    # 2026-09-04 たまごさん「とりあえず後回しでOKを押すと、後回しボックスに入れて欲しいのに、
    #   **押してるのに次から次へと出てくる。1回だから後回しでOKって言ったんだ。そこから消えて欲しい。**」
    #   → 「あとで直す」を新しい依頼として積み直すのをやめた（それが増え続ける原因だった）。
    #     status を later（後回しボックス）にするだけ。確認待ちからは即座に消え、発車もしない。
    #     時間ができたら「後回しを回して」の一言で waiting に戻す。
    src["status"] = "later"
    src["laterAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    src["checkedAt"] = src["laterAt"]
    src["checkNote"] = "たまごさん判定：とりあえずOK（70点。時間があるとき直す）"
    q["items"] = items
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を後回しボックスへ入れました（確認待ちからは消えます）" % n


def queue_prio(target):
    """進捗表「🚏次に発車」の行のPボタン → その番号の優先度を queue.json に書き込む。

    2026-09-04 たまごさん「そこにも俺、優先順位つけるよ」。
    これまでPボタンは端末の中（localStorage）にしか残らず、**Mac側の発車順には
    一切効いていなかった**。押した意味が無い状態だったので、他のボタンと同じ
    obsidian経由の指示に乗せ、queue.json の item.priority を直接書き換える。
    target は "37:1"（番号:優先度）。優先度0は「Pを外す」。
    """
    try:
        s = str(target)
        n_s, p_s = s.split(":", 1)
        n, p = int(n_s), int(p_s)
    except Exception:
        return "failed", "指定が不正: %r（番号:優先度 の形で渡す）" % target
    q = _load_queue()
    for it in q.get("items") or []:
        if it.get("n") == n:
            if p:
                it["priority"] = p
            else:
                it.pop("priority", None)
            q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
            _save_queue(q)
            return "done", "%d番の優先度を%sにしました" % (n, ("P%d" % p) if p else "なし")
    return "failed", "%d番がqueue.jsonに見つかりません" % n


def _repo_status(name):
    return os.path.join(REPO, "status", name)


def launch_switch(on):
    """発車のもと栓。2026-09-04 たまごさん「ガソリンが切れる。家にたどり着かなきゃいけないのに寄り道してる」

    止めているあいだも、終わったものの回収・判定・繰り上げの順番は動く。燃料だけ使わない。
    """
    flag = _repo_status("no_launch.flag")
    if on:
        try:
            os.remove(flag)
        except Exception:
            pass
        return "done", "発車を再開しました"
    with io.open(flag, "w", encoding="utf-8") as f:
        f.write("たまごさんが進捗表から止めました %s\n" % time.strftime("%Y-%m-%d %H:%M"))
    return "done", "発車を止めました（走っているものはそのまま）"


def launch_cap(target):
    """同時に走らせる本数の上限。少ないクレジットを何本に配るかをたまごさんが決める。"""
    try:
        n = int(target)
    except Exception:
        return "failed", "本数が不正: %r" % target
    n = max(0, min(6, n))
    with io.open(_repo_status("launch_cap.json"), "w", encoding="utf-8") as f:
        json.dump({"cap": n, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f, ensure_ascii=False, indent=1)
    return "done", "同時に走る本数を%d本にしました" % n


def process(cmd):
    action = cmd.get("action")
    if action in ("queue_ok", "queue_redo", "queue_add", "queue_prio", "queue_later", "queue_pause", "queue_delete"):
        with queue_lock():
            return _process_queue(action, cmd)

    target = cmd.get("target")
    if action == "close_app":
        return close_app(target)
    if action == "resume":
        return resume(target)
    if action == "stop":
        return stop(target)
    if action == "handoff":
        return handoff(target)
    return _process_other(action, cmd)


def _process_queue(action, cmd):
    target = cmd.get("target")
    if action == "queue_ok":
        return queue_ok(target)
    if action == "queue_redo":
        return queue_redo(target)
    if action == "queue_add":
        return queue_add(target, cmd.get("priority"))
    if action == "queue_prio":
        return queue_prio(target)
    if action == "queue_later":
        return queue_later(target)
    if action == "queue_pause":
        return queue_pause(target)
    if action == "queue_delete":
        return queue_delete(target)
    return "failed", "不明なアクション: %s" % action


def git_unlock(_target=None):
    """置き去りのgitロックを消す（このリポジトリの .git 直下のみ）。

    2026-09-05：Cowork側のサンドボックスから `git add` を叩くと、マウント越しでは
    `.git/index.lock` を消せず（Operation not permitted）残ってしまい、
    以後ホスト側の commit/push が全部止まる＝**進捗表が更新されなくなる**。
    ホスト側で動くこのプロセスなら消せるので、専用の指示を用意した。
    消すのは「このリポジトリの .git 直下の *.lock と objects の一時ファイル」だけ。
    """
    import glob as _glob
    removed = []
    for pat in (os.path.join(REPO, ".git", "*.lock"),
                os.path.join(REPO, ".git", "refs", "**", "*.lock"),
                os.path.join(REPO, ".git", "objects", "*", "tmp_obj_*")):
        for f in _glob.glob(pat, recursive=True):
            try:
                os.remove(f)
                removed.append(os.path.relpath(f, REPO))
            except Exception:
                pass
    return "done", ("消しました: %s" % ", ".join(removed[:6])) if removed else ("skipped", "ロックはありませんでした")[1] if False else ("消しました: %s" % ", ".join(removed[:6]) if removed else "ロックはありませんでした")


def push_unlock(_target=None):
    """5分おきの巡回が止まったときに、置き去りのロックを外す。

    2026-09-05：巡回(machine_status_push.sh)は二重起動を防ぐためロックを置くが、
    途中で死ぬとロックが残り、以後の巡回が全部 exit 0 で素通りして
    **計測もpushも止まる**（実測：02:42で止まり、進捗表が更新されなくなった）。
    中のpidが生きていなければ外す。生きているなら触らない。
    """
    lock = os.path.join(REPO, "status", ".machine_status_push.lock")
    if not os.path.exists(lock):
        return "skipped", "ロックはありません"
    try:
        pid = int(open(lock).read().strip())
    except Exception:
        pid = None
    if pid:
        try:
            os.kill(pid, 0)
            return "skipped", "巡回はまだ動いています（pid %d）" % pid
        except Exception:
            pass
    try:
        os.remove(lock)
        return "done", "止まった巡回のロックを外しました（pid %s は生きていません）" % pid
    except Exception as e:
        return "failed", str(e)


def queue_pause(target):
    """走行中の仕事を安全に引っ込めて、続きから再開できる形で列に戻す。

    2026-09-05 たまごさん：
      「**今あなたこれ1回引っ込めて**、みたいな。作業の途中で引っ込めるとどういうエラーが出ちゃうのか
       分かんないけど、**それも安全に止められるように、続きから再開できるように。**
       途中で止めても。**割り込みもあり。緊急で入るから。**」

    やること：SIGTERM（強制終了ではない）で止める → status を waiting に戻す →
    `resumeFrom` にセッションIDを残す。次に発車するとき auto_launcher が
    `claude -p --resume <id>` で**前回の続きから**起こす。最初からやり直しにはならない。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    it = _find_item(q.get("items") or [], n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") != "running":
        return "skipped", "%d番は走っていません（今は%s）" % (n, it.get("status"))
    pid = it.get("pid")
    killed = False
    if pid:
        try:
            os.kill(int(pid), 15)      # SIGTERM。-9は使わない（途中成果を書き切らせる）
            killed = True
        except Exception:
            pass
    it["status"] = "waiting"
    it["pausedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if it.get("sessionId"):
        it["resumeFrom"] = it["sessionId"]     # 続きから再開するための目印
    it.pop("pid", None)
    it["priority"] = it.get("priority") or 3
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を引っ込めました（%s。次に発車するとき続きから再開します）" % (
        n, "止めました" if killed else "すでに終わっていました")


def queue_delete(target):
    """タスクそのものを台帳から消す。

    2026-09-05 たまごさん：
      「**タスク自体削除っていう削除にして、その4つにして。**完了と、とりあえずOK（あとで直す）と、
       やり直しますと、あとタスク削除。この4つにして。」

    完了（成果として積む）とは別物。**もう要らない依頼を列から消す**ためのもの。
    消す前に status/deleted.json へ丸ごと退避する（憲法：消さずに倉庫へ。取り消せるようにしておく）。
    """
    try:
        n = int(target)
    except Exception:
        return "failed", "番号が不正: %r" % target
    q = _load_queue()
    items = q.get("items") or []
    it = _find_item(items, n)
    if it is None:
        return "failed", "%d番がqueue.jsonに見つかりません" % n
    if it.get("status") == "running" and it.get("pid"):
        try:
            os.kill(int(it["pid"]), 15)
        except Exception:
            pass
    box = os.path.join(REPO, "status", "deleted.json")
    d = load_json(box, {"items": []})
    it["deletedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    d.setdefault("items", []).append(it)
    d["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    save_json(box, d)
    q["items"] = [x for x in items if x.get("n") != n]
    q["updatedAt"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(q)
    return "done", "%d番を消しました（取り消せるよう status/deleted.json に控えてあります）" % n


def auth_probe(_target=None):
    """claude CLI が本当に認証できるかを、いちばん軽い実行で確かめる（2026-09-05）。

    たまごさんは「ログインしている」と言っている。アプリのログインとCLIの認証は
    別々に持っているので、**推測せずに実際に叩いて確かめる。**
    """
    r = run([CLAUDE, "-p", "--model", "claude-sonnet-5", "--output-format", "json", "1+1は？"], timeout=60)
    if r is None:
        return "failed", "claude が応答しませんでした（タイムアウト）"
    out = (r.stdout or "") + (r.stderr or "")
    if "Failed to authenticate" in out or "OAuth session expired" in out:
        return "failed", "まだ認証が切れています（OAuth session expired）"
    if '"result"' in out:
        try:
            import json as _j
            d = _j.loads(out.strip().splitlines()[-1])
            return "done", "認証OK。返事=%s" % str(d.get("result"))[:40]
        except Exception:
            return "done", "認証OK（応答あり）"
    return "failed", ("見慣れない応答: " + out[-200:]).replace("\n", " ")


def auth_where(_target=None):
    """認証がどこに入っているか・どのclaudeを使っているかを調べる（中身は読まない・場所と日時だけ）。"""
    import glob as _g
    lines = []
    for c in ("~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude",
              "/Applications/Claude.app/Contents/Resources/claude",
              "~/.claude/local/claude"):
        pth = os.path.expanduser(c)
        if os.path.exists(pth):
            v = run([pth, "--version"], timeout=20)
            lines.append("%s : %s" % (c, ((v.stdout or v.stderr or "").strip()[:40] if v else "応答なし")))
    for c in ("~/.claude/.credentials.json", "~/Library/Application Support/Claude/.credentials.json"):
        pth = os.path.expanduser(c)
        lines.append("%s : %s" % (c, time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(pth)))
                                  if os.path.exists(pth) else "無し"))
    k = run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"], timeout=15)
    lines.append("キーチェーン(Claude Code-credentials): %s" % ("あり" if (k and k.returncode == 0) else "無し/読めない"))
    return "done", " ｜ ".join(lines)[:900]


def restart_heartbeat(_target=None):
    """心臓を入れ直す（2026-09-05）。

    bash の while ループは起動時にまとめて読み込まれるので、`heartbeat.sh` を書き換えても
    **走っている心臓には反映されない**（実測：auth_watch.py を足したのに1時間以上呼ばれていなかった）。
    ここで一度落とす。5分おきの巡回が新しい中身で立て直す。
    """
    r = run(["pkill", "-f", "tools/heartbeat.sh"], timeout=10)
    time.sleep(1)
    chk = run(["pgrep", "-f", "tools/heartbeat.sh"], timeout=10)
    still = bool(chk and (chk.stdout or "").strip())
    # すぐ立て直す（巡回を待たない）
    try:
        subprocess.Popen(["bash", os.path.join(REPO, "tools", "heartbeat.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        return "failed", "落としたが立て直せませんでした: %s" % e
    return "done", "心臓を入れ直しました（新しい中身で起動）%s" % ("" if not still else "／古いものが残っている可能性")


def auth_login_url(_target=None):
    """ログイン用のURLだけを取り出す（2026-09-05・安全版）。

    最初の版は `p.stdout.readline()` で待っていたため、`claude setup-token` が
    入力待ちで黙り込むと**心臓ごと固まった**（07:03〜、たまごさんにPCを再起動させた）。
    **ぶら下がる読み取りは絶対に使わない。必ず時間で切って、残骸も落とす。**
    """
    r = run([CLAUDE, "setup-token"], timeout=20)
    out = ((r.stdout or "") + (r.stderr or "")) if r else ""
    run(["pkill", "-f", "setup-token"], timeout=5)
    import re as _re
    m = _re.search(r"https://\S+", out)
    if m:
        return "done", "ログインURL: %s" % m.group(0)
    return "failed", ("URLが出ませんでした: " + out[-250:]).replace("\n", " ")

def _process_other(action, cmd):
    target = cmd.get("target")
    if action == "close_app":
        return close_app(target)
    if action == "resume":
        return resume(target)
    if action == "stop":
        return stop(target)
    if action == "handoff":
        return handoff(target)
    if action == "push_unlock":
        return push_unlock(target)
    if action == "restart_heartbeat":
        return restart_heartbeat(target)
    if action == "auth_where":
        return auth_where(target)
    if action == "auth_login_url":
        return auth_login_url(target)
    if action == "auth_probe":
        return auth_probe(target)
    if action == "git_unlock":
        return git_unlock(target)
    if action == "launch_pause":
        return launch_switch(False)
    if action == "launch_resume":
        return launch_switch(True)
    if action == "launch_cap":
        return launch_cap(target)
    return "failed", "不明なアクション: %s" % action


def main():
    os.makedirs(INBOX_DIR, exist_ok=True)
    out = load_json(OUT, {"results": []})
    done_ids = {r.get("id") for r in out.get("results", [])}
    # 2026-09-04 受信箱を2つにした。
    #   Vault側(iCloud)は同期に数分かかることがあり、Dispatchからの指示が届くのが遅れた（実測4分以上）。
    #   リポジトリ内の status/inbox/ は同じディスクなので**すぐ届く**。Dispatchはこちらを使う。
    local_inbox = os.path.join(REPO, "status", "inbox")
    os.makedirs(local_inbox, exist_ok=True)
    files = sorted(glob.glob(os.path.join(INBOX_DIR, "*.md")) + glob.glob(os.path.join(local_inbox, "*.md")))
    changed = False
    for fp in files:
        try:
            txt = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            continue
        try:
            cmd = json.loads(m.group(0))
        except Exception:
            continue
        cid = cmd.get("id")
        if not cid or cid in done_ids:
            continue
        status, message = process(cmd)
        out.setdefault("results", []).append({
            "id": cid, "action": cmd.get("action"), "target": cmd.get("target"), "label": cmd.get("label"),
            "status": status, "message": message, "doneAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        done_ids.add(cid)
        changed = True
        print("%s: %s / %s -> %s (%s)" % (cid, cmd.get("action"), cmd.get("target"), status, message))
    if changed:
        out["results"] = out["results"][-200:]  # 肥やさない
        out["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save_json(OUT, out)


if __name__ == "__main__":
    main()
