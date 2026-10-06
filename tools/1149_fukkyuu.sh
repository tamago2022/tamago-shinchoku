#!/bin/bash
# 1149番【落ちても続きから再開する外袋】
#
# たまごさん（2026-09-26）:
#   「落ちたら自動でやり直す。続きから再開できる形を必ず残す（途中経過を1件ごとに書く）。」
#   「認証で落ちたら発車を止めて、復帰したら自動で再開。同じ失敗を量産しない。」
#
# 使い方:
#   tools/1149_fukkyuu.sh <仕事の名前> -- <実際のコマンド...>
#   例) tools/1149_fukkyuu.sh daicho -- python3 tools/1149_daicho.py --naosu
#
# やること（SREの「再試行＋サーキットブレーカー＋チェックポイント」をそのまま借りた）
#   1. 走り出す前に status/1149/ckpt/<名前>.json に「走り出した」を書く（＝途中で落ちても跡が残る）
#   2. 落ちたら 5秒→15秒→45秒 と間を空けて最大3回やり直す（指数バックオフ）
#   3. 出力に「ログイン切れ／OAuth／token」が出たら **やり直さない。発車を止める。**
#      → status/.hassha_stop を置く。これがある間、この外袋は最初から走らない。
#      （同じ失敗を1,403回積み上げたのが今日の事故。★認証だけは再試行してはいけない）
#   4. 鍵が戻ったら（status/.hassha_stop を消せば）次の呼び出しから自動で再開する
#   5. 終わったら ckpt に「終わった」を書く（＝やりっぱなし帳簿①から自動で消える）
#
# 戻し方（1行）:
#   tools/1149_fukkyuu.sh --susumu     # 止めた発車を戻すだけ（札を空にする＝解除）
#
# 自己テスト済み（2026-09-26 実測）:
#   正常→done / 失敗→5・15秒あけて3回やり直し→failed /
#   「ログイン切れ」→**やり直さず即停止**（1回で止まった。1,403回積まない） /
#   停止中の次の呼び出し→skipped（走らない） / --susumu→また走った
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CK="$REPO/status/1149/ckpt"
STOP="$REPO/status/.hassha_stop"
LOG="$REPO/status/1149/fukkyuu.jsonl"
mkdir -p "$CK" "$(dirname "$LOG")"

NAME="${1:-noname}"; shift || true
[ "${1:-}" = "--" ] && shift

now() { date '+%Y-%m-%dT%H:%M:%S%z'; }
# detail は改行・引用符を潰してから書く（改行が混じるとJSONL 1行が壊れて、台帳が読めなくなる）
rec() { D="$(printf '%s' "${2:-}" | tr -d '\n\r' | tr '"' "'" | cut -c1-200)"
        printf '{"at":"%s","name":"%s","event":"%s","detail":"%s"}\n' "$(now)" "$NAME" "$1" "$D" >> "$LOG"; }

# 解除は「消す」でも「空にする」でもできる（消せない場所でも詰まらないように）
if [ "$NAME" = "--susumu" ]; then
  : > "$STOP" 2>/dev/null || true
  rm -f "$STOP" 2>/dev/null || true
  echo "発車停止を解除しました。"
  exit 0
fi

# 中身が空の停止札は「解除済み」とみなす
if [ -f "$STOP" ] && [ ! -s "$STOP" ]; then rm -f "$STOP" 2>/dev/null || true; fi

if [ -s "$STOP" ]; then
  rec "skipped" "発車が止まっています（$(cat "$STOP" 2>/dev/null | head -c 120)）"
  echo "発車停止中のため走りません: $(cat "$STOP" 2>/dev/null | head -c 200)"
  exit 0
fi

printf '{"at":"%s","name":"%s","state":"running","pid":%s}\n' "$(now)" "$NAME" "$$" > "$CK/$NAME.json"
rec "start"

TRY=0; WAIT=5; RC=1
# ★ mktemp は必ず XXXXXX 付きで呼ぶ。2026-09-25 に pre-push の関所が
#   「mkstemp failed: File exists」で判定できないまま“通過”表示になった事故と同じ形。
OUTF="$(mktemp "${TMPDIR:-/tmp}/f1149-$NAME.XXXXXX")" || OUTF="${TMPDIR:-/tmp}/f1149-$NAME.$$"
while [ $TRY -lt 3 ]; do
  TRY=$((TRY+1))
  "$@" > "$OUTF" 2>&1
  RC=$?
  cat "$OUTF"
  if [ $RC -eq 0 ]; then break; fi
  # ★認証で落ちたときは、やり直さない。止める。
  if grep -qiE 'ログイン切れ|oauth|unauthorized|401|invalid[_ ]token|refresh.?token|setup-token' "$OUTF"; then
    printf '認証で落ちました（%s）。鍵が戻るまで発車を止めます。\n戻し方: tools/1149_fukkyuu.sh --susumu  （または rm -f %s）\n' "$(now)" "$STOP" > "$STOP"
    rec "auth_stop" "認証で落ちたので発車を止めた（やり直さない）"
    printf '{"at":"%s","name":"%s","state":"auth_stopped"}\n' "$(now)" "$NAME" > "$CK/$NAME.json"
    echo "認証で落ちました。やり直さず発車を止めました → $STOP"
    rm -f "$OUTF"; exit 2
  fi
  rec "retry" "rc=$RC try=$TRY wait=${WAIT}s"
  [ $TRY -lt 3 ] && sleep $WAIT
  WAIT=$((WAIT*3))
done
rm -f "$OUTF"

if [ $RC -eq 0 ]; then
  printf '{"at":"%s","name":"%s","state":"done"}\n' "$(now)" "$NAME" > "$CK/$NAME.json"
  rec "done"
else
  printf '{"at":"%s","name":"%s","state":"failed","rc":%s}\n' "$(now)" "$NAME" "$RC" > "$CK/$NAME.json"
  rec "failed" "rc=$RC（3回やり直しても駄目。赤のまま残す）"
fi
exit $RC
