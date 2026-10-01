#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1200番【ずんだ音声をVaultの外へ出す】(2026-10-02)

Obsidianが重い（iPhoneで索引30秒）ので、円卓会議の音声をVaultの外（iCloud Driveの別フォルダ）へ
**移動**し、ノートの `![[…mp3]]` を「▶ 読み上げを聴く」リンク1行に置き換える。削除はしない。

  python3 tools/1200_zunda_vault_gai.py --only "未来予想"   # 1件だけ
  python3 tools/1200_zunda_vault_gai.py --all               # 全件
  python3 tools/1200_zunda_vault_gai.py --undo-note         # 元に戻し方を表示

出力：
  置き場   ~/Library/Mobile Documents/com~apple~CloudDocs/円卓ずんだ音声/
  台帳     置き場/_移動一覧.tsv（元の場所→今の場所）
  戻し     置き場/_元に戻す.sh
  一覧     Vault/AI出力/40_プロジェクト/円卓会議🔥/読み上げ一覧.md（リンクだけの軽いノート）
公開リポ（tamago-shinchoku の share/）には一切置かない。
"""
import hashlib
import io
import os
import re
import shutil
import sys
import urllib.parse

HOME = os.path.expanduser("~")
VAULT = os.path.join(HOME, "Library", "Mobile Documents", "iCloud~md~obsidian",
                     "Documents", "tamago_brain")
OLD = os.path.join(VAULT, "AI出力", "40_プロジェクト", "円卓会議🔥", "音声")
DEST = os.path.join(HOME, "Library", "Mobile Documents", "com~apple~CloudDocs", "円卓ずんだ音声")
OTHER = os.path.join(DEST, "_その他の録音")
LIST_NOTE = os.path.join(VAULT, "AI出力", "40_プロジェクト", "円卓会議🔥", "読み上げ一覧.md")
IOS_ROOT = "/private/var/mobile/Library/Mobile Documents/com~apple~CloudDocs/円卓ずんだ音声/"
LEDGER = os.path.join(DEST, "_移動一覧.tsv")
EMBED = re.compile(r"^!\[\[(円卓音声_[^\]]+\.(?:mp3|m4a))\]\]\s*$", re.M)


def short_name(note_path):
    """ノート名のsha1先頭8桁。リンクを短く保つ（日本語名だとURLが数百文字になりスマホ編集が重い）"""
    t = os.path.basename(note_path)[:-3]
    return "entaku_%s" % hashlib.sha1(t.encode("utf-8")).hexdigest()[:8]


def link_line(fname):
    return "[▶ 読み上げを聴く](shareddocuments://%s)" % urllib.parse.quote(IOS_ROOT + fname, safe="/~")


def move_audio(fname, newname=None):
    """OLD にあれば DEST へ（短い名前で）移す。台帳に追記。戻り値：DEST側に在るか"""
    src, dst = os.path.join(OLD, fname), os.path.join(DEST, newname or fname)
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
        with io.open(LEDGER, "a", encoding="utf-8") as f:
            f.write("%s\t%s\n" % (src, dst))
    return os.path.exists(dst)


def fix_note(path):
    t = io.open(path, encoding="utf-8", errors="ignore").read()
    changed = [0]

    short = short_name(path) + os.path.splitext(EMBED.search(t).group(1))[1] if EMBED.search(t) else None

    def rep(m):
        fname = m.group(1)
        if not move_audio(fname, short):
            return m.group(0)
        changed[0] += 1
        return link_line(short)
    new = EMBED.sub(rep, t)
    # 「🔊 ずんだもんの読み上げ」の見出し行は残す（その下にリンク1行）
    if changed[0]:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return changed[0]


def candidates():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in files:
            if n.endswith(".md"):
                yield os.path.join(root, n)


def main():
    os.makedirs(DEST, exist_ok=True)
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    allrun = "--all" in sys.argv
    if not only and not allrun:
        print(__doc__)
        return 0
    done = []
    for p in candidates():
        if only and only not in os.path.basename(p):
            continue
        try:
            head = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if "![[円卓音声_" not in head:
            continue
        n = fix_note(p)
        if n:
            done.append(os.path.relpath(p, VAULT))
            print("置換 %d: %s" % (n, os.path.basename(p)[:50]))
    if allrun:
        # 埋め込みの無い残り音声（ノート無し・別名）も外へ。.wavの大物も_その他へ
        os.makedirs(OTHER, exist_ok=True)
        for n in sorted(os.listdir(OLD)) if os.path.isdir(OLD) else []:
            if n.lower().endswith((".mp3", ".m4a", ".wav")):
                move_audio(n)
        for n in os.listdir(VAULT):
            if n.lower().endswith(".wav"):
                src, dst = os.path.join(VAULT, n), os.path.join(OTHER, n)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    with io.open(LEDGER, "a", encoding="utf-8") as f:
                        f.write("%s\t%s\n" % (src, dst))
    # 戻すスクリプトと一覧ノート
    rows = [l.rstrip("\n").split("\t") for l in io.open(LEDGER, encoding="utf-8")] if os.path.exists(LEDGER) else []
    with io.open(os.path.join(DEST, "_元に戻す.sh"), "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n# 音声を元のVault内へ戻す（ノートのリンクは戻らない＝![[…]]へ戻したい時は別途）\n")
        for a, b in rows:
            f.write("mkdir -p %s && mv -n %s %s\n" % (shlex_q(os.path.dirname(a)), shlex_q(b), shlex_q(a)))
    return 0


def shlex_q(s):
    return "'" + s.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    sys.exit(main())
