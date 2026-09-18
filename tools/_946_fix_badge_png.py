#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【946番・2026-09-19】金バッジ(concierge-pick.png)を、銀バッジ(good-cover.png)に px 単位で揃える。

たまごさん：「寄ってないよ。比べてみてよ、銀のバッジと。」
           「銀が95点の正解。金を銀に一致させる。新しい値を考えない。」

■ 何が違っていたのか（実測・2026-09-19）
  CSSはもう金銀で完全に同じだった（`padding: min(6.5cqw, 6.5cqh)` /
  `height: min(28cqw, 28cqh)`。実測でも上余白px＝左余白px が桁まで一致していた）。
  違っていたのは **PNGの中身** ：

    good-cover.png      432x512 … 絵の周りに透明の余白が 左50/上50/右50/下50 px
    concierge-pick.png 1536x1024… 透明の余白が 左12/上0/右11/下1 px（＝ほぼ無し）

  CSSは「画像の箱」を置く。箱の中で絵がどこにいるかは見ていない。
  だから箱が同じ位置・同じ大きさでも、**目に見える絵**は
    銀 … 箱より内側に約9.8%引っ込んだ位置から始まる
    金 … 箱の角からいきなり始まる
  となり、大きさも 銀の絵は箱の80.5%、金の絵は箱の100% で、金だけ約1.24倍大きい。
  「比べると金だけ違う」の正体はこれ。CSSをいくら直しても直らなかった理由でもある。

■ 直し方
  CSSは1文字も触らない（銀の値をそのまま使う＝たまごさん指示）。
  **金のPNGに、銀と同じ割合の透明余白を焼き込む。**
  そうすると同じCSSのまま、絵の位置も絵の大きさも銀と一致する。

  銀の割合（正本）:
    上の透明余白 / 画像の高さ = 50/512 = 9.7656%
    左の透明余白 / 画像の高さ = 50/512 = 9.7656%   ※CSSは height 指定・width:auto なので、
                                                     横も「高さ」で割った比率で効く
    絵の高さ     / 画像の高さ = 412/512 = 80.4688%

  ついでに解像度を半分に落とす（1536x1024→約881x636）。実際に描かれるのは
  高さ200px程度なので3倍以上の余裕があり、たまごさんのスマホの通信量を食わない。

使い方:
    python3 tools/_946_fix_badge_png.py <joy-relief-stationのpublic/badgesのパス> [--write]
"""
import json
import os
import sys

from PIL import Image

SILVER = "good-cover.png"
GOLD = "concierge-pick.png"
SCALE = 0.5  # 解像度を半分に（見た目は変わらない。実描画は高さ200px前後）


# 縮小(LANCZOS)をかけると絵のふちの「ほとんど見えない薄いピクセル」が0になり、
# getbbox() の結果が縮小の前後で変わってしまう（実測：1513x1023 → 559x478）。
# 目に見えるかどうかで測るため、しきい値を入れて二値化してから測る。
ALPHA_MIN = 8


def ink_bbox(im):
    return im.split()[3].point(lambda a: 255 if a >= ALPHA_MIN else 0).getbbox()


def ink_box(path):
    im = Image.open(path).convert("RGBA")
    return im, ink_bbox(im)


def ratios(size, bbox):
    """CSSは height を決めて width:auto なので、縦も横も『画像の高さ』で割った比率で効く。"""
    w, h = size
    l, t, r, b = bbox
    return {
        "画像": f"{w}x{h}",
        "絵": f"{r - l}x{b - t}",
        "左余白/高さ": round(l / h, 6),
        "上余白/高さ": round(t / h, 6),
        "絵の高さ/高さ": round((b - t) / h, 6),
    }


def main():
    badges_dir = sys.argv[1]
    write = "--write" in sys.argv
    sp = os.path.join(badges_dir, SILVER)
    gp = os.path.join(badges_dir, GOLD)

    sim, sbb = ink_box(sp)
    src = gp + ".946bak"  # 一度直した後も、いつも元絵から組み直せるようにする
    gim, gbb = ink_box(src if os.path.exists(src) else gp)
    before = {"銀": ratios(sim.size, sbb), "金(直す前)": ratios(gim.size, gbb)}

    # --- 銀の割合を正本として、金の新しい画像を組み立てる ---
    sw, sh = sim.size
    sl, st, sr, sb = sbb
    r_left = sl / sh          # 0.097656
    r_top = st / sh           # 0.097656
    r_ink_h = (sb - st) / sh  # 0.804688

    # 先に縮小してから測る（縮小後の絵の実寸で組む＝後から測り直してもズレない）
    gsmall = gim.resize(
        (int(round(gim.width * SCALE)), int(round(gim.height * SCALE))), Image.LANCZOS
    )
    sl2, st2, sr2, sb2 = ink_bbox(gsmall)
    ink = gsmall.crop((sl2, st2, sr2, sb2))
    ink_w, ink_h = ink.size

    # 絵の高さが「画像の高さ」の r_ink_h になるような画像の高さ
    new_h = int(round(ink_h / r_ink_h))
    top = int(round(r_top * new_h))
    left = top  # 上と左を同じpxにする（銀も 50/50 で同じ）
    new_h = top + ink_h + top          # 上下対称（銀と同じ作り）
    new_w = left + ink_w + left        # 左右対称（銀と同じ作り）

    out = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    out.paste(ink, (left, top))
    after = ratios(out.size, ink_bbox(out))

    # --- 揃ったかを数字で確かめる（サムネ短辺378pxのときの実寸で比較）---
    S = 378.0
    inset = 0.065 * S           # CSS: padding min(6.5cqw, 6.5cqh)
    box_h = 0.28 * S            # CSS: height min(28cqw, 28cqh)

    def visual(r):
        return {
            "絵の左余白px": round(inset + box_h * r["左余白/高さ"], 3),
            "絵の上余白px": round(inset + box_h * r["上余白/高さ"], 3),
            "絵の高さpx": round(box_h * r["絵の高さ/高さ"], 3),
        }

    result = {
        "サムネ枠": "672x378（たまごさん実測のお手本と同じ）",
        "銀": visual(before["銀"]),
        "金(直す前)": visual(before["金(直す前)"]),
        "金(直した後)": visual(after),
        "割合": {"銀": before["銀"], "金(直す前)": before["金(直す前)"], "金(直した後)": after},
    }
    print(json.dumps(result, ensure_ascii=False, indent=1))

    if write:
        bak = gp + ".946bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy2(gp, bak)
        out.save(gp, optimize=True)
        print(f"書いた: {gp}  {new_w}x{new_h}  {os.path.getsize(gp)} bytes（元は {os.path.getsize(bak)} bytes）")
    else:
        print("（--write が無いので書き込んでいません）")


if __name__ == "__main__":
    main()
