#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNSに出した曲ページの「シェアしたときの画像（OGP）」を、曲だと分かる絵にそろえる（2026-10-29・たまごさん指示）

たまごさんの言葉（2026-10-29）：
  「中島みゆき『糸』はほぼ白、Leon Russell は小さい。どちらも動画のサムネイルが元。動画は差し替えず、
    同じ動画の別の高画質サムネイル（maxres や hq）か、見栄えのする場面を使って、XやLINEでシェアしたときに
    曲だと分かる画像にする。ほかのSNSで出した曲のページも、同じ弱さ（白っぽい・小さい・別の人の顔）が無いか
    機械で全部確かめて、まとめて直す。見た目の型は変えない。」

なぜ弱くなるか（実測 2026-10-29）：
  本番の og:image は /api/public/share-image/<動画ID>（maxresdefault → sddefault → hqdefault の順に YouTube から取って返す）。
  ・Leon Russell「A Song For You」(37dw2r45Xzg)：maxres も sddefault も 404 → 480×360 の hqdefault。
    ページは 1280×720 と名乗るので、X・LINE では小さい四角になる。同じ動画の sd1〜sd3（640×480 の場面）は取れる。
  ・中島みゆき「糸」(hDisMIGEP1U)：maxresdefault は平均の明るさ 5/255 のほぼ真っ黒な舞台。
  → 同じ動画の候補（maxresdefault・maxres1〜3・hq720・sddefault・sd1〜3・hqdefault・hq1〜3）を全部測り、
    いちばん大きく・暗すぎず白すぎず・のっぺりしていない1枚を選んで、黒帯を落として 1200×630 にした静止画を
    joy-relief-station の public/og-sns/ に置く。曲ページは名簿（src/lib/snsOg.generated.ts）に載った曲だけその絵を使う。
    絵は動画のサムネイルそのまま（文字や枠は足さない＝見た目の型はそのまま）。暗すぎる絵だけ、明るさを少し持ち上げる。

使い方：
  python3 tools/sns_og_kaizen.py --check [--out 結果.json]      本番の今の画像を全曲測るだけ（直さない）
  python3 tools/sns_og_kaizen.py --naosu --jrs <joy-relief-station の作業場>   弱い曲の絵を作り、名簿を書く（push はしない）
  python3 tools/sns_og_kaizen.py --self-test
対象：status/public/toukou_daicho.json の posts の songKey／songKeys（X・YouTube・TikTok に出した曲）。
安全：YouTube の公開サムネイル（i.ytimg.com）と本番のページを読むだけ。課金0・ブラウザなし・鍵なし。
      一時ファイルは作らない（画像はメモリの中で測る）。
結果：status/public/sns_og_kenpin.json（曲ごとの 前の画像の大きさ・明るさ・判定 → 後）。
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "public", "toukou_daicho.json")
OUT = os.path.join(REPO, "status", "public", "sns_og_kenpin.json")
SITE = "https://joy-relief-station.lovable.app"
UA_BOT = "Twitterbot/1.0"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
KOUHO = ["maxresdefault", "maxres1", "maxres2", "maxres3", "hq720", "sddefault", "sd1", "sd2", "sd3",
         "hqdefault", "hq1", "hq2", "hq3"]
W, H = 1200, 630
# 判定のしきい値（0〜255 の明るさ）
CHIISAI_W = 1000      # これより横幅が小さい＝X・LINE で小さく出る
SHIROI_MEAN = 205     # 平均がこれ以上、または
SHIROI_RATIO = 0.55   # 真っ白に近い画素(>235)がこれ以上 ＝ 白っぽい
KURAI_MEAN = 28       # 平均がこれ未満 ＝ 暗すぎて何の絵か分からない
NOPPERI_STD = 22      # 明るさのばらつきがこれ未満 ＝ のっぺり（文字だけ・単色）


def get(url, ua=UA, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def song_keys():
    d = json.load(io.open(DAICHO, encoding="utf-8"))
    keys = []
    for p in d.get("posts", []):
        for k in [p.get("songKey")] + list(p.get("songKeys") or []):
            if k and "/" in k and k not in keys:
                keys.append(k)
    return keys


def page_url(key):
    a, s = key.split("/", 1)
    return "%s/cover-guide?artist=%s&song=%s" % (SITE, urllib.parse.quote(a, safe=""), urllib.parse.quote(s, safe=""))


def meta(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), html)
    return m.group(1).replace("&amp;", "&") if m else None


