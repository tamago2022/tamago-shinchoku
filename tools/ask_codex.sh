#!/bin/bash
# AI直通の口：Codex(ChatGPT)に1問投げて答えをファイルに出す。たまごさんを介さない。
# 使い方: tools/ask_codex.sh "質問文" [出力ファイル(省略時 status/codex_answers/<時刻>.md)] [待ち秒(既定600)]
# 仕組み: Issue #580 に「@codex 質問」とコメント → chatgpt-codex-connector の返信が付くまで待つ → 本文を保存して標準出力へ。
set -eu
REPO="tamago2022/joy-relief-station"; ISSUE=580
Q="$1"; OUT="${2:-}"; WAIT="${3:-600}"
D="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$OUT" ] || { mkdir -p "$D/status/codex_answers"; OUT="$D/status/codex_answers/$(date +%Y%m%d-%H%M%S).md"; }
BODY=$(printf '@codex 次の質問に答えてください。コードは変更せず、回答だけをこのIssueにコメントしてください。\n\n%s' "$Q")
URL=$(gh issue comment $ISSUE -R $REPO --body "$BODY")
CID=$(echo "$URL" | sed 's/.*issuecomment-//')
echo "投げた: $URL" >&2
end=$(( $(date +%s) + WAIT ))
while [ "$(date +%s)" -lt "$end" ]; do
  A=$(gh api "repos/$REPO/issues/$ISSUE/comments?per_page=100" --paginate \
    -q "[.[]|select(.id>$CID and (.user.login|startswith(\"chatgpt-codex-connector\")))]|first|.body // empty" 2>/dev/null | head -c 20000)
  case "$A" in *"reached your Codex usage limits"*) echo "Codex側の利用上限（口は通っている）。上限回復後に再実行" >&2; exit 2;; esac
  if [ -n "$A" ]; then printf '%s\n' "$A" | tee "$OUT"; echo "保存: $OUT" >&2; exit 0; fi
  sleep 20
done
echo "タイムアウト(${WAIT}秒)。質問: $URL" >&2; exit 1
