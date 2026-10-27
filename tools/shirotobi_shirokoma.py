#!/usr/bin/env python3
"""白コマの数え係（2026-10-27・たまごさん「白飛びが全然直らない」）。

tools/shirotobi_sokutei.mjs が保存したコマ（kiroku.json＋f*.jpg）を1枚ずつ見て、場面ごとに数える。
「白飛び」＝**一瞬だけ出て、あとで消える白**。ずっと出ている白（カードの地・白い商品写真）は意匠なので数えない。
  白っぽい … R・G・Bすべて243以上（#f3f3f3より明るい。カードの地 #fefbf6 は入る／生成りの背景 #f9f4ec は入らない）
  真っ白コマ … 画面（上2%を除く）の90%以上が白っぽく、その場面の最後のコマはそうではない
  白い箱コマ … 「そのコマでは白っぽいが、最後のコマでは白っぽくない」所がつながって画面の8%以上
              （読み込み前の画像の枠・動画/埋め込みの白い下地・遷移中の白い板など）
  紫コマ   … 初回アクセスの目印（about:blank を #ff00ff に塗ったもの）。数えない。
使い方:
  python3 tools/shirotobi_shirokoma.py <フォルダ> [--koma <白いコマの写しを置く先>] [--json <結果>]
  python3 tools/shirotobi_shirokoma.py --self-test
exit: 真っ白コマか白い箱コマが1つでもあれば 2、0なら 0。
"""
import json, os, shutil, sys

WHITE_MIN = 243
GRID_W, GRID_H = 60, 130
MASSHIRO = 0.90
HAKO = 0.08


def _px(im):
    im = im.convert("RGB")
    w, h = im.size
    im = im.crop((0, int(h * 0.02), w, h)).resize((GRID_W, GRID_H))
    return list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())


def white_mask(px):
    return [min(p) >= WHITE_MIN for p in px]


def is_magenta(px):
    return sum(1 for p in px if p[0] >= 200 and p[1] <= 70 and p[2] >= 200) / len(px) >= 0.6


def biggest(mask):
    n = len(mask)
    seen = [False] * n
    best = 0
    for i in range(n):
        if not mask[i] or seen[i]:
            continue
        st, c = [i], 0
        seen[i] = True
        while st:
            j = st.pop()
            c += 1
            x = j % GRID_W
            for k in ((j - 1) if x > 0 else -1, (j + 1) if x < GRID_W - 1 else -1, j - GRID_W, j + GRID_W):
                if 0 <= k < n and mask[k] and not seen[k]:
                    seen[k] = True
                    st.append(k)
        best = max(best, c)
    return best / n


def hantei(frame_px, final_px):
    """1コマ（と、その場面の最後のコマ）→ (真っ白か, 一瞬の白い塊の割合)"""
    w, wf = white_mask(frame_px), white_mask(final_px)
    n = len(w)
    full = sum(w) / n >= MASSHIRO and sum(wf) / n < MASSHIRO
    trans = [a and not b for a, b in zip(w, wf)]
    return full, biggest(trans)


def kazoeru(d, koma_out=None):
    from PIL import Image
    k = json.load(open(os.path.join(d, "kiroku.json"), encoding="utf-8"))
    fr = k["frames"]
    evs = [e for e in k["events"] if "t" in e]
    res = []
    for i, e in enumerate(evs):
        t1 = evs[i + 1]["t"] if i + 1 < len(evs) else 10 ** 12
        seg = [f for f in fr if e["t"] <= f["t"] < t1]
        pxs = [(f, _px(Image.open(os.path.join(d, f["f"])))) for f in seg]
        pxs = [(f, p) for f, p in pxs if not is_magenta(p)]
        masshiro, hako, worst = [], [], (None, 0.0)
        if pxs:
            final = pxs[-1][1]
            # 比べる相手＝同じスクロール位置の、その場面の最後のコマ（スクロールしただけの差を白飛びと数えない）
            last_at = {}
            for f, p in pxs:
                last_at[f.get("sy", -1)] = (f, p)
            for f, p in pxs[:-1]:
                sy = f.get("sy", -1)
                ref = last_at.get(sy)
                if sy != -1 and ref is not None and ref[0] is f:
                    continue  # 同じ位置のコマがこれしか無い＝比べられない
                full, box = hantei(p, ref[1] if (sy != -1 and ref) else final)
                if full:
                    masshiro.append(f["f"])
                elif box >= HAKO:
                    hako.append(f["f"])
                if box > worst[1]:
                    worst = (f["f"], box)
        r = {"場面": e.get("label"), "行き先": e.get("landed") or e.get("target"), "コマ数": len(seg),
             "真っ白コマ": len(masshiro), "白い箱コマ": len(hako),
             "いちばん白いコマ": worst[0], "一瞬の白の割合": round(worst[1], 3)}
        if koma_out and (masshiro or hako):
            os.makedirs(koma_out, exist_ok=True)
            pick = (masshiro + hako)[:3]
            if pxs:
                pick.append(pxs[-1][0]["f"])  # 比べる用に最後のコマも
            r["写し"] = []
            for f in pick:
                dst = "%02d_%s" % (i + 1, f)
                shutil.copy(os.path.join(d, f), os.path.join(koma_out, dst))
                r["写し"].append(dst)
        res.append(r)
    return {"base": k.get("base"), "場面": res,
            "真っ白コマ合計": sum(r["真っ白コマ"] for r in res),
            "白い箱コマ合計": sum(r["白い箱コマ"] for r in res)}


def self_test():
    from PIL import Image, ImageDraw
    ok = True
    W, H = 390, 844
    cream = Image.new("RGB", (W, H), (249, 244, 236))
    page = cream.copy()
    ImageDraw.Draw(page).rectangle((20, 200, 370, 420), fill=(254, 251, 246))  # カード（ずっと出ている）
    white = Image.new("RGB", (W, H), (255, 255, 255))
    box = cream.copy()
    ImageDraw.Draw(box).rectangle((0, 450, 390, 650), fill=(255, 255, 255))  # 一瞬の白い枠
    loaded = cream.copy()
    ImageDraw.Draw(loaded).rectangle((0, 450, 390, 650), fill=(90, 60, 40))  # 画像が載った
    mg = Image.new("RGB", (W, H), (255, 0, 255))
    a = hantei(_px(page), _px(page)); ok &= (not a[0]) and a[1] < 0.01          # カードは数えない
    b = hantei(_px(white), _px(page)); ok &= b[0]                               # 真っ白
    c = hantei(_px(box), _px(loaded)); ok &= (not c[0]) and c[1] >= HAKO       # 一瞬の白い枠
    d = hantei(_px(cream), _px(page)); ok &= (not d[0]) and d[1] < 0.01         # 生成りは白でない
    ok &= is_magenta(_px(mg)) and not is_magenta(_px(white))
    print("self-test", "PASS" if ok else "FAIL", a, b, c, d)
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
