#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1141番【棚合わせ】覆面100人の「好きなもの」を棚の索引に1件ずつ照合する。
★0円・AIを呼ばない・ネットに出ない・ブラウザを使わない。
★測るのは飴玉の前半＝在庫があるか。後半（あるのに出せない＝案内人）は実機でしか測れないので混ぜない。
出力 status/1141/zaiko_rows.json / zaiko.json"""
import json,io,os,re,glob
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS=os.path.join(REPO,"share","check","assets","953-songs")
OUT=os.path.join(REPO,"status","1141")
def _norm(s):
    s=(s or "").strip().lower()
    return re.sub(r"[\s　'’\"“”・･,\.\-_!?()\[\]:;/&+]","",s)
arts=set();songs=set()
d=json.load(io.open(SONGS+"/head.json",encoding="utf-8"))
for a in d.get("A",[]):
    arts.add(_norm(a.get("n")))
    for al in (a.get("al") or []): arts.add(_norm(al))
for p in glob.glob(SONGS+"/t/*.json"):
    try:
        for row in json.load(io.open(p,encoding="utf-8")):
            if isinstance(row,list) and len(row)>2: songs.add(_norm(row[2]))
    except Exception: pass
# ★ジャンル・気分の言葉は「棚に無い名前」ではない。仕入れの名前と混ぜない。
GENRE=re.compile(r"(音楽|ポップス|ポップ|ロック|ヒップホップ|ラップ|バラード|フォーク|アンビエント|ジャズ|ソウル|ゴスペル|タンゴ|ボレロ|フラメンコ|カリプソ|サントラ|サウンドトラック|歌謡曲|ブーンバップ|ダンス|アフロビーツ|の曲|が好き$|流れてくる)")
def toks(s):
    s=re.split(r"[。]",re.sub(r"[。\.]$","",(s or "").strip()))[0]
    parts=re.split(r"[、,／/]|と(?=[A-Za-z゠-ヿ一-鿿฀-๿؀-ۿ가-힯])",s)
    out=[]
    for p in parts:
        p=(p or "").strip(" 　・。")
        p=re.sub(r"が好き$","",p).strip()
        if p and len(p)<=28: out.append(p)
    return out
def hit(name):
    k=_norm(name)
    if len(k)<3: return "fumei"
    if k in arts: return "artist"
    if k in songs: return "song"
    for a in arts:
        if len(a)>=4 and (k in a or a in k): return "artist_yure"
    return None
y=json.load(io.open(os.path.join(REPO,"status","kyaku50","yaku.json"),encoding="utf-8"))["yaku"]
rows=[]
for p in y:
    w=toks(p.get("suki"))
    res=[(x,hit(x)) for x in w]
    ari=[x for x,r in res if r in ("artist","song","artist_yure")]
    nashi=[x for x,r in res if r is None and not GENRE.search(x)]
    genre=[x for x,r in res if r is None and GENRE.search(x)]
    rows.append({"id":p["id"],"kuni":p.get("kuni"),"toshi":p.get("toshi"),"go":p.get("go"),
                 "hoshii":w,"ari":ari,"nashi":nashi,"genre":genre,"amedama":bool(ari)})
zz=[r for r in rows if not r["amedama"]]
kaimono=sorted({x for r in rows for x in r["nashi"]})
summary={"人数":len(rows),"在庫ゼロ人数":len(zz),"在庫ゼロ率":round(len(zz)*100/max(1,len(rows)),1),
         "買い物リスト件数":len(kaimono),
         "ジャンル希望で棚に無いもの":sorted({x for r in rows for x in r["genre"]}),
         "測ったもの":"在庫だけ（案内人が出せるかは含まない）","円":0}
os.makedirs(OUT,exist_ok=True)
json.dump(rows,io.open(os.path.join(OUT,"zaiko_rows.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump({"summary":summary,"kaimono":kaimono},io.open(os.path.join(OUT,"zaiko.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(json.dumps(summary,ensure_ascii=False)[:400])
