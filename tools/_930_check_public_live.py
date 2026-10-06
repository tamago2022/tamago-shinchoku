import urllib.request, json, time

u = 'https://tamago2022.github.io/tamago-shinchoku/status/public/done_archive.json'
req = urllib.request.Request(u + '?t=' + str(int(time.time())), headers={'Cache-Control': 'no-cache'})
with urllib.request.urlopen(req, timeout=15) as r:
    body = r.read()
d = json.loads(body)
for it in d.get('items', []):
    if it.get('n') in (726, 796, 802, 884):
        print(it.get('n'), it.get('status'))
print('etag/last-modified:', r.headers.get('ETag'), r.headers.get('Last-Modified'))
