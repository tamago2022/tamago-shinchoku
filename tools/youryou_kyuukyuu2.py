#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容量の救急・第2便（2026-10-12）。

第1便（~/Library/Caches・npm/bun/pnpm・ms-playwright 等）で約7GB、控え箱の圧縮で約9GB空いて
空き13.6GB。たまごさんの「最低20GB」に届かないため、測った結果（status/youryou_hakaru2.json）から
**作り直せるキャッシュ・一時フォルダ・ビルド生成物だけ**を追加で消す。
  ・アプリの Cache / Code Cache / GPUCache / Temp（アプリが次に起動したとき作り直す）
  ・工場の作業場に残った node_modules（bun/npm install で作り直せる・2時間以上触られていないもの）
触らない：Vault・iCloud(CloudDocs)・Google Drive・Claudeの仮想マシン・会話ログ・作業場の中身（node_modules以外）
・Brave の中身・たまごさんの書類。
あわせて、次に一覧を見せるためのもう一段深い測定も書く。
status/youryou_kyuukyuu2.go がある時だけ1回動く。結果：status/youryou_kyuukyuu2.json
"""
import json
import os
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "youryou_kyuukyuu2.go")
OUT = os.path.join(REPO, "status", "youryou_kyuukyuu2.json")
AS = os.path.join(HOME, "Library/Application Support")

KESU = [
    (AS + "/Notion/Partitions/notion/Cache", "Notionのキャッシュ"),
    (AS + "/Notion/Partitions/notion/Code Cache", "Notionのキャッシュ"),
    (AS + "/Notion/Partitions/notion/GPUCache", "Notionのキャッシュ"),
    (AS + "/Notion/Partitions/notion/DawnGraphiteCache", "Notionのキャッシュ"),
    (AS + "/Notion/Partitions/notion/DawnWebGPUCache", "Notionのキャッシュ"),
    (AS + "/Notion/Partitions/notion/Service Worker/CacheStorage", "Notionのキャッシュ"),
    (AS + "/Notion/Cache", "Notionのキャッシュ"),
    (AS + "/Notion/Code Cache", "Notionのキャッシュ"),
    (AS + "/discord/Cache", "Discordのキャッシュ"),
    (AS + "/discord/Code Cache", "Discordのキャッシュ"),
    (AS + "/Wondershare Filmora Mac/ProgramData/Temp", "Filmoraの一時フォルダ"),
    (AS + "/Google/GoogleUpdater/crx_cache", "Google更新のダウンロード控え"),
    (AS + "/Spotify/PersistentCache", "Spotifyのキャッシュ"),
    (AS + "/Typeless/Cache", "Typelessのキャッシュ"),
    (AS + "/Typeless/Code Cache", "Typelessのキャッシュ"),
    (AS + "/Wispr Flow/Cache", "Wispr Flowのキャッシュ"),
    (AS + "/Wispr Flow/Code Cache", "Wispr Flowのキャッシュ"),
    (HOME + "/.npm/_npx", "npxの一時インストール"),
    (HOME + "/.tamago/pwold", "古いPlaywrightのブラウザ"),
    (HOME + "/.tamago/chrome-publish/Default/Cache", "工場用Chromeのキャッシュ"),
    (HOME + "/.tamago/chrome-publish/Default/Code Cache", "工場用Chromeのキャッシュ"),
    (HOME + "/.tamago/buffer-profile/Default/Cache", "工場用Chromeのキャッシュ"),
    (HOME + "/.tamago/buffer-profile/Default/Code Cache", "工場用Chromeのキャッシュ"),
    (HOME + "/.tamago/chrome-line/Default/Cache", "工場用Chromeのキャッシュ"),
    (HOME + "/.tamago/chrome-line/Default/Code Cache", "工場用Chromeのキャッシュ"),
]
# ★HowItHolds の _build は fal で作った素材を含む（作り直すとお金がかかる）ので消さない。一覧に出すだけ。
# node_modules を探す作業場（2時間以上触られていないもの・作業場と分かる場所の中だけ）
NM_ROOTS = [HOME + "/tamago",HOME + "/Documents/AI作業", REPO + "/status"]
WT_MARKS = ("/.worktrees/", "_wt/", "/wt-", "/status/_pr", "/.tmp_q")
DEEP = [
    (HOME + "/Documents/AI作業/.worktrees", 1),
    (HOME + "/Documents/AI作業", 1),
    (REPO + "/status", 1),
    (HOME + "/.claude/projects", 1),
    (AS + "/CloudDocs/session/t", 1),
    (AS + "/Notion/Partitions/notion", 1),
    (AS + "/Claude", 1),
    (HOME + "/howitholds/ep01", 1),
    (HOME + "/Desktop", 1),
    (HOME + "/.tamago", 1),
]


def free_gb():
    try:
        st = os.statvfs("/System/Volumes/Data")
        return round(st.f_bavail * st.f_frsize / 1e9, 2)
    except Exception:
        return None


def save(res):
    try:
        with open(OUT + ".tmp", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        os.replace(OUT + ".tmp", OUT)
    except Exception:
        pass


def rm(p, kind, res):
    if not os.path.isdir(p) or os.path.islink(p):
        return
    b = free_gb() or 0
    shutil.rmtree(p, ignore_errors=True)
    res["deleted"].append({"path": p.replace(HOME, "~", 1), "kind": kind, "gb": round((free_gb() or 0) - b, 2)})
    save(res)


def main():
    if not os.path.exists(GO):
        return
    try:
        os.remove(GO)
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb_start": free_gb(), "state": "消している", "deleted": []}
    save(res)
    for p, kind in KESU:
        rm(p, kind, res)
    # 作業場の node_modules（2時間以上触られていない・.git を持つ作業場の中のものだけ）
    now = time.time()
    for root in NM_ROOTS:
        for dp, dns, fns in os.walk(root):
            if "node_modules" in dns:
                nm = os.path.join(dp, "node_modules")
                try:
                    old = now - os.path.getmtime(nm) > 7200 and now - os.path.getmtime(dp) > 7200
                except Exception:
                    old = False
                if old and os.path.exists(os.path.join(dp, "package.json")) \
                        and any(m in nm for m in WT_MARKS):
                    rm(nm, "作業場の node_modules（npm/bun install で作り直せる）", res)
            dns[:] = [d for d in dns if d not in ("node_modules", ".git")]
    res["free_gb_after"] = free_gb()
    res["deleted_total_gb"] = round(sum(d["gb"] for d in res["deleted"]), 2)
    res["state"] = "測っている"
    save(res)
    deep = []
    for p, d in DEEP:
        try:
            r = subprocess.run(["du", "-xk", "-d", str(d), p], capture_output=True, text=True, timeout=600)
            for line in r.stdout.splitlines():
                kb, q = line.split("\t", 1)
                if int(kb) >= 200 * 1024:
                    try:
                        mt = time.strftime("%m-%d", time.localtime(os.path.getmtime(q)))
                    except Exception:
                        mt = ""
                    deep.append({"path": q.replace(HOME, "~", 1), "gb": round(int(kb) / 1048576, 2), "mtime": mt})
        except Exception as e:
            deep.append({"path": p, "gb": None, "err": str(e)[:80]})
    res["deep"] = sorted(deep, key=lambda r: -(r["gb"] or 0))
    res["state"] = "完了"
    res["finished"] = time.strftime("%F %T")
    res["free_gb_end"] = free_gb()
    save(res)


if __name__ == "__main__":
    main()
