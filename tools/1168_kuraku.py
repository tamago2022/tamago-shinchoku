#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1168番：公開されるページを「1枚のCSS」に繋いで暗くする、ただ1つの機械。

■ たまごさんの言葉
    「全てのgithubダークモードにして　見やすいから」
    お手本は 1165-hassha.html。新しい配色は発明しない。

■ 穴に段ボールを貼るのではなく、パイプごと替える
    746枚のHTMLが**それぞれ自分で色を書いていた**。1枚ずつ暗く書き直すと、
    次に機械が作るページは明るいまま生まれてくる（＝穴が開いたまま）。
    だからここでは、公開の道（tools/pages_publish.sh）の途中に1箇所だけ関所を置いて、
      (1) ページの中の色を全部 var(--t-…) に置き換える
          → 色の実体は theme/tamago-dark.css にしか無くなる
      (2) その1枚を読み込む <link> を挿す
    をやる。**以後に作られるページも、公開される時に必ずここを通るので自動で暗くなる。**

■ 色の決め方（勘で決めていない）
    元の色の「明るさ(WCAG相対輝度)」と「鮮やかさ」だけを見て機械的に割り振る。
      ・くすんだ色（灰・白・黒・生成り）→ 明るさで 地/面/線/文字の4段に振る
      ・鮮やかな色 → 色相だけ残して 緑=ok / 赤=ng / 黄=warn / 青=info … に寄せる
        （たまごさんの指摘「緑や赤のバッジが見えない」を、暗い地の上で見える
          明度の同系色に置き換えることで潰す）

■ 使い方
    python3 tools/1168_kuraku.py --tree <ディレクトリ>          … 実際に書き換える
    python3 tools/1168_kuraku.py --tree <ディレクトリ> --dry-run … 数えるだけ
    1度通したファイルには印（tamago-dark 1）が入り、2度目は触らない（＝何度流しても同じ）。
    1枚失敗しても、そのファイルは元のまま残して次へ進む（公開を止めない）。
