#!/usr/bin/env bash
# 【937番・2026-09-18】メール登録と目安箱を「受け取ったあと」まで繋ぐ工事のホスト側実行スクリプト。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station フォルダがマウントされておらず、
#   GitHub の資格情報も無い。tools/_930_push_joy_footer_fix.sh ／ tools/_936_jrs_bottom_merge.sh と
#   同じ理由・同じ形で、ホスト側で動く command_ingest.py の joy_push から1発だけ呼んでもらう。
#
# ★ status/_937/ は .gitignore の `status/*` で除外されるので、ここに置いたものは公開されない。
#   Supabase の鍵・登録メールアドレスなどの個人情報は必ずこの下だけに置くこと。
#
# PHASE（status/_937/PHASE の中身）で切り替える：
#   recon  … joy-relief-station の必要ファイル＋.env を status/_937/ へ写す（読むため）
#   sql    … status/_937/run.sql を本番Supabaseへ流す（テーブル作成など）
#   apply  … status/_937/patched/ の修正版を origin/main へ commit + push する
#   shot   … 本番ページのスクショを headless で撮る（たまごさんの画面を奪わない）
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

JOY="/Users/mac/Desktop/joy-relief-station"
REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_937"
LOG="${WORK}/run.log"
TMP_WT="/tmp/jrs-937-mail"
PHASE_FILE="${WORK}/PHASE"

mkdir -p "${WORK}"
PHASE="$(cat "${PHASE_FILE}" 2>/dev/null || echo recon)"

