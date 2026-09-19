#!/bin/bash
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_jitsugaku3.txt"
exec >"$OUT" 2>&1
[ -f "$HOME/.tamago/keys/api_keys.env" ] && { set -a; . "$HOME/.tamago/keys/api_keys.env"; set +a; }
echo "== 972-3 $(date '+%F %T') =="
echo "### 200確認"
for U in "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" "https://tamago2022.github.io/tamago-shinchoku/969-kagi-daicho.html" "https://tamago2022.github.io/tamago-shinchoku/index.html"; do
  echo "$(curl -sS -o /dev/null -m 10 -w '%{http_code}' -L "$U" 2>/dev/null || echo 000)  $U"
done
echo "### GitHub Actions 課金"
GH=""; for C in /opt/homebrew/bin/gh /usr/local/bin/gh "$HOME/.local/bin/gh"; do [ -x "$C" ] && { GH="$C"; break; }; done
echo "gh=${GH:-見つからない}"
GHT=""; [ -n "$GH" ] && GHT="$("$GH" auth token 2>/dev/null || true)"; [ -z "$GHT" ] && GHT="${GITHUB_TOKEN:-}"
echo "gh鍵=$([ -n "$GHT" ] && echo あり || echo なし)"
if [ -n "$GHT" ]; then
  L=$(curl -sS -m 10 -H "Authorization: Bearer $GHT" https://api.github.com/user | sed -n 's/.*"login": *"\([^"]*\)".*/\1/p' | head -1)
  echo "login=${L:-取れず}"
  [ -n "$L" ] && { echo "--- actions billing ---"; curl -sS -m 10 -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $GHT" "https://api.github.com/users/$L/settings/billing/actions" | head -c 700; }
fi
echo; echo "== おわり $(date '+%F %T') =="
