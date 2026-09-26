import urllib.request, re

urls = [
    'https://tamago2022.github.io/tamago-shinchoku/share/check/726-queue-light.html',
    'https://tamago2022.github.io/tamago-shinchoku/share/check/796-shinchoku-loading-loop-fix.html',
    'https://tamago2022.github.io/tamago-shinchoku/share/check/802-dekimono-read-less.html',
]
for u in urls:
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode('utf-8', 'ignore')
    imgs = re.findall(r'<img[^>]+>', html)
    print(u)
    print('  len', len(html), 'img count', len(imgs))
