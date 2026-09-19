#!/usr/bin/env python3
"""652番: 溜まっているローカルcommitをoriginへ送るだけの一回限りの道具。
既存の巡回(tools/machine_status_push.sh)がMac高負荷で詰まっている間の橋渡し用。
"""
import subprocess

REPO = "/Users/mac/Desktop/tamago-shinchoku"


def run(args):
    r = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=60)
    print(" ".join(args), "->", r.returncode)
    if r.stdout.strip():
        print(r.stdout.strip()[:800])
    if r.stderr.strip():
        print(r.stderr.strip()[:800])
    return r


run(["git", "-c", "credential.helper=!gh auth git-credential", "push", "origin", "main"])
