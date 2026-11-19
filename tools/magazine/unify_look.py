# -*- coding: utf-8 -*-
"""全マガジンの見た目を統一する（2026-10-16）。本番の写し（status/magazine_prod）と確認ページ（share/check）の両方。

【2026-11-16・204014号・改善】たまごさんの赤入れ「見た目・型を全部そろえる（ちょっとずつ違うのはダメ）」
（status/tenaoshi/kimari.json の mitame-soroe・2026-10-14／2026-10-16の2回）を機械の関所に固定するための改善。
以前は検査対象（本番側）を PAGES という固定リストで手書きしていたため、新しいマガジンを
status/magazine_prod/ へ追加しても、このリストへの1行追記を忘れると検査対象から漏れて
「ちょっとずつ違う」が再発する穴があった（実例：2026-11-16時点で anohi-ni-kaeritai.html が
固定リストに入っておらず、一度も見た目の統一検査を受けていなかった＝実際に起きていた漏れ）。
今回、本番側（status/magazine_prod/*.html）は固定リストをやめ、ディレクトリを毎回スキャンする
方式に変えた（追記不要＝漏れが構造的に起きない）。確認ページ（share/check）側はファイル名が
不規則（tokushu-接頭辞など）で自動推測できないため、分かっている対応だけ CHK_NAME に残す。

使い方: python3 tools/magazine/unify_look.py            → 直す
        python3 tools/magazine/unify_look.py --check    → 検査だけ（ズレがあれば exit 2）
        python3 tools/magazine/unify_look.py --self-test → 逆テスト（正常はPASS・崩したものはFAILになるか。見た目は変えない・何も書き換えない）
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mag_build as MB

# 確認ページ（share/check）側は名前が不規則なので、分かっている対応だけここに残す。
# 無い物は share/check 側の検査を省く（本番側は下の _prod_pages() で自動検出するので漏れない）。
CHK_NAME = {
    'rei-harakami.html': 'tokushu-rei-harakami.html',
    'ikareru-01.html': 'tokushu-ikareru-01.html',
    'hikigatari-josh-turner.html': 'hikigatari-josh-turner-b.html',
    'kimi-wa-hoshi-katsu.html': 'tokushu-hoshi-katsu.html',
}


def _prod_pages():
    """検査・統一の対象になる本番マガジン一覧。固定リストではなく status/magazine_prod/*.html を毎回スキャンする。"""
    paths = sorted(glob.glob(os.path.join(MB.REPO, 'status', 'magazine_prod', '*.html')))
    return [os.path.basename(p) for p in paths]


def targets():
    return [(prod, CHK_NAME.get(prod, prod)) for prod in _prod_pages()]


def run_check(pages, fix=False):
    """pages=[(prod名, chk名), ...] を検査する。fix=True なら統一ルールに直して上書きする。戻り値はNG件数。"""
    ng = 0
    for prod, chk in pages:
        for d, name in (('status/magazine_prod', prod), ('share/check', chk)):
            p = os.path.join(MB.REPO, d, name)
            if not os.path.exists(p):
                continue
            h = open(p, encoding='utf-8').read()
            if fix:
                h = MB.unify_look(h)
                open(p, 'w', encoding='utf-8').write(h)
            bad = MB.look_check(h)
            ng += bool(bad)
            print(('NG ' if bad else 'OK ') + d + '/' + name, len(h.encode()), '／'.join(bad))
    return ng


def self_test():
    """逆テスト：①固定リストに無い新規ファイルも自動で検査対象へ入るか ②崩したHTMLはFAILになるか ③整った物はPASSになるか。ファイルは一切書き換えない。"""
    import tempfile

    bad = []
    pages = _prod_pages()
    if not pages:
        bad.append("status/magazine_prod に1件も無い（スキャン自体が動いていない）")

    # ① 固定リストを使わず自動検出できているか（旧PAGESの固定9件より多い＝新規ファイルも拾えている証拠）
    OLD_FIXED_COUNT = 9
    if len(pages) < OLD_FIXED_COUNT:
        bad.append("自動検出が旧の固定リスト件数(%d)より少ない：%d件" % (OLD_FIXED_COUNT, len(pages)))

    # ② 正常なマガジン（本番の実物）は look_check が合格すること
    ok_sample = None
    for prod in pages:
        p = os.path.join(MB.REPO, 'status', 'magazine_prod', prod)
        h = open(p, encoding='utf-8').read()
        if not MB.look_check(h):
            ok_sample = (prod, h)
            break
    if ok_sample is None:
        bad.append("正常なはずの本番マガジンが1件も look_check に合格しない")
    else:
        prod, h = ok_sample
        # ③ わざと崩して、崩した種類ごとに look_check がFAILを検出するか（逆テスト本体）
        breaks = {
            '白枠が戻る': h.replace('id="cw-base"', 'id="cw-base-x"'),
            'Magazine Storyが出る': h.replace('</body>', '<span>Magazine Story</span></body>', 1),
            '章頭の型が崩れる': h.replace('</body>', '<p class="cw-chead__title">テスト</p></body>', 1),
        }
        for name, broken_h in breaks.items():
            if not MB.look_check(broken_h):
                bad.append("逆テスト失敗：%s を仕込んでも look_check が検出できない（%s）" % (name, prod))

    # ④ 固定リストに無い“新規ファイル”を一時的に置いても、スキャンが自動で拾うか（差し替え無しの実物テスト）
    tmp_dir = os.path.join(MB.REPO, 'status', 'magazine_prod')
    tmp_name = '_self_test_dummy_204014.html'
    tmp_path = os.path.join(tmp_dir, tmp_name)
    try:
        # 崩れた最小HTML（白枠が戻る＝id="cw-base"が無い）をわざと置く
        open(tmp_path, 'w', encoding='utf-8').write('<html><head></head><body>dummy</body></html>')
        found = tmp_name in _prod_pages()
        if not found:
            bad.append("新規ファイルを置いても自動スキャンに出てこない（固定リスト方式に戻っている）")
        else:
            ng = run_check([(tmp_name, tmp_name)], fix=False)
            if ng == 0:
                bad.append("新規ファイルの崩れ（白枠無し）を検査しても NG にならない")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    print('SELF_TEST', 'PASS' if not bad else 'FAIL', bad)
    return 0 if not bad else 1


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    check = '--check' in sys.argv
    ng = run_check(targets(), fix=not check)
    print('LOOK_RESULT:', 'FAIL' if ng else 'PASS')
    sys.exit(2 if ng else 0)
