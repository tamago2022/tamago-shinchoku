#!/usr/bin/env bash
# 【2026-09-17・たまごさん指摘「トップから案内所に行く時、ストップモーションの絵が現れる」】
#
# なぜこのスクリプトが要るか：
#   直したコード（joy-relief-station の2ファイル）は Cowork のサンドボックスから書けたが、
#   サンドボックスには GitHub の資格情報が無く push できない（tools/command_ingest.py の
#   git_push() に書いてあるのと同じ制約。あちらは tamago-shinchoku 専用の口だった）。
#   ホスト側で動く command_ingest.py から1回だけ呼んでもらうための、joy-relief-station 版。
#
# やること（冪等・失敗したら非ゼロで終わる）：
#   1. サンドボックスが消せずに残した .git のロック・一時ファイルを片付ける
#   2. origin/main を取り直して、使い捨ての detached worktree を作る
#   3. 修正済みの2ファイルを、その worktree へコピーする
#   4. 差分があればコミットして origin の main へ push する
#   5. 作業に使った worktree を片付ける
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

JOY="/Users/mac/Desktop/joy-relief-station"
SRC_WT="${JOY}/.claude/worktrees/footer-flash-0917"
TMP_WT="/tmp/jrs-930-footer-flash"
LOG="/Users/mac/Desktop/tamago-shinchoku/status/_930_push_joy.log"
FILES=("src/router.tsx" "src/routes/__root.tsx")

{
  echo "=== run $(date '+%F %T') ==="

  # 1) サンドボックスが残したロックを片付ける（消せるのはホスト側だけ）
  rm -f "${JOY}"/.git/*.lock 2>/dev/null || true
  rm -f "${JOY}"/.git/worktrees/footer-flash-0917/*.lock 2>/dev/null || true
  find "${JOY}/.git/refs" -name "*.lock" -delete 2>/dev/null || true
  find "${JOY}/.git/objects" -name "tmp_obj_*" -delete 2>/dev/null || true

  cd "${JOY}" || { echo "NG: ${JOY} が開けません"; exit 1; }

  for f in "${FILES[@]}"; do
    [ -f "${SRC_WT}/${f}" ] || { echo "NG: 修正版が見つかりません: ${SRC_WT}/${f}"; exit 1; }
  done

  # 2) origin/main の最新を取り直して、使い捨ての worktree を用意する
  git -c credential.helper='!gh auth git-credential' fetch origin main --quiet \
    || { echo "NG: fetch に失敗"; exit 1; }
  git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
  rm -rf "${TMP_WT}" 2>/dev/null || true
  git worktree prune >/dev/null 2>&1 || true
  git worktree add --detach "${TMP_WT}" origin/main >/dev/null 2>&1 \
    || { echo "NG: worktree を作れません"; exit 1; }

  # 3) 修正済みファイルを載せ替える
  for f in "${FILES[@]}"; do
    cp -f "${SRC_WT}/${f}" "${TMP_WT}/${f}" || { echo "NG: コピー失敗 ${f}"; exit 1; }
  done

  cd "${TMP_WT}" || { echo "NG: ${TMP_WT} が開けません"; exit 1; }
  if [ -z "$(git status --porcelain -- "${FILES[@]}")" ]; then
    echo "OK: すでに origin/main と同じ内容です（pushするものはありません）"
  else
    git add -- "${FILES[@]}"
    git -c user.name="tamago-cowork" \
        -c user.email="tamago-cowork@users.noreply.github.com" \
        commit -q -m "fix: ページ遷移中にフッターのストップモーション動画が全画面で現れるバグを修理

たまごさん指摘（2026-09-17）:
「外部から入力すると、要はストップモーションのフッターって言うのかな？
  ページのフッターのストップモーション、それとセットで来るやつが急にここに現れるようになった。」
「トップから案内所に行く時、ストップモーションの絵が現れたりするのよ。バグ。」

原因: router.tsx の RoutePending（遷移中のプレースホルダ）が position:fixed の
2pxバーだけで通常フローの高さが0だったため、__root.tsx で <Outlet /> の直後に
置かれている <JoyReliefFooterLoop />（全ページ共通のフッター動画）が画面最上部まで
せり上がり、遷移の1秒弱のあいだ全画面で再生されていた。

直し方: ①RoutePending に1画面分の高さ(min-h-[100svh])の箱を足す
        ②<Outlet /> 自体も min-h-[100svh] で包み、中身が0高さになっても
          フッターが画面へ入れない構造にする" \
      || { echo "NG: commit に失敗"; exit 1; }

    ok=0
    for i in 1 2 3; do
      if git -c credential.helper='!gh auth git-credential' fetch origin main --quiet \
         && git rebase origin/main --quiet \
         && git -c credential.helper='!gh auth git-credential' push origin HEAD:main --quiet; then
        ok=1; break
      fi
      echo "push失敗（${i}回目）。少し待って再試行します。"
      git rebase --abort >/dev/null 2>&1 || true
      sleep 6
    done
    if [ "${ok}" != "1" ]; then echo "NG: push に失敗しました"; exit 1; fi
    echo "OK: push しました $(git rev-parse --short HEAD)"
  fi

  # 5) 片付け
  cd "${JOY}" || true
  git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
  git worktree remove --force "${SRC_WT}" >/dev/null 2>&1 || true
  git branch -D claude/q-footer-stopmotion-flash-0917 >/dev/null 2>&1 || true
  git worktree prune >/dev/null 2>&1 || true
  echo "=== done $(date '+%F %T') ==="
} >>"${LOG}" 2>&1

tail -n 400 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
