#!/bin/bash
# ================================================================
# 1163号：たまごさんが「貼って押すだけ」で棚が動くようにする1枚。
#
# このファイルをダブルクリックすると、
#   ① Supabaseの鍵のページがChromeで開く
#   ② 鍵を貼る欄が出る（画面には表示されません）
#   ③ 本当に書けるか、その場で試す
#   ④ 書けたら、たまっている分を全部棚へ入れて、公開まで済ませる
# ここで打つコマンドは1つもありません。
#
# ★鍵はMacの中（~/.tamago/supabase_service_role・600・gitの外）にしか置きません。
#   画面にも、ログにも、GitHubにも、1バイトも出ません。
# ================================================================
set -u
cd "$(dirname "$0")" || exit 1
REPO="$(pwd)"
KEY="$HOME/.tamago/supabase_service_role"
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

printf '\n\033[1m棚に書ける鍵を入れます\033[0m\n\n'

# ---- ① 鍵のページを開く（プロジェクトの番号は .env から読む。画面には出さない） ----
REF="$(grep -m1 -E '^SUPABASE_PROJECT_ID=' "$HOME/Desktop/joy-relief-station/.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r')"
if [ -n "$REF" ]; then
  open -a "Google Chrome" "https://supabase.com/dashboard/project/$REF/settings/api-keys" 2>/dev/null
  echo "Chromeに『API Keys』の画面を開きました。"
else
  open -a "Google Chrome" "https://supabase.com/dashboard/projects" 2>/dev/null
  echo "Chromeに Supabase を開きました。joy-relief-station のプロジェクト → Settings → API Keys へ。"
fi

cat <<'TXT'

  その画面の  service_role  の行にある「Reveal」を押して、鍵をコピーしてください。
  （ anon / publishable ではありません。service_role です ）

TXT

# ---- ② 貼ってもらう（画面には出ない） ----
printf 'ここに貼って、return を押す（文字は出ません）: '
IFS= read -rs PASTED
printf '\n\n'
PASTED="$(printf '%s' "$PASTED" | tr -d '[:space:]')"

if [ -z "$PASTED" ]; then
  echo "何も貼られませんでした。このまま閉じて大丈夫です。"
  exit 1
fi
case "$PASTED" in
  *ey*|sb_secret_*) : ;;
  *) echo "これは鍵の形をしていません。もう一度ダブルクリックしてやり直してください。"; exit 1 ;;
esac

mkdir -p "$HOME/.tamago"
printf '%s' "$PASTED" > "$KEY"
chmod 600 "$KEY"
unset PASTED
echo "鍵を ~/.tamago/supabase_service_role に保存しました（権限600・gitの外）。"

# ---- ③ 本当に書けるか、その場で試す ----
echo
echo "本当に棚に書けるか試します…"
python3 - <<'PY'
import sys, os, urllib.parse
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import tana
diag = []
url, key, keyname, where = tana.keys(diag)
if not url:
    print("  × Supabaseの入口が見つかりません"); sys.exit(3)
st, rows = tana._req(url, key, "/rest/v1/admin_stock?select=id,whisper&limit=1")
if not rows:
    print("  × 棚が1行も読めません（HTTP %s）" % st); sys.exit(3)
tid, w = rows[0]["id"], rows[0]["whisper"]
st2, back = tana._req(url, key,
    "/rest/v1/admin_stock?id=eq.%s" % urllib.parse.quote(tid, safe=""),
    method="PATCH", body={"whisper": w}, prefer="return=representation")
if not back:
    print("  × まだ書けません（HTTP %s・書けた行は0）。貼ったのが service_role か確かめてください。" % st2)
    sys.exit(3)
print("  ○ 書けました。")
PY
if [ $? -ne 0 ]; then
  rm -f "$KEY"
  echo
  echo "貼られた鍵では書けなかったので、保存した鍵は消しました（間違った鍵を残さないため）。"
  echo "もう一度このファイルをダブルクリックして、service_role の行の鍵を貼ってください。"
  echo
  read -r -p "return を押すと閉じます " _
  exit 1
fi

# ---- ④ たまっている分を全部入れて、公開まで済ませる ----
echo
echo "たまっている分を棚へ入れます…"
python3 "$REPO/tools/1152_ireru.py"        2>&1 | tail -30
python3 "$REPO/tools/nagekomi_shelf.py" --force 2>&1 | tail -20
python3 "$REPO/tools/nagekomi_list.py"     2>&1 | tail -5
bash    "$REPO/tools/pages_publish.sh" --force  2>&1 | tail -5

cat <<'TXT'

──────────────────────────────
ここを開いて、出ているか目で見てください。

  投げ込み箱（入った記録つき）
  https://tamago2022.github.io/tamago-shinchoku/share/nagekomi-c5fd9d5791b32e88.html

  犬の棚 / 飼い主大好き / 食>スープ
  https://joy-relief-station.lovable.app/
──────────────────────────────

これ以降は、鍵はもう貼らなくていいです。
投げ込み箱にURLを貼って「投げる」を押すだけで棚に入ります。

TXT
read -r -p "return を押すと閉じます " _
