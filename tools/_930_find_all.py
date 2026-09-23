import json

targets = [719, 726, 731, 734, 771, 792, 796, 802, 876, 884]
found = {}
for path in ['/Users/mac/Desktop/tamago-shinchoku/status/queue.json',
             '/Users/mac/Desktop/tamago-shinchoku/status/done_archive.json']:
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    for it in d.get('items', []):
        n = it.get('n')
        if n in targets:
            found[n] = (path.split('/')[-1], it.get('status'), it.get('holdNote', '')[:0])

for n in targets:
    print(n, found.get(n, 'NOT FOUND'))
