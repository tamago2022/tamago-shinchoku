#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""空振り止め（2026-11-12）。同じ便が同じ理由で発車に失敗し続けたら、20回目で列から外す。

きっかけ：205276番が「無駄カット」で保留にされるのに台帳へ保存されず、11-10 18:05〜11-12 00:44 に
1469回選び直されて空振りした（上限1本の枠が塞がり発車が止まった）。

仕組み（便ごと・理由ごとの連続回数）：
  after(item, ok, reason) を発車係 launch_one の外側から1回呼ぶ。
    ok=True（発車成功）            → その便の回数を消す（リセット）
    ok=False・同じ理由              → 回数+1
    ok=False・別の理由              → 1からやり直し
  20回目に達した時だけ：①item を hold にして列から外す ②現在地(genzaichi)を赤にする
  （red_lines() が genzaichi.py の redFlags へ入る） ③status/dispatch_outbox.jsonl に type:"karaburi" を1行。
  19回までは何もしない。外れた後は数えない（二重通知しない）。
状態：status/karaburi_state.json（便番号→{reason,count,tripped,...}）。登録は tools/jidou_daicho.json。
解除：`python3 tools/karaburi_kanmon.py --kaijo <番号>`（赤を消す。便の保留解除は台帳側で別にやる）。
逆テスト：`python3 tools/karaburi_kanmon.py --self-test`
"""
import io
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "status", "karaburi_state.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
LIMIT = 20
# 工場全体の停止（便のせいではない）は数えない。数えると全部の便が外れてしまう。
SKIP_WORDS = ("緊急停止中",)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def norm_reason(reason, n=None):
    """理由の比べ方：数字・時刻を消して文面だけで比べる（「10回発車済み」と「11回」は同じ理由）。"""
    s = str(reason or "").strip()
    s = re.sub(r"[0-9０-９]+", "N", s)
    return s[:120] or "(理由なし)"


def _load():
    try:
        return json.load(io.open(STATE, encoding="utf-8")) or {}
    except Exception:
        return {}


def _save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, STATE)


def _outbox(n, title, reason, count):
    row = {"ts": _now(), "n": "%s-karaburi" % n, "type": "karaburi",
           "title": "同じ空振りが%d回続いたので保留にしました" % count,
           "message": "%s番「%s」：理由＝%s／連続%d回。自動発車の列から外して保留にしました（再選択されません）。"
                      % (n, (title or "")[:40], reason, count)}
    with io.open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def after(item, ok, reason, state_path=None):
    """発車を試した結果を1回記録する。20回目に外れた時だけ True を返す。"""
    n = str(item.get("n"))
    d = _load()
    if ok:
        if n in d and not d[n].get("tripped"):
            d.pop(n, None)
            _save(d)
        elif n in d:  # 外れたあとに成功した＝人が直して発車した。赤も消す
            d.pop(n, None)
            _save(d)
        return False
    if any(w in str(reason or "") for w in SKIP_WORDS):
        return False
    r = norm_reason(reason)
    e = d.get(n)
    if e and e.get("tripped"):
        return False  # 外れたあとは数えない・再通知しない
    if not e or e.get("reason") != r:
        e = {"reason": r, "reasonRaw": str(reason or "")[:200], "count": 0, "firstAt": _now()}
    e["count"] += 1
    e["lastAt"] = _now()
    e["title"] = str(item.get("title") or "")[:60]
    tripped = e["count"] >= LIMIT
    if tripped:
        e["tripped"] = True
        item["karaburiBefore"] = item.get("status")
        item["status"] = "hold"
        item["holdNote"] = "空振り止め（%s）：同じ理由で連続%d回空振りしたので保留。理由＝%s" % (_now()[:16], e["count"], e["reasonRaw"][:80])
        try:
            _outbox(n, item.get("title"), e["reasonRaw"] or r, e["count"])
        except Exception:
            pass
    d[n] = e
    _save(d)
    return tripped


def red_lines():
    """現在地(genzaichi)の赤旗に足す行。外れた便が残っている間だけ出る。"""
    out = []
    for n, e in sorted(_load().items()):
        if e.get("tripped"):
            out.append("空振り止め：%s番が同じ理由で%d回空振り→保留にしました（%s）"
                       % (n, e.get("count", 0), str(e.get("reasonRaw") or e.get("reason"))[:60]))
    return out


def kaijo(n):
    d = _load()
    if d.pop(str(n), None) is not None:
        _save(d)
        return True
    return False


def self_test():
    global STATE, OUTBOX
    import tempfile
    tmp = tempfile.mkdtemp()
    STATE, OUTBOX = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.jsonl")
    ng = 0

    def chk(name, cond):
        nonlocal ng
        print(("OK  " if cond else "NG  ") + name)
        if not cond:
            ng += 1

    it = {"n": 111, "title": "テスト便", "status": "waiting"}
    R = "🛑 無駄カット：111番は%d回発車済みなので保留にしました"
    for i in range(19):
        after(it, False, R % (10 + i))
    chk("19回では外れない", it["status"] == "waiting" and not os.path.exists(OUTBOX) and not red_lines())
    t = after(it, False, R % 40)
    chk("20回目で外れる(hold)", t and it["status"] == "hold")
    rows = [json.loads(x) for x in open(OUTBOX, encoding="utf-8")]
    chk("outboxに1行・n文字列・type", len(rows) == 1 and rows[0]["n"] == "111-karaburi" and rows[0]["type"] == "karaburi"
        and "111" in rows[0]["message"] and "20" in rows[0]["message"])
    chk("現在地が赤(red_lines)", len(red_lines()) == 1)
    after(it, False, R % 41)
    chk("外れた後は二重通知しない", len(open(OUTBOX, encoding="utf-8").read().splitlines()) == 1)
    # 別理由でリセット
    it2 = {"n": 222, "title": "別便", "status": "waiting"}
    for i in range(19):
        after(it2, False, "理由A")
    after(it2, False, "理由B")
    chk("別理由で1に戻る", _load()["222"]["count"] == 1 and it2["status"] == "waiting")
    for i in range(18):
        after(it2, False, "理由B")
    chk("理由Bが19回目でも外れない", it2["status"] == "waiting")
    # 発車成功でリセット
    it3 = {"n": 333, "title": "成功便", "status": "waiting"}
    for i in range(19):
        after(it3, False, "理由A")
    after(it3, True, "")
    chk("成功でリセット(状態から消える)", "333" not in _load())
    after(it3, False, "理由A")
    chk("リセット後は1から", _load()["333"]["count"] == 1 and it3["status"] == "waiting")
    # 便ごと：別の便の空振りは混ざらない
    it4 = {"n": 444, "title": "x", "status": "waiting"}
    for i in range(10):
        after(it3, False, "理由A")
        after(it4, False, "理由A")
    chk("便ごとに数える", _load()["444"]["count"] == 10 and it4["status"] == "waiting")
    # 工場全体の停止は数えない
    it5 = {"n": 555, "title": "x", "status": "waiting"}
    for i in range(30):
        after(it5, False, "緊急停止中のため発車しません 555番")
    chk("緊急停止は数えない", "555" not in _load() and it5["status"] == "waiting")
    chk("解除で赤が消える", kaijo(111) and not any("111番" in x for x in red_lines()))
    print("self-test:", "全部OK" if ng == 0 else "%d件NG" % ng)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--kaijo" in sys.argv:
        print(kaijo(sys.argv[sys.argv.index("--kaijo") + 1]))
        sys.exit(0)
    for l in red_lines():
        print(l)
