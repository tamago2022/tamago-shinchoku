#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

echo "=== robots.txt ==="
curl -sL --max-time 10 -A "$UA" "https://creator.line.me/robots.txt"
echo ""
echo "=== GitHub code search: LINEスタンプ 申請 自動 ==="
curl -sL --max-time 15 "https://api.github.com/search/repositories?q=LINE+stamp+creator+automation" -H "Accept: application/vnd.github+json" -o /tmp/gh1.json -w 'code=%{http_code}\n'
echo "=== GitHub search: puppeteer LINE creator ==="
curl -sL --max-time 15 "https://api.github.com/search/repositories?q=line-creator+sticker" -H "Accept: application/vnd.github+json" -o /tmp/gh2.json -w 'code=%{http_code}\n'
echo "=== DuckDuckGo HTML search ==="
curl -sL --max-time 15 -A "$UA" "https://html.duckduckgo.com/html/?q=LINEスタンプ+申請+自動化+Selenium" -o /tmp/ddg1.html -w 'code=%{http_code}\n'
wc -c /tmp/ddg1.html
