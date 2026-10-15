#!/bin/bash
# 2026-09-28 20:00-23:05 の勉強会を画面＋音で録る。launchd が 19:55 に起動する。
# 録るかどうかの最終判断はたまごさん。止めたいときは:
#   launchctl bootout gui/$(id -u)/com.tamago.zoom-rec-20260928
set -u
BASE="$HOME/Documents/AI作業/zoom_rec"
LOG="$BASE/log.txt"
STAMP=$(date +%Y%m%d)
OUTFILE="$BASE/勉強会_${STAMP}_2000-2305.mov"
TESTFILE="$BASE/テスト録画_${STAMP}.mov"
SW="$BASE/audio_switch.py"
mkdir -p "$BASE"
say() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

say "=== 起動 ==="
say "元の状態: $(python3 "$SW" --show 2>&1 | tr '\n' ' ')"
ORIG_OUT=$(python3 "$SW" --show 2>/dev/null | sed -n 's/^OUT=//p')
ORIG_IN=$(python3 "$SW" --show 2>/dev/null | sed -n 's/^IN=//p')
echo "$ORIG_OUT" > "$BASE/.orig_out"; echo "$ORIG_IN" > "$BASE/.orig_in"

switch_on() {
  python3 "$SW" --out "複数出力装置" >> "$LOG" 2>&1
  python3 "$SW" --in "BlackHole 2ch" >> "$LOG" 2>&1
  say "切替後: $(python3 "$SW" --show 2>&1 | tr '\n' ' ')"
}
switch_back() {
  [ -n "$ORIG_OUT" ] && python3 "$SW" --out "$ORIG_OUT" >> "$LOG" 2>&1
  [ -n "$ORIG_IN" ] && python3 "$SW" --in "$ORIG_IN" >> "$LOG" 2>&1
  say "戻した: $(python3 "$SW" --show 2>&1 | tr '\n' ' ')"
}
trap switch_back EXIT

# --- 1. 60秒のテスト録画（本番前に必ず確かめる） ---
switch_on
rm -f "$TESTFILE"
say "テスト録画 60秒 開始"
/usr/sbin/screencapture -x -v -g -V 60 "$TESTFILE" >> "$LOG" 2>&1
RC=$?
if [ -s "$TESTFILE" ]; then
  SZ=$(stat -f%z "$TESTFILE")
  say "テスト OK rc=$RC size=${SZ}B"
  mdls -name kMDItemCodecs -name kMDItemDurationSeconds "$TESTFILE" >> "$LOG" 2>&1
else
  say "テスト 失敗 rc=$RC ファイル無し → 画面収録の許可が無い。本番は録れない。"
  echo "NG 画面収録の許可が無い" > "$BASE/結果.txt"
  exit 1
fi

# --- 2. 20:00 ちょうどまで待つ ---
TARGET=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 20:00:00" +%s)
NOW=$(date +%s)
WAIT=$((TARGET - NOW))
[ $WAIT -gt 0 ] && { say "20:00まで ${WAIT}秒 待つ"; sleep $WAIT; }

# --- 3. 本番 20:00 → 23:05（11100秒） ---
say "本番録画 開始 -> $OUTFILE"
rm -f "$OUTFILE"
caffeinate -dimsu -t 11400 &
CAF=$!
/usr/sbin/screencapture -x -v -g -V 11100 "$OUTFILE" >> "$LOG" 2>&1
RC=$?
kill $CAF 2>/dev/null
if [ -s "$OUTFILE" ]; then
  say "本番 OK rc=$RC size=$(stat -f%z "$OUTFILE")B"
  echo "OK $OUTFILE" > "$BASE/結果.txt"
else
  say "本番 失敗 rc=$RC"
  echo "NG 本番で失敗 rc=$RC" > "$BASE/結果.txt"
fi
say "=== 終了 ==="
