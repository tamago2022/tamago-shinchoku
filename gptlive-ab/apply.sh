#!/usr/bin/env bash
# gptlive-ab/apply.sh
# このキットの3ファイルを joy-relief-station へ複製する。
# 既存ファイルは1つも上書きしない（全部が新規ファイル）。
set -euo pipefail

SRC="$HOME/Desktop/tamago-shinchoku/gptlive-ab"
DST="${1:-$HOME/Desktop/joy-relief-station}"

if [ ! -d "$DST/.git" ]; then
  echo "✗ $DST が git リポジトリではありません。パスを引数で渡してください:"
  echo "  bash $0 /path/to/joy-relief-station"
  exit 1
fi

copy() {
  local rel="$1"
  if [ -e "$DST/$rel" ]; then
    echo "⚠️  既にあるので飛ばしました: $rel"
    return
  fi
  mkdir -p "$DST/$(dirname "$rel")"
  cp "$SRC/$rel" "$DST/$rel"
  echo "✓ $rel"
}

copy "supabase/functions/gptlive-session/index.ts"
copy "src/lib/gptLiveConcierge.ts"
copy "src/pages/LabGptLive.tsx"

echo
echo "── 残り（手でやる分） ──────────────────────────"
echo "1. gptlive-session/index.ts の __PASTE_FROM_...__ 2か所に"
echo "   voice-session/index.ts の instructions と tools をそのまま貼る"
echo "2. voiceConcierge.ts の検索関数に export を1個付ける"
echo "3. ルーターに <Route path=\"/lab/gptlive\" element={<LabGptLive />} /> を1行"
echo "   （メニュー・sitemap には載せない）"
echo "4. Supabase Secrets に OPENAI_API_KEY"
echo "5. git add -A && git commit && git push"
echo "6. ★Lovable のコードエディタで gptlive-session/index.ts を開いて保存 → 公開"
echo "   （push だけでは Edge Function は再デプロイされない）"
echo "   ※ Lovable のチャット／エージェントは押さない"
