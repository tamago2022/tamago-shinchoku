#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1141番【完了の門】自己申告の「完了」を、実体で採点し直す係。

★決まりは status/KANRYO.md。4条件（本番にある／中身がある／検品を通った／第三者が見た）。
★1つでも欠けたら done ではない。--apply を付けると台帳を awaiting_check へ戻す。
★0円。AIを1回も呼ばない。ネットにも出ない（GitHub Pagesは公開ブランチの実体で判定する）。
出力: status/1141/mon.json
"""
import json,io,os,re,sys,subprocess,datetime
from urllib.parse import urlparse,unquote
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(REPO,"status","1141")
APPLY="--apply" in sys.argv
def sh(a):
    r=subprocess.run(a,cwd=REPO,capture_output=True)
    class R:pass
    o=R(); o.returncode=r.returncode
    o.stdout=r.stdout.decode('utf-8','replace'); o.raw=r.stdout
    return o
ref="origin/main"
if sh(["git","rev-parse","--verify",ref]).returncode!=0: ref="HEAD"
tree=set(sh(["git","ls-tree","-r","--name-only",ref]).stdout.splitlines())
def blob(p):
    r=sh(["git","show",f"{ref}:{p}"])
    return r.stdout if r.returncode==0 else None
def textlen(s):
    s=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',s)
    return len(re.sub(r'\s+','',re.sub(r'(?s)<[^>]+>',' ',s)))

# 条件3の材料：検品の台帳
def load(p,d):
    try: return json.load(io.open(os.path.join(REPO,p),encoding="utf-8"))
    except Exception: return d
cc=load("status/content_check_stats.json",{})
ng=set()
for h in cc.get("history",[]):
    if h.get("ok") is False and h.get("n") is not None: ng.add(h["n"])
oni_seen=set();oni_ng=set()
try:
    for line in io.open(os.path.join(REPO,"status","oni_kantoku_log.jsonl"),encoding="utf-8"):
        r=json.loads(line); n=r.get("n")
        if n is None: continue
        oni_seen.add(n)
        if r.get("decision") in ("ng","reject","fail"): oni_ng.add(n)
except Exception: pass
ai=load("status/ai_verify_stats.json",{})
ai_seen=set()
for h in (ai.get("history") or []):
    if h.get("n") is not None: ai_seen.add(h["n"])

def judge(it):
    n=it.get("n"); urls=it.get("urls") or []
    c={}
    # ① 本番に出ている
    live=[];dead=[]
    for u in urls:
        p=urlparse(u); path=unquote(p.path)
        if p.netloc=="tamago2022.github.io":
            rel=path[len("/tamago-shinchoku/"):] if path.startswith("/tamago-shinchoku/") else path.lstrip("/")
            if rel=="" or rel.endswith("/"): rel+="index.html"
            (live if rel in tree else dead).append((u,rel))
        else:
            dead.append((u,None))   # 外から確かめられない＝通さない
    c["①本番にある"]= bool(live) and not dead
    # ② 中身がある
    ok2=bool(live)
    for u,rel in live:
        b=blob(rel)
        if b is None or len(b.encode('utf-8','replace'))<200: ok2=False;break
        if rel.endswith(".html") and textlen(b)<120: ok2=False;break
    c["②中身がある"]=ok2
    # ③ 検品を通った
    c["③検品を通った"]= (n in oni_seen or n in ai_seen or n in {h.get("n") for h in cc.get("history",[])}) and n not in ng and n not in oni_ng
    # ④ 第三者が見た
    c["④第三者が見た"]= bool(it.get("okBy")) or (n in oni_seen) or (n in ai_seen)
    return c

def run():
    da=load("status/done_archive.json",{"items":[]})
    q=load("status/queue.json",{"items":[]})
    rows=[];pass_=0
    for src,items in (("done_archive",da.get("items",[])),("queue",q.get("items",[]))):
        for it in items:
            if it.get("status")!="done": continue
            c=judge(it)
            ok=all(c.values())
            if ok: pass_+=1
            rows.append({"src":src,"n":it.get("n"),"title":(it.get("title") or "")[:70],
                         "pass":ok,"jouken":c,
                         "kaketa":[k for k,v in c.items() if not v]})
    res={"at":datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
         "通した":pass_,"弾いた":len(rows)-pass_,"見た":len(rows),
         "弾いた率":round((len(rows)-pass_)*100/max(1,len(rows)),1),
         "apply":APPLY,"rows":rows}
    os.makedirs(OUT,exist_ok=True)
    json.dump(res,io.open(os.path.join(OUT,"mon.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    if APPLY:
        bad={r["n"] for r in rows if not r["pass"]}
        for path,key in (("status/done_archive.json","items"),("status/queue.json","items")):
            d=load(path,None)
            if not d: continue
            ch=0
            for it in d.get(key,[]):
                if it.get("status")=="done" and it.get("n") in bad:
                    it["status"]="awaiting_check"
                    it["kanryoGate"]="門を通らなかったので未完了へ戻した（status/KANRYO.md）"
                    ch+=1
            if ch:
                full=os.path.join(REPO,path)
                bak=full+".bak1141"
                if not os.path.exists(bak):
                    io.open(bak,"w",encoding="utf-8").write(io.open(full,encoding="utf-8").read())
                # ★同時書き込み対策：読んだ後に他の係が触っていたら、読み直してやり直す（最大5回）
                for _ in range(5):
                    mt=os.path.getmtime(full)
                    d2=load(path,None)
                    if not d2: break
                    for it in d2.get(key,[]):
                        if it.get("status")=="done" and it.get("n") in bad:
                            it["status"]="awaiting_check"
                            it["kanryoGate"]="門を通らなかったので未完了へ戻した（status/KANRYO.md）"
                    tmp=full+".tmp1141"
                    json.dump(d2,io.open(tmp,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
                    if os.path.getmtime(full)==mt:
                        os.replace(tmp,full); break
                    os.remove(tmp)
            res.setdefault("applied",{})[path]=ch
    print(json.dumps({k:v for k,v in res.items() if k!="rows"},ensure_ascii=False))
run()
