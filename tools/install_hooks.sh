#!/usr/bin/env bash
# 案件#898：このリポジトリの共有gitフック（.githooks/）を有効化する。
# 新しいworktreeを作った直後や、まっさらにcloneし直した環境で1回だけ実行すればよい
# （core.hooksPathはリポジトリ共通のconfigに書かれるため、以後は自動で全pushにかかる）。
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
chmod +x .githooks/pre-push
git config core.hooksPath .githooks
echo "✅ core.hooksPath を .githooks に設定しました（関所(sekisho)のpre-pushフックが有効です）"
git config --get core.hooksPath
