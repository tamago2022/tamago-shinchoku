#!/bin/bash
# 963番：公開（進捗表＝スマホの画面）を main から切り離す、ただ1人の書き手。
#
# ■ 何が起きていたか（実測）
#   ・この工場の git は 232回 詰まっていた（push失敗95／「向こうが先で合流できない」64／
#     取り残しロック23／pull失敗9）。
#   ・詰まりの主犯は **5分おきに status/public/ の写しを main へ commit+push していたこの経路**。
#     9人の書き手と17個のworktreeが同じ main を触っているところへ、機械が1日73回
#     割り込んでいた。人間側の作業は毎回その後ろに並ばされ、合流できずに失敗していた。
#   ・さらに .github/workflows/pages.yml は main への push のたびに
#     **リポジトリ丸ごと(681MB)** を Pages の成果物として上げ直していた。
#
# ■ 直し方（穴に段ボールを貼るのではなく、パイプごと替える）
#   達人側の答えは一致している：
#     Homebrew … 5分間隔のgit配信が潰れたのでJSON配信へ移した
#     CocoaPods … GitHubにCPU制限をかけられてCDNへ移した
#     cargo     … gitインデックスをやめて sparse index へ移した
#   いずれも「**配信の道を、作業の道から外す**」という同じ一手。ここでも同じことをする。
#
#   公開用の枝 gh-pages を1本立て、**この1本だけが書き手**になる。
#   履歴は常に1コミットに固定し、毎回 force push する。
#   → 書き手が1人しか居ない枝に、履歴1コミットで force push するのだから、
#     「向こうが先で合流できない(non-fast-forward)」は**原理的に起きない**。
#   → main は人間の作業だけの道に戻る。機械は main に一切書かない。
#
# ■ たまごさんに渡した URL は1本も変わらない
#   枝を変えるだけで、配信されるサイトの中身と場所（https://tamago2022.github.io/tamago-shinchoku/）
#   は同じ。index.html も share/check/*.html も status/public/*.json も、今までどおりの住所に出る。
#
# ■ 何を載せるか（ここが事故の分かれ目）
#   載せるのは次の2つだけ。どちらも**今すでに公開されているもの**しか含まない。
#     (1) main が追跡しているファイル（git archive HEAD＝追跡外のゴミは原理的に入らない）
#     (2) status/public/ の生きた中身（＝今までスマホへ届いていたもの）
#   作業ディレクトリを `git add -A` で丸ごと拾うことは**しない**。
#   過去にツイート47,011件(12MB)を誤って公開した事故は「share/ を丸ごとaddしていた」ため。
#   同じ形を二度と作らない。加えて (2) には下の関所を通す。
#
#   関所（status/public/ の中だけに掛ける。main追跡分は今も公開中なので触らない）：
#     ・1MBを超えるものは載せない
#     ・.env / *.pem / *key* / *token* / *secret* / id_rsa は名前だけで弾く
#     ・載せた顔ぶれは status/pages_publish_files.txt に毎回書き出す（後から目で見られる）
#
# ■ 使い方
#   tools/pages_publish.sh          … 変化があれば公開する（machine_status_push.sh から毎周呼ぶ）
#   tools/pages_publish.sh --force  … 変化が無くても公開する（切り替え時の確認用）
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PAGES="$HOME/.tamago-pages"          # ★ Desktop の外に置く。worktree_reaper にも他セッションにも見えない
BRANCH="gh-pages"
URL="https://github.com/tamago2022/tamago-shinchoku.git"
LOG="$REPO/status/pages_publish.log"
LIST="$REPO/status/pages_publish_files.txt"
LOCK="$REPO/status/.pages_publish.lock"
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# ---- 二本走らせない ----
# ★2026-09-23 実測で直した。ここが「本番に出ない」の本体だった。
#   前：錠が300秒より古ければ奪う。ところが**この仕事は300秒より長くかかることがある**
#       （pushが1回15秒待ち×3回＋上りの時間）。5分便は300秒おきに来るので、
#       遅い回は必ず次の回に追い越され、**2本が同時に gh-pages を押す。**
#       その結果がこれ：
#         ! [remote rejected] HEAD -> gh-pages
#           (cannot lock ref: is at c871… but expected 5437…)
#       ＝ 片方が先に押したので、もう片方の「向こうはここのはず」が外れて弾かれる。
#       10:35 以降、本番が1度も更新されていなかった（＝出したものが出ていない）。
#   後：時間ではなく**錠を持っている者が本当に生きているか**で見る。
#       生きていれば譲る（何時間かかっても2本にならない）。
#       死んでいれば即座に奪う（止まった錠で何時間も待たされることも無くなる）。
if [ -f "$LOCK" ]; then
  LPID="$(awk 'NR==1{print $1}' "$LOCK" 2>/dev/null || echo "")"
  if [ -n "$LPID" ] && kill -0 "$LPID" 2>/dev/null; then
    exit 0                      # 本物が走っている。黙って譲る
  fi
  log "前の錠(pid=${LPID:-?})はもう生きていないので奪います"
