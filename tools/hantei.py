#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/hantei.py ── 判定日が来たら機械が見に行く係。うやむやを構造的に不可能にする。

たまごさん（2026-09-26）:
  「1行＝1依頼。列：言われた日時／内容／言われた回数／状態／1週間後の判定日／
    1ヶ月後の判定日／実際どうなったか。判定日が来たら機械が自動で状態を見に行って、
    変わっていなければ★自動で赤＋P1に繰り上げ。うやむやを構造的に不可能にする。」

★人が「まだやってます」と言えない。判定日は言われた瞬間に台帳へ焼かれ、
  その日が来たら機械が勝手に見に行って、勝手に赤にする。誰の許可も要らない。

━━ 何を見るか ━━
  status/shukudai/daicho.jsonl の状態（＝宿題台帳が正本）。
  さらに tools/oni_modoshi.py の検品結果があれば、そちらを優先する
  （自己申告の「完了」ではなく、機械が200を確認した「完了」だけを完了と読む）。

━━ 判定 ━━
  完了になっている          → 「返した」。実際どうなったかに証拠URLを書いて閉じる
  状態が言われた時から不変  → ★赤。P1に繰り上げて、その場で再発車する
  途中（走行中・確認待ち）  → 「動いてはいる」。赤にはしないが、1ヶ月判定では赤

★1ヶ月の判定日を過ぎてまだ返っていないものは、理由を問わず赤。例外を作らない。

使い方
    python3 tools/hantei.py              # 判定日が来たものを見に行く（心臓から1日1回）
    python3 tools/hantei.py --show
    python3 tools/hantei.py --self-test
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

HATSUGEN = os.path.join(ST, "kioku", "hatsugen.jsonl")
DAICHO = os.path.join(ST, "shukudai", "daicho.jsonl")
KENPIN = os.path.join(ST, "oni_modoshi", "kenpin.jsonl")
LOG = os.path.join(ST, "kioku", "hantei.jsonl")

JST = datetime.timezone(datetime.timedelta(hours=9))
_YOUBI = "月火水木金土日"


def now():
    return datetime.datetime.now(JST)


def today():
    return now().strftime("%Y-%m-%d")


def stamp():
    return now().strftime("%Y-%m-%d %H:%M")


def norm(s):
    return re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "").lower()


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


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def append(p, obj):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def ja_nichiji(dt):
    return "%s(%s) %s" % (dt.strftime("%Y-%m-%d"), _YOUBI[dt.weekday()], dt.strftime("%H:%M"))


def parse_hi(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(s)[:16], f).replace(tzinfo=JST)
        except Exception:
            continue
    return None


# ────────────────────────────────────────── いまの状態を見に行く


def ima_no_jotai():
    """題名 → いまの状態。★機械が確認した完了を、自己申告より上に置く。"""
    by = {}
    for r in jsonl(DAICHO):
        by.setdefault(norm(r.get("title"))[:24],
                      {"state": r.get("state") or "未着手", "evidence": r.get("evidence")})
    # 検品を通った（＝URLが200で中身が入っていた）ものだけ、完了に上書きしてよい
    for k in jsonl(KENPIN):
        if not k.get("ok"):
            continue
        key = norm(k.get("title"))[:24]
        if key:
            by[key] = {"state": "完了", "evidence": k.get("url")}
    return by


def hantei_1ken(r, ima):
    """1件を判定する。返すのは（赤か、実際どうなったか、いまの状態）。"""
    cur = ima.get(norm(r.get("title"))[:24]) or {"state": "未着手", "evidence": None}
    st = cur["state"]
    t = today()
    w = r.get("hantei1w") or ""
    m = r.get("hantei1m") or ""
    kita = [x for x in (("1週間", w), ("1ヶ月", m))
            if x[1] and x[1] <= t and x[0] not in (r.get("hanteiSumi") or [])]
    if not kita:
        return None
    which = kita[-1][0]

    if st == "完了":
        return {"which": which, "aka": False, "state": st,
                "sonogo": "返した（%s／%s）" % (cur.get("evidence") or "証拠URLなし", t)}
    if st in ("走行中", "確認待ち"):
        aka = (which == "1ヶ月")     # ★1ヶ月の判定日を過ぎて返っていなければ、途中でも赤
        return {"which": which, "aka": aka, "state": st,
                "sonogo": ("★%s経っても返っていない（%s のまま）" % (which, st)) if aka
                          else "%s後：まだ %s。返っていない" % (which, st)}
    # 未着手・止まっている・引き継ぎ ＝ 言われた時から1ミリも動いていない
    return {"which": which, "aka": True, "state": st,
            "sonogo": "★%s経っても %s のまま。1ミリも動いていない" % (which, st)}


