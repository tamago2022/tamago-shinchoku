#!/bin/bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
urls=(
  "https://creator.line.me/ja/"
  "https://creator.line.me/ja/service_agreement/"
  "https://creator.line.me/ja/guideline/"
  "https://creator.line.me/ja/download_guideline/"
  "https://terms2.line.me/LINE_Creators_ISA?lang=ja"
  "https://terms2.line.me/LINE_terms_and_privacy_kr?lang=ja"
)
for u in "${urls[@]}"; do
  code=$(curl -sL --max-time 10 -A "$UA" -o /tmp/probe_out.html -w '%{http_code}' "$u")
  echo "$u -> $code"
done
