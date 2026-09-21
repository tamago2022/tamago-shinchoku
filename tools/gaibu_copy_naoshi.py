#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""971番の相棒：外部から入れたもののコピーを**毎朝ひとりでに直す係**。

たまごさん（2026-09-22・原文）:
  「外部追加分のコピーを全部直す ⇨ これはもう毎日やること」
  「走った回数と、直した件数の両方を数える。走った>0 なのに 直した=0 は赤」
  「できなかったものは理由をそのまま残す。嘘のログを書かない。skip を黙って飲み込まない」

------------------------------------------------------------------
なぜ要るか（実測）
------------------------------------------------------------------
  971番（tools/gaibu_copy_nippou.py）は**数える係**として動いていた。
  09-22 06:07 時点で「手つかず16件」を毎回きちんと出していた。
  だが**直す係が居なかった。**だから数字だけが毎朝更新され、16件は16件のまま座り続けた。
  ここがその「直す係」。数える係とは別ファイルにして、判定だけを数える係から輸入する
  （＝水道水の基準を2箇所に書かない。基準が増えると必ずズレる）。

------------------------------------------------------------------
決め
------------------------------------------------------------------
  ・新しい常駐（launchd便）は増やさない。既にある5分便 machine_status_push.sh に相乗りする。
    → **心臓（auto_launcher）が死んでいても launchd が直接起こす便なので必ず回ってくる。**
  ・中で1日1回ゲートする。朝06:00以降の最初の便で走る。手で回したいときは
    status/.gaibu_copy_naoshi_force を置く（置いた次の便で即走る）。
  ・書き直しは `claude -p`（既にこの工場が使っている口。新しい課金APIを増やさない）。
  ・**材料が無いものは書かない。**題名しか無く、元コピーも無く、URLも無いものは
    「見ていないものを想像で書く」ことになるので**触らず、理由を残して一覧に出す。**
    （たまご憲法11条・関所「出典の取れない断定は書かない」／§11-3「空欄で出す」）
  ・書き直した結果は**もう一度同じ判定にかける。**水道水のままなら書き戻さない。
  ・前の文は必ず残す（status/public/gaibu_copy_naoshi.json の history）。戻せる形にする。
  ・鍵の値はどこにも書き出さない。名前と、通ったか通らないかだけ。

------------------------------------------------------------------
回線についての実測事実
------------------------------------------------------------------
  Cowork/Dispatchのサンドボックスからは Supabase へ出られない（Tunnel 403）。
  たまごさんのMacからは出る。だからここ（5分便＝Mac側）で叩く。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 判定・鍵の探索・取得は「数える係」のものをそのまま使う。**基準を2箇所に書かない。**
import gaibu_copy_nippou as nippou  # noqa: E402

JST = timezone(timedelta(hours=9))
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "gaibu_copy_naoshi.json")
GATE = os.path.join(STATUS, ".gaibu_copy_naoshi_last")
FORCE = os.path.join(STATUS, ".gaibu_copy_naoshi_force")
LOCK = os.path.join(STATUS, ".gaibu_copy_naoshi.lock")

MORNING_HOUR = 6          # 朝6時以降の最初の便で走る
LOCK_STALE_SEC = 30 * 60  # 30分以上握ったままのロックは詰まりとみなす
MAX_PER_RUN = 12          # 1回で直す上限（Macを占有しないため。残りは翌朝に回る）
CLAUDE_TIMEOUT = 150
HISTORY_KEEP = 200

