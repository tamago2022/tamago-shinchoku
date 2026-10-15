#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1184号【オリジナルでやってしまっている箇所の洗い出し】2026-09-29

たまごさん：「多分、他にもたくさんあると思う。」
→ 憶測で数えない。機械で洗って件数を出す。**直すのは後日。一覧を作るところまで。**

■ 何を「オリジナル」と見なすか（判定は機械。人の感想を入れない）
  実行物（.py/.mjs/.js/.ts/.sh）の**冒頭60行**に、
  「先人に当たった形跡」＝ 公式 / docs.claude.com / code.claude.com / MCP /
  出典 / 参考 / 仕様 / http(s):// のどれも1つも出てこないもの。
  ＝「何を見て作ったか」がファイル自身に書かれていない＝自分で考えた疑い。

  ★これは「黒」ではなく「候補」。証拠はファイル冒頭という1か所だけ見ている。
    確定させるには1件ずつ①〜④を当て直す（tools/1184_kanmon.py shirabe）。

■ 別枠で必ず先頭に出すもの（既に判明している黒）
  26,000件をJSに直書き（V8公式が「10kB超はJSONで持て」と明言）。
  → .js で 300KB を超えるものを機械で拾って先頭に出す。

出すもの：
  status/1184_original_ichiran.md       （全文）
  share/1184-original-ichiran.html      （スマホ・URLで見る用）
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

EXT = (".py", ".mjs", ".cjs", ".js", ".ts", ".sh")
SKIP_DIR = {".git", "node_modules", "status", "share", "dist", "build", "venv", ".venv"}
SENJIN = ["公式", "docs.claude.com", "code.claude.com", "developer.", "MCP",
          "出典", "参考", "仕様", "http://", "https://", "RFC", "標準"]
BIG_JS = 300 * 1024

OUT_MD = os.path.join(REPO, "status", "1184_original_ichiran.md")
OUT_HTML = os.path.join(REPO, "share", "1184-original-ichiran.html")
URL = "https://tamago2022.github.io/tamago-shinchoku/share/1184-original-ichiran.html"


def head(p, n=60):
    try:
        with io.open(p, encoding="utf-8", errors="replace") as f:
            return "".join([f.readline() for _ in range(n)])
    except Exception:
        return ""


def walk():
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR and not d.startswith(".")]
        for n in files:
            if n.endswith(EXT):
                yield os.path.join(root, n)


def main():
    kouho, big = [], []
    zen = 0
    for p in walk():
        rel = os.path.relpath(p, REPO)
        try:
            size = os.path.getsize(p)
        except Exception:
            continue
        if p.endswith(".js") and size >= BIG_JS:
            big.append((rel, size))
        zen += 1
        h = head(p)
        if not any(s in h for s in SENJIN):
            kouho.append((rel, size))

    kouho.sort(key=lambda t: -t[1])
    big.sort(key=lambda t: -t[1])

    L = []
    A = L.append
    A("# 1184号：オリジナルでやってしまっている候補（機械で洗った一覧）")
    A("")
    A("**直すのは後日。ここは数えるところまで。**")
    A("")
    A("判定：実行物の冒頭60行に『何を見て作ったか』（公式／MCP／出典／参考／URL）が"
      "1つも書かれていないもの。黒ではなく候補。")
    A("")
    A("| | 件数 |")
    A("|---|---|")
    A("| 調べた実行物 | %d |" % zen)
    A("| ★オリジナル疑いの候補 | **%d** |" % len(kouho))
    A("| うち、大きすぎるJS（直書きデータ疑い） | %d |" % len(big))
    A("")
    A("## 1. 筆頭：データをJSに直書きしている（既に判明している黒）")
    A("")
    A("V8公式が「10kBを超えるデータはJSONで持て」と明言している。"
      "26,000件をJSに直書きしたのはこれに真っ向から反している。")
    A("")
    if big:
        for rel, size in big:
            A("- `%s` … %.0f KB" % (rel, size / 1024.0))
    else:
        A("- （300KBを超える .js は見つからなかった）")
    A("")
    A("## 2. オリジナル疑いの候補（大きい順）")
    A("")
    for rel, size in kouho:
        A("- `%s` … %.0f KB" % (rel, size / 1024.0))
    A("")
    A("## 直し方（1件ずつ）")
    A("")
    A("`python3 tools/1184_kanmon.py shirabe --nani \"<そのファイルがやっていること>\" "
      "--koushiki … --mcp … --sample … --jitsurei … --gaibu … --ketsuron sonomama`")
    A("")
    A("① で公式にやり方があれば、そのまま差し替える。**「似せる」は不合格、「そのまま」が合格。**")

    md = "\n".join(L) + "\n"
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    body = md
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.M)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.M)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"`(.+?)`", r"<code>\1</code>", body)
    body = re.sub(r"^- (.+)$", r"<li>\1</li>", body, flags=re.M)
    html = (
        "<!doctype html><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>1184号：オリジナル候補の一覧</title>"
        "<style>body{font-family:-apple-system,sans-serif;max-width:56em;margin:2em auto;"
        "padding:0 1em;line-height:1.7}code{background:#f3f3f3;padding:.1em .3em;"
        "border-radius:3px;font-size:.9em}li{list-style:none;margin:.2em 0}"
        "table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.3em .8em}"
        "</style><body>" + body + "</body>"
    )
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("調べた実行物: %d" % zen)
    print("オリジナル疑いの候補: %d" % len(kouho))
    print("大きすぎるJS: %d" % len(big))
    print(URL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
