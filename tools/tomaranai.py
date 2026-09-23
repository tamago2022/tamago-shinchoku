#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/tomaranai.py ── 止まらない係。手が空いたら、聞かずに自分で発車する。

たまごさん（2026-09-26）:
  「手が空いた＝走行0本を検知したら、こちらに聞かずに台帳の上から自分で発車する。
    launchdで1分おき。『やることがない』を存在させない。
    証拠＝自動発車したログの行数。」
  「俺に言われて動き出すのはもうダメだよ、30点。」

★聞かない。★止まらない。★落ちても続きから（状態は全部ファイルに置く）。

━━ 何を見て「手が空いた」と判断するか ━━
  ① いま走っている本数が0（status/queue.json の running）
  ② 直近6時間、本物の発車が0本（空回しだけ＝実質止まっている）
  ③ 今日いちども完了が出ていない（status/shukudai/count.jsonl の closedToday=0）
  ④ 宿題の残りが昨日から減っていない
  ★どれか1つでも当たったら発車する。全部そろうのを待たない。

━━ 何を発車するか（台帳の上から）━━
  1. 1152-nankai.html のP1（3回以上言わせたもの）… 一番高くついている借金
  2. 宿題台帳の未完了を古い順
  3. それも無ければ0円の工程（tools/aitara_mawasu.py の順番）
  ★「やることがない」は存在しない。3が必ず当たるから。

━━ 守っていること ━━
  - 1回の発車で積むのは既定2本まで（暴走で列を埋めない）
  - 同じ案件を二重に積まない（queue_add が skipped を返す＋自分でも印を持つ）
  - たまごさんに質問しない。判断して、やったことをログに残す
  - ブラウザを使わない・AIをここでは呼ばない（積むだけ）＝この係自体は0円

使い方
    python3 tools/tomaranai.py            # 1回見て、空いていれば発車（launchd/心臓から）
    python3 tools/tomaranai.py --show     # いまの判定だけ（1バイトも書かない）
    python3 tools/tomaranai.py --self-test
