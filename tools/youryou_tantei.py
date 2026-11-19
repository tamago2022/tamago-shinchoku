#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の探偵（2026-10-16・たまごさん「空き容量がガンガン減ってる。原因を突き止めて」）。

Mac本体のどこが何GBで、前回からどれだけ増えたかを測る。消さない・動かさない（測るだけ）。
  ・測る場所：/private/tmp・$TMPDIRの親（/private/var/folders/…）・/private/var/vm（スワップ）・
    ~/Library/Caches・~/Library/Application Support の子（Claude のセッションは1つずつ）・
    ~/Library/Developer（Xcode）・~/Movies・~/Documents/AI作業 の子・~/howitholds の子・
    ~/.cache（Whisper・huggingface）・~/tamago の子・~/.tamago・~/.claude・~/.npm 等・
    APFS のローカルスナップショット（tmutil listlocalsnapshots /）
  ・許可ポップアップが出る場所（Containers・Mail・Downloads・Pictures・ゴミ箱 等）には降りない。sudo なし。
  ・結果：status/youryou_tantei/snap-YYYYmmdd-HHMMSS.json（全部）／
          status/public/youryou_tantei.json（上位20・前回との差の上位20・空き・スワップ）
使い方：python3 tools/youryou_tantei.py        （心臓から切り離して走らせる：tools/1144_hanareru.py）
        python3 tools/youryou_tantei.py --self-test
"""
import concurrent.futures as cf
import glob
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
AS = HOME + "/Library/Application Support"
DIR = os.path.join(REPO, "status", "youryou_tantei")
PUB = os.path.join(REPO, "status", "public", "youryou_tantei.json")

NO_ENTER = ("AddressBook", "CallHistoryDB", "com.apple.TCC", "Knowledge", "MobileSync", "FileProvider",
            "CloudDocs", "com.apple.sharedfilelist", "iCloud", "Mobile Documents")


def free_gb():
    st = os.statvfs("/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def du_gb(p, t=900):
    try:
        r = subprocess.run(["du", "-skx", p], capture_output=True, text=True, timeout=t)
        return round(int(r.stdout.split()[0]) / 1048576, 3)
    except Exception:
        return None


def kids(p, skip=()):
    try:
        return [os.path.join(p, n) for n in os.listdir(p)
                if not any(s in n for s in skip) and not os.path.islink(os.path.join(p, n))]
    except Exception:
        return []


def targets():
    t = ["/private/var/vm"]
    t += kids("/private/tmp")
    tmp = tempfile.gettempdir().rstrip("/")            # /private/var/folders/xx/yyyy/T
    t += kids(os.path.dirname(tmp))                     # T・C・0・X
    t += kids(HOME + "/Library/Caches")
    for p in kids(AS, NO_ENTER):
        if os.path.basename(p) == "Claude":
            t += kids(p)
            for s in glob.glob(p + "/local-agent-mode-sessions/*/*"):
                t.append(s)
            t = [x for x in t if not x.endswith("/local-agent-mode-sessions")]
        elif os.path.basename(p) in ("Google", "BraveSoftware"):
            t += kids(p)
        else:
            t.append(p)
    for base in ("/Library/Developer", "/Movies", "/Documents/AI作業", "/howitholds", "/.cache", "/tamago"):
        t += kids(HOME + base)
    for x in (".tamago", ".claude", ".npm", ".cargo", ".rustup", ".ollama", ".docker", ".local", ".bun",
              "go", "Library/Logs", "Library/pnpm", "miniconda3", "anaconda3"):
        if os.path.exists(os.path.join(HOME, x)):
            t.append(os.path.join(HOME, x))
    seen, out = set(), []
    for x in t:
        if x not in seen and os.path.exists(x):
            seen.add(x)
            out.append(x)
    return out


def snapshots():
    try:
        r = subprocess.run(["tmutil", "listlocalsnapshots", "/"], capture_output=True, text=True, timeout=60)
        return [l.strip() for l in r.stdout.splitlines() if "com.apple" in l]
    except Exception as e:
        return ["失敗 %s" % e]


def main():
    os.makedirs(DIR, exist_ok=True)
    t0 = time.time()
    res = {"at": time.strftime("%F %T"), "free_gb_before": free_gb()}
    sizes = {}
    part = os.path.join(DIR, "_tochuu.json")   # 途中経過（殺されても、そこまでの測定は残る）
    tg = targets()
    with cf.ThreadPoolExecutor(4) as ex:
        futs = {ex.submit(du_gb, p, 300): p for p in tg}
        for f in cf.as_completed(futs):
            g = f.result()
            if g is not None:
                sizes[futs[f]] = g
            try:
                json.dump({"at": time.strftime("%F %T"), "done": len(sizes), "of": len(tg), "free_gb": free_gb(),
                           "top": sorted(sizes.items(), key=lambda x: -x[1])[:30]},
                          open(part, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except Exception:
                pass
    res["sizes_gb"] = dict(sorted(sizes.items(), key=lambda x: -x[1]))
    res["swap"] = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout.strip()
    res["local_snapshots"] = snapshots()
    res["free_gb_after"] = free_gb()
    res["sec"] = round(time.time() - t0)
    prevs = sorted(glob.glob(DIR + "/snap-*.json"))
    name = DIR + "/snap-%s.json" % time.strftime("%Y%m%d-%H%M%S")
    json.dump(res, open(name, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pub = {k: res[k] for k in ("at", "free_gb_before", "free_gb_after", "swap", "sec")}
    pub["local_snapshots"] = len(res["local_snapshots"])
    pub["top20"] = [{"p": p.replace(HOME, "~"), "gb": round(g, 2)} for p, g in list(res["sizes_gb"].items())[:20]]
    if prevs:
        prev = json.load(open(prevs[-1], encoding="utf-8"))
        ps = prev.get("sizes_gb", {})
        diff = []
        for p in set(ps) | set(sizes):
            d = (sizes.get(p) or 0) - (ps.get(p) or 0)
            if abs(d) >= 0.05:
                diff.append({"p": p.replace(HOME, "~"), "gb": round(d, 2), "now": round(sizes.get(p) or 0, 2)})
        pub["since"] = prev.get("at")
        pub["free_diff_gb"] = round(res["free_gb_after"] - prev.get("free_gb_after", 0), 2)
        pub["fueta20"] = sorted(diff, key=lambda x: -x["gb"])[:20]
        pub["hetta10"] = sorted(diff, key=lambda x: x["gb"])[:10]
    for old in prevs[:-30]:
        os.remove(old)
    os.makedirs(os.path.dirname(PUB), exist_ok=True)
    json.dump(pub, open(PUB + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(PUB + ".tmp", PUB)
    print(json.dumps(pub, ensure_ascii=False, indent=1))


def self_test():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "a"), "wb").write(b"x" * 2_000_000)
    g = du_gb(d)
    assert g and 0.001 < g < 0.01, g
    assert du_gb(d + "/nai") is None
    os.remove(os.path.join(d, "a"))
    os.rmdir(d)
    print("self-test OK")


if __name__ == "__main__":
    import signal
    for _s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(_s, signal.SIG_IGN)   # 測っている途中で畳まれない（消さない・測るだけの係）
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()