fi
echo "$$ $(date '+%F %T')" > "$LOCK"
trap 'rm -f "$LOCK" 2>/dev/null || true' EXIT INT TERM

# ---- 初回だけ：公開用の作業場を作る ----
# ★ --shared を使う。main の中身(681MB)を**コピーせずに**参照するので一瞬で終わり、
#   push のときも「向こうが既に持っているもの」として除外されるため、上りはほぼ写しの分だけ。
if [ ! -d "$PAGES/.git" ]; then
  log "公開用の作業場を作ります: $PAGES"
  rm -rf "$PAGES" 2>/dev/null || true
  git clone --shared --no-checkout --quiet "$REPO" "$PAGES" || { log "🛑 作業場が作れませんでした"; exit 1; }
  git -C "$PAGES" remote set-url origin "$URL"
  git -C "$PAGES" config user.name  "tamago-pages"
  git -C "$PAGES" config user.email "tamago-pages@users.noreply.github.com"
  git -C "$PAGES" config gc.auto 0          # 勝手な掃除で共有元を触らせない
  git -C "$PAGES" switch --orphan "$BRANCH" --quiet 2>/dev/null \
    || git -C "$PAGES" checkout --orphan "$BRANCH" --quiet
  rm -f "$PAGES/.git/lastmain" 2>/dev/null || true
fi

cd "$PAGES" || { log "🛑 $PAGES へ入れませんでした"; exit 1; }

# ---- (1) main の追跡ファイルを反映 ----
# ★ 毎回まるごと展開し直さない。681MBを展開すると3分以上かかり、5分おきの巡回が詰まる。
#   前回どこまで映したかを .git/lastmain に覚えておき、**その差分だけ**を映す。
#   main の1コミットで動くのはたいてい数ファイルなので、2回目以降は一瞬で終わる。
CUR="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo "")"
[ -z "$CUR" ] && { log "🛑 main の HEAD が読めませんでした"; exit 1; }
LAST="$(cat "$PAGES/.git/lastmain" 2>/dev/null || echo "")"

