#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sL --max-time 15 -A "$UA" "https://creator.line.me/ja/terms/" -o /tmp/creator_terms.html
echo "size1:"; wc -c /tmp/creator_terms.html
curl -sL --max-time 15 -A "$UA" "https://terms2.line.me/usersticker_rev" -o /tmp/usersticker_rev.html
echo "size2:"; wc -c /tmp/usersticker_rev.html
curl -sL --max-time 15 -A "$UA" "https://creator.line.me/ja/review_guideline/" -o /tmp/review_guideline.html
echo "size3:"; wc -c /tmp/review_guideline.html
