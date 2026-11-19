# -*- coding: utf-8 -*-
"""月の特集 vol.1 の訳を、組み直すたびに訳キー（kN）へ当て直す（125816番・2026-10-19）。
訳の正本は日本語の文→訳の表 i18n_tsuki01_bytext.json（番号がずれても文で引く）。
手順：spec_tsuki01 を組む → 本番の写しの [data-i18n] から {kN: 日本語} を取る → 表で訳す → i18n_tsuki01.json に書く → もう一度組む。
訳の無い文が残ったら一覧を出して exit 2（訳の抜けを出さない）。
使い方: python3 tools/magazine/tsuki01_i18n.py
"""
import json, os, sys
from bs4 import BeautifulSoup
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
LANGS = ('en', 'zh-Hans', 'es', 'ko')
I18N = os.path.join(HERE, 'i18n_tsuki01.json')
BYTEXT = os.path.join(HERE, 'i18n_tsuki01_bytext.json')


def keys(path):
    main = BeautifulSoup(open(path, encoding='utf-8').read(), 'html.parser').find('main')
    return {el['data-i18n']: el.decode_contents().strip() for el in main.select('[data-i18n]') if el['data-i18n'].startswith('k')}


def table():
    t = {r[0]: dict(zip(LANGS, r[1:])) for r in json.load(open(BYTEXT, encoding='utf-8'))['rows']}
    # 前の版から引き継いだ文（見出し・曲名・出典名など）は、いまの i18n_tsuki01.json の訳を文で引けるよう _bytext_keep に控える
    keep = json.load(open(I18N, encoding='utf-8')).get('_bytext_keep', {})
    for ja, tr in keep.items():
        t.setdefault(ja, tr)
    return t


def main():
    import importlib
    spec = importlib.import_module('spec_tsuki01')
    p = spec.write(spec.M)
    ks = keys(os.path.join(spec.MB.REPO, 'status/magazine_prod', spec.MB.PROD['tsuki01']))
    t = table()
    cur = json.load(open(I18N, encoding='utf-8'))
    out = {'_title': cur['_title'], '_bytext_keep': cur.get('_bytext_keep', {})}
    for l in LANGS:
        out[l] = {}
    miss = []
    for k, ja in ks.items():
        tr = t.get(ja)
        if not tr or not all(tr.get(l) for l in LANGS):
            miss.append((k, ja)); continue
        for l in LANGS:
            out[l][k] = tr[l]
    used = set(ks.values())
    out['_bytext_keep'] = {ja: tr for ja, tr in out['_bytext_keep'].items() if ja in used}
    json.dump(out, open(I18N, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    importlib.reload(spec)
    spec.write(spec.M)
    print('訳を当てた', len(ks) - len(miss), '／', len(ks), p)
    for k, ja in miss:
        print('訳なし', k, ja[:60])
    return 2 if miss else 0


if __name__ == '__main__':
    sys.exit(main())
