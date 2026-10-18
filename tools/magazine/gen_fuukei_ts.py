# fuukei.json → joy-relief-station src/lib/fuukeiPhotos.ts（React の特集用。手で書き換えない）
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'fuukei.json'), encoding='utf-8'))
r = {k: v for k, v in d.items() if k.startswith('feature/')}
# 2026-10-19：画像ファイルが無い写真は表に入れない（シティポップで写真のファイルだけ消え、枠と代替テキストが本番に残った事故）
_jrs = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[1]))))
if os.path.isdir(os.path.join(_jrs, 'public')):
    for k in r:
        miss = [x['src'] for x in r[k] if not os.path.exists(os.path.join(_jrs, 'public', x['src'].lstrip('/')))]
        if miss:
            print('画像ファイルが無いので外した', k, miss)
        r[k] = [x for x in r[k] if x['src'] not in miss]
out = ('/**\n * 雰囲気の静止画（特集用・2026-10-18）。tamago-shinchoku tools/magazine/fuukei.json から gen_fuukei_ts.py で生成。手で書き換えない。\n'
       ' * 写真は自由ライセンス（Wikimedia Commons）。credit があるものは小さくクレジットを出す。AIの絵は credit なし。\n */\n'
       'export type FuukeiPhoto = { after: string; src: string; w: number; h: number; alt: string; credit?: string; page?: string; lic?: string };\n'
       'export const FUUKEI: Record<string, FuukeiPhoto[]> = ' + json.dumps(r, ensure_ascii=False, indent=2) + ';\n')
open(sys.argv[1], 'w', encoding='utf-8').write(out); print('ok', {k: len(v) for k, v in r.items()})
