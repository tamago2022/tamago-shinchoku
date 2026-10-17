# -*- coding: utf-8 -*-
"""たまごさんのAI絵をマガジンに差し込む（2026-10-18）。
受け取り口：Google Drive「マイドライブ/AI制作物/Claude/マガジン/<フォルダ名>/」。ファイル名の頭で置き場所を決める：
  ch03.jpg ／ ch03_なんでも.png → 3章のすぐ後ろ（同じ章に何枚でも可）。名前の頭が chNN でないものは読まない。
手順：① Mac で `bash tools/magazine/ai_e_copy.sh`（Drive → status/fuukei/ai_in/ に写すだけ）
      ② `python3 tools/magazine/ai_e_torikomi.py`（幅960のwebpにして status/fuukei/out/ に置き、fuukei.json に足す）
      ③ いつも通り組み直して本番へ（静的は unify_look、React の特集は src/lib/fuukeiPhotos.ts を作り直す）
AIの絵はクレジットもキャプションも付けない（alt は「イラスト」）。有料の画像生成は使わない。
"""
import json, os, re, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
FOLDERS = {  # Driveのフォルダ名 → fuukei.json のページ名
    '怒れる人々': 'ikareru-01.html', '君は星勝を知っているか': 'kimi-wa-hoshi-katsu.html', '君はレイ・ハラカミを知っているか': 'rei-harakami.html',
    '多幸感ポップス': 'naze-ongaku-01-takoukan.html', '弾き語り・ジョシュ・ターナー編': 'hikigatari-josh-turner.html',
    '世界が先に見つけた日本の夜（シティポップ）': 'feature/citypop-sekai', '心を震わせる弾き語り': 'feature/hikigatari'}
IN = os.path.join(REPO, 'status/fuukei/ai_in'); OUT = os.path.join(REPO, 'status/fuukei/out')
data = json.load(open(os.path.join(HERE, 'fuukei.json'), encoding='utf-8'))
n = 0
for folder, page in FOLDERS.items():
    d = os.path.join(IN, folder)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        m = re.match(r'(ch\d\d)', f, re.I)
        if not m or not f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
        key = page.split('/')[-1].replace('.html', '')
        stem = re.sub(r'[^A-Za-z0-9]+', '-', os.path.splitext(f)[0]).strip('-').lower() or m.group(1).lower()
        fn = f'{key}-ai-{stem}.webp'
        im = Image.open(os.path.join(d, f)).convert('RGB'); im.thumbnail((960, 2000))
        os.makedirs(OUT, exist_ok=True); im.save(os.path.join(OUT, fn), 'WEBP', quality=66, method=6)
        src = ('assets/fuukei/' if page.endswith('.html') else '/magazine/assets/fuukei/') + fn
        lst = data.setdefault(page, [])
        lst[:] = [x for x in lst if x['src'] != src]
        lst.append(dict(after=m.group(1).lower(), src=src, w=im.width, h=im.height, alt='イラスト'))
        n += 1
json.dump(data, open(os.path.join(HERE, 'fuukei.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('取り込み', n, '枚')
