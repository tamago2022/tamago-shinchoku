#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""見回りの成果を7日分の記録から数える（2026-11-05 たまごさん「1日に何百回も見回って、役に立っているのか」）。

Mac で走らせる（mac_jobs 経由）。読むだけ。何も止めない・消さない。
  python3 tools/mimawari_shousa.py --claude   # ~/.claude/projects の7日分の会話の「最初の一言」を数える
  python3 tools/mimawari_shousa.py --ikkatsu  # 心臓・相乗り・launchd を洗い出して、7日の証拠を集める
結果：status/mihari_tanaoroshi/claude_7d.json ・ shousa_7d.json
"""
import collections, glob, io, json, os, re, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "mihari_tanaoroshi")
NOW = time.time()
D7 = NOW - 7 * 86400


def claude_census():
    base = os.path.expanduser("~/.claude/projects")
    c = collections.Counter(); n = 0; ex = {}
    for p in glob.glob(os.path.join(base, "*", "*.jsonl")):
        try:
            if os.path.getmtime(p) < D7:
                continue
        except Exception:
            continue
        n += 1
        first = ""
        try:
            with io.open(p, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 30:
                        break
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("type") == "user":
                        m = o.get("message", {}).get("content")
                        if isinstance(m, list):
                            m = " ".join(x.get("text", "") for x in m if isinstance(x, dict))
                        first = (m or "").strip()
                        break
        except Exception:
            pass
        key = re.sub(r"[0-9０-９]+", "#", first.replace("\n", " "))[:40]
        c[key] += 1
        ex.setdefault(key, os.path.basename(os.path.dirname(p)))
    res = {"at": time.strftime("%F %T"), "files_7d": n,
           "top": [{"n": v, "head": k, "dir": ex[k]} for k, v in c.most_common(80)]}
    json.dump(res, open(os.path.join(OUT, "claude_7d.json"), "w"), ensure_ascii=False, indent=1)
    print(n)


def tail_lines_7d(path, maxbytes=3_000_000):
    """ログの最後の方から、7日以内らしい行を返す（日付が読めない行も含める）。"""
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as f:
            if sz > maxbytes:
                f.seek(sz - maxbytes)
            txt = f.read().decode("utf-8", "replace")
    except Exception:
        return []
    lim = time.strftime("%Y-%m-%d", time.localtime(D7))
    out = []
    for ln in txt.splitlines():
        m = re.search(r"(20\d\d-\d\d-\d\d)", ln)
        if m and m.group(1) < lim:
            continue
        out.append(ln)
    return out


SEIKA = re.compile(r"(直し|直した|消し|消した|片付け|積ん|積み|公開|push|pushed|commit|起こし|戻し|蹴り直|再開|回した|入れた|訳し|付けた|書いた|送っ|fixed|moved|deleted|queued|畳ん|上げ)")
KARA = re.compile(r"(何もしない|変化なし|異常なし|スキップ|skip|見送り|待ち|なし$|0件|空振り|nothing|no change|unchanged|既に)")


def ikkatsu():
    hb = io.open(os.path.join(REPO, "tools", "heartbeat.sh"), encoding="utf-8").read().splitlines()
    ts = io.open(os.path.join(REPO, "tools", "top_status.py"), encoding="utf-8").read().splitlines()
    ent = []
    for i, ln in enumerate(hb):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = re.search(r'tools/([\w/]+\.(?:py|sh|mjs))', s)
        if not m:
            m2 = re.search(r'(\$HOME/[\w/.-]+\.sh)', s)
            if not m2:
                continue
            name = m2.group(1)
        else:
            name = m.group(1)
        if name in ("heartbeat.sh",):
            continue
        te = re.findall(r"tick_every (\d+)", s)
        go = re.search(r'-f "\$REPO/status/([\w.]+\.go)"', s)
        if te:
            per_day = int(86400 / (15 * int(te[0])))
            kankaku = "%s秒おき" % (15 * int(te[0]))
        elif go:
            per_day = 0; kankaku = "%s があるとき" % go.group(1)
        else:
            per_day = 5760; kankaku = "毎周（15秒）"
        if go and te:
            kankaku += "＋" + go.group(1)
        ent.append({"name": name, "kind": "心臓", "line": i + 1, "kankaku": kankaku, "per_day": per_day})
    for i, ln in enumerate(ts):
        s = ln.strip()
        m = re.match(r'_okosu\("([\w/.]+)"', s)
        if not m:
            continue
        ent.append({"name": m.group(1), "kind": "心臓の相乗り", "line": i + 1,
                    "kankaku": "毎周（15秒・中で間引くものあり）", "per_day": 5760})
    # launchd
    for p in sorted(glob.glob(os.path.expanduser("~/Library/LaunchAgents/com.tamago.*.plist"))):
        try:
            j = json.loads(subprocess.run(["plutil", "-convert", "json", "-o", "-", p], capture_output=True, text=True, timeout=10).stdout)
        except Exception:
            continue
        lab = j.get("Label")
        if j.get("KeepAlive"):
            per = 1; kk = "常駐"
        elif j.get("StartInterval"):
            per = int(86400 / int(j["StartInterval"])); kk = "%s秒おき" % j["StartInterval"]
        elif j.get("StartCalendarInterval"):
            sc = j["StartCalendarInterval"]; sc = sc if isinstance(sc, list) else [sc]
            per = len(sc); kk = "毎日 " + "・".join("%02d:%02d" % (x.get("Hour", 0), x.get("Minute", 0)) for x in sc)
        else:
            per = 0; kk = "読み込み時だけ"
        ent.append({"name": lab, "kind": "launchd", "kankaku": kk, "per_day": per,
                    "prog": " ".join(j.get("ProgramArguments", []))[-120:], "plist": p})
    # 証拠：outbox
    ob = collections.defaultdict(list)
    for ln in tail_lines_7d(os.path.join(ST, "dispatch_outbox.jsonl"), 30_000_000):
        try:
            o = json.loads(ln)
        except Exception:
            continue
        ob[str(o.get("from") or o.get("type") or "?")].append(re.sub(r"\d+", "#", str(o.get("what") or o.get("text") or ""))[:50])
    # 証拠：git（7日）
    try:
        gl = subprocess.run(["git", "-C", REPO, "log", "--since=7.days", "--format=%s"], capture_output=True, text=True, timeout=60).stdout.splitlines()
    except Exception:
        gl = []
    jrs = "/Users/mac/Desktop/joy-relief-station"
    try:
        gl2 = subprocess.run(["git", "-C", jrs, "log", "origin/main", "--since=7.days", "--format=%s"], capture_output=True, text=True, timeout=60).stdout.splitlines()
    except Exception:
        gl2 = []
    # 証拠：ファイル
    allfiles = []
    for root, dirs, files in os.walk(ST):
        if root.count(os.sep) - ST.count(os.sep) > 2:
            dirs[:] = []
            continue
        for fn in files:
            if fn.endswith((".log", ".jsonl", ".json", ".txt")):
                allfiles.append(os.path.join(root, fn))
    for e in ent:
        stem = os.path.basename(e["name"]).rsplit(".", 1)[0]
        if e["kind"] == "launchd":
            stem = e["name"].replace("com.tamago.", "").split(".")[-1]
        keys = {stem, stem.replace("-", "_")}
        e["outbox_7d"] = sum(len(ob[k]) for k in keys if k in ob)
        e["outbox_kinds"] = len(set(sum((ob[k] for k in keys if k in ob), [])))
        e["git_7d"] = sum(1 for s in gl if stem in s) + sum(1 for s in gl2 if stem in s)
        logs = [p for p in allfiles if stem in os.path.basename(p) or ("/%s/" % stem) in p]
        if e.get("prog"):
            for tok in re.findall(r"(/Users/mac/[\w/.\-]+\.log)", json.dumps(e)):
                logs.append(tok)
        s_n = k_n = l_n = 0; newest = 0
        for p in logs[:6]:
            try:
                newest = max(newest, os.path.getmtime(p))
            except Exception:
                pass
            if p.endswith((".log", ".jsonl", ".txt")):
                for ln in tail_lines_7d(p, 1_500_000):
                    l_n += 1
                    if SEIKA.search(ln):
                        s_n += 1
                    elif KARA.search(ln):
                        k_n += 1
        e["log_files"] = [os.path.relpath(p, REPO) if p.startswith(REPO) else p for p in logs[:6]]
        e["log_lines_7d"] = l_n; e["log_seika_7d"] = s_n; e["log_kara_7d"] = k_n
        e["log_newest"] = time.strftime("%m-%d %H:%M", time.localtime(newest)) if newest else ""
        try:
            src = os.path.join(REPO, "tools", e["name"]) if e["kind"] != "launchd" else ""
            txt = io.open(src, encoding="utf-8", errors="replace").read() if src and os.path.exists(src) else ""
            e["claude_yobu"] = bool(re.search(r'claude_bin\(\)|"claude",\s*"-p"|claude -p|_claude_bin\(\)', txt))
        except Exception:
            e["claude_yobu"] = False
    res = {"at": time.strftime("%F %T"), "entries": ent,
           "outbox_from_7d": {k: len(v) for k, v in sorted(ob.items(), key=lambda x: -len(x[1]))[:80]},
           "git_7d": len(gl), "git_jrs_7d": len(gl2)}
    json.dump(res, open(os.path.join(OUT, "shousa_7d.json"), "w"), ensure_ascii=False, indent=1)
    print(len(ent))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if "--claude" in sys.argv:
        claude_census()
    if "--ikkatsu" in sys.argv:
        ikkatsu()
