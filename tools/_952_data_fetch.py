import io,json,os,subprocess,time
HERE=os.path.abspath('tools'); REPO=os.path.abspath('.')
OUT=os.path.join(REPO,"status","952_seihon","data")
CLONE=os.path.expanduser("~/Desktop/joy-relief-station")
NAMES=("worlds.ts","foodCards.ts","danceCards.ts","extraCards.ts","summerCards.ts")
ASSETS=("egg-concierge-chef.png","world-food.jpg","world-cute.jpg","world-travel.jpg","world-laugh.jpg")
def _git(a,t=180):
    r=subprocess.run(["git"]+a,cwd=CLONE,capture_output=True,text=True,timeout=t); return r.returncode,r.stdout,r.stderr
def _fetch_paths(payload):
    """★追加：正本リポジトリから「指定した道のファイルだけ」を読み取り専用で持ち帰る。
    payload = {"files":["docs/.../02.html", ...], "out":"status/xxx", "fetch":true}
    書き込みは一切しない（fetch と show だけ）。"""
    repo2=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out=os.path.join(repo2,payload.get("out") or "status/952_seihon/concierge")
    os.makedirs(out,exist_ok=True)
    log=[];got=[]
    if not os.path.isdir(CLONE):
        return {"ok":False,"error":"clone なし","totalYen":0.0}
    if payload.get("fetch",True):
        rc,o,e=_git(["fetch","origin","main"],t=300)
        log.append("fetch rc=%d %s"%(rc,(e or "")[-300:]))
    ref="origin/main"
    rc,o,e=_git(["rev-parse",ref])
    if rc!=0:
        ref="HEAD";rc,o,e=_git(["rev-parse",ref])
    log.append("ref=%s %s"%(ref,(o or "").strip()[:12]))
    rc,tree,e=_git(["ls-tree","-r","--name-only",ref,"docs/design/concierge-html-css/"])
    io.open(os.path.join(out,"_tree.txt"),"w",encoding="utf-8").write(tree or e or "")
    log.append("tree %d件"%len((tree or "").splitlines()))
    for path in (payload.get("bin") or []):
        r=subprocess.run(["git","show","%s:%s"%(ref,path)],cwd=CLONE,capture_output=True,timeout=120)
        if r.returncode==0 and r.stdout:
            io.open(os.path.join(out,os.path.basename(path)),"wb").write(r.stdout)
            got.append(os.path.basename(path));log.append("取得(画像) %s (%d bytes)"%(path,len(r.stdout)))
        else:
            log.append("×取れない %s"%path)
    for path in (payload.get("files") or []):
        rc2,body,e2=_git(["show","%s:%s"%(ref,path)])
        if rc2==0 and body is not None:
            io.open(os.path.join(out,os.path.basename(path)),"w",encoding="utf-8").write(body)
            got.append(os.path.basename(path));log.append("取得 %s (%d字)"%(path,len(body)))
        else:
            log.append("×取れない %s: %s"%(path,(e2 or "")[:200]))
    io.open(os.path.join(out,"_log.txt"),"w",encoding="utf-8").write("%s\n\n%s\n"%(time.strftime("%Y-%m-%d %H:%M:%S"),"\n".join(log)))
    return {"ok":bool(got),"got":got,"log":log,"totalYen":0.0}

def run_job(payload=None):
    payload=payload or {}
    if payload.get("files") or payload.get("bin"):
        return _fetch_paths(payload)
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
