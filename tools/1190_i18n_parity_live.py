#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【言語を変えても、変わるのは言葉だけ】実際の画面で、言語ごとの中身の量を数えて比べる（2026-10-09）

たまごさんの合格条件：
  「言語を変えても、変わるのは言葉だけ。ページもレイアウトも中身の量も同じ」
  英語・中国語・スペイン語・韓国語すべてで、日本語と同じページに同じ数のカード・動画・章が出ること。

  python3 scripts/i18n_parity_live.py https://joy-relief-station.lovable.app \
      --paths "/cover-guide?artist=hotei-tomoyasu,/feature/hikigatari" --out result.json

・各言語で同じURLを開き（localStorage の gokigen-lang で言語を選ぶ）、下までゆっくりスクロールしてから数える。
・数えるもの：見えているカード・曲ページへのリンク・リンク全体・画像・動画（埋め込み／サムネ）・章（section・見出し）、
  および「隠したカード」（data-i18n-hidden）。日本語と1つでも違えば赤（exit 1）。
・アーティストページ→曲ページへの「ページ内の移動」も1回たどる（英語で行き止まりになった不具合の再発検査）。
・公開前はプレビューURL、公開後は本番URLで走らせる。CHROMIUM_EXE で chromium の場所を渡せる。
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

LANGS = ["ja", "en", "zh-Hans", "es", "ko"]
DEFAULT_PATHS = [
    "/cover-guide?artist=hotei-tomoyasu",
    "/cover-guide?artist=hotei-tomoyasu&song=dancing-with-the-moonlight",
    "/feature/hikigatari",
    "/feature/citypop-sekai",
]
# ページ内の移動：アーティストページ → このリンクを押して曲ページへ
NAV_FROM = "/cover-guide?artist=hotei-tomoyasu"
NAV_TEXT = "DANCING WITH THE MOONLIGHT"  # 曲カードはボタン。曲名の文字で押す

COUNT_JS = r"""() => {
  const vis = (el) => {
    if (!el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const q = (s) => Array.from(document.querySelectorAll(s));
  const v = (s) => q(s).filter(vis).length;
  return {
    cards: v('[data-card-kind]'),
    songLinks: v('a[href*="/cover-guide?"]'),
    links: v('a[href]'),
    images: v('img'),
    videos: v('iframe, img[src*="ytimg.com/vi/"]'),
    chapters: v('section, h1, h2, h3'),
    hidden: q('[data-i18n-hidden]').length,
    lang: document.documentElement.lang,
    nokori: (() => {
      // 2026-10-10 追加：画面に残った日本語の文（人名・曲名の原題は除く）。
      // 名前の一覧はサイト側が window.__i18nNames で出す（元の表記の配列）。
      const KANA = /[\u3040-\u30ff]/, JA = /[\u3040-\u30ff\u3400-\u9fff]/;
      const names = (window.__i18nNames || []).slice().sort((a, b) => b.length - a.length);
      const strip = (t) => { let x = t; for (const n of names) if (n && x.includes(n)) x = x.split(n).join(' '); return x; };
      const out = [];
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        const p = n.parentElement;
        if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName) || p.closest('[data-no-translate]')) continue;
        if (!vis(p)) continue;
        const raw = (n.nodeValue || '').trim();
        if (!raw || !JA.test(raw)) continue;
        const t = strip(raw);
        out.push({ t: raw.slice(0, 120), kana: KANA.test(t), ja: JA.test(t) });
      }
      return out;
    })(),
  };
}"""
KEYS = ["cards", "songLinks", "links", "images", "videos", "chapters"]


def settle(pg, lg, wait):
    try:
        pg.wait_for_function("document.documentElement.lang===%r" % ("ja" if lg == "ja" else lg), timeout=30000)
    except Exception:
        pass
    pg.wait_for_timeout(wait)
    h = pg.evaluate("document.body.scrollHeight")
    y = 0
    steps = 0
    while y < h and steps < 30:  # 下まで（長いページでも30回まで）
        steps += 1
        y += 700
        pg.evaluate("window.scrollTo(0,%d)" % y)
        pg.wait_for_timeout(250)
        h = pg.evaluate("document.body.scrollHeight")
    pg.wait_for_timeout(2500)
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(800)


def measure(browser, base, path, lg, wait):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.add_init_script("try{localStorage.setItem('gokigen-lang','%s')}catch(e){}" % lg)
    pg = ctx.new_page()
    try:
        pg.goto(base + path, wait_until="load", timeout=90000)
        settle(pg, lg, wait)
        return pg.evaluate(COUNT_JS)
    except Exception as e:
        return {"error": str(e)[:160]}
    finally:
        ctx.close()


