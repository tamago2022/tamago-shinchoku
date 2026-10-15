#!/usr/bin/env python3
"""許可ゼロ設定（2026-10-08・たまごさん指示）

目的：たまごさんの画面に出る許可・承認ポップアップを、設定で「出せない」状態にする。
やること（1回走らせれば全部済む・何度走らせても同じ結果）：
  1. 今日のセッションログ（~/Library/Application Support/Claude 配下・~/.claude/projects）を読むだけで、
     ポップアップを出す道具（内蔵ブラウザ・computer-use・request_access・フォルダ要求・osascript）を数える。
  2. ~/.claude/settings.json を ~/.tamago/backup/ に控えてから、permissions に deny/allow を追記（1回の書き込み）。
     Claude in Chrome（mcp__claude-in-chrome__*）は deny しない。
  3. 読み直して入ったかを確かめ、status/kyoka_zero.json に書く（health.json に写る）。
元に戻す：cp ~/.tamago/backup/settings.json.<日時> ~/.claude/settings.json
"""
import glob, json, os, re, shutil, time
from collections import Counter

HOME = os.path.expanduser("~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
BACKUP_DIR = os.path.join(HOME, ".tamago", "backup")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "status", "kyoka_zero.json")

DENY = ["mcp__Claude_Browser__*", "mcp__computer-use__*", "mcp__cowork__request_cowork_directory"]
ALLOW = ["WebFetch", "WebSearch", "Bash", "Read", "Write", "Edit", "Glob", "Grep"]
TITLES = ["弾き語り特集を本番へ", "弾き語り特集マガジン", "リップシンク動画とお金台帳"]
# ポップアップの元になる道具の見分け方（名前の一部）
POPUP = {
    "mcp__Claude_Browser__": "mcp__Claude_Browser__*",
    "mcp__computer-use__": "mcp__computer-use__*",
    "request_cowork_directory": "mcp__cowork__request_cowork_directory",
    "request_access": "request_access",
    "osascript": "Bash(osascript*)",
}


def scan_today():
    today = time.strftime("%Y-%m-%d")
    roots = [os.path.join(HOME, "Library", "Application Support", "Claude"), os.path.join(HOME, ".claude", "projects")]
    hits, files = Counter(), 0
    for root in roots:
        for p in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True) + glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
            try:
                if time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))) != today or os.path.getsize(p) > 200_000_000:
                    continue
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if not any(t in txt for t in TITLES):
                continue
            files += 1
            for name in re.findall(r'"name"\s*:\s*"([^"]+)"', txt):
                for key, rule in POPUP.items():
                    if key in name:
                        hits[rule] += 1
            hits["Bash(osascript*)"] += len(re.findall(r'"command"\s*:\s*"[^"]*osascript', txt))
    return files, {k: v for k, v in hits.items() if v}


def main():
    files, hits = scan_today()
    culprits = sorted(hits, key=lambda k: -hits[k])
    deny_add = DENY + [c for c in culprits if c not in DENY and c != "request_access" and "claude-in-chrome" not in c]

    cur = {}
    if os.path.exists(SETTINGS):
        cur = json.load(open(SETTINGS, encoding="utf-8"))
        os.makedirs(BACKUP_DIR, exist_ok=True)
        bk = os.path.join(BACKUP_DIR, "settings.json." + time.strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(SETTINGS, bk)
    else:
        bk = "（元ファイル無し）"
    perm = cur.setdefault("permissions", {})
    for key, add in (("deny", deny_add), ("allow", ALLOW)):
        lst = perm.setdefault(key, [])
        for r in add:
            if r not in lst:
                lst.append(r)
    # allow と deny が重なったら deny を優先（Chrome は deny に入れない）
    perm["deny"] = [r for r in perm["deny"] if "claude-in-chrome" not in r]
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    tmp = SETTINGS + ".tmp"
    json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS)  # ← 書き込みはこの1回だけ

    back = json.load(open(SETTINGS, encoding="utf-8")).get("permissions", {})
    ok = all(r in back.get("deny", []) for r in DENY) and all(r in back.get("allow", []) for r in ALLOW)
    res = {
        "label": "許可ゼロ設定", "state": "入" if ok else "未",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "deny": back.get("deny", []), "allow": back.get("allow", []),
        "culprits": hits, "scannedSessionFiles": files,
        "backup": bk, "undo": f"cp '{bk}' ~/.claude/settings.json",
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"許可ゼロ設定：{res['state']}／犯人 {culprits or '見つからず'}／戻す: {res['undo']}")


if __name__ == "__main__":
    main()
