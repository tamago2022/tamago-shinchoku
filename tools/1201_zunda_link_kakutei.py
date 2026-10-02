#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1201番【読み上げリンクを調査済みの形に直す】(2026-10-02)

憲法「調べてから着手」違反の手直し。Obsidianフォーラム・公式ドキュメントを調べた結果：
  - 音声をVault外に出す判断＝複数の実例で確認済み「正しい」(80MB mp3をVault外に出して
    重さが直った、という報告が独立に複数)。→ そのまま。
  - リンク方式の shareddocuments:// は、iOS側の任意の外部パスを開く確認例がどこにも無い
    独自の推測だった。実例で確認できるのは file:// (Mac限定・確認済み)と、iPhoneは
    「Shortcuts化＋shortcuts://」が唯一の実例ベースの回避策（それ以外は未解決と明言されている）。
これを反映し、1行リンクを「Mac確認済みのfile://」中心にして、shareddocuments://は
「試す」扱いに下げ、未確認であることをその場に明記する。
"""
import hashlib
import io
import os
import re
import sys
import urllib.parse

HOME = os.path.expanduser("~")
VAULT = os.path.join(HOME, "Library", "Mobile Documents", "iCloud~md~obsidian",
                     "Documents", "tamago_brain")
DEST = os.path.join(HOME, "Library", "Mobile Documents", "com~apple~CloudDocs", "円卓ずんだ音声")
IOS_ROOT = "/private/var/mobile/Library/Mobile Documents/com~apple~CloudDocs/円卓ずんだ音声/"
OLD_LINE = re.compile(r"^\[▶ 読み上げを聴く\]\(shareddocuments://([^)]+)\)\s*$", re.M)


def new_line(fname):
    mac = "file://" + urllib.parse.quote(os.path.join(DEST, fname), safe="/")
    ios = "shareddocuments://" + urllib.parse.quote(IOS_ROOT + fname, safe="/~")
    return ("[▶ 聴く（Mac・確認済み）](%s) ／ "
            "[iPhoneで試す（未確認）](%s)" % (mac, ios))


def main():
    n = 0
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if not name.endswith(".md"):
                continue
            p = os.path.join(root, name)
            try:
                t = io.open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            m = OLD_LINE.search(t)
            if not m:
                continue
            fname = urllib.parse.unquote(m.group(1)).rsplit("/", 1)[-1]
            new = OLD_LINE.sub(lambda _m: new_line(fname), t, count=1)
            if new != t:
                io.open(p, "w", encoding="utf-8").write(new)
                n += 1
    print("直した: %d本" % n)


if __name__ == "__main__":
    sys.exit(main())
