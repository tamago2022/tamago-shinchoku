#!/bin/bash
# 読みの作り直し。新しいアーティストが入荷したら、これを走らせるだけで読みが付く。
# 危ないものだけ share/yomi/yomi-review.json に赤で残る。お金は1円も出ない。
#
#   bash tools/yomi/run.sh            … 作り直す
#   bash tools/yomi/run.sh --kaigi    … 外部AIへ出す問いも作る
set -euo pipefail
cd "$(dirname "$0")/../.."
export PATH="$HOME/.local/bin:$PATH"

# 本物の棚（非公開リポジトリ）が手元にあればそれを最優先。無ければ写しで作る。
JRS="${JRS:-$HOME/Desktop/joy-relief-station}"
SRC=()
for f in \
  "$JRS/src/lib/coverGuide.ts" \
  ../joy-relief-station/src/lib/coverGuide.ts \
  status/_936/keep/src/lib/coverGuide.ts \
  status/_952/recon/HIT_src_lib_coverGuide.ts ; do
  [ -f "$f" ] && SRC+=("$f")
done
if [ ${#SRC[@]} -eq 0 ]; then echo "coverGuide.ts が見つかりません"; exit 1; fi
# 本物があるなら写しは混ぜない（もう棚に無い人の読みを作らないため）
[ -f "$JRS/src/lib/coverGuide.ts" ] && SRC=("$JRS/src/lib/coverGuide.ts")
echo "   読む棚: ${SRC[*]}"

PROF=()
for f in \
  "$JRS/src/lib/coverGuide.profiles.generated.ts" \
  ../joy-relief-station/src/lib/coverGuide.profiles.generated.ts \
  status/966_seihon/coverGuide.profiles.generated.ts ; do
  [ -f "$f" ] && PROF+=(--profiles "$f")
done

echo "── 0. 形態素解析（Sudachi）があるか。無ければ入れる（0円・1回だけ）"
python3 -c "import sudachipy, sudachidict_core" 2>/dev/null || {
  pip3 install --quiet --user sudachipy sudachidict-core 2>/dev/null \
  || pip3 install --quiet --break-system-packages sudachipy sudachidict-core 2>/dev/null \
  || echo "  入りませんでした。ローマ字だけで進めます（結果が変わるので後で入れること）"
}
python3 -c "
import sys
try:
    import sudachipy, sudachidict_core; print('  Sudachi: あり（漢字の裏取りが効く）')
except Exception:
    print('  Sudachi: なし ★ローマ字の裏取りが片方しか効きません')
"

echo "── 1. 読みを起こす（辞書 → aliases → idのローマ字 → 形態素解析）"
python3 tools/yomi/build_yomi.py "${SRC[@]}" ${PROF[@]+"${PROF[@]}"} --out tools/yomi/out

sync 2>/dev/null || true; sleep 2   # 共有フォルダの書き込みが見えるまで待つ

echo "── 2. 案内人が読む形にする"
python3 tools/yomi/emit_ts.py --out tools/yomi/out

echo "── 3. 配る"
mkdir -p share/yomi
cp tools/yomi/out/yomi.js          share/yomi/yomi.js
cp tools/yomi/out/yomi-review.json share/yomi/yomi-review.json
cp tools/yomi/out/yomi-stats.json  share/yomi/yomi-stats.json

echo "── 4. 自動テスト（King Gnu がカタカナで案内人に渡るか）"
node tools/yomi/test_yomi.mjs

if [ "${1:-}" = "--kaigi" ]; then
  echo "── 5. 外部AIへ出す問いを作る"
  python3 tools/yomi/make_kaigi.py --out tools/yomi/out --limit 200
  echo "   → tools/yomi/out/kaigi-question.md"
fi

python3 - <<'PY'
import json
s=json.load(open("tools/yomi/out/yomi-stats.json",encoding="utf-8"))
print("\n読みが付いた: %d／%d 件　　赤（要確認）: %d 件"
      % (s["artists_dict"], s["artists_total"], s["red"]))
PY
