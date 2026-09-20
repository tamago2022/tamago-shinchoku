#!/bin/bash
# 972番 本体：公式の使用量APIを叩いて実額を取る。★読み取りだけ・課金しない・鍵の値は出さない。
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_jitsugaku.txt"
exec >"$OUT" 2>&1
ENVF="$HOME/.tamago/keys/api_keys.env"
[ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; }
[ -f "$REPO/.env" ] && { set -a; . "$REPO/.env"; set +a; }
FAL_ADMIN=""; [ -f "$HOME/.fal_admin_key" ] && FAL_ADMIN="$(tr -d '\n' < "$HOME/.fal_admin_key")"
OK="${OPENAI_API_KEY:-}"; OAK="${OPENAI_ADMIN_KEY:-}"; FALK="${FAL_KEY:-}"; DEVK="${DEVIN_API_KEY:-}"
AK="${OAK:-$OK}"
FROM=1789405200
hit(){ local l="$1" u="$2" h="${3:-}" b c
  if [ -n "$h" ]; then b=$(curl -sS -m 12 -w $'\n__C__%{http_code}' -H "$h" "$u" 2>&1); else b=$(curl -sS -m 12 -w $'\n__C__%{http_code}' "$u" 2>&1); fi
  c=$(printf '%s' "$b" | sed -n 's/.*__C__//p' | tail -1); b=$(printf '%s' "$b" | sed 's/__C__[0-9]*$//')
  echo "[$l] $u -> HTTP ${c:-000}"; printf '%s\n' "$b" | head -c 900; echo; }
echo "== 972 実額しらべ $(date '+%F %T') =="
echo "鍵の有無： openai=$([ -n "$OK" ] && echo あり || echo なし) openai_admin=$([ -n "$OAK" ] && echo あり || echo なし) fal=$([ -n "$FALK" ] && echo あり || echo なし) fal_admin=$([ -n "$FAL_ADMIN" ] && echo あり || echo なし) devin=$([ -n "$DEVK" ] && echo あり || echo なし)"
echo; echo "### 1 OpenAI 公式Costs"
[ -n "$AK" ] && hit oa-costs "https://api.openai.com/v1/organization/costs?start_time=$FROM&limit=31&bucket_width=1d" "Authorization: Bearer $AK"
echo "### 2 OpenAI 公式Usage"
[ -n "$AK" ] && hit oa-usage "https://api.openai.com/v1/organization/usage/completions?start_time=$FROM&bucket_width=1d&limit=31" "Authorization: Bearer $AK"
echo "### 3 fal 公式Billing"
for U in "https://rest.alpha.fal.ai/billing/user_spending" "https://rest.alpha.fal.ai/billing" "https://api.fal.ai/v1/billing"; do
  [ -n "$FAL_ADMIN" ] && hit fal-admin "$U" "Authorization: Key $FAL_ADMIN"
done
[ -n "$FALK" ] && hit fal-normal "https://rest.alpha.fal.ai/billing/user_spending" "Authorization: Key $FALK"
echo "### 4 Devin 使用量の口"
for U in "https://api.devin.ai/v1/enterprise/consumption" "https://api.devin.ai/v1/usage" "https://api.devin.ai/v1/billing"; do
  [ -n "$DEVK" ] && hit devin "$U" "Authorization: Bearer $DEVK"
done
echo "### 5 GitHub Actions 課金"
GHT="$(gh auth token 2>/dev/null || echo "${GITHUB_TOKEN:-}")"
if [ -n "$GHT" ]; then
  LOGIN=$(curl -sS -m 12 -H "Authorization: Bearer $GHT" https://api.github.com/user | sed -n 's/.*"login": *"\([^"]*\)".*/\1/p' | head -1)
  echo "login=${LOGIN:-取れず}"
  [ -n "$LOGIN" ] && hit gh-actions "https://api.github.com/users/$LOGIN/settings/billing/actions" "Authorization: Bearer $GHT"
fi
echo "### 6 URLの200確認"
for U in "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" "https://tamago2022.github.io/tamago-shinchoku/" "https://platform.openai.com/usage" "https://fal.ai/dashboard/billing" "https://app.devin.ai/settings" "https://console.x.ai/" "https://github.com/settings/billing" "https://lovable.dev/" ; do
  echo "200確認: $(curl -sS -o /dev/null -m 12 -w '%{http_code}' -L "$U" 2>/dev/null || echo 000)  $U"
done
echo; echo "== おわり $(date '+%F %T') =="
