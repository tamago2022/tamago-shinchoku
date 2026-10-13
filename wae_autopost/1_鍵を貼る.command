#!/bin/bash
cd "$(dirname "$0")"
echo "=============================================="
echo " わえ自動投稿：鍵を貼る（1回だけ）"
echo "=============================================="
echo "README_鍵の取り方.md の手順4でコピーした文字列を、下に貼って Enter を押してください。"
echo ""
printf "トークン> "
read -r TOKEN
[ -z "$TOKEN" ] && { echo "何も貼られていません。終わります。"; read -r _; exit 1; }
python3 - "$TOKEN" <<'PY'
import sys, json, urllib.request, urllib.parse, os
tok=sys.argv[1].strip()
G="https://graph.facebook.com/v21.0"
def get(p):
    with urllib.request.urlopen(f"{G}/{p}{'&' if '?' in p else '?'}access_token={urllib.parse.quote(tok)}",timeout=60) as r:
        return json.loads(r.read().decode())
try:
    pages=get("me/accounts?fields=id,name,instagram_business_account")["data"]
except Exception as e:
    print("× 鍵が効きませんでした:",e); sys.exit(1)
target=None
for p in pages:
    if p.get("instagram_business_account"): target=p; break
if not target:
    print("× Instagramにつながったページが見つかりません。権限の付け忘れかもしれません。"); sys.exit(1)
ig=target["instagram_business_account"]["id"]
name=get(f"{ig}?fields=username").get("username")
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if False else "/Users/mac/Desktop/tamago-shinchoku"
envp=os.path.join(root,".env")
lines=[l for l in (open(envp,encoding="utf-8").read().splitlines() if os.path.exists(envp) else [])
       if not l.startswith(("META_ACCESS_TOKEN=","IG_USER_ID=","FB_PAGE_ID="))]
lines+=[f"META_ACCESS_TOKEN={tok}",f"IG_USER_ID={ig}",f"FB_PAGE_ID={target['id']}"]
open(envp,"w",encoding="utf-8").write("\n".join(lines)+"\n")
print(f"○ 鍵を保存しました。つながった先: @{name}（ページ: {target['name']}）")
PY
echo ""
echo "終わりました。このウィンドウは閉じて大丈夫です。"
read -r _
