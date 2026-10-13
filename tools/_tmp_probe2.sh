#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sL --max-time 15 -A "$UA" "https://creator.line.me/ja/" -o /tmp/creator_top.html
echo "size:"
wc -c /tmp/creator_top.html
echo "---links---"
grep -o -E 'href="[^"]*"' /tmp/creator_top.html | grep -i -E 'term|agreement|guideline|rule|policy|kiyaku' | sort -u
