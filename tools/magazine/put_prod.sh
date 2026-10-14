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
for f in ikareru-01.html naze-ongaku-01-takoukan.html rei-harakami.html hikigatari-josh-turner.html; do put status/magazine_prod/$f public/magazine/$f $R; done
[ "${1:-}" = "--assets" ] && { put share/check/assets/cw/styles.css public/magazine/assets/cw/styles.css $R; put share/check/assets/owner/x-avatar.jpg public/magazine/assets/owner/x-avatar.jpg $R; }
T=tamago2022/tamago-shinchoku
for f in share/check/tokushu-ikareru-01.html share/check/naze-ongaku-01-takoukan.html share/check/tokushu-rei-harakami.html share/check/hikigatari-josh-turner-b.html tools/magazine/mag_build.py tools/magazine/spec_ikareru.py tools/magazine/spec_takoukan.py tools/magazine/spec_harakami.py tools/magazine/spec_josh.py tools/magazine/put_prod.sh tools/magazine_monogatari_kanmon.py CLAUDE.md; do put $f $f $T; done
