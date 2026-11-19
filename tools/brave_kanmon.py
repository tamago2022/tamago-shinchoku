#!/usr/bin/env python3
"""Brave関所（2026-10-08）：決まり「Braveに触らない」を機械で守る。
工場の自動処理が Brave を画面なし・遠隔操作・別プロファイルで起動したら、そのプロセスだけを止めて記録する。
たまごさんの普通のBrave（引数なし）には触らない。30秒おきにlaunchdが実行。"""
import subprocess, os, time, signal
LOG = '/Users/mac/tamago/tamago-shinchoku/status/brave_kanmon.log'
BAD = ('--head' + 'less', '--remote-' + 'debugging', '--user-data-' + 'dir')
out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
for line in out.splitlines():
    pid, _, cmd = line.strip().partition(' ')
    if 'Brave Browser.app/Contents/MacOS/Brave Browser' in cmd and any(b in cmd for b in BAD):
        try:
            os.kill(int(pid), signal.SIGTERM)
            res = 'stopped'
        except Exception as e:
            res = 'fail %s' % e
        open(LOG, 'a', encoding='utf-8').write('%s %s pid=%s %s\n' % (time.strftime('%F %T'), res, pid, cmd[:200]))
