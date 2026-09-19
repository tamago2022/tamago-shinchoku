#!/usr/bin/env bash
# 目安箱の門番を joy-relief-station に据え付ける（1回だけ・冪等・元に戻せる）。
#
# たまごさん：「出せなくする仕組みにしてください」
# → 置き場所を直すのではなく、コミットの手前で止める。
#
#   使い方:  bash tools/install_meyasubako_gate.sh
#   外す時:  cd ~/Desktop/joy-relief-station && git config --unset core.hooksPath
#
set -uo pipefail

SRC_REPO="${SRC_REPO:-$HOME/Desktop/tamago-shinchoku}"
DST_REPO="${DST_REPO:-$HOME/Desktop/joy-relief-station}"

if [ ! -d "$DST_REPO/.git" ]; then
  echo "NG  $DST_REPO が git リポジトリではない"
  exit 1
fi

mkdir -p "$DST_REPO/tools" "$DST_REPO/.githooks"
cp "$SRC_REPO/tools/gate_meyasubako.py" "$DST_REPO/tools/gate_meyasubako.py"

cat > "$DST_REPO/.githooks/pre-commit" <<'HOOK'
#!/usr/bin/env bash
# 目安箱（FeedbackDoor）＋フレンドテスト（FriendTest）の門番。
# 954番の事故「緑の見出しの箱の中に目安箱が入っていた」を、置き場所ではなく
# 「ページ側に置けること」そのものを塞いで再発させない。
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$ROOT" || exit 0
[ -f tools/gate_meyasubako.py ] || exit 0

# コミットに入る .tsx/.jsx だけを見る（速い）
FILES="$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(tsx|jsx)$' || true)"
[ -z "$FILES" ] && exit 0

TMP="$(mktemp -d /tmp/meyasubako.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
while IFS= read -r f; do
  [ -z "$f" ] && continue
  mkdir -p "$TMP/$(dirname "$f")"
  git show ":$f" > "$TMP/$f" 2>/dev/null || true
done <<< "$FILES"

# __root.tsx は順序も見るので、差分に無くても必ず一緒に渡す
if [ -f src/routes/__root.tsx ] && [ ! -f "$TMP/src/routes/__root.tsx" ]; then
  mkdir -p "$TMP/src/routes"; cp src/routes/__root.tsx "$TMP/src/routes/__root.tsx"
fi

if ! python3 tools/gate_meyasubako.py --repo "$TMP"; then
  echo ""
  echo "🚧 目安箱の門番がコミットを止めました。"
  echo "   目安箱＋フレンドテストは統合済みの1ブロックで、src/routes/__root.tsx が"
  echo "   全ページの一番下（ストップモーションの直前）に1回だけ出します。"
  echo "   ページ側の <FeedbackDoor /> を消してください。"
  exit 1
fi
exit 0
HOOK

chmod +x "$DST_REPO/.githooks/pre-commit"
( cd "$DST_REPO" && git config core.hooksPath .githooks )

echo "OK  据え付け完了"
echo "    $DST_REPO/tools/gate_meyasubako.py"
echo "    $DST_REPO/.githooks/pre-commit  (core.hooksPath=.githooks)"
echo ""
echo "--- いまの全ページ点検 ---"
python3 "$DST_REPO/tools/gate_meyasubako.py" --repo "$DST_REPO"
