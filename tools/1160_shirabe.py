#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1160番【調べもの常駐ライン】Gensparkに「調べて」を1本ずつ絶やさず流し続ける係。

━━ なぜ要るか（2026-09-26・たまごさん原文）━━
  「俺がこれまで調べてって言ったことを、全部調べさせて。」
  「1件だけ投げて終わりにするな。Gensparkを休ませない常駐ラインにする。」
  「Gensparkが薄い／返さないときは突き返して書き直させる。1回で諦めない。」

━━ 実測で分かっていること（憶測なし・2026-09-26）━━
  ・gsk は /Users/mac/.npm-global/bin/gsk（1.14.0）。サンドボックスからは出られない＝心臓（Mac）から走らせる。
  ・`gsk me` は消費0。残クレジット 574.837（2026-09-26 11:44 実測）。plan=plus。
  ・`gsk task create deep_research --args-file <json>` は **投げて数秒で返る**（async）。
    返り値の project_id を `gsk task status <project_id>` で追う。
  ・投げた直後の残クレジットは **変わらなかった**（574.837 → 574.837）。
    ＝ deep_research は投げた時点では引かれない。終わってからの残も毎回記録して確かめる。

━━ 決まり ━━
  ① 消費0の口だけ（deep_research / super_agent）。Claw・AI Developer・音声は呼ばない。
  ② 投げる前と後の残クレジットを必ず台帳に書く（status/1160/daicho.jsonl）。
  ③ 残が CREDIT_FLOOR を切ったら **止まるのではなく待つ**（次の周回で見に来る）。
  ④ 同時に走らせるのは MAX_INFLIGHT 本まで。1本終わったら即次を着火する。
  ⑤ 薄い答え（出典URLが少ない／短い／失敗例が無い）は `gsk task ask` で突き返す。最大 MAX_SASHIMODOSHI 回。
  ⑥ status/genspark.stop があれば1本も投げない（栓）。
  ⑦ たまごさんに質問しない。

━━ 使い方 ━━
    python3 tools/1160_shirabe.py            # 1周（心臓から1分おきに呼ばれる本体）
    python3 tools/1160_shirabe.py --joukyou   # いまの状態を出す
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DIR = os.path.join(REPO, "status", "1160")
QUEUE = os.path.join(DIR, "queue.jsonl")
KOTAE = os.path.join(DIR, "kotae")
DAICHO = os.path.join(DIR, "daicho.jsonl")
RAW = os.path.join(DIR, "raw")
LOCK = os.path.join(DIR, "lock")
LOG = os.path.join(DIR, "nagashi.log")
STOP = os.path.join(REPO, "status", "genspark.stop")
GSK = "/Users/mac/.npm-global/bin/gsk"

MAX_INFLIGHT = 2          # 同時に走らせる本数
CREDIT_FLOOR = 40.0       # これを切ったら投げない（待つ）
MAX_SASHIMODOSHI = 2      # 突き返しの上限
STALE_MIN = 45            # これ以上 mtime が動かなければ死んだと見る（分）
LOCK_STALE = 600          # 鍵が居座ったら壊す（秒）
MIN_CHARS = 3500          # 答えの最低の長さ
MIN_URLS = 8              # 答えに要る出典URLの本数
SHIPPAI_GO = ("失敗", "やめ", "撤退", "事故", "戻し", "規約", "止めた", "断念")


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def log(s):
    try:
        os.makedirs(DIR, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (now(), s))
    except Exception:
        pass


def daicho(rec):
    try:
        os.makedirs(DIR, exist_ok=True)
        rec = dict(rec)
        rec["at"] = now()
        with io.open(DAICHO, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ───────── 鍵（二重投げを止める） ─────────
def kagi_toru():
    os.makedirs(DIR, exist_ok=True)
    try:
        if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) > LOCK_STALE:
            os.remove(LOCK)
            log("居座った鍵を壊した")
    except Exception:
        pass
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def kagi_hanasu():
    try:
        os.remove(LOCK)
    except Exception:
        pass


# ───────── 列（queue.jsonl） ─────────
def yomu():
    rows = []
    if not os.path.exists(QUEUE):
        return rows
    with io.open(QUEUE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def kaku(rows):
    os.makedirs(DIR, exist_ok=True)
    tmp = QUEUE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, QUEUE)


