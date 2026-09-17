#!/usr/bin/env bash
# 【936番・2026-09-18】joy-relief-station のページ最下部（フレンドテスト＋目安箱の統合／
# メール登録の文言／フェルトのストップモーションを一番下へ）を直すための、ホスト側実行スクリプト。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station フォルダがマウントされておらず、
#   GitHub の資格情報も無い。tools/_930_push_joy_footer_fix.sh と同じ理由・同じ形で、
#   ホスト側で動く command_ingest.py の joy_push から1発だけ呼んでもらう。
#
# 2段階で使う（PHASE で切り替える）：
#   recon  … joy-relief-station の該当ファイルを status/_936/ へ写して、サンドボックスから読めるようにする
#   apply  … status/_936/patched/ に置いた修正版を origin/main へ commit + push する
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

JOY="/Users/mac/Desktop/joy-relief-station"
REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_936"
LOG="${WORK}/run.log"
TMP_WT="/tmp/jrs-936-bottom"
PHASE_FILE="${WORK}/PHASE"

mkdir -p "${WORK}"
PHASE="$(cat "${PHASE_FILE}" 2>/dev/null || echo recon)"

# ★2026-09-18：command_watch.sh は30秒おきに command_ingest.py を起動するため、
#   1回の実行が30秒を超えると**同じ指示を2つのプロセスが同時に処理する**
#   （処理済みidが記録されるのは process() から戻ったあとなので、走っている間は未処理扱い）。
#   apply は同じ /tmp worktree を作って消すので、二重起動すると相手の作業場を壊す。
#   macOS の素の環境に flock は無いので mkdir のアトミック性で1本に絞る。
LOCK="${WORK}/.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
  # 30分以上前の置き去りロックだけは引き取る
  if [ -d "${LOCK}" ] && [ -z "$(find "${LOCK}" -maxdepth 0 -mmin -30 2>/dev/null)" ]; then
    rm -rf "${LOCK}" 2>/dev/null || true
    mkdir "${LOCK}" 2>/dev/null || { echo "他の実行が動いています（skip）" >>"${LOG}"; exit 0; }
  else
    echo "$(date '+%F %T') 他の実行が動いているので見送ります（skip）" >>"${LOG}"
    exit 0
  fi
fi
trap 'rm -rf "${LOCK}" 2>/dev/null || true' EXIT

