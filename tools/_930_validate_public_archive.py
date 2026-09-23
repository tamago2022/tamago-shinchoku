import json

with open('/Users/mac/Desktop/tamago-shinchoku/status/public/done_archive.json', encoding='utf-8') as f:
    d = json.load(f)
for it in d.get('items', []):
    if it.get('n') in (726, 796, 802, 884):
        print(it.get('n'), it.get('status'))
