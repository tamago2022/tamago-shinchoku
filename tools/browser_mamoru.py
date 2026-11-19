#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ブラウザ（Brave・Chrome）のフォルダは、どの片付け係も一切触らない（憲法・2026-10-17）。

きっかけ（2026-10-16〜17 実測）：shimau.py の「ブラウザのキャッシュ掃除」が Brave の
Service Worker/ScriptCache まで消し、拡張機能「Mark tab manager」（タブの自動グループ化）が
動かなくなった疑い。たまごさん「今後どの片付け係もブラウザ（Brave・Chrome）のフォルダは一切触らない」。

使い方：片付け係の「消す」関数の頭で
    import browser_mamoru
    if browser_mamoru.mamoru(path): return   # ブラウザのフォルダなら消さない
工場の自動操作用の使い捨て（$TMPDIR の playwright*・~/.tamago/chrome-* 等）は「たまごさんのブラウザ」ではないので対象外。
逆テスト：python3 tools/browser_mamoru.py --self-test
"""
import os
import sys

HOME = os.path.expanduser("~")
MAMORU = tuple(os.path.join(HOME, p) for p in (
    "Library/Application Support/BraveSoftware",
    "Library/Caches/BraveSoftware",
    "Library/Caches/com.brave.Browser",
    "Library/Application Support/Google/Chrome",      # Chrome・Chrome-headless・Chrome Beta など全部
    "Library/Caches/Google/Chrome",
    "Library/Caches/com.google.Chrome",
    "Library/Saved Application State/com.brave.Browser.savedState",
    "Library/Saved Application State/com.google.Chrome.savedState",
))


def mamoru(path):
    """ブラウザのフォルダ（とその中・その親まるごと）なら True＝消してはいけない。"""
    try:
        ap = os.path.abspath(os.path.expanduser(path))
    except Exception:
        return True
    for m in MAMORU:
        if ap == m or ap.startswith(m) or m.startswith(ap.rstrip("/") + "/"):
            return True   # 中身・前方一致（Chrome-headless 等）・親（~/Library/Caches まるごと等）も守る
    return False


def self_test():
    assert mamoru(HOME + "/Library/Caches/BraveSoftware")
    assert mamoru(HOME + "/Library/Application Support/BraveSoftware/Brave-Browser/Default/Service Worker/ScriptCache")
    assert mamoru(HOME + "/Library/Application Support/Google/Chrome-headless")
    assert mamoru(HOME + "/Library/Caches/com.brave.Browser/org.sparkle-project.Sparkle/PersistentDownloads")
    assert mamoru(HOME + "/Library/Caches"), "親まるごとを消すのも止める"
    assert not mamoru(HOME + "/Library/Caches/pip")
    assert not mamoru("/private/var/folders/x/T/playwright_chromiumdev_profile-abc")
    assert not mamoru(HOME + "/.tamago/chrome-publish/Default/Cache")
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