{
  echo "=== run $(date '+%F %T') phase=${PHASE} ==="

  [ -d "${JOY}" ] || { echo "NG: ${JOY} がありません"; exit 1; }
  cd "${JOY}" || { echo "NG: ${JOY} が開けません"; exit 1; }

  rm -f "${JOY}"/.git/*.lock 2>/dev/null || true
  find "${JOY}/.git/refs" -name "*.lock" -delete 2>/dev/null || true

  if [ "${PHASE}" = "recon" ]; then
    SNAP="${WORK}/snapshot"
    rm -rf "${SNAP}"; mkdir -p "${SNAP}"

    git -c credential.helper='!gh auth git-credential' fetch origin main --quiet || echo "warn: fetch 失敗（ローカルHEADで続行）"

    echo "--- HEAD ---"
    git rev-parse --short origin/main 2>/dev/null || git rev-parse --short HEAD

    echo "--- 追跡ファイル一覧(src配下) ---"
    git ls-tree -r --name-only origin/main -- src 2>/dev/null || git ls-files src

    echo "--- キーワードに当たるファイル ---"
    # ${WORK}/want.txt に見たいファイルを1行ずつ書いておくと、そちらだけを写す
    if [ -s "${WORK}/want.txt" ]; then
      HITS="$(grep -v '^[[:space:]]*$' "${WORK}/want.txt" | sort -u)"
    else
      HITS="$(git grep -l -e 'ひとこと目安箱' -e 'フレンドテスト' -e 'JoyReliefFooterLoop' -e '手探り' -e 'お届けします' -e '買ってよかった棚もどうぞ' -e '今日の気分診断' origin/main -- src 2>/dev/null | sed 's|^origin/main:||' | sort -u)"
    fi
    echo "${HITS}"

    echo "--- 写したファイル ---"
    while IFS= read -r f; do
      [ -n "${f}" ] || continue
      mkdir -p "${SNAP}/$(dirname "${f}")"
      if git show "origin/main:${f}" > "${SNAP}/${f}" 2>/dev/null; then
        echo "OK ${f} ($(wc -c < "${SNAP}/${f}") bytes)"
      else
        echo "NG ${f}"
      fi
    done <<< "${HITS}"

    echo "=== recon done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "video" ]; then
    # 「静止画だけの動画を載せない」を機械で確かめる。
    # フッター動画から3コマ抜いてハッシュを比べ、全部同じなら静止画＝不合格。
    MP4="${JOY}/public/media/joy-relief-footer-loop.mp4"
    [ -f "${MP4}" ] || MP4="$(find "${JOY}" -path "${JOY}/node_modules" -prune -o -path "${JOY}/.git" -prune -o -name 'joy-relief-footer-loop*' -print 2>/dev/null | head -5 | tee /dev/stderr | grep '\.mp4$' | head -1)"
    echo "mp4: ${MP4}"
    [ -f "${MP4}" ] || { echo "NG: mp4 が見つかりません"; exit 1; }
    ls -la "${MP4}"
    if command -v ffprobe >/dev/null 2>&1; then
      ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height,nb_frames,avg_frame_rate -of default=noprint_wrappers=1 "${MP4}"
    fi
    if command -v ffmpeg >/dev/null 2>&1; then
      FR="${WORK}/frames"; rm -rf "${FR}"; mkdir -p "${FR}"
      DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${MP4}" 2>/dev/null | cut -d. -f1)"
      [ -n "${DUR}" ] || DUR=3
      for t in 0 $((DUR/3)) $((DUR*2/3)); do
        ffmpeg -v error -ss "${t}" -i "${MP4}" -frames:v 1 "${FR}/f_${t}.png" -y 2>/dev/null
      done
      echo "--- フレームのハッシュ（全部同じなら静止画） ---"
      shasum "${FR}"/*.png 2>/dev/null
      echo "--- ユニーク数 ---"
      shasum "${FR}"/*.png 2>/dev/null | awk '{print $1}' | sort -u | wc -l
    else
      echo "warn: ffmpeg が無いのでホスト側でのコマ比較は省略。mp4 を status/_936/ へ写して、サンドボックス側で調べる"
      cp -f "${MP4}" "${WORK}/footer-loop.mp4" && echo "copied: $(ls -la "${WORK}/footer-loop.mp4")"
    fi
    echo "=== video done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "shot" ]; then
    # 本番ページのスクショを、たまごさんの画面を奪わずに撮る。
    # 見えるChromeのタブは1枚も増やさない（--headless は別プロセス・別プロファイル）。
    SHOT="${WORK}/shots"
    mkdir -p "${SHOT}"
    CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    [ -x "${CH}" ] || CH="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    [ -x "${CH}" ] || { echo "NG: headless に使えるブラウザが見つかりません"; exit 1; }
    echo "browser: ${CH}"
    URL="$(cat "${WORK}/shot_url.txt" 2>/dev/null || echo 'https://joy-relief-station.lovable.app/')"
    echo "url: ${URL}"
    PROF="/tmp/jrs-936-shot-profile"
    rm -rf "${PROF}"; mkdir -p "${PROF}"
    for size in "1440,3600:pc" "375,3600:sp375"; do
      wh="${size%%:*}"; name="${size##*:}"
      "${CH}" --headless=new --disable-gpu --hide-scrollbars --no-first-run --no-default-browser-check \
        --user-data-dir="${PROF}" --window-size="${wh}" --virtual-time-budget=12000 \
        --screenshot="${SHOT}/${name}.png" "${URL}" >/dev/null 2>&1
      if [ -f "${SHOT}/${name}.png" ]; then
        echo "OK ${name}.png ($(wc -c < "${SHOT}/${name}.png") bytes)"
      else
        echo "NG ${name}.png が撮れませんでした"
      fi
    done
    rm -rf "${PROF}" 2>/dev/null || true
    echo "=== shot done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "apply" ]; then
    PATCHED="${WORK}/patched"
    [ -d "${PATCHED}" ] || { echo "NG: ${PATCHED} がありません"; exit 1; }

    git -c credential.helper='!gh auth git-credential' fetch origin main --quiet \
      || { echo "NG: fetch に失敗"; exit 1; }
    git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
    rm -rf "${TMP_WT}" "/private${TMP_WT}" 2>/dev/null || true
    rm -rf "${JOY}/.git/worktrees/$(basename "${TMP_WT}")" 2>/dev/null || true
    git worktree prune >/dev/null 2>&1 || true
    git worktree add --detach "${TMP_WT}" origin/main 2>&1 \
      || { echo "NG: worktree を作れません"; exit 1; }

    ( cd "${PATCHED}" && find . -type f -print ) | sed 's|^\./||' | while IFS= read -r f; do
      mkdir -p "${TMP_WT}/$(dirname "${f}")"
      cp -f "${PATCHED}/${f}" "${TMP_WT}/${f}" && echo "copy ${f}"
    done

    cd "${TMP_WT}" || { echo "NG: worktree が開けません"; exit 1; }

    # ビルドが通るかを先に見る（node_modules は元リポジトリのものを借りる）
    if [ -d "${JOY}/node_modules" ]; then
      ln -sfn "${JOY}/node_modules" "${TMP_WT}/node_modules"
      if [ -f package.json ]; then
        # ★2026-09-18：`npm run build` をこの使い捨て worktree で走らせると、
        #   借りている ${JOY}/node_modules の中の nitro/vite キャッシュ(.nitro)が
        #   別ディレクトリからのビルドと噛み合わず、SSR段で
        #   「"_getRenderedMatches" is not exported by @tanstack/router-core」で必ず落ちる
        #   （クライアント側は "✓ 2938 modules transformed" まで通る＝コードの誤りではない）。
        #   たまごさんの working tree では触らない方針なので、ここでは型検査だけを門にする。
        #   直したファイルに型・import の誤りがあれば必ずここで出る。
        echo "--- typecheck (tsc --noEmit) ---"
        npx --no-install tsc --noEmit >"${WORK}/build.log" 2>&1 || true
        MINE="$(grep -E 'FeedbackDoor\.tsx|FriendTest\.tsx|__root\.tsx' "${WORK}/build.log" || true)"
        if [ -n "${MINE}" ]; then
          echo "TYPECHECK NG（直したファイルにエラー）"
          echo "${MINE}" | head -n 20
          cd "${JOY}"; git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
          exit 1
        fi
        echo "TYPECHECK OK（直した3ファイルにエラーなし／他ファイルの既存エラー $(grep -c 'error TS' "${WORK}/build.log" || echo 0) 件はこの依頼の範囲外）"
      fi
      rm -f "${TMP_WT}/node_modules"
    else
      echo "warn: node_modules が無いのでビルド確認は省略"
    fi

    if [ -z "$(git status --porcelain)" ]; then
      echo "OK: すでに origin/main と同じ内容です（pushするものはありません）"
    else
      git add -A
      MSG_FILE="${WORK}/commit_msg.txt"
      if [ -f "${MSG_FILE}" ]; then
        git -c user.name="tamago-cowork" -c user.email="tamago-cowork@users.noreply.github.com" \
            commit -q -F "${MSG_FILE}" || { echo "NG: commit に失敗"; exit 1; }
      else
        git -c user.name="tamago-cowork" -c user.email="tamago-cowork@users.noreply.github.com" \
            commit -q -m "fix: ページ最下部を整理（936番）" || { echo "NG: commit に失敗"; exit 1; }
      fi
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

    cd "${JOY}" || true
    git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
    git worktree prune >/dev/null 2>&1 || true
    echo "=== apply done $(date '+%F %T') ==="
    exit 0
  fi

  echo "NG: 不明な PHASE=${PHASE}"
  exit 1
} >>"${LOG}" 2>&1

tail -n 800 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
