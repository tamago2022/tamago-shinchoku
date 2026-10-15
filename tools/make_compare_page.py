#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「案の比較台」（share/compare/*.html）を、毎回ゼロから書かずに量産する道具。

背景（2026-09-11・747番・たまごさん指示）:
  Dispatchが作ったGIF・動画・画像の案（A案／B案…）を、たまごさんが
  スマホでその場に並べて同時に再生し「これにする」を押して選べるページ。
  「outputsフォルダにあります」はスマホに届かない＝負け。作った案は
  必ずこのページを1本作ってURLで渡す。

  確認ページ（share/check/、tools/make_check_page.py）とは目的が違う：
  - 確認ページ＝「直った／直っていない」を見せて終わり（一方通行）
  - 比較台　　＝「どれがいいか」をたまごさんに選んでもらい、選んだ結果を
    既存の中継所（obsidian://new不要・relay.json→command_ingest.pyの
    queue_add）でDispatchの発車待ち列へ直接積む（双方向）。

使い方（GIFを2〜4案並べる例）:
  python3 tools/make_compare_page.py \
    --n 747 --slug oniyome-loop \
    --title "鬼嫁ちゃんループGIF 見比べ" \
    --what "ストップモーション風(A)と小刻み揺れ(B)、どちらのループがいいか見比べてください。" \
    --item "A案：ストップモーション（6コマ）|img/747-oniyome/A.gif|img/747-oniyome/A|6" \
    --item "B案：小刻み揺れ（8コマ）|img/747-oniyome/B.gif|img/747-oniyome/B|8" \
    --print-url

--item の書式（|区切り、4〜5項目）:
  表示名|GIFの相対パス|コマ送り用フレームのディレクトリ(相対・拡張子なし)|フレーム枚数[|拡張子(既定.jpg)]
  フレームディレクトリが無い（コマ送り不要）場合は空文字でよい："表示名|img/x.gif||"

画像・GIFは事前に share/compare/img/ 配下へ自分でコピーしておくこと
（このスクリプトは画像そのものは作らない。パスを渡すだけ）。
1MB超のファイルを置くとkenpou_check.py⑦が赤くなるので、GIFは事前に
減色・縮小して1MB未満に収めること（Pillowの quantize(colors=100, dither=Image.Dither.NONE)
が実測でノイズが出にくく効いた＝747番の実績値）。