SEKISHO_BLOCKED=0
sync_one() {  # $1=コミット $2=パス
  local d; d="$PAGES/$(dirname "$2")"
  mkdir -p "$d" 2>/dev/null || return 0
  if ! git -C "$REPO" show "$1:$2" > "$PAGES/$2" 2>/dev/null; then
    rm -f "$PAGES/$2" 2>/dev/null || true
    return 0
  fi
  # ---- 関所(sekisho)：本番(gh-pages)に出る手前の最終防衛（898番・4回目の再設計 2026-09-27）----
  # 検品指摘(898番3回目)で実測済み：.githooks/pre-push は (a) core.hooksPath未設定の
  # 新規clone/worktreeでは無音で丸ごとスキップされ、(b) 設定済みでもmktempの
  # テンプレート形式がmacOS(Darwin)のBSD mktempと非互換でXが展開されないまま
  # 動き続け、(c) CI(pages.yml)側にもチェックが無い。つまり「呼び忘れたら素通り」
  # という穴が3通り開いていた。
  # ここ(pages_publish.sh)は963番の設計で「gh-pages(本番)へ実際に反映される
  # 唯一の書き手」になっている。mainの誰がどうpushしたか・pre-pushが有効かに
  # 一切関係なく、公開直前の**この1箇所だけ**を必ず通るので、ここに関所を
  # 置けば環境差・設定漏れに関わらず「本番に出ているshare/check/*.htmlは
  # 必ず関所を通っている」をコードで強制できる。
  # 対象は今回の差分(増えた/変わったページ)だけ。git archiveでの初回一括展開
  # （既存497ページ、実測不合格97件は別タスクで把握済み＝oni_gate.pyのbaseline
  # と同じ「既存分は借金、新規だけ厳密化」の考え方）では呼ばれない。
  case "$2" in
    share/check/*.html)
      case "$2" in */_template.html) return 0 ;; esac
      if ! python3 "$REPO/tools/sekisho.py" --local-file "$PAGES/$2" --n "publish-$(basename "$2" .html)" >/tmp/sekisho-publish.out 2>&1; then
        rm -f "$PAGES/$2" 2>/dev/null || true
        log "🛑 関所(sekisho)FAILのため公開から外しました: $2 / $(grep SEKISHO_RESULT /tmp/sekisho-publish.out 2>/dev/null | head -1)"
        SEKISHO_BLOCKED=$((SEKISHO_BLOCKED+1))
      fi
      ;;
  esac
}

if [ "$CUR" != "$LAST" ]; then
  # 前回の印が無い／その印を main がもう知らない（掃除された等）→ 最初から全部映す
  if [ -z "$LAST" ] || ! git -C "$REPO" cat-file -e "$LAST^{commit}" 2>/dev/null; then
    log "main の中身をまるごと映します（初回・時間がかかります）"
    find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} + 2>/dev/null || true
    # git archive は**追跡しているものしか出さない**＝置きっぱなしのゴミは原理的に入らない
    if ! git -C "$REPO" archive "$CUR" | tar -x -C "$PAGES"; then
      log "🛑 main の中身を取り出せませんでした（今回は公開を見送る）"
      exit 1
    fi
  else
    # 消えたもの
    while IFS= read -r -d '' f; do
      [ -n "$f" ] && rm -f "$PAGES/$f" 2>/dev/null || true
    done < <(git -C "$REPO" diff --no-renames -z --name-only --diff-filter=D "$LAST" "$CUR" 2>/dev/null)
    # 増えたもの・変わったもの
    while IFS= read -r -d '' f; do
      [ -n "$f" ] && sync_one "$CUR" "$f"
    done < <(git -C "$REPO" diff --no-renames -z --name-only --diff-filter=ACMRTX "$LAST" "$CUR" 2>/dev/null)
  fi
  echo "$CUR" > "$PAGES/.git/lastmain"
  log "main の中身を $(echo "$LAST" | cut -c1-9) → $(echo "$CUR" | cut -c1-9) へ追従しました"
fi

# ---- (2) 生きた写し（status/public/）を上書き ----
mkdir -p "$PAGES/status/public"
rsync -a --delete "$REPO/status/public/" "$PAGES/status/public/" 2>/dev/null || {
  log "🛑 写しの同期に失敗（今回は公開を見送る）"; exit 1; }

# ---- 関所：status/public/ の中だけを見る ----
BLOCKED=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  rm -f "$f"
  log "🛑 公開から外しました（1MB超）: ${f#./}"
  BLOCKED=$((BLOCKED+1))
done < <(find ./status/public -type f -size +1024k 2>/dev/null)
while IFS= read -r f; do
  [ -z "$f" ] && continue
  rm -f "$f"
  log "🛑 公開から外しました（名前が危ない）: ${f#./}"
  BLOCKED=$((BLOCKED+1))
done < <(find ./status/public -type f \( -name '.env*' -o -name '*.pem' -o -name '*key*' \
          -o -name '*token*' -o -name '*secret*' -o -name 'id_rsa*' \) 2>/dev/null)

