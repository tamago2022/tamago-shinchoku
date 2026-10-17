# -*- coding: utf-8 -*-
"""全マガジンの見た目を統一する（2026-10-16）。本番の写し（status/magazine_prod）と確認ページ（share/check）の両方。
使い方: python3 tools/magazine/unify_look.py          → 直す
        python3 tools/magazine/unify_look.py --check  → 検査だけ（ズレがあれば exit 2）
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mag_build as MB
PAGES = [('rei-harakami.html', 'tokushu-rei-harakami.html'), ('ikareru-01.html', 'tokushu-ikareru-01.html'),
         ('naze-ongaku-01-takoukan.html', 'naze-ongaku-01-takoukan.html'), ('hikigatari-josh-turner.html', 'hikigatari-josh-turner-b.html'),
         ('kimi-wa-hoshi-katsu.html', 'tokushu-hoshi-katsu.html'), ('backnumber.html', 'backnumber.html'),
         ('hito-wa-naze-tsuki-wo-miru-01.html', 'hito-wa-naze-tsuki-wo-miru-01.html')]
check = '--check' in sys.argv
ng = 0
for prod, chk in PAGES:
    for d, name in (('status/magazine_prod', prod), ('share/check', chk)):
        p = os.path.join(MB.REPO, d, name)
        if not os.path.exists(p):
            continue
        h = open(p, encoding='utf-8').read()
        if not check:
            h = MB.unify_look(h); open(p, 'w', encoding='utf-8').write(h)
        bad = MB.look_check(h)
        ng += bool(bad)
        print(('NG ' if bad else 'OK ') + d + '/' + name, len(h.encode()), '／'.join(bad))
print('LOOK_RESULT:', 'FAIL' if ng else 'PASS')
sys.exit(2 if ng else 0)