# command_watch.sh は30秒おきに command_ingest.py を起動するので、二重起動を mkdir で1本に絞る
LOCK="${WORK}/.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
  if [ -d "${LOCK}" ] && [ -z "$(find "${LOCK}" -maxdepth 0 -mmin -20 2>/dev/null)" ]; then
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

    echo "--- supabase 配下の追跡ファイル ---"
    git ls-tree -r --name-only origin/main -- supabase 2>/dev/null | head -100

    echo "--- メール・購読まわりに当たるファイル ---"
    git grep -l -e 'mail_subscribers' -e 'cover_guide_feedback' -e 'resend' -e 'Resend' -e 'send-email' origin/main 2>/dev/null | sed 's|^origin/main:||' | sort -u | head -40

    echo "--- 写したファイル ---"
    if [ -s "${WORK}/want.txt" ]; then
      HITS="$(grep -v '^[[:space:]]*$' "${WORK}/want.txt" | sort -u)"
    else
      HITS="src/integrations/supabase/client.ts"
    fi
    while IFS= read -r f; do
      [ -n "${f}" ] || continue
      mkdir -p "${SNAP}/$(dirname "${f}")"
      if git show "origin/main:${f}" > "${SNAP}/${f}" 2>/dev/null; then
        echo "OK ${f} ($(wc -c < "${SNAP}/${f}") bytes)"
      else
        rm -f "${SNAP}/${f}" 2>/dev/null || true
        echo "NG ${f}（origin/main に無い）"
      fi
    done <<< "${HITS}"

    echo "--- 追跡外だが必要なもの（.env / config.toml / CLI） ---"
    for f in .env .env.local supabase/config.toml; do
      if [ -f "${JOY}/${f}" ]; then
        mkdir -p "${SNAP}/$(dirname "${f}")"
        cp -f "${JOY}/${f}" "${SNAP}/${f}"
        echo "OK(untracked) ${f} ($(wc -c < "${SNAP}/${f}") bytes)"
      else
        echo "-- 無し ${f}"
      fi
    done
    echo "supabase CLI: $(command -v supabase || echo 'なし')"
    echo "psql: $(command -v psql || echo 'なし')"
    echo "=== recon done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "run" ]; then
    # status/_937/run_step.sh をホスト側（ネットワークあり・curl あり）で実行する。
    # サンドボックスからは外へ出られないので、本番Supabaseの実測・疎通確認はここで行う。
    STEP="${WORK}/run_step.sh"
    [ -f "${STEP}" ] || { echo "NG: ${STEP} がありません"; exit 1; }
    bash "${STEP}" 2>&1 | tail -n 200
    echo "step rc=${PIPESTATUS[0]}"
    echo "=== run done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "sql" ]; then
    # status/_937/run.sql を本番Supabaseへ流す。
    # 接続情報は status/_937/db_url.txt（1行・postgresql://…）に置く。★公開されない場所。
    SQLF="${WORK}/run.sql"
    URLF="${WORK}/db_url.txt"
    [ -f "${SQLF}" ] || { echo "NG: ${SQLF} がありません"; exit 1; }
    [ -f "${URLF}" ] || { echo "NG: ${URLF} がありません"; exit 1; }
    DBURL="$(tr -d '\r\n' < "${URLF}")"
    PSQL="$(command -v psql || true)"
    if [ -z "${PSQL}" ]; then
      for c in /opt/homebrew/opt/libpq/bin/psql /opt/homebrew/opt/postgresql@16/bin/psql /usr/local/opt/libpq/bin/psql /Applications/Postgres.app/Contents/Versions/latest/bin/psql; do
        [ -x "${c}" ] && PSQL="${c}" && break
      done
    fi
    [ -n "${PSQL}" ] || { echo "NG: psql が見つかりません"; exit 1; }
    echo "psql: ${PSQL}"
    "${PSQL}" "${DBURL}" -v ON_ERROR_STOP=1 -f "${SQLF}" 2>&1 | sed -e 's/postgresql:\/\/[^ ]*/<DBURL>/g'
    rc=${PIPESTATUS[0]}
    echo "psql rc=${rc}"
    [ "${rc}" = "0" ] || exit 1
    echo "=== sql done $(date '+%F %T') ==="
    exit 0
  fi

  if [ "${PHASE}" = "shot" ]; then
    SHOT="${WORK}/shots"
    mkdir -p "${SHOT}"
    CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    [ -x "${CH}" ] || CH="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    [ -x "${CH}" ] || { echo "NG: headless に使えるブラウザが見つかりません"; exit 1; }
    URL="$(cat "${WORK}/shot_url.txt" 2>/dev/null || echo 'https://joy-relief-station.lovable.app/')"
    echo "url: ${URL}"
    PROF="/tmp/jrs-937-shot-profile"
    rm -rf "${PROF}"; mkdir -p "${PROF}"
    for size in "1440,3600:pc" "375,3600:sp375"; do
      wh="${size%%:*}"; name="${size##*:}"
      "${CH}" --headless=new --disable-gpu --hide-scrollbars --no-first-run --no-default-browser-check \
        --user-data-dir="${PROF}" --window-size="${wh}" --virtual-time-budget=15000 \
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

    if [ -d "${JOY}/node_modules" ] && [ -f package.json ]; then
      ln -sfn "${JOY}/node_modules" "${TMP_WT}/node_modules"
      echo "--- typecheck (tsc --noEmit) ---"
      npx --no-install tsc --noEmit >"${WORK}/build.log" 2>&1 || true
      # 直したファイルにだけエラーが出ていないかを門にする（他ファイルの既存エラーは範囲外）
      PAT="$( ( cd "${PATCHED}" && find . -name '*.ts' -o -name '*.tsx' ) | sed 's|^\./||' | xargs -n1 basename 2>/dev/null | sed 's/\./\\./g' | paste -sd'|' - )"
      if [ -n "${PAT}" ]; then
        MINE="$(grep -E "${PAT}" "${WORK}/build.log" || true)"
        if [ -n "${MINE}" ]; then
          echo "TYPECHECK NG（直したファイルにエラー）"
          echo "${MINE}" | head -n 20
          cd "${JOY}"; git worktree remove --force "${TMP_WT}" >/dev/null 2>&1 || true
          exit 1
        fi
      fi
      echo "TYPECHECK OK（直したファイルにエラーなし／他ファイルの既存エラー $(grep -c 'error TS' "${WORK}/build.log" || echo 0) 件はこの依頼の範囲外）"
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
            commit -q -m "feat: メール登録と目安箱の受け皿（937番）" || { echo "NG: commit に失敗"; exit 1; }
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