CLAUDE = os.environ.get("CLAUDE_BIN") or (
    os.path.expanduser("~/.local/bin/claude")
    if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")


def claude_env():
    """キーチェーンを正本にする（command_ingest.py と同じ理由・2026-09-05の実測）。"""
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    if not os.path.exists(os.path.expanduser("~/.tamago/use_token")):
        return env
    try:
        t = io.open(os.path.expanduser("~/.tamago/claude_token"), encoding="utf-8").read().strip()
        if t:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = t
    except Exception:
        pass
    return env


# ---------------------------------------------------------------- 書き直しの注文書
# bonjovi-ojisan-kobun（コピーの型）と sekisho-jijitsu-shutten（出典の関所）を、
# スキルを読めない環境でも効く形に落としたもの。**新しい基準を発明しない。**
PROMPT = """あなたは「ごきげん補給所」のコピーを書く編集者です。
下の1件について、カードに載せる一言（whisper）を書き直してください。

【型：ボンジョビおじさん構文】
・曲紹介・動画紹介を書かない。**ただの行為を、小さな事件に変える。**
　例：電車に乗るだけ → 全員ボンジョビ部に入部／公園で歌うだけ → 町内会ロックフェス
・短く。1文か2文。全部で60〜90文字。
・クリックしたくなるものに。誘う。脅さない。煽らない。

【絶対の禁止】
・「収められています」「が映し出され」「する様子」「様子が」などの説明テンプレ。
・「必見」「見逃せない」「話題」「反響」「絶賛」「バズ」など、観測していない他人の反応。
・「代表曲のひとつ」のような誰にでも書ける説明文。
・**材料に書かれていないことを足さない。**国名・年号・人物名・関係・受賞・数字を、
　材料に無いのに書いたらその時点で失格。裏が取れないものは書かない。
・たまごさん個人を主語にしない。

【材料】ここに書いてあることだけが、あなたが知っている全部です。
題名：%(title)s
いま載っている一言：%(copy)s
出どころ：%(url)s

【出し方】
書き直した一言だけを1行で出す。前置き・説明・かぎかっこ・箇条書きを付けない。
材料が薄すぎて、何かを足さないと1行も書けない場合は、無理に書かず
NO_MATERIAL とだけ出す。"""


def load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def take_lock():
    """二重起動を防ぐ。詰まったロックは時間で剥がす（門前払いを続けない）。"""
    if os.path.exists(LOCK):
        try:
            pid = int(io.open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        age = time.time() - os.path.getmtime(LOCK)
        alive = False
        if pid:
            try:
                os.kill(pid, 0)
                alive = True
            except Exception:
                alive = False
        if alive and age < LOCK_STALE_SEC:
            return False
        try:
            os.remove(LOCK)
        except Exception:
            pass
    try:
        with io.open(LOCK, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    return True


def drop_lock():
    try:
        os.remove(LOCK)
    except Exception:
        pass


def clean(s):
    """CLIの返事を1行の一言に整える。"""
    s = (s or "").strip()
    # 前置きが付いてきたら最後の非空行を採る（CLIはたまに「はい、こちらです：」を足す）
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return ""
    s = lines[-1] if len(lines) > 1 and len(lines[-1]) >= 12 else lines[0]
    s = s.strip().strip("「」\"'`").strip()
    s = re.sub(r"^[-*・\d\.\s]+", "", s)
    return s.strip()


def ask_claude(title, copy, url, diag):
    """claude -p に書き直させる。通らなければ (None, 理由) を返す。嘘のログを書かない。"""
    prompt = PROMPT % {"title": title or "（題名なし）",
                       "copy": copy or "（まだ無い）",
                       "url": url or "（無い）"}
    cmd = [CLAUDE, "-p", "--model", "claude-sonnet-5", "--output-format", "json", prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT,
                           cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL,
                           env=claude_env())
    except subprocess.TimeoutExpired:
        return None, "claude -p が %d秒で返らなかった" % CLAUDE_TIMEOUT
    except FileNotFoundError:
        return None, "claude コマンドが見つからない（%s）" % CLAUDE
    except Exception as e:
        return None, "claude -p が起動できない（%s）" % type(e).__name__
    out = (r.stdout or "") + (r.stderr or "")
    if "Failed to authenticate" in out or "OAuth session expired" in out:
        return None, "claudeの認証が切れている（OAuth session expired）"
    if "usage limit" in out.lower() or "rate limit" in out.lower():
        return None, "claudeの利用上限に当たった"
    try:
        j = json.loads(r.stdout or "{}")
        text = j.get("result") or ""
        if j.get("total_cost_usd") is not None:
            diag.append("cost_usd=%s" % j.get("total_cost_usd"))
    except Exception:
        text = r.stdout or ""
    text = clean(text)
    if not text:
        return None, "claude -p が空を返した（rc=%s）" % r.returncode
    if "NO_MATERIAL" in text:
        return None, "材料が題名だけで、足さずには書けない（動画を見ないと書けない）"
    return text, None


def patch_copy(url, key, row_id, text):
    """admin_stock の whisper だけを1件ずつ書き戻す。丸ごと一括更新はしない。"""
    q = urllib.parse.urlencode({"id": "eq." + str(row_id)})
    body = json.dumps({"whisper": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url + "/rest/v1/admin_stock?" + q, data=body, method="PATCH",
        headers={"apikey": key, "Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8") or "[]"), r.status


def find_write_key(diag):
    """**書ける鍵**を探す。数える係は「読めればいい」ので最初に見つかった鍵で止まるが、
    こちらは書き戻すので、置き場を全部見てから一番強い鍵を採る。

    実測：数える係が拾っていたのは SUPABASE_PUBLISHABLE_KEY（読み取り用）。
    RLS が効いていれば PATCH は 401/403 で弾かれる。弾かれたらその番号を
    そのまま一覧に残す（嘘のログを書かない）。値はここから一歩も外へ出さない。
    """
    url, key, keyname, where = nippou.find_supabase(diag)
    if not url:
        return None, None, None, where
    best = (key, keyname, where, 5)
    rank = {"SERVICE_ROLE": 0, "SERVICE": 1, "SECRET": 2, "PUBLISHABLE": 4, "ANON": 4}
    for rel in nippou.ENV_RELS:
        p = os.path.join(nippou.JRS, rel)
        if not os.path.exists(p):
            continue
        env = nippou.read_env_names(p)
        for k, v in env.items():
            ku = k.upper()
            if "SUPABASE" not in ku or not v:
                continue
            r = next((sc for pref, sc in rank.items() if pref in ku), 5)
            if r < best[3]:
                best = (v, k, rel, r)
    diag.append("書き戻しに使う鍵：%s（%s）" % (best[1], best[2]))
    return url, best[0], best[1], best[2]


def pick_targets(url, key, diag, since_days):
    """昨日ぶん＋溜まっているぶんから、手つかずのものを新しい順に拾う。人は選ばない。"""
    now = datetime.now(JST)
    since = (now - timedelta(days=since_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = nippou.fetch_stock(url, key, since.isoformat())
    targets = []
    for r in rows:
        if not isinstance(r, dict) or r.get("deleted_at"):
            continue
        title = nippou.pick(r, ["title", "name", "song_title"])
        copy = nippou.pick(r, ["whisper", "copy", "lead"])
        link = nippou.pick(r, ["url", "source_url", "link", "youtube_url", "ref"])
        kind = nippou.pick(r, ["kind"])
        if link and not link.startswith("http"):
            link = ("https://youtu.be/" + link) if kind == "youtube" else ""
        why = nippou.judge(title, copy)
        if not why:
            continue
        created = nippou.pick(r, ["created_at", "createdAt", "inserted_at"])
        targets.append({"id": r.get("id"), "date": (created or "")[:10],
                        "title": title, "copy": copy, "url": link,
                        "kind": kind, "why": why})
    targets.sort(key=lambda t: t["date"], reverse=True)
    diag.append("手つかず %d件を拾った（直近%d日）" % (len(targets), since_days))
    return targets


def run(since_days=14):
    now = datetime.now(JST)
    prev = load(OUT_JSON, {}) or {}
    out = {
        "generatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "ranAt": now.isoformat(),
        "runs": int((prev.get("runs") or 0)) + 1,       # 走った回数（累計）
        "fixedTotal": int((prev.get("fixedTotal") or 0)),
        "targets": 0, "fixed": 0, "skipped": 0,
        "changes": [],     # 今回の前後
        "skips": [],       # できなかったものと、その理由（そのまま残す）
        "red": [],
        "diag": [],
        "history": (prev.get("history") or [])[:HISTORY_KEEP],
    }
    diag = out["diag"]

    url, key, keyname, where = find_write_key(diag)
    if not url:
        out["red"].append("正本（admin_stock）に手が届かない：" + where)
        return out
    out["sourceNote"] = "admin_stock（鍵：%s・%s）" % (keyname, where)

    try:
        targets = pick_targets(url, key, diag, since_days)
    except urllib.error.HTTPError as e:
        out["red"].append("admin_stock が HTTP %d（鍵は在るが通らない）" % e.code)
        return out
    except Exception as e:
        out["red"].append("admin_stock に繋がらない（%s）" % type(e).__name__)
        return out

    out["targets"] = len(targets)
    for t in targets[:MAX_PER_RUN]:
        text, why_ng = ask_claude(t["title"], t["copy"], t["url"], diag)
        if not text:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"], "reason": why_ng})
            continue
        # 書き直したものを**同じ判定にもう一度かける。**水道水のままなら書き戻さない。
        again = nippou.judge(t["title"], text)
        if again:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き直したがまだ水道水（%s）：%s" % (again, text)})
            continue
        try:
            _rep, st = patch_copy(url, key, t["id"], text)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き戻しが HTTP %d（%s）" % (e.code, body),
                                 "draft": text})
            continue
        except Exception as e:
            out["skips"].append({"id": t["id"], "date": t["date"], "title": t["title"],
                                 "was": t["copy"], "why": t["why"],
                                 "reason": "書き戻せない（%s）" % type(e).__name__,
                                 "draft": text})
            continue
        ch = {"id": t["id"], "date": t["date"], "title": t["title"],
              "was": t["copy"], "now": text, "why": t["why"],
              "url": t["url"], "at": now.strftime("%Y-%m-%d %H:%M"), "http": st}
        out["changes"].append(ch)
        out["fixed"] += 1

    out["skipped"] = len(out["skips"])
    out["fixedTotal"] += out["fixed"]
    out["history"] = (out["changes"] + out["history"])[:HISTORY_KEEP]
    out["remaining"] = max(0, out["targets"] - out["fixed"])

    # 赤の決まり（たまごさん 2026-09-22 指定）
    # 「走った>0 なのに 直した=0」＝動いているのに何も取れていない。一番たちの悪い壊れ方。
    if out["targets"] > 0 and out["fixed"] == 0:
        out["red"].append("走ったのに1件も直っていない（対象%d件・理由は下の一覧）" % out["targets"])
    if out["skips"]:
        out["red"].append("直せなかったものが%d件（理由つきで下に出している）" % len(out["skips"]))
    out["redCount"] = len(out["red"])
    return out


def main():
    argv = sys.argv[1:]
    force = ("--force" in argv) or os.environ.get("NAOSHI_FORCE") == "1"
    if os.path.exists(FORCE):
        force = True
        try:
            os.remove(FORCE)
        except Exception:
            pass
    now = datetime.now(JST)
    if not force:
        # 1日1回。朝6時以降の最初の便で走る。
        if now.hour < MORNING_HOUR:
            return
        if os.path.exists(GATE):
            try:
                last = io.open(GATE, encoding="utf-8").read().strip()[:10]
            except Exception:
                last = ""
            if last == now.strftime("%Y-%m-%d"):
                return
    if not take_lock():
        return
    try:
        out = run()
        save(OUT_JSON, out)
        try:
            with io.open(GATE, "w", encoding="utf-8") as f:
                f.write(now.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            pass  # 印が書けなくても直した事実は残す（止まらない）
        # 直した直後に「数える係」を回し直して、1枚の数字をその場で合わせる。
        try:
            with io.open(os.path.join(STATUS, ".gaibu_copy_nippou_force"),
                         "w", encoding="utf-8") as f:
                f.write(now.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            pass
    finally:
        drop_lock()


if __name__ == "__main__":
    main()