def measure_nav(browser, base, lg, wait):
    """アーティストページから曲ページへ、ページ内の移動でたどる。"""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.add_init_script("try{localStorage.setItem('gokigen-lang','%s')}catch(e){}" % lg)
    pg = ctx.new_page()
    try:
        pg.goto(base + NAV_FROM, wait_until="load", timeout=90000)
        settle(pg, lg, wait)
        link = pg.locator("button", has_text=NAV_TEXT).first
        link.scroll_into_view_if_needed(timeout=15000)
        link.click(timeout=15000)
        pg.wait_for_url("**song=dancing-with-the-moonlight**", timeout=30000)
        settle(pg, lg, wait)
        return pg.evaluate(COUNT_JS)
    except Exception as e:
        return {"error": str(e)[:160]}
    finally:
        ctx.close()


def compare(ja, other):
    if "error" in ja or "error" in other:
        return ["読めない: %s" % (other.get("error") or ja.get("error"))]
    diffs = ["%s 日本語%d→%d" % (k, ja[k], other[k]) for k in KEYS if ja[k] != other[k]]
    if other.get("hidden"):
        diffs.append("隠したカード %d" % other["hidden"])
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--paths", default=",".join(DEFAULT_PATHS))
    ap.add_argument("--langs", default=",".join(LANGS[1:]))
    ap.add_argument("--wait", type=int, default=4000)
    ap.add_argument("--out", default="")
    ap.add_argument("--no-nav", action="store_true")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    langs = [x for x in a.langs.split(",") if x]
    exe = os.environ.get("CHROMIUM_EXE")
    res = {"base": base, "pages": {}, "red": []}
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        targets = [(path, False) for path in a.paths.split(",") if path]
        if not a.no_nav:
            targets.append(("(移動) " + NAV_FROM + " → 曲ページ", True))
        for path, nav in targets:
            row = {}
            take = (lambda lg: measure_nav(b, base, lg, a.wait)) if nav else (lambda lg: measure(b, base, path, lg, a.wait))
            ja_samples = [take("ja")]
            row["ja"] = ja_samples[0]
            for lg in langs:
                samples = [take(lg)]
                # おすすめ（ランダム・読み込みの順）で日本語どうしでも1枚前後ゆれる。
                # そこで、日本語と同じ数になった回が1度でもあれば「同じ」とみなす（最大3回ずつ取る）。
                # 以前の不具合（隠す処理）は毎回・大きく減るので、この取り方でも必ず赤になる（2026-10-09 実測）。
                # 判定：数ごとに「日本語で出た数の幅」と「その言語で出た数の幅」が重なれば同じ。
                #   おすすめはランダムなので、日本語どうしでも1〜2枚ゆれる（2026-10-10 実測：日本語だけで 8〜10）。
                #   以前の不具合（隠す処理）は毎回・大きく減る（英語 34→24、中国語 34→6）ので、幅を見ても必ず赤になる。
                def best():
                    ok_j = [j for j in ja_samples if "error" not in j]
                    ok_x = [x for x in samples if "error" not in x]
                    if not ok_j or not ok_x:
                        return compare((ok_j or ja_samples)[0], (ok_x or samples)[0]), (ok_x or samples)[0]
                    d = []
                    for k in KEYS:
                        jl, jh = min(j[k] for j in ok_j), max(j[k] for j in ok_j)
                        xl, xh = min(x[k] for x in ok_x), max(x[k] for x in ok_x)
                        if xh < jl or xl > jh:
                            d.append("%s 日本語%d〜%d→%d〜%d" % (k, jl, jh, xl, xh))
                    hid = max(x.get("hidden", 0) for x in ok_x)
                    if hid:
                        d.append("隠したカード %d" % hid)
                    return d, ok_x[-1]
                d, r = best()
                while d and (len(samples) < 3 or len(ja_samples) < 3):
                    if len(ja_samples) < 3:
                        ja_samples.append(take("ja"))
                    if len(samples) < 3:
                        samples.append(take(lg))
                    d, r = best()
                row[lg] = r
                if "error" not in r and lg != "ja":
                    kana = [x["t"] for x in r.get("nokori", []) if x["kana"]]
                    kanji = [x["t"] for x in r.get("nokori", []) if x["ja"] and not x["kana"]]
                    r["nokoriKana"] = len(kana)
                    r["nokoriKanji"] = len(kanji)
                    # 2026-10-10 たまごさんのルール：日本語以外の表示で、ひらがな・カタカナが
                    # （人名・曲名の原題以外に）出ていたら公開を止める。
                    if kana:
                        d = list(d) + ["かなが残っている %d件（例: %s）" % (len(kana), " / ".join(kana[:3]))]
                if d:
                    res["red"].append("%s [%s] %s" % (path, lg, " / ".join(d)))
            res["pages"][path] = row
        b.close()
    res["ok"] = not res["red"]
    for path, row in res["pages"].items():
        print(path)
        for lg, r in row.items():
            if "error" in r:
                print("  %-8s 読めない %s" % (lg, r["error"]))
            else:
                print("  %-8s " % lg + "  ".join("%s=%s" % (k, r.get(k)) for k in KEYS + ["hidden", "nokoriKana", "nokoriKanji"]))
    print("判定:", "✓ 全言語で中身の量が同じ" if res["ok"] else "✗ 違いあり")
    for x in res["red"]:
        print("  ✗", x)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