def sokutei(data):
    """画像のバイト列 → 大きさ・明るさ・白の割合・ばらつき（黒帯を除いた中身で）"""
    from PIL import Image, ImageStat
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    naka = kuroobi_nuku(im)
    g = naka.convert("L")
    small = g.resize((max(1, g.width // 4), max(1, g.height // 4)))
    px = list(small.getdata())
    st = ImageStat.Stat(small)
    return {"w": w, "h": h, "naka": [naka.width, naka.height], "mean": round(st.mean[0], 1), "std": round(st.stddev[0], 1),
            "shiro": round(sum(1 for p in px if p > 235) / len(px), 3)}


def kuroobi_nuku(im):
    """上下・左右の黒帯（ほぼ真っ黒の行・列）を落とす。中身が無くなるほどなら元のまま。"""
    g = im.convert("L")
    w, h = g.size
    px = g.load()

    # 帯＝暗くて、しかも平らな（ばらつきの無い）行・列。暗い舞台の絵は暗くても模様があるので帯と取り違えない
    def obi(vals):
        n = len(vals)
        m = sum(vals) / n
        sd = (sum((v - m) ** 2 for v in vals) / n) ** 0.5
        return m < 34 and sd < 7

    def row_dark(y):
        return obi([px[x, y] for x in range(0, w, max(1, w // 96))])

    def col_dark(x):
        return obi([px[x, y] for y in range(0, h, max(1, h // 96))])
    def haba(n, dark):
        """端から見て、帯がどこまで続くか。端の数画素の縁取り（明るい線）があっても帯とみなす（9割が帯ならよい）"""
        last, cnt = 0, 0
        for i in range(n // 3):
            if dark(i):
                cnt += 1
                if cnt >= 0.9 * (i + 1):
                    last = i + 1
        return last
    t = haba(h, row_dark)
    b = h - 1 - haba(h, lambda i: row_dark(h - 1 - i))
    l = haba(w, col_dark)
    r = w - 1 - haba(w, lambda i: col_dark(w - 1 - i))
    if (b - t) < h // 2 or (r - l) < w // 2:
        return im
    return im.crop((l, t, r + 1, b + 1))


def hantei(m):
    """弱さの名前のリスト（空なら合格）"""
    if not m:
        return ["取れない"]
    ng = []
    if m["naka"][0] < CHIISAI_W:
        ng.append("小さい")
    if m["mean"] >= SHIROI_MEAN or m["shiro"] >= SHIROI_RATIO:
        ng.append("白っぽい")
    if m["mean"] < KURAI_MEAN:
        ng.append("暗すぎ")
    if m["std"] < NOPPERI_STD:
        ng.append("のっぺり")
    return ng


def tensuu(m):
    """候補の点（大きいほど良い）。大きさ＞明るさのほどよさ＞ばらつき。"""
    if not m or m["w"] <= 120:
        return -1
    s = min(m["naka"][0], 1280) / 1280 * 50
    mean = m["mean"]
    s += 30 - min(30, abs(mean - 110) / 3)
    s += min(20, m["std"] / 3)
    if m["shiro"] >= SHIROI_RATIO:
        s -= 40
    return s


def kouho_atsume(vid):
    def one(v):
        url = "https://i.ytimg.com/vi/%s/%s.jpg" % (vid, v)
        try:
            st, data = get(url)
            if st != 200 or len(data) < 2000:
                return v, None, None
            return v, data, sokutei(data)
        except Exception:
            return v, None, None
    with ThreadPoolExecutor(6) as ex:
        return [x for x in ex.map(one, KOUHO) if x[1]]


def oembed_title(vid):
    try:
        st, data = get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote("https://www.youtube.com/watch?v=" + vid))
        j = json.loads(data)
        return j.get("title", ""), j.get("author_name", "")
    except Exception:
        return None, None


def tsukuru(data, m):
    """選んだ1枚 → 黒帯を落として 1200×630 に（真ん中で切る）。暗すぎる絵だけ少し明るく。"""
    from PIL import Image, ImageOps, ImageEnhance
    im = kuroobi_nuku(Image.open(io.BytesIO(data)).convert("RGB"))
    im = ImageOps.fit(im, (W, H), method=Image.LANCZOS, centering=(0.5, 0.42))
    if m["mean"] < 60:
        import math
        im = ImageOps.autocontrast(im, cutoff=0.5)
        from PIL import ImageStat
        mean = max(1.0, ImageStat.Stat(im.convert("L")).mean[0])
        if mean < 70:  # 人や楽器のある明るい所だけ持ち上げる（ガンマ）。底の黒（圧縮のブロックが出る所）は黒のまま
            bp = 12
            gam = max(0.55, min(1.0, math.log(75 / 255.0) / math.log(mean / 255.0)))
            lut = [0 if i < bp else int(255 * (((i - bp) / (255.0 - bp)) ** gam)) for i in range(256)]
            im = im.point(lut * 3)
        im = ImageEnhance.Contrast(im).enhance(1.05)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return buf.getvalue()


def file_name(key):
    a, s = key.split("/", 1)
    safe = lambda x: re.sub(r"[^A-Za-z0-9_-]", "", x) or ("x%d" % (abs(hash(x)) % 10 ** 6))
    import hashlib
    return "%s__%s-%s.jpg" % (safe(a)[:40], safe(s)[:50], hashlib.sha1(key.encode()).hexdigest()[:6])


def mite(key):
    """本番の曲ページの今の og:image を測る"""
    r = {"key": key, "page": page_url(key)}
    try:
        st, body = get(r["page"], ua=UA_BOT)
        html = body.decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        r["err"] = "ページが読めない（%s）" % str(e)[:80]
        return r
    img = meta(html, "og:image")
    r["og_image"] = img
    r["og_wh"] = [meta(html, "og:image:width"), meta(html, "og:image:height")]
    m = re.search(r"/share-image/([A-Za-z0-9_-]{11})", img or "")
    v = re.search(r'"embedUrl":"https://www\.youtube\.com/embed/([A-Za-z0-9_-]{11})', html)
    r["vid"] = (m.group(1) if m else None) or (v.group(1) if v else None)
    try:
        st, data = get(img, ua=UA_BOT)
        r["mae"] = sokutei(data)
    except Exception as e:  # noqa: BLE001
        r["mae"] = None
        r["err_img"] = str(e)[:80]
    r["yowai"] = hantei(r["mae"])
    if r["vid"]:
        t, au = oembed_title(r["vid"])
        r["douga"] = {"title": t, "author": au}
        # 別の人の顔の疑い：ページのアーティスト名が、動画の題名にも投稿者名にも無い（直さない・数えて見せるだけ）
        ogt = meta(html, "og:title") or ""
        mm = re.match(r".+? — (.+?)(?:（\d{4}）)?｜", ogt)
        name = (mm.group(1) if mm else "").strip()
        r["artist"] = name
        norm = lambda x: re.sub(r"[\s・.\-_'’]", "", (x or "").lower())
        if name and t is not None and norm(name) not in norm(t) + norm(au):
            r["betsu_no_hito"] = True
    return r


def check(keys):
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(mite, keys))
    return rows


def naosu(rows, jrs):
    od = os.path.join(jrs, "public", "og-sns")
    os.makedirs(od, exist_ok=True)
    meibo = {}
    gen = os.path.join(jrs, "src", "lib", "snsOg.generated.ts")
    try:  # 前回の名簿は残す（今回直さなかった曲を落とさない）
        for k, f in re.findall(r'\["([^"]+)", "([^"]+)"\]', io.open(gen, encoding="utf-8").read()):
            if os.path.exists(os.path.join(od, f)):
                meibo[k] = f
    except OSError:
        pass
    for r in rows:
        if not r.get("vid") or not r.get("yowai"):
            continue
        ks = kouho_atsume(r["vid"])
        if not ks:
            r["ato"] = {"kekka": "候補が取れない"}
            continue
        best = max(ks, key=lambda x: tensuu(x[2]))
        out = tsukuru(best[1], best[2])
        fn = file_name(r["key"])
        am = sokutei(out)
        # 前より良くならないなら置かない（例：ジャケットそのものが白い＝ビートルズ『ホワイト・アルバム』）
        if len(hantei(am)) >= len(r["yowai"]):
            r["ato"] = {"kekka": "前より良い絵が無い（今のまま）", "kouho": best[0], "sokutei": am, "yowai": hantei(am)}
            if os.path.exists(os.path.join(od, fn)):
                os.remove(os.path.join(od, fn))
            meibo.pop(r["key"], None)
            continue
        io.open(os.path.join(od, fn), "wb").write(out)
        r["ato"] = {"kouho": best[0], "moto": best[2], "file": "/og-sns/" + fn, "sokutei": am, "yowai": hantei(am),
                    "kouho_kazu": len(ks)}
        meibo[r["key"]] = fn
    lines = ["// SNSに出した曲の、シェア用の画像（OGP）の名簿。tools/sns_og_kaizen.py（tamago-shinchoku）が自動で書く。手で書かない。",
             "// 載っている曲だけ og:image が /og-sns/<ファイル> を指す（同じ動画の、いちばん見栄えのするサムネイルを 1200×630 にしたもの）。",
             "// ★戻し方（1行）：下の配列を [] にして push すれば、全曲が前の状態（/api/public/share-image/<動画ID>）に戻る。",
             "// 生成: %s  曲数: %d" % (time.strftime("%Y-%m-%d %H:%M"), len(meibo)),
             "export const SNS_OG = new Map<string, string>(["]
    for k in sorted(meibo):
        lines.append('  ["%s", "%s"],' % (k, meibo[k]))
    lines.append("]);")
    io.open(gen, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return meibo


def self_test():
    assert hantei({"naka": [480, 360], "mean": 60, "std": 50, "shiro": 0.0}) == ["小さい"]
    assert "白っぽい" in hantei({"naka": [1280, 720], "mean": 230, "std": 30, "shiro": 0.8})
    assert "暗すぎ" in hantei({"naka": [1280, 720], "mean": 5, "std": 17, "shiro": 0.0})
    assert hantei({"naka": [1280, 720], "mean": 100, "std": 50, "shiro": 0.05}) == []
    big_dark = {"w": 1280, "naka": [1280, 720], "mean": 15, "std": 27, "shiro": 0.0}
    small_ok = {"w": 480, "naka": [480, 360], "mean": 70, "std": 50, "shiro": 0.0}
    sd_ok = {"w": 640, "naka": [640, 480], "mean": 70, "std": 50, "shiro": 0.0}
    assert tensuu(sd_ok) > tensuu(small_ok)
    assert tensuu({"w": 120, "naka": [120, 90], "mean": 190, "std": 27, "shiro": 0}) == -1
    assert tensuu(big_dark) > 0
    assert file_name("leon-russell/a-song-for-you").startswith("leon-russell__a-song-for-you-")
    assert re.match(r"^[A-Za-z0-9_-]+\.jpg$", file_name("anri/anri-オリヒ-アを聴きなか-ら"))
    try:
        from PIL import Image
        im = Image.new("RGB", (480, 360), (0, 0, 0))
        im.paste((120, 100, 90), (0, 45, 480, 315))
        assert kuroobi_nuku(im).size[1] < 300
    except ImportError:
        pass
    print("sns_og_kaizen self-test OK")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--naosu", action="store_true")
    ap.add_argument("--jrs")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    keys = song_keys()
    rows = check(keys)
    doc = {"at": time.strftime("%Y-%m-%d %H:%M"), "label": "SNSに出した曲ページのシェア画像（OGP）", "kyoku": len(rows),
           "yowai": sum(1 for r in rows if r.get("yowai")), "rows": rows}
    if a.naosu:
        if not a.jrs:
            print("--jrs が要る")
            return 2
        meibo = naosu(rows, a.jrs)
        doc["meibo"] = len(meibo)
        doc["ato_yowai"] = sum(1 for r in rows if r.get("ato") and r["ato"].get("yowai"))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(doc, io.open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(y for r in rows for y in (r.get("yowai") or []))
    print("SNS_OG: %d曲・弱い %d曲（%s）%s" % (len(rows), doc["yowai"], "・".join("%s %d" % kv for kv in c.most_common()),
                                          ("・直した %d" % doc.get("meibo", 0)) if a.naosu else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
