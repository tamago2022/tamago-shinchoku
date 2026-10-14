#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""マガジンは「曲を使った短い物語」にする、の関所（2026-10-14・たまごさん指示）。

たまごさんの言葉（要約）：
  マガジンは曲を使った短い物語にしたい。冒頭のつかみと起承転結を意識する。
  並べ方で意味が変わるので「最後にこれをどうぞ」のような締めも歓迎。
  ただの羅列や紹介で終わらせない。

見るもの（<meta name="tamago-magazine" content="story"> が付いたページだけ）：
  ① つかみ：本文の最初の章より前に、導入（cw-open / lead）がある
  ② つなぎ：最後の章以外の各章に <p class="bridge">（次の曲へつなぐ一言）がある
  ③ 締め：「最後に」「次回」「お楽しみに」のどれかで終わる締めがある

使い方：
  python3 tools/magazine_monogatari_kanmon.py share/check/xxx.html [...]
  python3 tools/magazine_monogatari_kanmon.py --all        # share/check の対象ページ全部
  python3 tools/magazine_monogatari_kanmon.py --self-test
最後の行は MONOGATARI_RESULT: PASS|FAIL - ...（終了コード 0/1）
"""
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = re.compile(r'<meta name="tamago-magazine" content="story">')
CH = re.compile(r'<section[^>]*\bid="ch(\d\d)"[^>]*>(.*?)</section>', re.S)


def check(html):
    errs = []
    chs = CH.findall(html)
    if not chs:
        return ["章（id=chNN の section）が1つも無い"]
    first = html.find('id="ch%s"' % chs[0][0])
    head = html[:first]
    if not re.search(r'class="(cw-open|lead)', head):
        errs.append("つかみ（最初の章より前の導入）が無い")
    for no, body in chs[:-1]:
        if 'class="bridge"' not in body:
            errs.append("ch%s に次の曲へつなぐ一言（p.bridge）が無い" % no)
    tail = html[html.find('id="ch%s"' % chs[-1][0]):]
    if not re.search(r"最後に|次回|お楽しみに", tail):
        errs.append("締め（最後に／次回／お楽しみに）が無い")
    return errs


def run(paths):
    bad = 0
    n = 0
    for p in paths:
        html = open(p, encoding="utf-8").read()
        if not MARK.search(html):
            continue
        n += 1
        errs = check(html)
        if errs:
            bad += 1
            print("FAIL %s：%s" % (os.path.relpath(p, REPO), " ／ ".join(errs)))
        else:
            print("PASS %s" % os.path.relpath(p, REPO))
    if bad:
        print("MONOGATARI_RESULT: FAIL - %d/%d ページが物語の型を満たしていない" % (bad, n))
        return 1
    print("MONOGATARI_RESULT: PASS - %d ページ" % n)
    return 0


def self_test():
    ok_html = ('<meta name="tamago-magazine" content="story"><section class="cw-open">つかみ</section>'
               '<section id="ch01">a<p class="bridge">次へ</p></section>'
               '<section id="ch02">b 最後に、これをどうぞ</section>')
    ng_html = ('<meta name="tamago-magazine" content="story">'
               '<section id="ch01">a</section><section id="ch02">b</section>')
    a = check(ok_html)
    b = check(ng_html)
    good = (a == [] and len(b) == 3)
    print("SELFTEST", "PASS" if good else "FAIL", a, b)
    return 0 if good else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self-test" in args:
        sys.exit(self_test())
    if "--all" in args or not args:
        args = sorted(glob.glob(os.path.join(REPO, "share", "check", "*.html")))
    sys.exit(run(args))