# ───────── gsk ─────────
def gsk(args, timeout=180):
    try:
        r = subprocess.run([GSK] + list(args), capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, "ERR %s" % e


def zan():
    """残クレジット（消費0）。取れなければ None。"""
    rc, out = gsk(["me"], timeout=60)
    try:
        m = re.search(r'"credit_balance"\s*:\s*([0-9.]+)', out)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


def kekka_toru(pid):
    """(state, mtime, 本文) を返す。

    ★2026-09-26 実測で分かった落とし穴（1回やらかした）：
      走っている途中の `task status` も result_content を返す。中身は「検索の航跡」で、
      レポート本文ではない。長さも出典URLの数も足りてしまうので、検品を通り抜ける。
      → **state が finished になるまで受け取らない。**
      終わったときの result_content.content は list で、**いちばん長い要素が本文**
      （実測：item[0] が24,931字の完成レポート、item[1] は65字の見出しだけ）。
    """
    rc, out = gsk(["task", "status", pid], timeout=240)
    try:
        j = json.loads(out[out.index("{"):])
    except Exception:
        return ("fetch_ng", None, "")
    d = (j or {}).get("data") or {}
    state = d.get("state") or "?"
    if d.get("stop_reason") == "finished":
        state = "finished"
    mtime = d.get("mtime")
    rcont = d.get("result_content") or {}
    body = rcont.get("content")
    if isinstance(body, list):
        body = max([str(x) for x in body] or [""], key=len)
    body = body or ""
    try:
        os.makedirs(RAW, exist_ok=True)
        with io.open(os.path.join(RAW, "%s.json" % pid), "w", encoding="utf-8") as f:
            f.write(out)
    except Exception:
        pass
    return (state, mtime, body)


# ───────── 検品（薄いかどうか） ─────────
def usui(body):
    """薄ければ理由の文字列、良ければ None。"""
    if not body:
        return "中身が空"
    # 使い回しの読み物部分だけを見る（アーカイブ部分を含んでも長さは足りる）
    urls = set(re.findall(r"https?://[^\s\)\]\"'>]+", body))
    if len(body) < MIN_CHARS:
        return "短すぎる（%d文字 < %d）" % (len(body), MIN_CHARS)
    if len(urls) < MIN_URLS:
        return "出典URLが少ない（%d本 < %d）" % (len(urls), MIN_URLS)
    if not any(g in body for g in SHIPPAI_GO):
        return "失敗例・やめた事例が入っていない"
    return None


SASHIMODOSHI_BUN = (
    "この答えは受け取れません。理由：{riyuu}。\n"
    "同じ問いに、次を満たして書き直してください。\n"
    "・すべての事実に出典URLを本文中に併記する（実在するURLだけ。存在を確認できないURLは書かない）\n"
    "・数字は必ず出典URLつき。出典が取れない数字は書かない\n"
    "・失敗例・やめた事例・規約に触れて撤退した事例を各章に必ず入れる\n"
    "・憶測・一般論で埋めない。確認できなかったことは「公開情報では確認できなかった」と書く\n"
    "・日本語の長文レポートとして、章立てして最後に出典一覧を通し番号つきで付ける\n"
    "・最低8本以上の出典URLを挙げる\n"
    "最後に、まとめたレポート本文を全文出力してください。"
)


def main():
    os.makedirs(DIR, exist_ok=True)
    os.makedirs(KOTAE, exist_ok=True)

    if os.path.exists(STOP) or os.path.exists(os.path.join(DIR, "stop")):
        return 0
    if not os.path.exists(GSK):
        log("gsk が無い")
        return 1
    if not kagi_toru():
        return 0
    try:
        rows = yomu()
        if not rows:
            return 0
        z = zan()

        # ① 走っている本を見る
        inflight = 0
        for r in rows:
            if r.get("state") != "走っている":
                continue
            pid = r.get("project_id")
            if not pid:
                r["state"] = "順番待ち"
                continue
            state, mtime, body = kekka_toru(pid)
            r["last_poll"] = now()
            r["gsk_state"] = state
            owatta = str(state) in ("finished", "completed", "succeeded", "done")
            shinda = str(state) in ("failed", "error", "stopped", "cancelled")
            # running_or_stale は mtime で見分ける
            furui = False
            if mtime:
                try:
                    t = datetime.strptime(str(mtime)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    furui = (datetime.now(timezone.utc) - t) > timedelta(minutes=STALE_MIN)
                except Exception:
                    pass
            # ★終わっていないものは、中身がどれだけ長くても受け取らない（航跡なので）
            if not owatta and not shinda and not furui:
                inflight += 1
                continue

            riyuu = usui(body)
            if riyuu is None and owatta:
                # 取れた
                p = os.path.join(KOTAE, "%s.md" % r["id"])
                with io.open(p, "w", encoding="utf-8") as f:
                    f.write("# %s\n\n" % r.get("title", r["id"]))
                    f.write("- 調べたAI: Genspark（deep_research）\n")
                    f.write("- 投げた: %s\n" % r.get("submitted_at"))
                    f.write("- 取れた: %s\n" % now())
                    f.write("- 突き返した回数: %d\n" % r.get("sashimodoshi", 0))
                    f.write("- タスク: %s\n\n---\n\n" % r.get("task_url", ""))
                    f.write(body)
                r["state"] = "取れた"
                r["kotae"] = os.path.relpath(p, REPO)
                r["zan_after"] = z
                daicho({"id": r["id"], "nani": "取れた", "title": r.get("title"),
                        "zan": z, "文字数": len(body)})
                log("取れた %s（%d文字）" % (r["id"], len(body)))
                continue

            # 終わっているのに薄い／死んでいる → 突き返す
            if riyuu is None:
                riyuu = "終わったのに本文が取れない（state=%s）" % state
            if r.get("sashimodoshi", 0) < MAX_SASHIMODOSHI:
                r["sashimodoshi"] = r.get("sashimodoshi", 0) + 1
                msg = SASHIMODOSHI_BUN.format(riyuu=riyuu)
                rc, out = gsk(["task", "ask", pid, "-m", msg], timeout=180)
                r["state"] = "走っている"
                r["last_sashimodoshi"] = now()
                inflight += 1
                daicho({"id": r["id"], "nani": "突き返した", "riyuu": riyuu,
                        "回数": r["sashimodoshi"], "rc": rc, "zan": z})
                log("突き返した %s（%s）" % (r["id"], riyuu))
            else:
                r["state"] = "取れない"
                r["riyuu"] = riyuu
                daicho({"id": r["id"], "nani": "取れない", "riyuu": riyuu, "zan": z})
                log("諦めた %s（%s）" % (r["id"], riyuu))

        # ② 空きがあれば次を着火
        if z is not None and z < CREDIT_FLOOR:
            log("残 %.3f < %.1f なので投げずに待つ" % (z, CREDIT_FLOOR))
        else:
            for r in rows:
                if inflight >= MAX_INFLIGHT:
                    break
                if r.get("state") != "順番待ち":
                    continue
                af = os.path.join(REPO, r["args_file"])
                if not os.path.exists(af):
                    r["state"] = "票が無い"
                    continue
                ttype = r.get("task_type", "deep_research")
                rc, out = gsk(["task", "create", ttype, "--args-file", af], timeout=300)
                pid = None
                turl = None
                try:
                    j = json.loads(out[out.index("{"):])
                    pid = ((j or {}).get("data") or {}).get("project_id")
                    turl = ((j or {}).get("data") or {}).get("task_url")
                except Exception:
                    pass
                if pid:
                    r["state"] = "走っている"
                    r["project_id"] = pid
                    r["task_url"] = turl
                    r["submitted_at"] = now()
                    r["zan_before"] = z
                    inflight += 1
                    daicho({"id": r["id"], "nani": "投げた", "title": r.get("title"),
                            "project_id": pid, "task_url": turl, "zan_before": z})
                    log("投げた %s → %s" % (r["id"], pid))
                else:
                    r["shippai"] = (r.get("shippai", 0) + 1)
                    if r["shippai"] >= 3:
                        r["state"] = "投げられない"
                    daicho({"id": r["id"], "nani": "投げられない", "out": out[:400]})
                    log("投げられない %s: %s" % (r["id"], out[:200]))

        kaku(rows)
        # ③ いまの状態を1枚
        with io.open(os.path.join(DIR, "joukyou.json"), "w", encoding="utf-8") as f:
            json.dump({
                "at": now(), "zan": z,
                "走っている": sum(1 for r in rows if r.get("state") == "走っている"),
                "順番待ち": sum(1 for r in rows if r.get("state") == "順番待ち"),
                "取れた": sum(1 for r in rows if r.get("state") == "取れた"),
                "取れない": sum(1 for r in rows if r.get("state") == "取れない"),
                "全部": len(rows),
            }, f, ensure_ascii=False, indent=2)
    finally:
        kagi_hanasu()
    return 0


if __name__ == "__main__":
    if "--joukyou" in sys.argv:
        p = os.path.join(DIR, "joukyou.json")
        print(io.open(p, encoding="utf-8").read() if os.path.exists(p) else "{}")
        sys.exit(0)
    sys.exit(main())