"""
import argparse
import colorsys
import os
import re
import sys

MARK = "tamago-dark 1"
THEME_REL = "theme/tamago-dark.css"

# ---------------------------------------------------------------- 色の道具
NAMED = {
    "white": "#ffffff", "black": "#000000", "whitesmoke": "#f5f5f5",
    "ivory": "#fffff0", "beige": "#f5f5dc", "snow": "#fffafa",
    "azure": "#f0ffff", "linen": "#faf0e6", "oldlace": "#fdf5e6",
    "silver": "#c0c0c0", "gainsboro": "#dcdcdc", "lightgray": "#d3d3d3",
    "lightgrey": "#d3d3d3", "gray": "#808080", "grey": "#808080",
    "darkgray": "#a9a9a9", "darkgrey": "#a9a9a9", "dimgray": "#696969",
    "dimgrey": "#696969", "lightslategray": "#778899",
    "red": "#ff0000", "crimson": "#dc143c", "firebrick": "#b22222",
    "tomato": "#ff6347", "salmon": "#fa8072", "indianred": "#cd5c5c",
    "orange": "#ffa500", "orangered": "#ff4500", "darkorange": "#ff8c00",
    "gold": "#ffd700", "yellow": "#ffff00", "khaki": "#f0e68c",
    "green": "#008000", "limegreen": "#32cd32", "lime": "#00ff00",
    "seagreen": "#2e8b57", "forestgreen": "#228b22", "olive": "#808000",
    "teal": "#008080", "cyan": "#00ffff", "aqua": "#00ffff",
    "blue": "#0000ff", "navy": "#000080", "royalblue": "#4169e1",
    "steelblue": "#4682b4", "dodgerblue": "#1e90ff", "skyblue": "#87ceeb",
    "lightblue": "#add8e6", "aliceblue": "#f0f8ff", "midnightblue": "#191970",
    "purple": "#800080", "violet": "#ee82ee", "magenta": "#ff00ff",
    "indigo": "#4b0082", "orchid": "#da70d6",
    "pink": "#ffc0cb", "hotpink": "#ff69b4", "lightpink": "#ffb6c1",
    "brown": "#a52a2a", "maroon": "#800000", "sienna": "#a0522d",
    "tan": "#d2b48c", "wheat": "#f5deb3", "cornsilk": "#fff8dc",
    "seashell": "#fff5ee", "mistyrose": "#ffe4e1", "lavender": "#e6e6fa",
}
SKIP_WORDS = {"transparent", "currentcolor", "inherit", "initial", "unset",
              "none", "auto", "revert"}

# 既に 1165 の配色そのものだったものは、迷わずその変数へ（お手本を壊さない）
EXACT = {
    "#0d0f12": "var(--t-bg)", "#0a0c0f": "var(--t-bg2)",
    "#15181d": "var(--t-panel)", "#1b1f26": "var(--t-panel2)",
    "#23272e": "var(--t-line)", "#1d2126": "var(--t-line2)",
    "#e8e6e1": "var(--t-fg)", "#c9d1d9": "var(--t-fg2)",
    "#9aa4ae": "var(--t-mute)", "#8b949e": "var(--t-mute2)",
    "#7d8590": "var(--t-dim)",
    "#5ddba0": "var(--t-ok)", "#ff7b72": "var(--t-ng)",
    "#e3b341": "var(--t-warn)", "#79c0ff": "var(--t-info)",
    "#d2a8ff": "var(--t-purple)", "#ff9bce": "var(--t-pink)",
}


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(r, g, b):
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) == 8:      # #rrggbbaa
        h = h[:6]
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _hue_var(h_deg, kind):
    """色相だけ残して意味のある色に寄せる。kind は 'fg' か 'bg'。"""
    if h_deg < 14 or h_deg >= 345:
        name = "ng"
    elif h_deg < 70:
        name = "warn"
    elif h_deg < 165:
        name = "ok"
    elif h_deg < 255:
        name = "info"
    elif h_deg < 290:
        name = "purple"
    else:
        name = "pink"
    return "var(--t-%s%s)" % (name, "-bg" if kind == "bg" else "")


def map_color(rgb, role):
    """元の色(rgb) と 役割(bg/fg/border) から、暗い配色の変数名を返す。"""
    r, g, b = rgb
    lum = _luminance(r, g, b)
    h, _l, _s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    h_deg = h * 360.0

    # 「くすんでいるか」は彩度(HLS)ではなく**色味の幅**で見る。
    #   HLSの彩度は白に近い色で暴れる（生成りの #f7f4ee が彩度0.36と出て、
    #   茶色のバッジに化けた。実測で掴んだ事故）。max-min なら生成り0.03・緑0.29と
    #   素直に別れる。
    chroma = (max(r, g, b) - min(r, g, b)) / 255.0
    dull = chroma < 0.16

    if role == "border":
        if not dull:
            return _hue_var(h_deg, "fg")
        return "var(--t-line)"

    if role == "bg":
        if not dull:
            return _hue_var(h_deg, "bg")
        if lum < 0.012:
            return "var(--t-bg)"
        if lum < 0.10:
            return "var(--t-panel)"
        if lum < 0.35:
            return "var(--t-line)"
        return "var(--t-panel)"

    # role == 'fg'
    if not dull:
        return _hue_var(h_deg, "fg")
    if lum < 0.06:
        return "var(--t-fg2)"
    if lum < 0.45:
        return "var(--t-mute)"
    return "var(--t-fg)"


# ------------------------------------------------- 「どの役割か」を property から
BG_RE = re.compile(r"(^|-)(background|bgcolor)")
BORDER_RE = re.compile(r"(border|outline|divider|rule)")
FG_RE = re.compile(r"(^color$|text|fill|stroke|caret|accent|stop-color|flood-color|placeholder|ink|font)")
SHADOW_RE = re.compile(r"(shadow|filter|backdrop)")


def role_of(prop):
    """CSSプロパティ名 → 役割。None を返したらその色は触らない。"""
    if not prop:
        return None
    p = prop.strip().lower()
    if SHADOW_RE.search(p):
        return None                      # 影はそのままで良い（暗い地でも邪魔しない）
    if p.startswith("--"):               # ページが自分で作った変数：名前で判断
        n = p[2:]
        if BG_RE.search(n) or re.search(r"(panel|surface|card|paper|sheet|bg|back|fill)", n):
            return "bg"
        if BORDER_RE.search(n) or re.search(r"(line|stroke|edge)", n):
            return "border"
        return "fg"
    if BG_RE.search(p):
        return "bg"
    if BORDER_RE.search(p):
        return "border"
    if FG_RE.search(p) or p == "color":
        return "fg"
    return None


COLOR_TOKEN = re.compile(
    r"#[0-9a-fA-F]{3,8}\b"
    r"|rgba?\(\s*[-\d.%]+\s*,\s*[-\d.%]+\s*,\s*[-\d.%]+\s*(?:,\s*[\d.%]+\s*)?\)"
    # 色の名前。var(--t-pink) の "pink" のような**変数名の一部**は拾わない
    r"|(?<![-\w])(?:" + "|".join(sorted(NAMED, key=len, reverse=True)) + r")(?![-\w])"
)
PROP_BEFORE = re.compile(r"([-a-zA-Z][-a-zA-Z0-9]*)\s*:\s*[^;{}]*$")


def _prop_for(css_text, pos):
    """色トークンの位置から左へ遡って、その色が属する property 名を拾う。"""
    start = max(css_text.rfind(";", 0, pos), css_text.rfind("{", 0, pos),
                css_text.rfind("}", 0, pos), css_text.rfind('"', 0, pos),
                css_text.rfind("'", 0, pos)) + 1
    m = PROP_BEFORE.search(css_text[start:pos])
    return m.group(1) if m else None


def _parse_rgb_func(tok):
    inner = tok[tok.index("(") + 1:tok.rindex(")")]
    parts = [p.strip() for p in inner.replace("/", ",").split(",")]
    if len(parts) < 3:
        return None, 1.0
    vals = []
    for p in parts[:3]:
        try:
            vals.append(int(round(float(p[:-1]) * 2.55)) if p.endswith("%") else int(round(float(p))))
        except ValueError:
            return None, 1.0
    a = 1.0
    if len(parts) >= 4:
        try:
            a = float(parts[3][:-1]) / 100.0 if parts[3].endswith("%") else float(parts[3])
        except ValueError:
            a = 1.0
    return tuple(max(0, min(255, v)) for v in vals), a


def recolor_css(css_text):
    """CSSの本文（<style>の中身／style=""の中身／.cssの全文）の色を変数に置き換える。"""
    out = []
    last = 0
    for m in COLOR_TOKEN.finditer(css_text):
        tok = m.group(0)
        low = tok.lower()
        if low in SKIP_WORDS:
            continue
        role = role_of(_prop_for(css_text, m.start()))
        if role is None:
            continue
        alpha = 1.0
        if low.startswith("rgb"):
            rgb, alpha = _parse_rgb_func(tok)
            # 薄い重ね（影・うっすら白）はそのままの方が自然。濃いものだけ置き換える
            if rgb is None or alpha < 0.5:
                continue
        elif low.startswith("#"):
            rgb = _hex_to_rgb(low)
        else:
            rgb = _hex_to_rgb(NAMED[low])
        if rgb is None:
            continue
        if low.startswith("#") and low in EXACT:
            rep = EXACT[low]
        else:
            rep = map_color(rgb, role)
        out.append(css_text[last:m.start()])
        out.append(rep)
        last = m.end()
    if not out:
        return css_text, 0
    out.append(css_text[last:])
    return "".join(out), len(out) // 2


# ------------------------------------------------------- <script> の中の色
# ★ ここだけは var(--t-…) ではなく**実体の色**を入れる。
#   canvas の fillStyle や一部の図ライブラリは var() を解釈できず、色が消えるため。
#   ただし値は theme/tamago-dark.css と同じ1枚から機械が引いている（手で決めていない）。
SCRIPT_BLOCK = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)
# '#fff' 単体だけでなく 'border:1px solid #eee7dc' のような**文字列の一部**も拾う
# （index.html の実測：JSが組み立てる枠線の色がここに隠れていた）
JS_COLOR = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])")
# ★ JSの色は「DOMの見た目をその場で塗っている所」だけ触る。
#   絵本・アバターなど**絵を描くための色の組（palette）は作品なので触らない**。
#   暗くしたいのは器（進捗表のUI）で、中の絵ではない。
#   実測で見分けが付いた：UIは必ず .style / cssText / setProperty / style=" を通る。
#   絵は ink:'#…' / fills:['#…'] のような色の組で持っている（.style を通らない）。
JS_COLOR_CTX = re.compile(r"""(\.style\b|setProperty\s*\(|cssText|style\s*=\s*["'`])""")


def recolor_scripts(text):
    n = 0

    def _js(m):
        nonlocal n
        body = m.group(2)
        out = []
        last = 0
        for t in JS_COLOR.finditer(body):
            ctx = body[max(0, t.start() - 90):t.start()]
            if not JS_COLOR_CTX.search(ctx):
                continue
            rgb = _hex_to_rgb(t.group(0))
            if rgb is None:
                continue
            near = ctx[-40:] + body[t.end():t.end() + 12]
            role = "border" if re.search(r"(border|stroke)", near, re.I) else \
                   ("bg" if re.search(r"(background|bg|fill(?!Text)|paper)", near, re.I) else "fg")
            var = EXACT.get(t.group(0).lower()) or map_color(rgb, role)
            out.append(body[last:t.start()])
            out.append(SVG_LITERAL[var])
            last = t.end()
            n += 1
        if not out:
            return m.group(0)
        out.append(body[last:])
        return m.group(1) + "".join(out) + m.group(3)

    return SCRIPT_BLOCK.sub(_js, text), n


# --------------------------------------------------------------- HTML の書き換え
STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
STYLE_ATTR = re.compile(r"""(\sstyle\s*=\s*)(["'])(.*?)\2""", re.S | re.I)
COLOR_ATTR = re.compile(
    r"""(\s(?:fill|stroke|stop-color|bgcolor|color|flood-color|text|bordercolor)\s*=\s*)(["'])(.*?)\2""",
    re.S | re.I)
THEME_META = re.compile(
    r"""(<meta[^>]*name\s*=\s*["']theme-color["'][^>]*content\s*=\s*)(["'])(.*?)\2""", re.I)


def transform_html(text, depth):
    n = 0

    def _block(m):
        nonlocal n
        new, c = recolor_css(m.group(2))
        n += c
        return m.group(1) + new + m.group(3)

    text = STYLE_BLOCK.sub(_block, text)

    def _attr(m):
        nonlocal n
        new, c = recolor_css(m.group(3))
        n += c
        return m.group(1) + m.group(2) + new + m.group(2)

    text = STYLE_ATTR.sub(_attr, text)

    def _cattr(m):
        nonlocal n
        v = m.group(3).strip()
        low = v.lower()
        if low in SKIP_WORDS or low.startswith("url") or low.startswith("var("):
            return m.group(0)
        prop = m.group(1).strip().rstrip("=").strip().lower()
        role = role_of(prop)
        if role is None:
            return m.group(0)
        if low.startswith("rgb"):
            rgb, a = _parse_rgb_func(v)
            if rgb is None or a < 0.5:
                return m.group(0)
        elif low.startswith("#"):
            rgb = _hex_to_rgb(low)
        elif low in NAMED:
            rgb = _hex_to_rgb(NAMED[low])
        else:
            return m.group(0)
        if rgb is None:
            return m.group(0)
        rep = EXACT.get(low) or map_color(rgb, role)
        n += 1
        return m.group(1) + m.group(2) + rep + m.group(2)

    text = COLOR_ATTR.sub(_cattr, text)
    text, c = recolor_scripts(text)
    n += c
    text = THEME_META.sub(lambda m: m.group(1) + m.group(2) + "#0d0f12" + m.group(2), text)

    href = ("../" * depth) + THEME_REL
    link = ('\n<!--%s--><link rel="stylesheet" href="%s">\n' % (MARK, href))

    # 一番最後に読み込ませる＝ページ側と同じ強さの指定なら、こちらが後に来て勝つ
    # ★ text.lower().rfind() は使わない。lower() は文字数が変わる字（İ など）があると
    #   位置がずれ、</body> の途中に挿し込んで閉じタグを壊す（実測で1枚壊れた）。
    for tag in ("body", "html"):
        hits = list(re.finditer(r"</\s*%s\s*>" % tag, text, re.I))
        if hits:
            i = hits[-1].start()
            return text[:i] + link + text[i:], n
    return text + link, n


def transform_css(text):
    new, n = recolor_css(text)
    return "/*%s*/\n" % MARK + new, n


def transform_svg(text, depth):
    n = 0

    def _block(m):
        nonlocal n
        new, c = recolor_css(m.group(2))
        n += c
        return m.group(1) + new + m.group(3)

    text = STYLE_BLOCK.sub(_block, text)

    def _attr(m):
        nonlocal n
        new, c = recolor_css(m.group(3))
        n += c
        return m.group(1) + m.group(2) + new + m.group(2)

    text = STYLE_ATTR.sub(_attr, text)

    # SVG は単体で <img> として出るので、変数が効かない。実体の色を直接入れる
    def _cattr(m):
        nonlocal n
        v = m.group(3).strip().lower()
        if v in SKIP_WORDS or v.startswith("url"):
            return m.group(0)
        role = role_of(m.group(1).strip().rstrip("=").strip().lower())
        if role is None:
            return m.group(0)
        rgb = _hex_to_rgb(v) if v.startswith("#") else _hex_to_rgb(NAMED.get(v, ""))
        if rgb is None:
            return m.group(0)
        n += 1
        return m.group(1) + m.group(2) + SVG_LITERAL[map_color(rgb, role)] + m.group(2)

    text = COLOR_ATTR.sub(_cattr, text)
    # 変数を実体に戻す（<style>内の置換分）
    for var, lit in SVG_LITERAL.items():
        text = text.replace(var, lit)
    if "<!--" + MARK + "-->" not in text:
        text = text.replace("<svg", "<!--%s--><svg" % MARK, 1)
    return text, n


SVG_LITERAL = {
    "var(--t-bg)": "#0d0f12", "var(--t-bg2)": "#0a0c0f",
    "var(--t-panel)": "#15181d", "var(--t-panel2)": "#1b1f26",
    "var(--t-line)": "#23272e", "var(--t-line2)": "#1d2126",
    "var(--t-fg)": "#e8e6e1", "var(--t-fg2)": "#c9d1d9",
    "var(--t-mute)": "#9aa4ae", "var(--t-mute2)": "#8b949e",
    "var(--t-dim)": "#7d8590",
    "var(--t-ok)": "#5ddba0", "var(--t-ng)": "#ff7b72",
    "var(--t-warn)": "#e3b341", "var(--t-info)": "#79c0ff",
    "var(--t-purple)": "#d2a8ff", "var(--t-pink)": "#ff9bce",
    "var(--t-ok-bg)": "#12241c", "var(--t-ng-bg)": "#2a1416",
    "var(--t-warn-bg)": "#261e0c", "var(--t-info-bg)": "#0f1e2e",
    "var(--t-purple-bg)": "#1e1630", "var(--t-pink-bg)": "#2a1524",
}

SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".worktrees"}
TARGET_EXT = {".html", ".htm", ".css", ".svg"}


def walk(tree):
    for root, dirs, files in os.walk(tree):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext in TARGET_EXT:
                yield os.path.join(root, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    tree = os.path.abspath(a.tree)
    theme_abs = os.path.join(tree, THEME_REL)

    tot = {"html": 0, "css": 0, "svg": 0}
    done = {"html": 0, "css": 0, "svg": 0}
    already = {"html": 0, "css": 0, "svg": 0}
    fail = []
    swaps = 0

    for path in walk(tree):
        if os.path.abspath(path) == os.path.abspath(theme_abs):
            continue
        ext = os.path.splitext(path)[1].lower()
        kind = "css" if ext == ".css" else ("svg" if ext == ".svg" else "html")
        tot[kind] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
                src = fh.read()
            if MARK in src:
                already[kind] += 1
                continue
            depth = len(os.path.relpath(path, tree).split(os.sep)) - 1
            if kind == "html":
                new, n = transform_html(src, depth)
            elif kind == "css":
                new, n = transform_css(src)
            else:
                new, n = transform_svg(src, depth)
            if new != src:
                if not a.dry_run:
                    tmp = path + ".1168tmp"
                    with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
                        fh.write(new)
                    os.replace(tmp, path)
                done[kind] += 1
                swaps += n
        except Exception as e:          # 1枚失敗しても公開は止めない
            fail.append("%s: %s" % (os.path.relpath(path, tree), e))

    if not a.quiet:
        print("1168 暗くした結果%s" % ("（数えるだけ）" if a.dry_run else ""))
        for k in ("html", "css", "svg"):
            print("  %-4s 全%d枚 / 今回暗くした%d枚 / 既に印あり%d枚"
                  % (k, tot[k], done[k], already[k]))
        print("  置き換えた色の個数: %d" % swaps)
        print("  失敗: %d枚" % len(fail))
        for f in fail[:20]:
            print("    - " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
