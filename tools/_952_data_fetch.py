import io,json,os,subprocess,time
HERE=os.path.abspath('tools'); REPO=os.path.abspath('.')
OUT=os.path.join(REPO,"status","952_seihon","data")
CLONE=os.path.expanduser("~/Desktop/joy-relief-station")
NAMES=("worlds.ts","foodCards.ts","danceCards.ts","extraCards.ts","summerCards.ts")
ASSETS=("egg-concierge-chef.png","world-food.jpg","world-cute.jpg","world-travel.jpg","world-laugh.jpg")
def _git(a,t=180):
    r=subprocess.run(["git"]+a,cwd=CLONE,capture_output=True,text=True,timeout=t); return r.returncode,r.stdout,r.stderr
def run_job(payload=None):
    log=[];os.makedirs(OUT,exist_ok=True);got=[]
    if not os.path.isdir(CLONE): return {"ok":False,"error":"clone なし","totalYen":0.0}
    ref="origin/main"
    rc,out,err=_git(["ls-tree","-r","-l",ref])
    if rc!=0: ref="HEAD";rc,out,err=_git(["ls-tree","-r","-l",ref])
    io.open(os.path.join(OUT,"_tree_all.txt"),"w",encoding="utf-8").write(out or err)
    log.append("ref=%s 全%d件"%(ref,len((out or '').splitlines())))
    for line in (out or "").splitlines():
        try: meta,path=line.split("\t",1);size=int(meta.split()[3])
        except Exception: continue
        base=os.path.basename(path)
        if base in NAMES and size<1200000:
            rc2,body,e2=_git(["show","%s:%s"%(ref,path)])
            if rc2==0 and body:
                io.open(os.path.join(OUT,base),"w",encoding="utf-8").write("\n".join(body.splitlines()[:1400]))
                got.append(base);log.append("%s (%d bytes)"%(path,size))
        if base in ASSETS and size<900000:
            r=subprocess.run(["git","show","%s:%s"%(ref,path)],cwd=CLONE,capture_output=True,timeout=120)
            if r.returncode==0 and r.stdout:
                io.open(os.path.join(OUT,base),"wb").write(r.stdout)
                got.append(base);log.append("%s (%d bytes・画像)"%(path,size))
    io.open(os.path.join(OUT,"_log.txt"),"w",encoding="utf-8").write("%s\n\n%s\n"%(time.strftime("%Y-%m-%d %H:%M:%S"),"\n".join(log)))
    return {"ok":bool(got),"got":got,"log":log,"totalYen":0.0}
