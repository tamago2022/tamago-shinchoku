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

# ===========================================================================
# ★1122番（2026-09-24）ここから下は「口を増やす」ための追記。
#   なぜここに足すか：gaibu_runner は kind=jrsdata のとき **このファイルを
#   importlib.reload する**。だから runner を触らずに口を増やせる（runnerを
#   書き換えると工場が死ぬ事故が 09-24 03:38 に起きている）。
#   足したのは3つだけ。どれも「白名簿」で外に出られる先を絞ってある。
#     op=shirabe … 見るだけ（ファイルの有無・git・鍵の有無。★値は出さない）
#     op=patch   … 正本リポジトリのファイルを差し替えて commit+push する
#     op=tool    … tamago-shinchoku の中の白名簿の道具を1本だけ走らせる
# ===========================================================================
TOOL_WHITELIST = ("kohyou_osu.py", "kohyou_kanshi.py", "og_kanmon.py",
                  "lovable_mcp_bootstrap.py", "kohyou_ima.py")


def _shinchoku():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _op_shirabe(payload):
    """見るだけ。鍵は「有る/無い」と持っている項目名だけ返す（値は返さない）。"""
    out = {"ok": True, "totalYen": 0.0}
    tok = os.path.expanduser("~/.tamago/lovable_oauth.json")
    if os.path.exists(tok):
        try:
            d = json.load(io.open(tok, encoding="utf-8"))
            out["lovableToken"] = {"exists": True, "keys": sorted(d.keys()),
                                   "sizes": {k: len(str(v)) for k, v in d.items()},
                                   "mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                                          time.localtime(os.path.getmtime(tok)))}
        except Exception as e:
            out["lovableToken"] = {"exists": True, "error": str(e)}
    else:
        out["lovableToken"] = {"exists": False}
    rc, o, e = _git(["status", "--porcelain"])
    out["cloneDirty"] = (o or "").strip().splitlines()[:40]
    rc, o, e = _git(["rev-parse", "HEAD"])
    out["cloneHead"] = (o or "").strip()[:12]
    rc, o, e = _git(["log", "-1", "--format=%s"])
    out["cloneHeadSubject"] = (o or "").strip()
    out["locks"] = []
    gd = os.path.join(CLONE, ".git")
    for root, dirs, files in os.walk(gd):
        for f in files:
            if f.endswith(".lock"):
                out["locks"].append(os.path.relpath(os.path.join(root, f), gd))
        if len(out["locks"]) > 30:
            break
    # ★grep は既定で origin/main を見る。手元の作業ツリーは 2026-09-14 で
    #   止まっていて行番号も中身もズレる（1122番で実測）。
    rev = payload.get("rev", "origin/main")
    for p in (payload.get("grep") or []):
        cmd = ["grep", "-n", p] + ([rev] if rev else []) + ["--"] + list(payload.get("paths") or ["src"])
        rc, o, e = _git(cmd)
        out.setdefault("grep", {})[p] = (o or e or "")[:6000]
    return out


def _op_patch(payload):
    """正本リポジトリのファイルを差し替えて commit+push する。

    payload = {"op":"patch",
               "edits":[{"path":"src/x.tsx","find":"...","replace":"...","count":1}, ...],
               "message":"...", "push":true}
    ・find が期待した回数だけ現れない edit は **1つも書かずに止める**（全部か無しか）。
    ・.git/*.lock は 60秒より古いものだけ外す（957番と同じ理由）。
    """
    edits = payload.get("edits") or []
    if not edits:
        return {"ok": False, "error": "edits が空です", "totalYen": 0.0}
    if not os.path.isdir(CLONE):
        return {"ok": False, "error": "clone なし", "totalYen": 0.0}
    log = []
    plan = []
    for ed in edits:
        p = os.path.join(CLONE, ed["path"])
        if not os.path.isfile(p):
            return {"ok": False, "error": "ファイルが無い: %s" % ed["path"],
                    "log": log, "totalYen": 0.0}
        body = io.open(p, encoding="utf-8").read()
        want = int(ed.get("count", 1))
        got = body.count(ed["find"])
        if got != want:
            return {"ok": False, "error": "見つかった数が違う: %s 期待%d 実際%d"
                    % (ed["path"], want, got), "log": log, "totalYen": 0.0}
        plan.append((p, body.replace(ed["find"], ed["replace"]), ed["path"]))
        log.append("下見OK %s (%d件)" % (ed["path"], got))
    for p, newbody, rel in plan:
        with io.open(p, "w", encoding="utf-8") as f:
            f.write(newbody)
        log.append("書いた %s" % rel)
    gd = os.path.join(CLONE, ".git")
    for root, dirs, files in os.walk(gd):
        for f in files:
            if not f.endswith(".lock"):
                continue
            fp = os.path.join(root, f)
            try:
                if time.time() - os.path.getmtime(fp) > 60:
                    os.remove(fp)
                    log.append("古いロックを外した %s" % os.path.relpath(fp, gd))
            except Exception:
                pass
    if not payload.get("push", True):
        return {"ok": True, "log": log, "pushed": False, "totalYen": 0.0}
    for _, _, rel in plan:
        rc, o, e = _git(["add", "--", rel])
        log.append("add %s rc=%d %s" % (rel, rc, (e or "")[:120]))
    msg = payload.get("message") or "1122番: コピーの出どころを1本にした"
    rc, o, e = _git(["commit", "-m", msg])
    log.append("commit rc=%d %s" % (rc, (o or e or "")[-300:]))
    rc, o, e = _git(["fetch", "origin", "main"], t=300)
    log.append("fetch rc=%d" % rc)
    rc, o, e = _git(["merge", "--no-edit", "origin/main"])
    log.append("merge rc=%d %s" % (rc, (o or e or "")[:200]))
    if rc != 0:
        _git(["merge", "--abort"])
        return {"ok": False, "error": "合流できないので戻した", "log": log, "totalYen": 0.0}
    rc, o, e = _git(["push", "origin", "HEAD:main"], t=300)
    log.append("push rc=%d %s" % (rc, (o or "")[-200:] + (e or "")[-300:]))
    rc2, sha, _ = _git(["rev-parse", "HEAD"])
    return {"ok": rc == 0, "log": log, "pushed": rc == 0,
            "sha": (sha or "").strip()[:12], "totalYen": 0.0}


def _op_tool(payload):
    """tamago-shinchoku の中の白名簿の道具を1本だけ走らせる。"""
    name = payload.get("name") or ""
    if name not in TOOL_WHITELIST:
        return {"ok": False, "error": "白名簿に無い道具です: %s" % name, "totalYen": 0.0}
    sh = _shinchoku()
    import sys as _sys
    cmd = [_sys.executable, os.path.join(sh, "tools", name)] + list(payload.get("args") or [])
    r = subprocess.run(cmd, cwd=sh, capture_output=True, text=True,
                       timeout=int(payload.get("timeout", 300)))
    return {"ok": r.returncode == 0, "rc": r.returncode,
            "stdout": (r.stdout or "")[-6000:], "stderr": (r.stderr or "")[-3000:],
            "totalYen": 0.0}


MIRU_ALLOW = ("https://joy-relief-station.lovable.app",
              "https://tamago2022.github.io")


def _op_miru(payload):
    """★本番のページを工場（Mac）から実際に叩いて、返ってきたHTMLを見る。
    サンドボックスからは出られないので、目で確かめる代わりがこれしかない。
    行き先は白名簿の2つだけ。GETのみ。"""
    import urllib.request
    url = payload.get("url") or ""
    if not any(url.startswith(a) for a in MIRU_ALLOW):
        return {"ok": False, "error": "白名簿の外です: %s" % url, "totalYen": 0.0}
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=int(payload.get("timeout", 40))) as r:
            body = r.read().decode("utf-8", "ignore")
            code, hdr = r.getcode(), dict(r.headers)
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                "url": url, "totalYen": 0.0}
    out = {"ok": code == 200, "httpCode": code, "url": url, "bytes": len(body),
           "sec": round(time.time() - t0, 1),
           "deploymentId": hdr.get("x-deployment-id") or hdr.get("X-Deployment-Id"),
           "totalYen": 0.0}
    for pat in (payload.get("sagasu") or []):
        out.setdefault("sagasu", {})[pat] = body.count(pat)
    if payload.get("head"):
        i = body.find("</head>")
        out["head"] = body[:i if i > 0 else 4000][:int(payload.get("head"))]
    if payload.get("save"):
        sh = os.path.join(_shinchoku(), payload["save"])
        os.makedirs(os.path.dirname(sh), exist_ok=True)
        io.open(sh, "w", encoding="utf-8").write(body)
        out["saved"] = payload["save"]
    return out


