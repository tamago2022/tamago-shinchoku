#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
echo "=== README full for links ==="
grep -n "http" /tmp/r1.md
echo "=== Bing search: LINEスタンプ 自動化 アカウント停止 ==="
curl -sL --max-time 15 -A "$UA" "https://www.bing.com/search?q=LINEスタンプ+申請+自動化+アカウント停止" -o /tmp/bing1.html -w 'code=%{http_code}\n'
wc -c /tmp/bing1.html
echo "=== Bing search: LINE Creators Market Selenium ==="
curl -sL --max-time 15 -A "$UA" "https://www.bing.com/search?q=%22LINE+Creators+Market%22+Selenium+OR+Puppeteer+%E8%87%AA%E5%8B%95%E7%94%B3%E8%AB%8B" -o /tmp/bing2.html -w 'code=%{http_code}\n'
wc -c /tmp/bing2.html
