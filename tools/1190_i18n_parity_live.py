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
ALLOW_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "status", "1191_nihongo_nokori", "allow_originals.json")

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
      // 2026-10-10 追加：画面に残った日本語（人名・曲名の「元の表記」は除く）。
      // 残ってよいもの＝①名前表（window.__i18nNames）②作品名など翻訳時に原文で確認した元の表記（window.__i18nAllow）
      //                ③「元の表記 読み」の形（かなのすぐ後に空白と大文字の読み・ハングル・漢字、または括弧つきの読み）
      // 判定は joy-relief-station/scripts/patrol/check-i18n-kana.mjs と同じ。中黒・長音は数えない（中国語でも使う）。
      const KANA = /[ぁ-ゟァ-ヺヽ-ヿ]/, JA = /[ぁ-ゟァ-ヺヽ-ヿ㐀-鿿]/;
      const RUN = /[ぁ-ゟァ-ヿ㐀-鿿々〆]+/g;
      const READ = /[A-Za-zÀ-ɏ가-힣一-鿿]/;
      const READ_START = /[A-ZÀ-Þ가-힣一-鿿¡¿0-9]/;
      const CLOSE = new Set([..."」』”》’\"）)]】"]);
      const allow = [...(window.__i18nNames || []), ...(window.__i18nAllow || [])];
      const idx = new Map();
      for (const a of allow) for (const r of (a.match(RUN) || [])) { if (!idx.has(r)) idx.set(r, []); idx.get(r).push(a); }
      const pairOk = (t, r) => {
        if (r.length > 30) return false;
        let i = 0;
        for (;;) {
          const j = t.indexOf(r, i); if (j < 0) return false;
          let k = j + r.length; while (k < t.length && CLOSE.has(t[k])) k++;
          if (k < t.length && ' （('.includes(t[k])) {
            let saw = t[k] !== ' ', k2 = k + 1;
            while (k2 < t.length && ' （(“"'.includes(t[k2])) { if ('（('.includes(t[k2])) saw = true; k2++; }
            if (k2 < t.length && (saw ? READ : READ_START).test(t[k2])) return true;
          }
          const b = j - 1;
          if (b >= 1 && t[b] === ' ' && READ.test(t[b - 1])) { let w = b - 1; while (w > 0 && READ.test(t[w - 1])) w--; if (READ_START.test(t[w])) return true; }
          i = j + 1;
        }
      };
      const kanaLeft = (t) => {
        for (const r of (t.match(RUN) || [])) {
          if (!KANA.test(r)) continue;
          if ((idx.get(r) || []).some((a) => t.includes(a))) continue;
          if (pairOk(t, r)) continue;
          return r;
        }
        return null;
      };
      const out = [];
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        const p = n.parentElement;
        if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName) || p.closest('[data-no-translate]')) continue;
        if (!vis(p)) continue;
        const raw = (n.nodeValue || '').trim();
        if (!raw || !JA.test(raw)) continue;
        const left = kanaLeft(raw);
        // 読みの二重（「布袋寅泰 Tomoyasu Hotei Tomoyasu Hotei」）も数える（2026-10-10 実測で起きた）
        const dup = /(?:^|[\s(（“「『])([A-Z][\w'’.-]+(?: [A-Z][\w'’.-]+){1,3}) \1(?![\w])/.test(raw) || /([가-힣]{2,}(?: [가-힣]{2,}){1,2}) \1/.test(raw);
        // 2026-10-10（1192番）曲名だけがローマ字なしで出ている（「異邦人」だけ等）。曲名の一覧は window.__songTitlesJa
        const bare = !!(window.__songTitlesJa && window.__songTitlesJa.has(raw.replace(/^[「『“"]|[」』”"]$/g, '').trim()));
        out.push({ t: raw.slice(0, 120), kana: !!left, ja: JA.test(raw), left: left || '', dup, bare });
      }
      return out;
    })(),
  };
}"""
try:
    ALLOW_JS = json.dumps(json.load(open(ALLOW_FILE, encoding="utf-8")), ensure_ascii=False)
except Exception:
    ALLOW_JS = "[]"
# 1192番：かな・漢字の曲名の一覧（曲名がローマ字なしで出ていないかを見る）
SONGS_FILE = os.path.join(os.path.dirname(ALLOW_FILE), "..", "1192_romaji", "songs.json")
try:
    import re as _re
    _JA = _re.compile(r"[\u3040-\u30ff\u3400-\u9fff々〆]")
    _ts = set()
    for _s in json.load(open(SONGS_FILE, encoding="utf-8")):
        for _k in ("raw", "tidy"):
            _t = (_s.get(_k) or "").strip()
            if _JA.search(_t):
                _ts.add(_t)
    TITLES_JS = json.dumps(sorted(_ts), ensure_ascii=False)
except Exception:
    TITLES_JS = "[]"
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
    ctx.add_init_script("window.__i18nAllow=%s;" % ALLOW_JS)
    ctx.add_init_script("window.__songTitlesJa=new Set(%s);" % TITLES_JS)
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
                    # 1192番（2026-10-10）：日本語以外の表示で、かな・漢字の曲名にローマ字（海外向け表記）が付いていなければ止める
                    bare = [x["t"] for x in r.get("nokori", []) if x.get("bare")]
                    r["romajiNashi"] = len(bare)
                    if bare:
                        d = list(d) + ["曲名にローマ字が無い %d件（例: %s）" % (len(bare), " / ".join(bare[:3]))]
                    dup = [x["t"] for x in r.get("nokori", []) if x.get("dup")]
                    r["nijuu"] = len(dup)
                    if dup:
                        d = list(d) + ["名前の読みが二重 %d件（例: %s）" % (len(dup), " / ".join(dup[:2]))]
                if d:
                    res["red"].append("%s [%s] %s" % (path, lg, " / ".join(d)))
            res["pages"][path] = row
            # 2026-10-10：ログイン画面などで中身が読めていないのに「同じ」と出ていた（プレビューURL）。中身が無ければ赤。
            j0 = row.get("ja", {})
            if "error" not in j0 and j0.get("links", 0) < 10:
                res["red"].append("%s 日本語のページに中身が無い（links=%s）。読めていない" % (path, j0.get("links")))
        b.close()
    res["ok"] = not res["red"]
    for path, row in res["pages"].items():
        print(path)
        for lg, r in row.items():
            if "error" in r:
                print("  %-8s 読めない %s" % (lg, r["error"]))
            else:
                print("  %-8s " % lg + "  ".join("%s=%s" % (k, r.get(k)) for k in KEYS + ["hidden", "nokoriKana", "nokoriKanji", "romajiNashi"]))
    print("判定:", "✓ 全言語で中身の量が同じ" if res["ok"] else "✗ 違いあり")
    for x in res["red"]:
        print("  ✗", x)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
