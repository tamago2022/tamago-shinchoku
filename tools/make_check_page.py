#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
確認ページ（share/check/*.html）を、毎回ゼロから書かずに型から量産するための道具。

背景（2026-09-06・たまごさん指示「仕組み・効率化」）:
  全セッションが確認ページのHTMLを毎回ゼロから書いていて、同じ枠組みを
  何十回も書き直していた。クレジットの無駄であり、出来上がりもバラバラに
  なる。番号・題名・数字・URL一覧・画像パスを渡すだけでHTMLを吐く道具に
  一本化する。

型（テンプレート）: share/check/_template.html
  {{TOKEN}} 形式のプレースホルダを埋めるだけ。CSSやレイアウトはここでは
  一切いじらない（型を直したい時は _template.html 側を直す）。

使い方1（CLI引数だけで一発生成・小さい確認ページ向け）:
  python3 tools/make_check_page.py \
    --n 420 --slug check-page-template \
    --title "確認ページの型（テンプレート）" \
    --what "確認ページを毎回ゼロから書くのをやめ、型から量産できるようにした。" \
    --num "3個|新規に作ったファイル数（_template.html／make_check_page.py／本ページ）" \
    --num "1行|auto_launcherの指示文をmake_check_page.py利用の1行に短縮" \
    --link "テンプレート本体|https://github.com/tamago2022/tamago-shinchoku/blob/main/share/check/_template.html" \
    --link "生成スクリプト|https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/make_check_page.py"

使い方2（JSON設定ファイルから生成・件数が多い／他スクリプトから呼ぶ時向け）:
  python3 tools/make_check_page.py --json path/to/config.json
  （JSONのキーは下記 build_context() のフィールド名と同じ。CLI引数と両方
   指定した場合はJSONの値をCLI引数が上書きする）

出力先: share/check/{n}-{slug}.html （--out で上書き可）
画像は事前に share/check/img/ 配下へ自分で置いておくこと（このスクリプトは
画像そのものは作らない。パスを渡すだけ）。
"""
import argparse
import datetime
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHECK_DIR = os.path.join(REPO, "share", "check")
TEMPLATE_PATH = os.path.join(CHECK_DIR, "_template.html")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/share/check/"


def esc(s):
    return html.escape(str(s), quote=True)


def build_nums_html(nums):
    if not nums:
        return '<div class="note">（数字なし）</div>'
    out = []
    for item in nums:
        value = item.get("value", "")
        label = item.get("label", "")
        out.append(
            '  <div class="num"><b>%s</b><span>%s</span></div>' % (esc(value), esc(label))
        )
    return "\n".join(out)


def build_shots_section(before_img, after_img, before_label, after_label, shots=None, shots_title=None):
    """スクショ節を組み立てる。

    後方互換のbefore/after（2枚専用）に加え、任意枚数を並べたい時は
    shots=[{"label":..., "img":..., "meta":...(省略可)}, ...] を渡す。
    before/afterとshotsを両方渡した場合は両方とも出す（通常はどちらか一方でよい）。
    """
    if not before_img and not after_img and not shots:
        return ""
    title = shots_title or "③ 実データでのスクリーンショット"
    parts = ["<h2>%s</h2>" % esc(title), '<div class="shots">']
    if before_img:
        parts.append(
            '  <div class="shot before"><b>%s</b><img src="%s" alt="前"></div>'
            % (esc(before_label or "前"), esc(before_img))
        )
    if after_img:
        parts.append(
            '  <div class="shot after"><b>%s</b><img src="%s" alt="後"></div>'
            % (esc(after_label or "後"), esc(after_img))
        )
    for s in shots or []:
        meta_html = ('<span class="meta">%s</span>' % esc(s["meta"])) if s.get("meta") else ""
        parts.append(
            '  <div class="shot plain"><b>%s</b><img src="%s" alt="%s">%s</div>'
            % (esc(s.get("label", "")), esc(s.get("img", "")), esc(s.get("label", "")), meta_html)
        )
    parts.append("</div>")
    return "\n".join(parts)


def build_links_html(links):
    if not links:
        return '<li><b>（リンクなし）</b></li>'
    out = []
    for item in links:
        label = item.get("label", "")
        url = item.get("url", "")
        out.append(
            '  <li><b>%s</b><a href="%s" target="_blank" rel="noopener">%s</a></li>'
            % (esc(label), esc(url), esc(url))
        )
    return "\n".join(out)


def build_table_section(rows):
    if not rows:
        return ""
    parts = ['<h2>⑤ 何をどう確かめたか</h2>', "<table>", "<tr><th>確認項目</th><th>結果</th></tr>"]
    for row in rows:
        item = row.get("item", "")
        result = row.get("result", "")
        ok = row.get("ok", True)
        cls = "yes" if ok else "no"
        parts.append(
            "<tr><td>%s</td><td class=\"%s\">%s</td></tr>" % (esc(item), cls, esc(result))
        )
    parts.append("</table>")
    return "\n".join(parts)


def build_context(cfg):
    n = cfg["n"]
    slug = cfg["slug"]
    title = cfg.get("title") or ("#%s %s" % (n, slug))
    if not title.startswith("#"):
        title = "#%s %s" % (n, title)
    date_line = cfg.get("date_line") or (
        datetime.date.today().isoformat() + " 実装・main合流・本番(GitHub Pages)反映まで実測確認"
    )
    what_html = cfg.get("what") or "（内容未記入）"
    nums_html = build_nums_html(cfg.get("nums") or [])
    shots_section = build_shots_section(
        cfg.get("before_img"),
        cfg.get("after_img"),
        cfg.get("before_label"),
        cfg.get("after_label"),
        cfg.get("shots"),
        cfg.get("shots_title"),
    )
    links_html = build_links_html(cfg.get("links") or [])
    table_section = build_table_section(cfg.get("table") or [])
    footer = cfg.get("footer") or (
        "このページは #%s のセッションが tools/make_check_page.py で自動生成した確認資料。"
        "書式は share/check/_template.html（共通の型）に揃えている。" % n
    )
    return {
        "TITLE": title,
        "DATE_LINE": date_line,
        "WHAT_HTML": what_html,
        "NUMS_HTML": nums_html,
        "SHOTS_SECTION": shots_section,
        "LINKS_HTML": links_html,
        "TABLE_SECTION": table_section,
        "FOOTER_NOTE": footer,
    }


def render(cfg):
    with io_open(TEMPLATE_PATH) as f:
        tpl = f.read()
    ctx = build_context(cfg)
    for key, value in ctx.items():
        tpl = tpl.replace("{{%s}}" % key, value)
    return tpl


def io_open(path):
    return open(path, "r", encoding="utf-8")


def parse_pair(raw, sep="|"):
    if sep not in raw:
        raise ValueError("形式は 'A%sB' です: %r" % (sep, raw))
    a, b = raw.split(sep, 1)
    return a.strip(), b.strip()


def main():
    ap = argparse.ArgumentParser(description="確認ページ(share/check/*.html)を型から生成する")
    ap.add_argument("--json", help="設定JSONファイルのパス（他のCLI引数より弱い＝CLI引数が上書きする）")
    ap.add_argument("--n", type=int, help="番号（発車待ちの番号など）")
    ap.add_argument("--slug", help="ファイル名に使う短い英語スラッグ（例: check-page-template）")
    ap.add_argument("--title", help="見出し（省略時は #n slug）")
    ap.add_argument("--date", dest="date_line", help="日付行（省略時は今日の日付＋定型文）")
    ap.add_argument("--what", help="① 何を直したか（1〜数文、htmlの<code>等は使ってよい）")
    ap.add_argument("--num", action="append", default=[], metavar="VALUE|LABEL", help="数字カード。複数指定可")
    ap.add_argument("--link", action="append", default=[], metavar="LABEL|URL", help="押せるリンク。複数指定可")
    ap.add_argument("--table", action="append", default=[], metavar="ITEM|RESULT|yes|no", help="確認項目の行。複数指定可")
    ap.add_argument("--before", dest="before_img", help="前スクショの相対パス（share/check/からの相対。例: img/420-before.png）")
    ap.add_argument("--after", dest="after_img", help="後スクショの相対パス")
    ap.add_argument("--before-label", dest="before_label")
    ap.add_argument("--after-label", dest="after_label")
    ap.add_argument(
        "--shot",
        action="append",
        default=[],
        metavar="LABEL|IMG[|META]",
        help="任意枚数のスクショを並べたい時（before/after2枚に収まらない場合）。複数指定可。META省略可。",
    )
    ap.add_argument("--shots-title", dest="shots_title", help="スクショ節の見出し（省略時は既定文言）")
    ap.add_argument("--footer", help="末尾の注記（省略時は自動生成）")
    ap.add_argument("--out", help="出力ファイルパス（省略時は share/check/{n}-{slug}.html）")
    ap.add_argument("--print-url", action="store_true", help="生成後、GitHub Pages上の想定URLを標準出力へ1行出す")
    ap.add_argument(
        "--allow-no-screenshot",
        help=(
            "スクショ無しで書き出すことを明示的に許可する（理由を1行必須。例: "
            "'--allow-no-screenshot \"調査のみでVault成果物へのリンクしか出せない\"'）。"
            "指定しない限り--before/--afterのどちらも無いと書き出しを拒否する"
            "（鬼監督の機械検品③がimg無しを問答無用でFAILにするため、事前に防ぐ）。"
        ),
    )
    args = ap.parse_args()

    cfg = {}
    if args.json:
        with io_open(args.json) as f:
            cfg = json.load(f)

    if args.n is not None:
        cfg["n"] = args.n
    if args.slug:
        cfg["slug"] = args.slug
    if args.title:
        cfg["title"] = args.title
    if args.date_line:
        cfg["date_line"] = args.date_line
    if args.what:
        cfg["what"] = args.what
    if args.before_img:
        cfg["before_img"] = args.before_img
    if args.after_img:
        cfg["after_img"] = args.after_img
    if args.before_label:
        cfg["before_label"] = args.before_label
    if args.after_label:
        cfg["after_label"] = args.after_label
    if args.footer:
        cfg["footer"] = args.footer
    if args.shots_title:
        cfg["shots_title"] = args.shots_title

    if args.shot:
        shots = cfg.get("shots") or []
        for raw in args.shot:
            parts = raw.split("|")
            if len(parts) < 2:
                raise ValueError("形式は 'LABEL|IMG' or 'LABEL|IMG|META' です: %r" % raw)
            label, img = parts[0].strip(), parts[1].strip()
            meta = parts[2].strip() if len(parts) >= 3 else None
            shots.append({"label": label, "img": img, "meta": meta})
        cfg["shots"] = shots

    if args.num:
        nums = cfg.get("nums") or []
        for raw in args.num:
            value, label = parse_pair(raw)
            nums.append({"value": value, "label": label})
        cfg["nums"] = nums

    if args.link:
        links = cfg.get("links") or []
        for raw in args.link:
            label, url = parse_pair(raw)
            links.append({"label": label, "url": url})
        cfg["links"] = links

    if args.table:
        rows = cfg.get("table") or []
        for raw in args.table:
            parts = raw.split("|")
            if len(parts) < 2:
                raise ValueError("形式は 'ITEM|RESULT|yes' or 'ITEM|RESULT|no' です: %r" % raw)
            item, result = parts[0].strip(), parts[1].strip()
            ok = True
            if len(parts) >= 3:
                ok = parts[2].strip().lower() not in ("no", "false", "0", "ng")
            rows.append({"item": item, "result": result, "ok": ok})
        cfg["table"] = rows

    if "n" not in cfg or "slug" not in cfg:
        print("エラー: --n と --slug は必須です（またはJSONにnとslugを入れる）", file=sys.stderr)
        sys.exit(1)

    if not cfg.get("before_img") and not cfg.get("after_img") and not cfg.get("shots"):
        allow_reason = args.allow_no_screenshot or cfg.get("allow_no_screenshot")
        if not allow_reason:
            print(
                "エラー: スクショ(--before/--after)が1枚もありません。"
                "鬼監督の機械検品(tools/verify_check_pages.py)は<img>タグが無い"
                "確認ページを問答無用でFAILにし、やり直しへ戻します"
                "（444/446/448番バッチで実際に繰り返し発生した事故）。"
                "先に share/check/img/ へスクショを置いて --before/--after で渡すか、"
                "本当にスクショが作れない事情がある時だけ"
                "--allow-no-screenshot \"理由\" を付けてください。",
                file=sys.stderr,
            )
            sys.exit(1)

    out_path = args.out or cfg.get("out") or os.path.join(
        CHECK_DIR, "%s-%s.html" % (cfg["n"], cfg["slug"])
    )
    if not os.path.isabs(out_path):
        out_path = os.path.join(REPO, out_path)

    html_out = render(cfg)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    rel = os.path.relpath(out_path, CHECK_DIR)
    print("書きました: %s" % out_path)
    if args.print_url or True:
        print("想定URL: %s%s" % (PAGES_BASE, rel))


if __name__ == "__main__":
    main()
