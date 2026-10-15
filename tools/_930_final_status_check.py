import json

with open('/Users/mac/tamago/tamago-shinchoku/status/done_archive.json', encoding='utf-8') as f:
    d = json.load(f)
targets = [719, 726, 731, 734, 771, 792, 796, 802, 876, 884]
for it in d.get('items', []):
    if it.get('n') in targets:
        print(it.get('n'), it.get('status'))
