#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
echo "=== FAQ page for bulk upload / API ==="
curl -sL --max-time 15 -A "$UA" "https://help2.line.me/creators/web/?lang=ja" -o /tmp/faq.html -w 'code=%{http_code}\n'
python3 -c "
import re
html = open('/tmp/faq.html', encoding='utf-8', errors='ignore').read()
text = re.sub(r'<script.*?</script>','',html,flags=re.S)
text = re.sub(r'<[^>]+>','\n',text)
text = re.sub(r'\n+','\n',text)
lines=[l.strip() for l in text.split('\n') if l.strip()]
for l in lines:
    if any(k in l for k in ['API','一括','ロボット','自動','BOT','外部ツール']):
        print(l)
"
echo "=== review_guideline for automation mention ==="
python3 -c "
import re
html = open('/tmp/review_guideline.html', encoding='utf-8', errors='ignore').read()
text = re.sub(r'<script.*?</script>','',html,flags=re.S)
text = re.sub(r'<[^>]+>','\n',text)
text = re.sub(r'\n+','\n',text)
lines=[l.strip() for l in text.split('\n') if l.strip()]
for l in lines:
    if any(k in l for k in ['API','一括','ロボット','自動','BOT','外部ツール','ブラウザ']):
        print(l)
"
