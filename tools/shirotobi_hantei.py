#!/usr/bin/env python3
"""白飛びの判定（tools/shirotobi_sokutei.mjs が保存したフレームを数える）。

まっさら＝画面（上2%を除く）の98%以上が1色。最初の1枚が描かれる前（about:blank）は数えない。
押してから次の画面に中身が出るまでの秒数と、その間のまっさらフレーム数を、押した操作ごとに出す。
使い方: python3 tools/shirotobi_hantei.py <フォルダ>
"""
import json, os, sys
from PIL import Image

D = sys.argv[1]
k = json.load(open(os.path.join(D, "kiroku.json"), encoding="utf-8"))
fr, evs = k["frames"], [e for e in k["events"] if "t" in e]


def blank(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((0, int(h * 0.02), w, h)).resize((78, 160))
    px = list(im.getdata())
    q = {}
    for r, g, b in px:
        key = (r // 12, g // 12, b // 12)
        q[key] = q.get(key, 0) + 1
    top, n = max(q.items(), key=lambda x: x[1])
    return n / len(px) >= 0.98, tuple(c * 12 + 6 for c in top)


res = []
for i, e in enumerate(evs):
    t1 = evs[i + 1]["t"] if i + 1 < len(evs) else 10 ** 9
    seg = [f for f in fr if e["t"] <= f["t"] < t1]
    bl, first_content = [], None
    for f in seg:
        b, col = blank(os.path.join(D, f["f"]))
        f["blank"], f["col"] = b, col
        if b:
            bl.append(f)
    # 押したあと「まっさら」が終わって中身が出た時刻（最後のまっさらの次のフレーム）
    last_blank = max((f["t"] for f in bl), default=None)
    after = [f for f in seg if not f.get("blank") and (last_blank is None or f["t"] > last_blank)]
    settle = (after[0]["t"] - e["t"]) / 1000 if after else None
    blank_ms = 0
    for f in bl:
        j = seg.index(f)
        nxt = seg[j + 1]["t"] if j + 1 < len(seg) else f["t"] + 16
        blank_ms += nxt - f["t"]
    # 最初の読み込み（goto）は about:blank からなので、最初の中身が出る前のまっさらは数えない
    if i == 0:
        first = next((f for f in seg if not f.get("blank")), None)
        pre = [f for f in bl if first and f["t"] < first["t"]]
        bl = [f for f in bl if f not in pre]
        blank_ms = sum(((seg[seg.index(f) + 1]["t"] if seg.index(f) + 1 < len(seg) else f["t"] + 16) - f["t"]) for f in bl)
    res.append({"操作": e.get("label"), "行き先": e.get("landed"), "フレーム数": len(seg),
                "まっさらフレーム": len(bl), "まっさらの合計ms": blank_ms,
                "まっさらの色": sorted({str(f["col"]) for f in bl})[:3],
                "押してから最後の画面が出るまで秒": settle})
out = {"base": k["base"], "結果": res, "まっさら合計": sum(r["まっさらフレーム"] for r in res)}
json.dump(out, open(os.path.join(D, "hantei.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
