#!/bin/bash
cd "$(dirname "$0")"
python3 ogp_check.py
echo ""
echo "終わりました。このまま閉じてください。"
read -n 1 -s
