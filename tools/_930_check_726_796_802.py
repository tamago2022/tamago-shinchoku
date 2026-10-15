#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""726/796/802が「完了の門」のどの条件で落ちるか、現状のstatusに関わらず判定するだけ(書き込みなし)。"""
import json, io, os, re, subprocess
from urllib.parse import urlparse, unquote

REPO = "/Users/mac/tamago/tamago-shinchoku"


def sh(a):
    r = subprocess.run(a, cwd=REPO, capture_output=True)
    class R: pass
    o = R(); o.returncode = r.returncode
    o.stdout = r.stdout.decode('utf-8', 'replace')
    return o


ref = "origin/main"
if sh(["git", "rev-parse", "--verify", ref]).returncode != 0:
    ref = "HEAD"
tree = set(sh(["git", "ls-tree", "-r", "--name-only", ref]).stdout.splitlines())


def blob(p):
    r = sh(["git", "show", f"{ref}:{p}"])
    return r.stdout if r.returncode == 0 else None


def textlen(s):
    s = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', s)
    return len(re.sub(r'\s+', '', re.sub(r'(?s)<[^>]+>', ' ', s)))


def load(p, d):
    try:
        return json.load(io.open(os.path.join(REPO, p), encoding="utf-8"))
    except Exception:
        return d


cc = load("status/content_check_stats.json", {})
ng = set()
for h in cc.get("history", []):
    if h.get("ok") is False and h.get("n") is not None:
        ng.add(h["n"])
oni_seen = set(); oni_ng = set()
try:
    for line in io.open(os.path.join(REPO, "status", "oni_kantoku_log.jsonl"), encoding="utf-8"):
        r = json.loads(line); n = r.get("n")
        if n is None:
            continue
        oni_seen.add(n)
        if r.get("decision") in ("ng", "reject", "fail"):
            oni_ng.add(n)
except Exception:
    pass
ai = load("status/ai_verify_stats.json", {})
ai_seen = set()
for h in (ai.get("history") or []):
    if h.get("n") is not None:
        ai_seen.add(h["n"])


def judge(it):
    n = it.get("n"); urls = it.get("urls") or []
    c = {}
    live = []; dead = []
    for u in urls:
        p = urlparse(u); path = unquote(p.path)
        if p.netloc == "tamago2022.github.io":
            rel = path[len("/tamago-shinchoku/"):] if path.startswith("/tamago-shinchoku/") else path.lstrip("/")
            if rel == "" or rel.endswith("/"):
                rel += "index.html"
            (live if rel in tree else dead).append((u, rel))
        else:
            dead.append((u, None))
    c["①本番にある"] = bool(live) and not dead
    ok2 = bool(live)
    for u, rel in live:
        b = blob(rel)
        if b is None or len(b.encode('utf-8', 'replace')) < 200:
            ok2 = False; break
        if rel.endswith(".html") and textlen(b) < 120:
            ok2 = False; break
    c["②中身がある"] = ok2
    c["③検品を通った"] = (n in oni_seen or n in ai_seen or n in {h.get("n") for h in cc.get("history", [])}) and n not in ng and n not in oni_ng
    c["④第三者が見た"] = bool(it.get("okBy")) or (n in oni_seen) or (n in ai_seen)
    return c, live, dead


da = load("status/done_archive.json", {"items": []})
for it in da.get("items", []):
    if it.get("n") in (726, 796, 802):
        c, live, dead = judge(it)
        print("n=", it.get("n"), "urls=", it.get("urls"))
        print("  jouken=", c, "live=", live, "dead=", dead)
