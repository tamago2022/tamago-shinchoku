#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【魂の門】魂の口が全部通るかを1発で確かめる。

    python3 tamashii/mon.py

  ここが緑でないものは「できた」と言わない（憲法第6条・完了の定義）。
  ★AIを1回も呼ばない。★0円。★何回走らせても同じ答え。
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SHIKEN = [
    ("魂を出す（coverGuide → tamashii.json）", [sys.executable, "tamashii/shukkoshi.py", "--self-test"]),
    ("魂の口（osusume / shiraberu / jinkaku）", [sys.executable, "tamashii/kuchi.py", "--self-test"]),
    ("突き合わせ表を書き直す", [sys.executable, "tamashii/kuchi.py", "--testvec"]),
    ("ブラウザ版の口が Python版と一致するか", ["node", "tamashii/kuchi.mjs", "--self-test"]),
    ("HTTPの窓口（実際に叩いて200）", [sys.executable, "tamashii/server.py", "--self-test"]),
    ("脳の差込口（3つとも魂を持っていないか）", [sys.executable, "nou/sashikomiguchi.py", "--self-test"]),
    ("覆面10問（脳なしで測れる分・0円）", [sys.executable, "nou/fukumen10.py", "--self-test"]),
]


def main() -> int:
    ng = []
    for namae, cmd in SHIKEN:
        if cmd[0] == "node" and not any(
            os.access(os.path.join(p, "node"), os.X_OK) for p in os.environ.get("PATH", "").split(":") if p
        ):
            print(f"― {namae} … node が無いので飛ばした（★通っていない扱い）")
            ng.append(namae)
            continue
        if not os.path.exists(os.path.join(REPO, cmd[1])):
            print(f"― {namae} … {cmd[1]} がまだ無い")
            ng.append(namae)
            continue
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        last = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
        print(f"{'○' if r.returncode == 0 else '✕'} {namae}")
        for l in last[-4:]:
            print(f"    {l}")
        if r.returncode != 0:
            ng.append(namae)

    print()
    if ng:
        print(f"✕ 通っていない門が {len(ng)} 個ある: {' / '.join(ng)}")
        return 1
    print("○ 魂の門、全部通った。脳を差し替えてもここは1バイトも変わらない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