def kuriageru(r, naze):
    """★自動でP1に繰り上げて、その場で再発車する。たまごさんに聞かない。"""
    try:
        import command_ingest
        try:
            import queue_store
            lock = queue_store.queue_lock
        except Exception:
            import contextlib
            lock = contextlib.nullcontext
        body = "\n".join([
            "【判定日で赤になった案件】%s" % r.get("title"),
            "【言われた日時】%s（%d回言われている）" % (r.get("firstSaidJa") or r.get("firstSaid"),
                                                    int(r.get("count") or 1)),
            "【なぜ赤か】%s" % naze,
            "【完了条件】本番URLが200で返り、中身が空でないこと。",
            "★自己申告では完了になりません（tools/oni_modoshi.py の検品を通ること）。",
            "たまごさんに質問しない。直して、URLを報告に貼る。",
        ])
        with lock():
            s, msg = command_ingest.queue_add(body, priority=1,
                                              label=("判定日赤｜" + (r.get("title") or ""))[:60],
                                              origin="user")
        return "%s:%s" % (s, msg)
    except Exception as e:
        return "failed:%s" % e


def hashiru(dry=False):
    rows = {r["id"]: r for r in jsonl(HATSUGEN) if r.get("id")}
    ima = ima_no_jotai()
    mita, aka, tojita = 0, 0, 0
    for r in rows.values():
        h = hantei_1ken(r, ima)
        if not h:
            continue
        mita += 1
        r["state"] = h["state"]
        r["sonogo"] = h["sonogo"]
        r["hanteiAt"] = stamp()
        r["hanteiSumi"] = sorted(set((r.get("hanteiSumi") or []) + [h["which"]]))
        if h["aka"]:
            aka += 1
            r["aka"] = True
            r["p"] = 1                      # ★自動でP1に繰り上げ
            if not dry:
                r["saihassha"] = kuriageru(r, h["sonogo"])
        else:
            r["aka"] = False
            if h["state"] == "完了":
                tojita += 1
        if not dry:
            append(LOG, {"at": stamp(), "id": r["id"], "title": (r.get("title") or "")[:80],
                         "which": h["which"], "aka": h["aka"], "state": h["state"],
                         "sonogo": h["sonogo"]})
    if not dry and rows:
        body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                       for r in sorted(rows.values(),
                                       key=lambda x: (-int(x.get("count") or 1),
                                                      str(x.get("firstSaid") or ""))))
        write_text(HATSUGEN, body)
    return {"mita": mita, "aka": aka, "tojita": tojita, "zen": len(rows)}


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        ima = {}
        r = {"id": "x", "title": "テストの一手を直してほしい", "count": 1,
             "firstSaid": "2020-01-01 00:00", "hantei1w": "2020-01-08",
             "hantei1m": "2020-01-31", "hanteiSumi": []}
        h = hantei_1ken(r, ima)
        if not h or not h["aka"]:
            ng.append("判定日を過ぎた未着手が赤にならない")
        r2 = dict(r, hanteiSumi=["1週間", "1ヶ月"])
        if hantei_1ken(r2, ima) is not None:
            ng.append("判定済みをもう一度判定している")
        r3 = dict(r, hantei1w="2999-01-01", hantei1m="2999-01-01")
        if hantei_1ken(r3, ima) is not None:
            ng.append("判定日が来ていないのに判定している")
        s = hashiru(dry=True)
        print("自己試験：%s／台帳 %d件・判定日が来ている %d件（うち赤 %d）"
              % ("OK" if not ng else "NG", s["zen"], s["mita"], s["aka"]))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        rows = jsonl(LOG)
        print("【判定日の係】これまでに判定した %d件／うち赤 %d件"
              % (len(rows), len([r for r in rows if r.get("aka")])))
        for r in rows[-10:]:
            print("  %s %s … %s" % ("🔴" if r.get("aka") else "✅",
                                    (r.get("title") or "")[:40], r.get("sonogo")))
        return 0
    s = hashiru()
    print("判定日が来た %d件を見に行った → ★赤 %d件／返っていた %d件（台帳 %d件）"
          % (s["mita"], s["aka"], s["tojita"], s["zen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
