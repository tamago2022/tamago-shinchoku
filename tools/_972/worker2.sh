#!/bin/bash
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_jitsugaku2.txt"
exec >"$OUT" 2>&1
ENVF="$HOME/.tamago/keys/api_keys.env"
[ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; }
[ -f "$REPO/.env" ] && { set -a; . "$REPO/.env"; set +a; }
DEVK="${DEVIN_API_KEY:-}"
hit(){ local l="$1" u="$2" h="${3:-}" b c
  if [ -n "$h" ]; then b=$(curl -sS -m 15 -w $'\n__C__%{http_code}' -H "$h" "$u" 2>&1); else b=$(curl -sS -m 15 -w $'\n__C__%{http_code}' "$u" 2>&1); fi
  c=$(printf '%s' "$b" | sed -n 's/.*__C__//p' | tail -1); b=$(printf '%s' "$b" | sed 's/__C__[0-9]*$//')
  echo "[$l] $u -> HTTP ${c:-000}"; printf '%s\n' "$b" | head -c 3000; echo; }
echo "== 972-2 $(date '+%F %T') =="
echo "### Devin consumption（日付つき）★本命"
for R in "start_date=2026-09-15&end_date=2026-09-21" "start_date=2026-09-01&end_date=2026-09-21" "start_date=2026-09-15T00:00:00Z&end_date=2026-09-21T23:59:59Z"; do
  [ -n "$DEVK" ] && hit devin-consumption "https://api.devin.ai/v1/enterprise/consumption?$R" "Authorization: Bearer $DEVK"
done
echo "### GitHub"
GH=""
for C in /opt/homebrew/bin/gh /usr/local/bin/gh "$HOME/.local/bin/gh" gh; do command -v "$C" >/dev/null 2>&1 && { GH="$C"; break; }; done
echo "gh=${GH:-見つからない}"
GHT=""
[ -n "$GH" ] && GHT="$("$GH" auth token 2>/dev/null || true)"
[ -z "$GHT" ] && GHT="${GITHUB_TOKEN:-}"
[ -z "$GHT" ] && [ -f "$HOME/.tamago/keys/api_keys.env" ] && GHT="${GH_TOKEN:-}"
echo "gh鍵： $([ -n "$GHT" ] && echo あり || echo なし)"
if [ -n "$GHT" ]; then
  LOGIN=$(curl -sS -m 15 -H "Authorization: Bearer $GHT" https://api.github.com/user | sed -n 's/.*"login": *"\([^"]*\)".*/\1/p' | head -1)
  echo "login=${LOGIN:-取れず}"
  [ -n "$LOGIN" ] && hit gh-actions "https://api.github.com/users/$LOGIN/settings/billing/actions" "Authorization: Bearer $GHT"
fi
echo "### 200確認（報告書）"
for U in "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" "https://github.com/settings/billing/summary" "https://console.x.ai/team" ; do
  echo "200確認: $(curl -sS -o /dev/null -m 15 -w '%{http_code}' -L "$U" 2>/dev/null || echo 000)  $U"
done
echo "== おわり $(date '+%F %T') =="
