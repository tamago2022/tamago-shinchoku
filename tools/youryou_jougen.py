#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""場所ごとの上限（2026-10-16・たまごさん「こういうことが起こらない仕組みにすること」）。

置き場ごとに「ここまで」を決め、超えたら古い順に、作り直せるものだけを片付ける。
shimau.py（毎日＋空き30GB未満なら1時間おき）から呼ばれる。負荷では止まらない（消すのは軽い）。

  /private/tmp            上限 3GB ：12時間さわられていないものを古い順に
                                      （作業場の複製・push用の写し・動画/音/画像/zip の一時物。claude-* と launchd/ssh の物は除く）
  $TMPDIR(/var/folders/T) 上限 5GB ：12時間さわられていないものを古い順に（com.apple.*・claude* は除く）
  Claudeの古いセッション   上限 15GB：今のセッション以外の outputs を古い順に（2日以上前のもの）
  ~/Library/Caches         上限 6GB ：アプリのキャッシュ（作り直せる）を大きい順に。Apple の物と Claude/Typeless 本体は除く
  ~/.npm/_cacache・~/.cache/pip・~/Library/Caches/Homebrew 等 … 上の Caches と同じ扱い

触らない：Brave（キャッシュも）・たまごさんのファイル・壺と金庫・Vault・iCloud・ドライブ・HDD・作品（mp4 の完成品は ~/Documents/AI作業 にある＝ここは見ない）・
         Whisper のモデル（~/.cache/whisper・huggingface：作り直しに時間がかかるので上限の対象外）・Brave/Chrome の Cookie。
結果：status/public/youryou_jougen.json
逆テスト：python3 tools/youryou_jougen.py --self-test
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
AS = HOME + "/Library/Application Support"
PUB = os.path.join(REPO, "status", "public", "youryou_jougen.json")
CUR_SESSION = "67542e85-a104-4946-bcde-7c7916354942"
H = 3600

FORBIDDEN = ("CloudStorage", "Mobile Documents", "iCloud", "Google Drive", "tamago_brain", "Vault", "Keychains",
             "/.ssh", "/.gnupg", "kagi", "kinko", "金庫", "壺", "Volumes/")
TMP_KEEP = ("claude-", "com.apple", "launchd", "ssh-", "tmux-", "powerlog", ".", "TemporaryItems", "MozillaUpdateLock",
            "boost_interprocess")
CACHE_KEEP = ("com.apple.", "BraveSoftware", "com.brave", "CloudKit", "com.anthropic", "Claude", "now.typeless.desktop", "Homebrew/downloads/.lock",
              "whisper", "huggingface")


