#!/bin/bash
# 2026-10-01 「@」ログイン退行の戻し（一回きり）。作業ツリーに触らず、git の配管だけでコミットを作って main へ push する。
cd ~/Desktop/joy-relief-station || exit 1
echo "--- $(date '+%F %T') start"
git worktree list
for d in /tmp/jrs-atlogin-*; do [ -d "$d" ] && git worktree remove --force "$d" && echo "removed $d"; done
git worktree prune
git fetch -q origin main || exit 1
P=src/lib/adminAuth.server.ts
T=/tmp/atlogin_adminAuth.ts
git show origin/main:$P > $T || exit 1
if grep -q '^  "@",' $T; then echo "ALREADY on origin/main"; git log origin/main -1 --pretty='SHA=%H'; exit 0; fi
python3 - "$T" <<'PY' || exit 1
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
a = '''  const secret = process.env.SESSION_SECRET;
  if (!secret) throw new Error("SESSION_SECRET is required");'''
b = '''  // 2026-10-01 戻し：6eb54f6cb で既定値を消したため、SESSION_SECRET 未設定の本番で
  // ログイン記録のCookieが焼けなくなり、店主の端末が覚えられなくなった。
  const secret = process.env.SESSION_SECRET || "gokigen-fallback-session-secret-please-set-env!!";'''
c = 'const OWNER_PASSPHRASES: string[] = [];'
d = '''const OWNER_PASSPHRASES: string[] = [
  // 2026-10-01 戻し：店主はスマホの編集画面に「@」1文字で入っている（2026-08-06〜の店主指示）。
  // 6eb54f6cb（9/27）でこれを消し、GOKIGEN_ADMIN_PASSWORD も未設定のため誰も入れなくなった。
  // 一度通った端末には400日のCookieが焼かれ、以後は聞かれない（下の refreshAllAdminCookies）。
  "@",
];'''
assert s.count(a) == 1 and s.count(c) == 1, "pattern not found"
s = s.replace(a, b).replace(c, d)
e = '  return process.env.GOKIGEN_ADMIN_PASSWORD || "";'
if s.count(e) == 1:
    s = s.replace(e, '  return process.env.GOKIGEN_ADMIN_PASSWORD || OWNER_PASSPHRASES[0];')
open(p, "w", encoding="utf-8").write(s)
print("edited")
PY
diff <(git show origin/main:$P) $T
BLOB=$(git hash-object -w $T)
export GIT_INDEX_FILE=/tmp/atlogin_index
rm -f $GIT_INDEX_FILE
git read-tree origin/main
git update-index --cacheinfo 100644,$BLOB,$P
TREE=$(git write-tree)
unset GIT_INDEX_FILE
PARENT=$(git rev-parse origin/main)
C=$(GIT_AUTHOR_NAME=tamago2022 GIT_AUTHOR_EMAIL=121603229+tamago2022@users.noreply.github.com GIT_COMMITTER_NAME=tamago2022 GIT_COMMITTER_EMAIL=121603229+tamago2022@users.noreply.github.com \
  git commit-tree $TREE -p $PARENT -m "fix(admin): スマホ編集画面に「@」で入れなくなった退行を戻す（6eb54f6cbの合言葉削除とSESSION_SECRET既定値削除を戻す）")
echo "COMMIT=$C parent=$PARENT"
git diff --stat $PARENT $C
git push origin $C:refs/heads/main 2>&1 && echo "PUSHED $C"
echo "--- $(date '+%F %T') end"
