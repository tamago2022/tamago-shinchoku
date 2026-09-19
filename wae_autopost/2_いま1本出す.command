#!/bin/bash
cd "$(dirname "$0")"
python3 post.py --show | less -R
echo ""
echo "上の文面でよければ y を押して Enter。やめるならそのまま Enter。"
printf "> "
read -r A
[ "$A" = "y" ] && python3 post.py --post || echo "やめました。"
echo ""; read -r _
