import json

with open('/Users/mac/Desktop/tamago-shinchoku/status/done_archive.json', encoding='utf-8') as f:
    d = json.load(f)
print('OK, items:', len(d.get('items', [])))
for it in d['items']:
    if it.get('n') in (726, 796, 802, 884):
        print(it.get('n'), it.get('status'))
