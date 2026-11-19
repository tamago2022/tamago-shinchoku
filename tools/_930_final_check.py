import urllib.request

u = 'https://tamago2022.github.io/tamago-shinchoku/share/check/930-batch4-triage-recheck.html'
req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode('utf-8', 'ignore')
    print('status', r.status, 'len', len(html))
    print('done確定(726,802)' in html, 'health.json計測停止' in html)
except Exception as e:
    print('ERR', e)
