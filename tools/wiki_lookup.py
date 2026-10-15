#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出典確認の道具（工場＝Mac側で走らせる）。子セッションは web_fetch を使わず、これを mac_jobs 経由で走らせる。
（web_fetch はたまごさんの画面に許可ポップアップを出すため禁止・2026-10-16）

使い方（status/mac_jobs/pending/<名前>.sh に書く）:
  python3 tools/wiki_lookup.py ja "星勝" "セカンド・ラブ (曲)" --grep 編曲 星勝 > status/hk2/wiki_out.txt
  python3 tools/wiki_lookup.py en "Only Yesterday (1991 film)" --grep Hoshi
  python3 tools/wiki_lookup.py ja --search "スローバラード RCサクセション"
  python3 tools/wiki_lookup.py url "https://example.com/page" --grep 語        # ふつうのページ（本文の文字だけ）
出力：題・URL・本文の長さ、--grep の語の前後120字（各語4か所まで）。--full で本文を全部。
"""
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {'User-Agent': 'gokigen-magazine/1.0 (eggypop2010@gmail.com)'}


def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read()


def wiki(lang, title):
    d = json.loads(get(f'https://{lang}.wikipedia.org/w/api.php?' + urllib.parse.urlencode(
        {'action': 'query', 'format': 'json', 'prop': 'extracts|info', 'inprop': 'url', 'explaintext': 1, 'redirects': 1, 'titles': title})))
    for p in d['query']['pages'].values():
        return p.get('title'), p.get('fullurl'), p.get('extract', '')


def search(lang, q):
    d = json.loads(get(f'https://{lang}.wikipedia.org/w/api.php?' + urllib.parse.urlencode(
        {'action': 'query', 'format': 'json', 'list': 'search', 'srsearch': q, 'srlimit': 8})))
    return [r['title'] for r in d['query']['search']]


def page_text(url):
    s = get(url).decode('utf-8', 'ignore')
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))


def show(title, url, x, words, full):
    print('=====', title, url, len(x))
    if full:
        print(x); return
    for w in words:
        i, c = 0, 0
        while c < 4:
            i = x.find(w, i)
            if i < 0:
                break
            print(f'  [{w}]', x[max(0, i - 120):i + 120].replace('\n', ' ')); i += len(w); c += 1


def main(a):
    full = '--full' in a
    a = [x for x in a if x != '--full']
    words = []
    if '--grep' in a:
        i = a.index('--grep'); words = a[i + 1:]; a = a[:i]
    kind = a[0]
    if kind == 'url':
        for u in a[1:]:
            show(u, u, page_text(u), words, full)
        return
    if len(a) > 1 and a[1] == '--search':
        print(search(kind, ' '.join(a[2:]))); return
    for t in a[1:]:
        show(*wiki(kind, t), words, full)


if __name__ == '__main__':
    main(sys.argv[1:])
