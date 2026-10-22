#!/usr/bin/env python3
"""クラウド便の回収：status/cloud_credit/log/*.log から claude.ai/code の URL を拾い、cloud_ledger.json の runs と
Dispatch（status/dispatch_outbox.jsonl）へ1行ずつ。同じ便は1回だけ。--self-test あり。"""
import json, re, sys, os, glob, datetime
F = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(F, "status")
RE_URL = re.compile(r"https://claude\.ai/code/(session_[A-Za-z0-9]+)|\b(session_[A-Za-z0-9]{20,})\b")
RE_PR = re.compile(r"https://github\.com/tamago2022/joy-relief-station/pull/\d+")
def pick(text):
    m = RE_URL.search(text); u = None
    if m: u = "https://claude.ai/code/" + (m.group(1) or m.group(2))
    return u, sorted(set(RE_PR.findall(text)))
def main():
    lp = os.path.join(ST, "cloud_ledger.json"); d = json.load(open(lp, encoding="utf-8"))
    runs = d.setdefault("runs", []); byname = {r.get("name"): r for r in runs if r.get("name")}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); out = []
    for p in sorted(glob.glob(os.path.join(ST, "cloud_credit", "log", "*.log"))):
        name = os.path.basename(p)[:-4]; t = open(p, encoding="utf-8", errors="replace").read()
        url, prs = pick(t); r = byname.get(name)
        if r is None:
            r = {"at_utc": now, "how": "claude -p … --cloud（CLI・本物のクラウドセッション）", "name": name, "session": None, "prs": [], "used_usd": None, "result": "起動待ち"}
            runs.append(r); byname[name] = r
        if url and not r.get("session"):
            r["session"] = url; r["result"] = "起動"; out.append(f"クラウド便「{name}」起動 {url}")
        if prs and prs != r.get("prs"):
            r["prs"] = prs; r["result"] = "PRあり"; out.append(f"クラウド便「{name}」PR {' '.join(prs)}")
        if not url: r["log_tail"] = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)[-600:]
        else: r.pop("log_tail", None)
    json.dump(d, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(os.path.join(ST, "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
        for s in out: f.write(json.dumps({"at": now, "type": "cloud_hassha", "text": s}, ensure_ascii=False) + "\n")
    for s in out: print(s)
if __name__ == "__main__":
    if "--self-test" in sys.argv:
        u, p = pick("x https://claude.ai/code/session_01AbC y https://github.com/tamago2022/joy-relief-station/pull/12")
        ok = u == "https://claude.ai/code/session_01AbC" and p == ["https://github.com/tamago2022/joy-relief-station/pull/12"] and pick("nothing") == (None, [])
        print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
    main()
