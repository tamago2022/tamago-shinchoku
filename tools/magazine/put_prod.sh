#!/bin/bash
# マガジン4本を本番（joy-relief-station public/magazine/）へ置く。gh api contents（ローカルgitに触らない）
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$HOME/tamago/tamago-shinchoku"
R=tamago2022/joy-relief-station
put() { # $1=ローカル $2=リポ内パス $3=repo
  SHA=$(gh api "repos/$3/contents/$2?ref=main" --jq .sha 2>/dev/null)
  python3 - "$1" "$SHA" "$2" > /tmp/pp.json <<'PY'
import sys,json,base64
p,sha,dst=sys.argv[1],sys.argv[2],sys.argv[3]
b={"message":"マガジン本番：%s を更新（tools/magazine から生成）"%dst,"branch":"main","content":base64.b64encode(open(p,'rb').read()).decode()}
if sha: b["sha"]=sha
print(json.dumps(b))
PY
  gh api -X PUT "repos/$3/contents/$2" --input /tmp/pp.json --jq '.commit.sha' >/dev/null && echo "OK $3 $2" || echo "NG $3 $2"
}
# 【101885番・2026-10-16】後退させない関所：置く前に送る量（KB）を基準と比べる。+5%超なら置かない（基準は小さくなった時だけ更新）
python3 tools/koutai_kanmon.py --check-files status/magazine_prod/ikareru-01.html status/magazine_prod/naze-ongaku-01-takoukan.html status/magazine_prod/rei-harakami.html status/magazine_prod/hikigatari-josh-turner.html status/magazine_prod/kimi-wa-hoshi-katsu.html status/magazine_prod/hito-wa-naze-tsuki-wo-miru-01.html status/magazine_prod/hito-ga-odoru-01.html status/magazine_prod/backnumber.html || { echo "★後退関所で停止：マガジンを置きません"; exit 2; }
python3 tools/magazine/unify_look.py --check >/dev/null || { echo "★見た目の統一の関所で停止（白い枠／Magazine Story／章頭の型）"; exit 2; }
for f in ikareru-01.html naze-ongaku-01-takoukan.html rei-harakami.html hikigatari-josh-turner.html kimi-wa-hoshi-katsu.html hito-wa-naze-tsuki-wo-miru-01.html hito-ga-odoru-01.html backnumber.html; do put status/magazine_prod/$f public/magazine/$f $R; done
# 月の特集の写真（雰囲気の静止画8枚＋ヘッダーの月・2026-10-18）。--assets のときだけ（毎回は重い）
[ "${2:-}" = "--assets" ] && { for f in status/magazine_prod/assets/fuukei/hito-wa-naze-tsuki-wo-miru-01-*.webp status/magazine_prod/assets/tsuki01/hero.webp status/magazine_prod/assets/tsuki01/hero-og.jpg; do put "$f" "public/magazine/${f#status/magazine_prod/}" $R; done; }
# 訳のJSON（日本語以外を選んだときだけ読まれる）も本番へ（2026-10-16）
for f in status/magazine_prod/*.i18n.json; do [ -f "$f" ] && put "$f" "public/magazine/$(basename "$f")" $R; done
[ "${2:-}" = "--assets" ] && { put share/check/assets/cw/styles.css public/magazine/assets/cw/styles.css $R; put share/check/assets/owner/x-avatar.jpg public/magazine/assets/owner/x-avatar.jpg $R; }
[ "${1:-}" = "--prod-only" ] && exit 0
T=tamago2022/tamago-shinchoku
for f in share/check/ikareru-01.i18n.json tools/magazine/i18n_ikareru.json share/check/tokushu-ikareru-01.html share/check/naze-ongaku-01-takoukan.html share/check/tokushu-rei-harakami.html share/check/hikigatari-josh-turner-b.html tools/magazine/mag_build.py tools/magazine/spec_ikareru.py tools/magazine/spec_takoukan.py tools/magazine/spec_harakami.py tools/magazine/spec_josh.py tools/magazine/spec_odoru01.py tools/magazine/photos_odoru01.json tools/magazine/i18n_odoru01.json tools/magazine/put_prod.sh tools/magazine/unify_look.py tools/magazine/share_bar.py tools/magazine/backnumber.py tools/magazine/photos_ikareru.json tools/magazine/i18n_hoshikatsu.json tools/magazine/spec_tsuki01.py tools/magazine/i18n_tsuki01.json tools/magazine/fuukei.json tools/magazine/song_pages.json tools/magazine_monogatari_kanmon.py share/check/hito-wa-naze-tsuki-wo-miru-01.html share/check/hito-wa-naze-tsuki-wo-miru-01.i18n.json tools/magazine/hoshikatsu_src/edit10_kanyo.py tools/magazine/hoshikatsu_src/edit11_memo.py tools/magazine_monogatari_kanmon.py CLAUDE.md; do put $f $f $T; done