"""
from __future__ import annotations

import datetime
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

QUEUE = os.path.join(ST, "queue.json")
COUNT = os.path.join(ST, "shukudai", "count.jsonl")
DAICHO = os.path.join(ST, "shukudai", "daicho.jsonl")
NANKAI = os.path.join(ST, "public", "nankai.json")
LOG = os.path.join(ST, "tomaranai.jsonl")          # ★証拠。行数がそのまま自動発車の回数
STATE = os.path.join(ST, ".tomaranai_state.json")  # ★落ちても続きから
NO_LAUNCH = os.path.join(ST, "no_launch.flag")
STOP = os.path.join(ST, "tomaranai.stop")          # 止めたいときはこれを置くだけ

JST = datetime.timezone(datetime.timedelta(hours=9))
IKKAI_NI = 2          # 1回の発車で積む上限
KANKAKU_BYO = 300     # 同じ理由で積み直すまでの最短間隔（秒）＝1分おきに呼ばれても暴れない

OPEN_STATES = ("未着手", "走行中", "確認待ち", "止まっている", "引き継ぎ")


def now():
    return datetime.datetime.now(JST)


def stamp():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsonl(p):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def append(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def save_state(s):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# ────────────────────────────────────────── 手が空いているか


def hashiitteru():
    """いま走っている本数と、発車待ちの本数。"""
    q = load_json(QUEUE, {}) or {}
    items = q.get("items") or []
    run = len([i for i in items if (i.get("status") or "") == "running"])
    machi = len([i for i in items if (i.get("status") or "") in ("waiting", "ready", "queued")])
    return run, machi


def honmono6h():
    """直近6時間に出た本物の発車。空回しは数えない（tools/aitara_mawasu.py と同じ見方）。"""
    try:
        import aitara_mawasu
        return aitara_mawasu.honmono_ga_deteru()
    except Exception:
        return 0


def kyou_no_kazu():
    """今日の完了件数と、残りが減っているか。"""
    h = jsonl(COUNT)
    if not h:
        return {"closedToday": 0, "open": None, "prevOpen": None, "hetteru": False}
    t = h[-1]
    op, pv = t.get("open"), t.get("prevOpen")
    return {"closedToday": int(t.get("closedToday") or 0), "open": op, "prevOpen": pv,
            "hetteru": bool(pv is not None and op is not None and op < pv)}


def mitate():
    """手が空いているかの見立て。★1つでも当たれば発車。"""
    run, machi = hashiitteru()
    hm = honmono6h()
    k = kyou_no_kazu()
    riyuu = []
    if run == 0:
        riyuu.append("走行0本")
    if hm == 0:
        riyuu.append("直近6時間 本物の発車0本")
    if k["closedToday"] == 0:
        riyuu.append("今日の完了0件")
    if k["prevOpen"] is not None and not k["hetteru"]:
        riyuu.append("宿題が昨日から減っていない")
    return {
        "at": stamp(), "running": run, "machi": machi, "honmono6h": hm,
        "closedToday": k["closedToday"], "open": k["open"], "prevOpen": k["prevOpen"],
        "aiteru": bool(riyuu), "riyuu": riyuu,
        "tomete": os.path.exists(STOP),
        "loginKire": os.path.exists(NO_LAUNCH),
    }


# ────────────────────────────────────────── 何を発車するか


def tsugi_no_tama(n=IKKAI_NI):
    """台帳の上から、次に発車する案件を n 本。

    ★順番は1か所（ここ）。他の場所に書かない。
      1) 3回以上言わせたもの（P1）… 一番高くついている借金から返す
      2) 宿題台帳の未完了を古い順
    """
    sunde = set((load_json(STATE, {}) or {}).get("hasshaZumi") or [])
    # ★もう列に並んでいる題名は選ばない。選ぶと queue_add が skipped を返すだけで、
    #   「2本発車した」と書いてあるのに列は1本も増えていない＝嘘のログになる。
    #   （2026-09-26 実測：初回の2本が両方 skipped だった）
    import re as _re
    def _k(s):
        return _re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "",
                       str(s or "")).lower()[:24]
    # ★状態を問わず、列に「その題名がある」なら選ばない。queue_add は題名で重複を
    #   見ているので、hold / stuck / done に居るものを選んでも skipped が返るだけ。
    #   止まっている案件を起こし直すのは復活係（tools/fukkatsu.py）の仕事で、ここではない。
    narande = {_k(i.get("title")) for i in ((load_json(QUEUE, {}) or {}).get("items") or [])}
    tama = []

    pub = load_json(NANKAI, {}) or {}
    for r in (pub.get("rows") or []):
        if len(tama) >= n:
            break
        if int(r.get("count") or 1) < 3 or r.get("state") == "完了":
            continue
        if r.get("id") in sunde or _k(r.get("title")) in narande:
            continue
        tama.append({"id": r["id"], "title": r["title"], "pri": 1,
                     "naze": "★%d回言わせている" % r["count"],
                     "doneWhen": "%s——が本番に出ていて、開いたURLが200で返る" % r["title"][:80]})

    if len(tama) < n:
        rows = [r for r in jsonl(DAICHO)
                if r.get("state") in OPEN_STATES and r.get("actionable")
                and r.get("id") not in sunde and not r.get("queuedAt")
                and _k(r.get("title")) not in narande]
        # 台帳の priority は数字のものと文字（"P1" 等）が混ざっている。
        # 比べる前に必ず数字へ落とす（混ざったまま sort すると TypeError で係ごと死ぬ）。
        def _p(v):
            try:
                return int(str(v).strip().lstrip("PpＰ") or 5)
            except Exception:
                return 5
        rows.sort(key=lambda r: (_p(r.get("priority")), str(r.get("saidAt") or "")))
        for r in rows[:n - len(tama)]:
            tama.append({"id": r["id"], "title": r["title"],
                         "pri": _p(r.get("priority")) if _p(r.get("priority")) <= 5 else 3,
                         "naze": "宿題台帳の古いもの（%s）" % (r.get("saidAt") or "日付不明"),
                         "doneWhen": r.get("doneWhen") or ""})
    return tama


def tsumu(tama, dry=False):
    """発車待ちに積む。★たまごさんに聞かない。"""
    try:
        import command_ingest
    except Exception as e:
        return [], "command_ingest を読めません: %s" % e
    try:
        import queue_store
        lock = queue_store.queue_lock
    except Exception:
        import contextlib
        lock = contextlib.nullcontext

    done = []
    for t in tama:
        body = "\n".join([
            "【タスク】%s" % t["title"],
            "【完了条件】%s" % t["doneWhen"],
            "【なぜ今これか】%s（止まらない係が自動で発車）" % t["naze"],
            "【報告】完了/問題/判断待ちの3行以内。本番反映があれば直リンク必須。",
            "★完了は自己申告できない。tools/oni_modoshi.py の検品を通るまで完了にならない。",
            "たまごさんに質問しない。判断は自分でして、報告に「こう決めた」と書く。",
        ])
        if dry:
            done.append({"id": t["id"], "st": "dry", "title": t["title"]})
            continue
        try:
            with lock():
                st, msg = command_ingest.queue_add(body, priority=t["pri"],
                                                   label=t["title"][:60], origin="user")
        except Exception as e:
            st, msg = "failed", str(e)
        done.append({"id": t["id"], "st": st, "msg": str(msg)[:120], "title": t["title"][:80]})
    return done, None


def zeroen_wo_mawasu():
    """積むタマが無いときの最後の逃げ道。★0円の工程を回す＝「やることがない」を作らない。"""
    p = os.path.join(HERE, "aitara_mawasu.py")
    if not os.path.exists(p):
        return None
    try:
        r = subprocess.run(["python3", p], capture_output=True, text=True,
                           timeout=900, cwd=REPO)
        return {"rc": r.returncode, "de": (r.stdout or "")[-200:]}
    except Exception as e:
        return {"rc": None, "de": "%s: %s" % (type(e).__name__, e)}


# ────────────────────────────────────────── 本体


def hashiru(dry=False):
    m = mitate()
    if m["tomete"]:
        return dict(m, shita="止めています（status/tomaranai.stop）", hassha=[])
    if not m["aiteru"]:
        return dict(m, shita="何もしない（手が空いていない）", hassha=[])

    st = load_json(STATE, {}) or {}
    # 1分おきに呼ばれるので、同じ理由で積み直すのは5分に1回まで
    last = st.get("lastHasshaEpoch") or 0
    import time as _t
    if not dry and (_t.time() - last) < KANKAKU_BYO:
        return dict(m, shita="様子見（前の発車から%d秒）" % int(_t.time() - last), hassha=[])

    tama = tsugi_no_tama()
    hassha, err = ([], None)
    zeroen = None
    if tama:
        hassha, err = tsumu(tama, dry=dry)
    else:
        zeroen = None if dry else zeroen_wo_mawasu()

    rec = dict(m, shita=("%d本を自動で発車" % len(hassha)) if hassha
               else "積むタマが無いので0円の工程を回した",
               hassha=hassha, zeroen=zeroen, err=err)
    if not dry:
        append(LOG, rec)
        ok = [h["id"] for h in hassha if h.get("st") in ("done", "ok", "skipped")]
        st["hasshaZumi"] = (st.get("hasshaZumi") or [])[-400:] + ok
        st["lastHasshaEpoch"] = _t.time()
        st["lastAt"] = stamp()
        st["goukei"] = int(st.get("goukei") or 0) + len(ok)
        save_state(st)
    return rec


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        m = mitate()
        for k in ("running", "honmono6h", "closedToday", "aiteru", "riyuu"):
            if k not in m:
                ng.append("見立てに %s が無い" % k)
        r = hashiru(dry=True)
        if "shita" not in r:
            ng.append("dry run が結果を返さない")
        if os.path.exists(LOG) and r.get("hassha"):
            pass
        print("自己試験：%s／走行%s本・本物6h%s本・今日の完了%s件 → %s"
              % ("OK" if not ng else "NG", m["running"], m["honmono6h"],
                 m["closedToday"], "手が空いている" if m["aiteru"] else "動いている"))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        m = mitate()
        print("【止まらない係】%s" % m["at"])
        print("  走行 %d本／発車待ち %d本／直近6時間の本物 %d本／今日の完了 %d件／残り %s（昨日 %s）"
              % (m["running"], m["machi"], m["honmono6h"], m["closedToday"],
                 m["open"], m["prevOpen"]))
        print("  → %s" % ("★手が空いている：" + "、".join(m["riyuu"]) if m["aiteru"]
                          else "動いている（何もしない）"))
        n = len(jsonl(LOG))
        print("  これまでに自動発車したログ：%d行（%s）" % (n, os.path.relpath(LOG, REPO)))
        return 0
    r = hashiru()
    print("%s／理由：%s" % (r["shita"], "、".join(r.get("riyuu") or []) or "なし"))
    for h in (r.get("hassha") or []):
        print("  - [%s] %s" % (h.get("st"), h.get("title")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
