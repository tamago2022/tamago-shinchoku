# -*- coding: utf-8 -*-
"""マガジンの「送る量」の基準を、たまごさん指示で中身を足した版に置き直す（理由を必ず残す）。
なぜ要るか：2026-10-16〜17、共有ボタン・SNS欄・写真・5言語などを足したが、koutai_kijun.json の files が何度も古い値（10/16 01:42）に戻され、
put_prod.sh の関所で毎回止まった。共通CSS 236KB を読むのをやめたので、ページ全体の送る量はむしろ減っている。
使い方: python3 tools/magazine/kijun_okinaoshi.py "理由" ファイル名...
"""
import json, os, sys, time
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = os.path.join(REPO, 'status/public/koutai_kijun.json')
riyuu, files = sys.argv[1], sys.argv[2:]
d = json.load(open(P, encoding='utf-8'))
for f in files:
    d.setdefault('files', {})[f] = {'bytes': os.path.getsize(os.path.join(REPO, 'status/magazine_prod', f)), 'setAt': time.strftime('%F %T'), 'riyuu': riyuu}
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('置き直し', files)
