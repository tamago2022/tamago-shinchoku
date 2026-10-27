#!/usr/bin/env python3
"""白コマの数え係（2026-10-27・たまごさん「白飛びが全然直らない」）。

tools/shirotobi_sokutei.mjs が保存したコマ（kiroku.json＋f*.jpg）を1枚ずつ見て、場面ごとに数える。
  真っ白コマ … 画面（上2%を除く）の90%以上が白（R・G・Bすべて244以上＝#f4f4f4より明るい）。生成り #faf5ec は白に数えない。
  白い箱コマ … 白がつながった塊が画面の12%以上（動画の枠・画像の枠・埋め込みの白い下地など）。
  紫コマ   … 初回アクセスの目印（about:blank を #ff00ff に塗ったもの）。数えない。
使い方:
  python3 tools/shirotobi_shirokoma.py <フォルダ> [--koma <白いコマの写しを置く先>] [--json <結果>]
  python3 tools/shirotobi_shirokoma.py --self-test
exit: 真っ白コマか白い箱コマが1つでもあれば 2、0なら 0。
"""
import json, os, shutil, sys

WHITE_MIN = 244
GRID_W, GRID_H = 60, 130


def _is_white(p):
    return p[0] >= WHITE_MIN and p[1] >= WHITE_MIN and p[2] >= WHITE_MIN


def _is_magenta(p):
    return p[0] >= 200 and p[1] <= 70 and p[2] >= 200


def koma_hantei(im):
    """1コマ → (白の割合, いちばん大きい白い塊の割合, 紫か)"""
    im = im.convert("RGB")
    w, h = im.size
    im = im.crop((0, int(h * 0.02), w, h)).resize((GRID_W, GRID_H))
    px = list(im.getdata())
    n = len(px)
    wh = [_is_white(p) for p in px]
    mg = sum(1 for p in px if _is_magenta(p))
    # つながった白の塊（4近傍）
    seen = [False] * n
    best = 0
    for i in range(n):
        if not wh[i] or seen[i]:
            continue
        st, c = [i], 0
        seen[i] = True
        while st:
            j = st.pop()
            c += 1
            x, y = j % GRID_W, j // GRID_W
            for k in ((j - 1) if x > 0 else -1, (j + 1) if x < GRID_W - 1 else -1, j - GRID_W, j + GRID_W):
                if 0 <= k < n and wh[k] and not seen[k]:
                    seen[k] = True
                    st.append(k)
        best = max(best, c)
    return sum(wh) / n, best / n, mg / n >= 0.6


def kazoeru(d, koma_out=None):
    from PIL import Image
    k = json.load(open(os.path.join(d, "kiroku.json"), encoding="utf-8"))
    fr = k["frames"]
    evs = [e for e in k["events"] if "t" in e]
    res = []
    for i, e in enumerate(evs):
        t1 = evs[i + 1]["t"] if i + 1 < len(evs) else 10 ** 12
        seg = [f for f in fr if e["t"] <= f["t"] < t1]
        masshiro, hako, worst = [], [], None
        for f in seg:
            wr, box, mg = koma_hantei(Image.open(os.path.join(d, f["f"])))
            if mg:
                continue
            if wr >= 0.90:
                masshiro.append(f["f"])
            elif box >= 0.12:
                hako.append(f["f"])
            if worst is None or box > worst[1]:
                worst = (f["f"], box)
        r = {"場面": e.get("label"), "行き先": e.get("landed") or e.get("target"), "コマ数": len(seg),
             "真っ白コマ": len(masshiro), "白い箱コマ": len(hako),
             "いちばん白いコマ": worst[0] if worst else None, "その白い塊の割合": round(worst[1], 3) if worst else None}
        if koma_out and (masshiro or hako):
            os.makedirs(koma_out, exist_ok=True)
            for f in (masshiro + hako)[:3]:
                dst = "%02d_%s" % (i + 1, f)
                shutil.copy(os.path.join(d, f), os.path.join(koma_out, dst))
            r["写し"] = ["%02d_%s" % (i + 1, f) for f in (masshiro + hako)[:3]]
        res.append(r)
    return {"base": k.get("base"), "場面": res,
            "真っ白コマ合計": sum(r["真っ白コマ"] for r in res),
            "白い箱コマ合計": sum(r["白い箱コマ"] for r in res)}


def self_test():
    from PIL import Image, ImageDraw
    ok = True
    cream = Image.new("RGB", (390, 844), (250, 245, 236))
    white = Image.new("RGB", (390, 844), (255, 255, 255))
    box = cream.copy()
    ImageDraw.Draw(box).rectangle((0, 200, 390, 420), fill=(255, 255, 255))
    mg = Image.new("RGB", (390, 844), (255, 0, 255))
    a = koma_hantei(cream); ok &= a[0] < 0.01 and a[1] < 0.01
    b = koma_hantei(white); ok &= b[0] >= 0.9
    c = koma_hantei(box); ok &= c[0] < 0.9 and c[1] >= 0.12
    m = koma_hantei(mg); ok &= m[2]
    print("self-test", "PASS" if ok else "FAIL", a, b, c, m)
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "--self-test":
        sys.exit(self_test())
    koma = a[a.index("--koma") + 1] if "--koma" in a else None
    out = kazoeru(a[0], koma)
    if "--json" in a:
        json.dump(out, open(a[a.index("--json") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(2 if (out["真っ白コマ合計"] or out["白い箱コマ合計"]) else 0)