出力先: share/compare/{n}-{slug}.html （--out で上書き可）
「これにする」ボタンは押すと status/relay.json の中継所へ
{"action":"queue_add","target":"...","label":"..."} を送る。中継所が
不通の時は localStorage(shinchoku_pending_cmds) に貯めて、進捗表(index.html)
を開いた時にまとめて送られる（進捗表と全く同じキーを共有しているため）。
"""
import argparse
import datetime
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
COMPARE_DIR = os.path.join(REPO, "share", "compare")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/share/compare/"

MAX_ASSET_BYTES = 1_000_000  # kenpou_check.py BIG_FILE_LIMIT と同じ基準（1MB超ガード）


def esc(s):
    return html.escape(str(s), quote=True)


def parse_item(raw, idx):
    parts = raw.split("|")
    while len(parts) < 5:
        parts.append("")
    name, gif, frame_dir, frame_count, ext = parts[:5]
    if not name.strip():
        raise SystemExit("--item の1つ目（表示名）が空です: %r" % raw)
    if not gif.strip():
        raise SystemExit("--item の2つ目（GIF相対パス）が空です: %r" % raw)
    ext = ext.strip() or ".jpg"
    try:
        frame_count = int(frame_count) if frame_count.strip() else 0
    except ValueError:
        raise SystemExit("--item の4つ目（フレーム枚数）は数字にしてください: %r" % raw)
    key = chr(ord("A") + idx) if idx < 26 else "item%d" % idx
    return {
        "key": key,
        "name": name.strip(),
        "gif": gif.strip(),
        "frame_dir": frame_dir.strip(),
        "frame_count": frame_count,
        "ext": ext,
    }


def check_asset_sizes(items, n, slug):
    """置いた画像が1MB超ガードに引っかからないか、生成前にここで検知する。
    （リポジトリに入れてからkenpou_checkの次回巡回で気づくより、その場で分かった方が早い）"""
    warnings = []
    base = os.path.join(COMPARE_DIR)
    for it in items:
        gif_path = os.path.join(base, it["gif"])
        if os.path.exists(gif_path):
            size = os.path.getsize(gif_path)
            if size > MAX_ASSET_BYTES:
                warnings.append(
                    "%s: %s が%.2fMBあり1MB超ガードに引っかかります。"
                    "Pillowで quantize(colors=100くらい, dither=Dither.NONE) して縮小してください。"
                    % (it["key"], it["gif"], size / 1e6)
                )
        else:
            warnings.append("%s: %s が見つかりません（share/compare/配下に置いたか確認）" % (it["key"], it["gif"]))
    return warnings


def build_card_html(it):
    gif_html = '<img class="loopgif" src="%s" alt="%s" loading="lazy">' % (esc(it["gif"]), esc(it["name"]))
    frame_html = ""
    if it["frame_dir"] and it["frame_count"] > 1:
        frame0 = "%s/f0%s" % (it["frame_dir"], it["ext"])
        frame_html = """
    <div class="frameviewer" data-prefix="%s" data-count="%d" data-ext="%s">
      <img class="frameimg" src="%s" alt="%sのコマ送り">
      <input type="range" class="frameslider" min="0" max="%d" value="0" step="1">
      <div class="framectrl">
        <button type="button" class="fbtn fprev">◀ 1コマ</button>
        <button type="button" class="fbtn fplay">▶ 自動</button>
        <button type="button" class="fbtn fnext">1コマ ▶</button>
        <span class="fcount">1 / %d</span>
      </div>
    </div>""" % (
            esc(it["frame_dir"]), it["frame_count"], esc(it["ext"]),
            esc(frame0), esc(it["name"]), it["frame_count"] - 1, it["frame_count"],
        )
    return """
  <div class="card" data-key="%s">
    <h2>%s</h2>
    <div class="loopwrap">%s</div>
    %s
    <button type="button" class="pickbtn" data-key="%s" data-name="%s">これにする（%s）</button>
    <div class="pickstatus" data-slot="%s"></div>
  </div>""" % (
        esc(it["key"]), esc(it["name"]), gif_html, frame_html,
        esc(it["key"]), esc(it["name"]), esc(it["key"]), esc(it["key"]),
    )


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{TITLE} 比較（{N}番）</title>
<style>
  :root{{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--aka:#c4483a;--ao:#3a5f7a;--midori:#3a7a52;}}
  *{{box-sizing:border-box;}}
  body{{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 16px calc(env(safe-area-inset-bottom) + 40px);
    background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;
    font-size:16px;line-height:1.7;max-width:900px;margin-left:auto;margin-right:auto;}}
  a{{color:var(--ao);}}
  h1{{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.3rem;letter-spacing:0.06em;margin:0 0 6px;}}
  .date{{color:var(--sub);font-size:0.8rem;margin-bottom:16px;}}
  .what{{border-left:3px solid var(--midori);padding:4px 0 4px 14px;margin:0 0 22px;font-size:1.02rem;}}
  .row{{display:flex;flex-wrap:wrap;gap:16px;}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;flex:1 1 260px;min-width:220px;max-width:420px;}}
  .card h2{{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.02rem;margin:0 0 10px;color:var(--ink);}}
  .loopwrap{{background:#efe9db;border-radius:10px;overflow:hidden;margin:0 0 10px;}}
  .loopgif{{display:block;width:100%;height:auto;}}
  .frameviewer{{margin:0 0 14px;}}
  .frameimg{{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--line);margin:0 0 8px;background:#efe9db;}}
  .frameslider{{width:100%;margin:0 0 8px;}}
  .framectrl{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}}
  .fbtn{{background:#efe9db;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:0.82rem;color:var(--ink);}}
  .fbtn:active{{background:var(--line);}}
  .fcount{{margin-left:auto;color:var(--sub);font-size:0.78rem;}}
  .pickbtn{{display:block;width:100%;background:var(--midori);color:#fff;border:none;border-radius:10px;padding:14px 10px;
    font-size:1.02rem;font-weight:700;letter-spacing:0.04em;}}
  .pickbtn:active{{opacity:0.85;}}
  .pickbtn.picked{{background:var(--sub);}}
  .pickstatus{{min-height:1.4em;margin-top:8px;font-size:0.8rem;color:var(--sub);text-align:center;}}
  .pickstatus.ok{{color:var(--midori);font-weight:700;}}
  footer{{color:var(--sub);font-size:0.78rem;margin-top:34px;line-height:1.6;}}
</style>
</head>
<body>
<!-- SHINCHOKU_BACK_LINK -->
<div id="shinchokuBackTop" style="position:sticky;top:0;left:0;right:0;z-index:9999;background:#1c1c1c;border-bottom:1px solid #3a3a3a;padding:8px 14px;text-align:left;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="https://tamago2022.github.io/tamago-shinchoku/" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.9rem;">← 進捗表に戻る</a>
</div>

<div class="date"><a href="./">案の比較台 一覧</a> ／ {N}番</div>
<h1>{TITLE}</h1>
<div class="date">{DATE_LINE}</div>
<div class="what">{WHAT_HTML}</div>

<div class="row">{CARDS_HTML}
</div>

<footer>
このページは案を見比べて選ぶための内部資料です。GIFは自動でループ再生されます（音は出ません）。
「これにする」を押すと、Dispatchの発車待ちの列に「{N}番 ◯案を採用」という指示として届きます
（既存の中継所を使うため、たまごさんが今使っている画面が切り替わることはありません）。
</footer>
<div id="shinchokuBackBottom" style="margin:30px 0 10px;padding:14px;text-align:center;background:#1c1c1c;border-radius:10px;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="https://tamago2022.github.io/tamago-shinchoku/" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.95rem;">← 進捗表に戻る</a>
</div>
<!-- /SHINCHOKU_BACK_LINK -->

<script>
/* ── コマ送りビューア（GIFとは別に、フレームを1枚ずつ見られるように） ── */
document.querySelectorAll(".frameviewer").forEach(function(fv){{
  var prefix = fv.dataset.prefix, count = +fv.dataset.count, ext = fv.dataset.ext;
  var img = fv.querySelector(".frameimg"), slider = fv.querySelector(".frameslider");
  var cnt = fv.querySelector(".fcount"), playBtn = fv.querySelector(".fplay");
  var timer = null, i = 0;
  function show(n){{ i = ((n % count) + count) % count; img.src = prefix + "/f" + i + ext; slider.value = i; cnt.textContent = (i+1) + " / " + count; }}
  slider.addEventListener("input", function(){{ stopPlay(); show(+slider.value); }});
  fv.querySelector(".fprev").addEventListener("click", function(){{ stopPlay(); show(i-1); }});
  fv.querySelector(".fnext").addEventListener("click", function(){{ stopPlay(); show(i+1); }});
  function stopPlay(){{ if(timer){{ clearInterval(timer); timer = null; playBtn.textContent = "▶ 自動"; }} }}
  playBtn.addEventListener("click", function(){{
    if(timer){{ stopPlay(); return; }}
    playBtn.textContent = "⏸ 停止";
    timer = setInterval(function(){{ show(i+1); }}, 220);
  }});
  show(0);
}});

/* ── 「これにする」→ 既存の中継所（obsidian://new不要・relay.json直POST）へ queue_add ──
   進捗表(index.html)のsendCommandWithId/flushCommandsと全く同じ考え方・同じlocalStorageキーを
   共有しているので、ここで送れなくても進捗表を次に開いた時にまとめて送られる。 */
var RELAY_HEADERS = {{"bypass-tunnel-reminder":"1"}};
var PENDING_KEY = "shinchoku_pending_cmds";
var PENDING = [];
try {{ PENDING = JSON.parse(localStorage.getItem(PENDING_KEY) || "[]") || []; }} catch(e) {{ PENDING = []; }}
function savePending(){{ try {{ localStorage.setItem(PENDING_KEY, JSON.stringify(PENDING.slice(-50))); }} catch(e) {{}} }}
var RELAY = null;
function refreshRelay(){{
  return fetch("../../status/relay.json?t=" + Date.now(), {{cache:"no-store"}})
    .then(function(r){{ return r.ok ? r.json() : null; }})
    .then(function(j){{ RELAY = j; flush(); }})
    .catch(function(){{}});
}}
function flush(){{
  if(!RELAY || !RELAY.url || !PENDING.length) return Promise.resolve();
  var batch = PENDING.slice();
  return fetch(RELAY.url.replace(/\\/$/, "") + "/cmd", {{
    method: "POST", mode: "cors",
    headers: Object.assign({{"Content-Type": "application/json"}}, RELAY_HEADERS),
    body: JSON.stringify({{commands: batch}}),
  }}).then(function(r){{
    if(!r.ok) throw new Error("HTTP " + r.status);
    PENDING = PENDING.filter(function(c){{ return !batch.some(function(b){{ return b.id === c.id; }}); }});
    savePending();
  }}).catch(function(){{}});
}}
refreshRelay();
setInterval(refreshRelay, 30000);

document.addEventListener("click", function(e){{
  var b = e.target.closest(".pickbtn"); if(!b) return;
  var key = b.dataset.key, name = b.dataset.name;
  var id = "cmp" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  var text = "{N}番の案の比較（{TITLE}）：" + name + " を採用に決定しました。";
  var label = "＋{N}番 " + name + " 採用";
  PENDING.push({{id: id, action: "queue_add", target: text, label: label, requestedAt: new Date().toISOString()}});
  savePending();
  flush();
  b.classList.add("picked");
  b.textContent = "選びました（" + name + "）";
  document.querySelectorAll(".pickbtn").forEach(function(x){{ if(x !== b) x.disabled = true; }});
  var slot = document.querySelector('.pickstatus[data-slot="' + key + '"]');
  if(slot){{ slot.textContent = "発車待ちの列に送りました（届くまで30〜60秒）"; slot.classList.add("ok"); }}
}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="案の比較台(share/compare/*.html)を型から生成する")
    ap.add_argument("--n", required=True, help="番号")
    ap.add_argument("--slug", required=True, help="ファイル名に使う短い英語スラッグ")
    ap.add_argument("--title", required=True, help="見出し")
    ap.add_argument("--date", dest="date_line", default=None, help="日付行（省略時は今日の日付）")
    ap.add_argument("--what", required=True, help="① 何を比べてほしいか")
    ap.add_argument("--item", action="append", default=[], help="表示名|GIF相対パス|フレームdir(拡張子なし)|フレーム枚数[|拡張子]")
    ap.add_argument("--out", default=None, help="出力ファイルパス（省略時は share/compare/{n}-{slug}.html）")
    ap.add_argument("--print-url", action="store_true", help="生成後、GitHub Pages上の想定URLを標準出力へ1行出す")
    ap.add_argument("--skip-size-check", action="store_true", help="1MB超ガードの事前チェックを飛ばす（非推奨）")
    args = ap.parse_args()

    if not args.item:
        raise SystemExit("--item を最低1つ（比較したいなら2つ以上）指定してください")

    items = [parse_item(raw, i) for i, raw in enumerate(args.item)]

    if not args.skip_size_check:
        warnings = check_asset_sizes(items, args.n, args.slug)
        if warnings:
            sys.stderr.write("警告：\n" + "\n".join("  - " + w for w in warnings) + "\n")

    date_line = args.date_line or ("作成: %s" % datetime.date.today().isoformat())
    cards_html = "".join(build_card_html(it) for it in items)

    html_out = PAGE_TEMPLATE.format(
        TITLE=esc(args.title),
        N=esc(args.n),
        DATE_LINE=esc(date_line),
        WHAT_HTML=args.what,  # 意図的にエスケープしない（<code>等の軽いHTMLを許す。make_check_page.pyと同じ方針）
        CARDS_HTML=cards_html,
    )

    out_path = args.out or os.path.join(COMPARE_DIR, "%s-%s.html" % (args.n, args.slug))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    rel = os.path.relpath(out_path, COMPARE_DIR)
    print("書き出した: %s" % out_path)
    if args.print_url:
        print(PAGES_BASE + rel.replace(os.sep, "/"))


if __name__ == "__main__":
    main()