# 載せた顔ぶれを必ず書き出す（後から目で確かめられるように）
{ echo "# $(date '+%F %T') 公開に載せた status/public/ の顔ぶれ"; \
  find ./status/public -type f | sed 's|^\./status/public/||' | sort; } > "$LIST" 2>/dev/null || true

# ---- 変化が無ければ何もしない（＝押し合いにならない）----
# ★ --force を付ける。ここに置いたものは「main が追跡しているもの」と
#   「status/public/ の生きた中身」だけで、既に全部よそへ出ているもの。
#   .gitignore に引っかかって**黙って公開から落ちる**ほうが危ない
#   （実測：status/fact_source_baseline.json が最初の1回で落ちていた）。
git add -A --force >/dev/null 2>&1

# 向こう（GitHub）が今どこまで持っているか。これと手元が同じなら本当に出すものが無い。
REMOTE_HAVE="$(git rev-parse --verify --quiet "refs/remotes/origin/$BRANCH" 2>/dev/null || echo "")"
LOCAL_HEAD="$(git rev-parse --verify --quiet HEAD 2>/dev/null || echo "")"
if [ "$FORCE" -eq 0 ] && git diff --cached --quiet 2>/dev/null \
   && [ -n "$REMOTE_HAVE" ] && [ "$REMOTE_HAVE" = "$LOCAL_HEAD" ]; then
  exit 0
fi
# ★ここが大事：中身に変化が無くても、**前回のpushが落ちていたら必ずやり直す。**
#  （2026-09-20 実測：1回目の push が回線都合で落ちた後、
#    「変化が無い」だけで抜けてしまい、配信が00:11のまま止まった。
#    画面は真っ白にはならないが、**古いまま生き続ける**＝一番たちが悪い壊れ方。）

MSG="公開（進捗表）$(date '+%F %T') / main=$(echo "$CUR" | cut -c1-9)"
# ★ 履歴は常に1コミット。親を持たせない＝ **非fast-forwardが起きようがない**
if ! git diff --cached --quiet 2>/dev/null || [ -z "$LOCAL_HEAD" ]; then
  if [ -n "$LOCAL_HEAD" ]; then
    git commit --amend -q --no-edit -m "$MSG" >/dev/null 2>&1 || true
  else
    git commit -q -m "$MSG" >/dev/null 2>&1 || true
  fi
fi

# ---- 2026-09-24（1054番）★網の向こうを待つ push に、必ず時間切れを付ける ----
#   実測：09-24 05:1x に 5分便が git の網待ちで36分固まり、公開も回収も全部止まった。
#   落ちるのは構わない（3回粘る作りが既にある）。**返ってこないのが一番たちが悪い。**
_mattenai() {   # 引数：秒数 コマンド…
  local _s="$1"; shift
  "$@" & local _p=$!
  ( sleep "$_s"; kill -9 "$_p" 2>/dev/null ) & local _w=$!
  wait "$_p" 2>/dev/null; local _rc=$?
  kill "$_w" 2>/dev/null
  return "$_rc"
}

# ★ 3回まで粘る。Macが重いと回線が切れることが実際にある（実測: curl 55 Recv failure）。
OK=0
for _try in 1 2 3; do
  if _mattenai 120 git -c credential.helper='!gh auth git-credential' \
       push --force --quiet --no-progress origin "HEAD:refs/heads/$BRANCH" 2>>"$LOG"; then
    OK=1; break
  fi
  log "…公開の push が落ちました（${_try}回目）。15秒待ってやり直します"
  sleep 15
done

if [ "$OK" -eq 1 ]; then
  # ★ 向こうが持っている地点を手元に必ず書き戻す。
  #   これが無いと git は「向こうは何も持っていない」と思い込み、
  #   毎回 600MB を上げ直そうとして回線が落ちる（今回の失敗の再発源）。
  git update-ref "refs/remotes/origin/$BRANCH" HEAD 2>/dev/null || true
  log "公開しました（写しの関所で外したもの: ${BLOCKED}件／sekisho(仕組み⑦)で外したもの: ${SEKISHO_BLOCKED}件）"
else
  log "🛑 公開の push に3回とも失敗しました。次の周回でまたやり直します"
  exit 1
fi
