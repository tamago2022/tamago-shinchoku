#!/bin/bash
curl -sL --max-time 15 "https://raw.githubusercontent.com/rnmkg-cmyk/line-sticker-skills/main/README.md" -o /tmp/r1.md
wc -l /tmp/r1.md
cat /tmp/r1.md
echo "===kymeraj==="
curl -sL --max-time 15 "https://raw.githubusercontent.com/kymeraj/sticker-submission/main/README.md" -o /tmp/r2.md
wc -l /tmp/r2.md
cat /tmp/r2.md