def free_gb():
    st = os.statvfs("/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def du_b(p, t=600):
    try:
        r = subprocess.run(["du", "-skx", p], capture_output=True, text=True, timeout=t)
        return int(r.stdout.split()[0]) * 1024
    except Exception:
        return 0


def newest(p, limit=5000):
    m = os.lstat(p).st_mtime
    if not os.path.isdir(p) or os.path.islink(p):
        return m
    n = 0
    for dp, dns, fns in os.walk(p):
        for x in dns + fns:
            try:
                m = max(m, os.lstat(os.path.join(dp, x)).st_mtime)
            except Exception:
                pass
            n += 1
            if n > limit:
                return m
    return m


def rm(p):
    if any(f in p for f in FORBIDDEN):
        return False
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            os.remove(p)
        except Exception:
            return False
    return not os.path.lexists(p)


def in_use(p):
    """開いているプロセスがあれば使用中（lsof +D は重いので、ディレクトリ直下だけを見る）。"""
    try:
        r = subprocess.run(["lsof", "-t", "+d", p], capture_output=True, text=True, timeout=20)
        return bool(r.stdout.strip())
    except Exception:
        return False


def trim(label, items, cap_gb, min_age_h, order="old", dry=False):
    """items: パスの一覧。合計が cap_gb を超えたら、min_age_h 以上さわられていないものを order 順に消す。"""
    now = time.time()
    rows = []
    for p in items:
        try:
            rows.append({"p": p, "b": du_b(p), "age_h": (now - newest(p)) / H})
        except Exception:
            pass
    total = sum(r["b"] for r in rows)
    res = {"what": label, "cap_gb": cap_gb, "before_gb": round(total / 1e9, 2), "removed": []}
    if total <= cap_gb * 1e9:
        res["after_gb"] = res["before_gb"]
        return res
    rows.sort(key=(lambda r: -r["age_h"]) if order == "old" else (lambda r: -r["b"]))
    for r in rows:
        if total <= cap_gb * 1e9:
            break
        if r["age_h"] < min_age_h or in_use(r["p"]):
            continue
        if dry or rm(r["p"]):
            total -= r["b"]
            res["removed"].append({"p": r["p"].replace(HOME, "~"), "gb": round(r["b"] / 1e9, 2),
                                   "age_h": round(r["age_h"], 1)})
    res["after_gb"] = round(total / 1e9, 2)
    return res


def kids(p, keep=()):
    try:
        return [os.path.join(p, n) for n in os.listdir(p) if not n.startswith(keep)]
    except Exception:
        return []


def run(dry=False):
    out = {"at": time.strftime("%F %T"), "free_gb_before": free_gb(), "places": []}
    tmp = tempfile.gettempdir()
    sessions = [o for o in glob.glob(AS + "/Claude/local-agent-mode-sessions/*/*/*/outputs") +
                glob.glob(AS + "/Claude/local-agent-mode-sessions/*/*/outputs") if CUR_SESSION not in o]
    caches = [p for p in kids(HOME + "/Library/Caches") if not any(k in p for k in CACHE_KEEP)]
    caches += [p for p in (HOME + "/.npm/_cacache", HOME + "/.cache/pip", HOME + "/.cache/yt-dlp",
                           HOME + "/.cache/puppeteer", HOME + "/.cache/ms-playwright") if os.path.exists(p)]
    plan = [("/private/tmp", kids("/private/tmp", TMP_KEEP), 3, 12, "old"),
            ("$TMPDIR", kids(tmp, TMP_KEEP), 5, 12, "old"),
            ("Claudeの古いセッションの outputs", sessions, 15, 48, "old"),
            ("キャッシュ（~/Library/Caches ほか）", caches, 6, 1, "big")]
    for label, items, cap, age, order in plan:
        try:
            out["places"].append(trim(label, items, cap, age, order, dry))
        except Exception as e:
            out["places"].append({"what": label, "error": str(e)[:200]})
    out["free_gb_after"] = free_gb()
    out["dry"] = dry
    if not dry:
        os.makedirs(os.path.dirname(PUB), exist_ok=True)
        json.dump(out, open(PUB + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(PUB + ".tmp", PUB)
    n = sum(len(p.get("removed", [])) for p in out["places"])
    return "%d個（空き %.1f→%.1fGB）" % (n, out["free_gb_before"], out["free_gb_after"])


def self_test():
    d = tempfile.mkdtemp()
    old = os.path.join(d, "old"); new = os.path.join(d, "new"); kin = os.path.join(d, "金庫_x")
    for p in (old, new, kin):
        os.makedirs(p)
        open(os.path.join(p, "f"), "wb").write(b"x" * 3_000_000)
    t = time.time() - 30 * H
    for p in (old, kin):
        os.utime(os.path.join(p, "f"), (t, t)); os.utime(p, (t, t))
    r = trim("test", [old, new, kin], 0.001, 12)
    assert not os.path.exists(old), "古いものが消えていない"
    assert os.path.exists(new), "新しいものを消した"
    assert os.path.exists(kin), "金庫を消した"
    r2 = trim("test", [new], 1, 0)
    assert os.path.exists(new) and not r2["removed"], "上限内なのに消した"
    shutil.rmtree(d)
    print("self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    elif "--dry" in sys.argv:
        print(run(dry=True))
    else:
        print(run())
