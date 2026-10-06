#!/usr/bin/env python3
"""share/check/ 配下の確認ページ一覧を index.html として生成する。

背景（1463番）：確認ページのテンプレートには「共有資料の一覧」という
リンクがあるが、絶対URL版（https://.../share/check/）を直接使っている
確認ページが index.html の不在で 404 になっていた。510件の確認ページが
同じ壊れたリンクを持っており、次に踏むページを機械検品(2回目)で見つけて
やり直しになった。index.html を作ることで恒久的に解消する。

使い方: python3 tools/build_check_index.py
"""
import os
import re

CHECK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "share", "check")
OUT_PATH = os.path.join(CHECK_DIR, "index.html")


def sort_key(name):
    m = re.match(r"^(\d+)", name)
    n = int(m.group(1)) if m else -1
    return (n, name)


def main():
    files = [f for f in os.listdir(CHECK_DIR) if f.endswith(".html") and f != "index.html" and not f.startswith("_")]
    files.sort(key=sort_key, reverse=True)

    rows = []
    for f in files:
        rows.append('<li><a href="./%s">%s</a></li>' % (f, f))

    html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>共有資料の一覧（確認ページ）</title>
<style>
  body{margin:0;padding:20px 16px 60px;background:#f4efe4;color:#2a2a2a;
    font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;font-size:15px;line-height:1.6;max-width:760px;margin-left:auto;margin-right:auto;}
  h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.2rem;margin:0 0 16px;}
  .count{color:#7a7568;font-size:0.85rem;margin-bottom:18px;}
  ul{list-style:none;margin:0;padding:0;}
  li{background:#fff;border:1px solid #e2dccd;border-radius:8px;padding:9px 13px;margin:0 0 8px;font-size:0.9rem;word-break:break-all;}
  a{color:#3a5f7a;text-decoration:none;}
  a:hover{text-decoration:underline;}
</style>
</head>
<body>
<h1>共有資料の一覧（確認ページ）</h1>
<div class="count">全 %d 件（番号の新しい順）</div>
<ul>
%s
</ul>
</body>
</html>
""" % (len(files), "\n".join(rows))

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote %s (%d files)" % (OUT_PATH, len(files)))


if __name__ == "__main__":
    main()
