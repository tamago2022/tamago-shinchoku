#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vault の dataless（iCloudにしか中身が無い）ファイルを本体へ戻す・第2版（2026-10-14）。
第1版：python で読むと全部失敗（451件連続）。ここでは方法を順に試し、効いた方法で全部戻す。
  A) brctl download <path>   B) fileproviderctl materialize <path>   C) /bin/cat <path>
status/obsidian_modosu2.go → status/obsidian_modosu2.json。iCloud/Obsidianの設定には触らない。"""
import json, os, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "obsidian_modosu2.go")
OUT = os.path.join(REPO, "status", "obsidian_modosu2.json")
VAULT = HOME + "/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
SF_DATALESS = 0x40000000


def dataless(p):
    try:
        return bool(os.lstat(p).st_flags & SF_DATALESS)
    except Exception:
        return False


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def run(cmd, t=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return r.returncode, (r.stdout + r.stderr).strip()[:200]
    except Exception as e:
        return -1, str(e)[:200]


METHODS = {
    "brctl": lambda p: run(["brctl", "download", p]),
    "fileproviderctl": lambda p: run(["fileproviderctl", "materialize", p]),
    "cat": lambda p: run(["/bin/sh", "-c", 'cat "$1" > /dev/null', "x", p]),
}


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    subprocess.run(["pkill", "-f", "tools/obsidian_modosu.py"])
    res = {"started": time.strftime("%F %T"), "free_gb": free_gb(), "tests": {}, "state": "試している"}
    files = []
    for dp, dns, fns in os.walk(VAULT):
        for fn in fns:
            p = os.path.join(dp, fn)
            if dataless(p):
                files.append(p)
    files.sort(key=lambda p: (0 if "/.obsidian/" in p else 1 if p.endswith(".md") else 2))
    res["dataless_before"] = len(files)
    save(res)
    good = None
    # 1つのフォルダ全体を一度に頼めるか（brctl はフォルダ指定で中身ごと落とす）
    for name in ("brctl", "fileproviderctl", "cat"):
        sample = [p for p in files if dataless(p)][:3]
        if not sample:
            break
        outs = []
        for p in sample:
            outs.append(METHODS[name](p))
        time.sleep(20)
        ok = sum(1 for p in sample if not dataless(p))
        res["tests"][name] = {"ok": ok, "of": len(sample), "out": outs}
        save(res)
        if ok:
            good = name
            break
    res["method"] = good
    if good:
        res["state"] = "戻している"
        save(res)
        if good == "brctl":
            run(["brctl", "download", VAULT], 600)  # フォルダごと
        n = 0
        for p in files:
            if free_gb() < 25:
                res["stopped"] = "空き25GB未満で止めた"
                break
            if dataless(p):
                METHODS[good](p)
                n += 1
                if n % 100 == 0:
                    res["requested"] = n
                    save(res)
        time.sleep(120)
    left = 0
    for dp, dns, fns in os.walk(VAULT):
        for fn in fns:
            if dataless(os.path.join(dp, fn)):
                left += 1
    res.update(dataless_after=left, state="完了", finished=time.strftime("%F %T"), free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
