#!/bin/bash
echo "=== repo tree ==="
curl -sL --max-time 15 "https://api.github.com/repos/rnmkg-cmyk/line-sticker-skills/git/trees/main?recursive=1" -o /tmp/tree.json
python3 -c "
import json
d=json.load(open('/tmp/tree.json'))
for it in d.get('tree',[]):
    print(it['path'])
"
echo "=== SKILL.md for submit ==="
curl -sL --max-time 15 "https://raw.githubusercontent.com/rnmkg-cmyk/line-sticker-skills/main/line-sticker-submit/SKILL.md" -o /tmp/submit_skill.md
cat /tmp/submit_skill.md