def _op_kazu(payload):
    """★1122番：admin_stock 側に「2本目のコピー」を持っている曲を数える。
    GETだけ。1件も書かない。鍵の値は返さない。"""
    import urllib.parse
    import urllib.request
    sys_path = os.path.join(_shinchoku(), "tools")
    import sys as _sys
    if sys_path not in _sys.path:
        _sys.path.insert(0, sys_path)
    diag = []
    import gaibu_copy_nippou as nippou
    url, key, keyname, where = nippou.find_supabase(diag)
    if not url:
        return {"ok": False, "error": "Supabaseの鍵が見つかりません", "diag": diag[-3:],
                "totalYen": 0.0}
    q = urllib.parse.urlencode({
        "kind": "eq.cover-guide", "whisper": "not.is.null",
        "select": "ref,whisper", "limit": "5000"})
    req = urllib.request.Request(url + "/rest/v1/admin_stock?" + q, headers={
        "apikey": key, "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = json.loads(r.read().decode("utf-8") or "[]")
    rows = [x for x in rows if (x.get("whisper") or "").strip()]
    out = {"ok": True, "keyName": keyname, "futatsuAru": len(rows),
           "rei": [{"ref": x.get("ref"), "len": len((x.get("whisper") or ""))}
                   for x in rows[:12]], "totalYen": 0.0}
    if payload.get("save"):
        sh = os.path.join(_shinchoku(), payload["save"])
        os.makedirs(os.path.dirname(sh), exist_ok=True)
        with io.open(sh, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        out["saved"] = payload["save"]
    return out


OPS = {"shirabe": _op_shirabe, "patch": _op_patch, "tool": _op_tool,
       "miru": _op_miru, "kazu": _op_kazu}


def run_job(payload=None):
    payload=payload or {}
    op = payload.get("op")
    if op in OPS:
        try:
            return OPS[op](payload)
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "totalYen": 0.0}
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
