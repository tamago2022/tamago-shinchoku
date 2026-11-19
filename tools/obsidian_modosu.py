#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obsidian の Vault（tamago_brain）を本体に戻す（2026-10-14・Obsidianフリーズの割り込み対応）。
status/obsidian_modosu.go → status/obsidian_modosu.json（途中経過も書く）
  ① 空き容量
  ② Vault のうち「iCloudにしか無い（本体に中身が無い＝dataless）」ファイルの数
  ③ Obsidian の保存領域（~/Library/Application Support/obsidian）と Vault の .obsidian の有無・大きさ・更新日時
  ④ dataless のファイルを読んで本体へ戻す（.obsidian → .md/.canvas → その他。空き25GBを切ったら止める）
iCloud の設定・Obsidian の設定・アカウントには触らない。消さない。
"""
import json, os, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
GO = os.path.join(REPO, "status", "obsidian_modosu.go")
OUT = os.path.join(REPO, "status", "obsidian_modosu.json")
VAULT = HOME + "/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
APP = HOME + "/Library/Application Support/obsidian"
SF_DATALESS = 0x40000000


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return round(st.f_bavail * st.f_frsize / 1e9, 2)


def save(res):
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)


def scan():
    tot, dl, dl_bytes, files = 0, 0, 0, []
    dl_dirs = 0
    for dp, dns, fns in os.walk(VAULT):
        for d in dns:
            try:
                if os.lstat(os.path.join(dp, d)).st_flags & SF_DATALESS:
                    dl_dirs += 1
            except Exception:
                pass
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.lstat(p)
            except Exception:
                continue
            tot += 1
            if st.st_flags & SF_DATALESS:
                dl += 1
                dl_bytes += st.st_size
                files.append((p, st.st_size))
    return tot, dl, dl_bytes, dl_dirs, files


def info(p):
    if not os.path.exists(p):
        return "無い"
    n, b, m = 0, 0, 0
    for dp, dns, fns in os.walk(p):
        for fn in fns:
            try:
                st = os.lstat(os.path.join(dp, fn))
                n += 1
                b += st.st_blocks * 512
                m = max(m, st.st_mtime)
            except Exception:
                pass
    return {"files": n, "gb": round(b / 1e9, 3), "newest": time.strftime("%F %T", time.localtime(m)) if m else None,
            "dir_mtime": time.strftime("%F %T", time.localtime(os.path.getmtime(p)))}


def main():
    if not os.path.exists(GO):
        return
    os.remove(GO)
    try:
        os.setsid()
    except Exception:
        pass
    res = {"started": time.strftime("%F %T"), "free_gb": free_gb(), "state": "数えている",
           "vault_exists": os.path.isdir(VAULT)}
    save(res)
    res["app_support"] = info(APP)
    res["app_indexeddb"] = info(APP + "/IndexedDB")
    res["vault_dot_obsidian"] = info(VAULT + "/.obsidian")
    res["caches_md_obsidian"] = info(HOME + "/Library/Caches/md.obsidian")
    tot, dl, dlb, dld, files = scan()
    res.update(vault_files=tot, dataless_files=dl, dataless_gb=round(dlb / 1e9, 2), dataless_dirs=dld)
    res["state"] = "本体へ戻している"
    save(res)

    def order(x):
        p = x[0]
        if "/.obsidian/" in p:
            return 0
        if p.endswith((".md", ".canvas", ".json", ".base")):
            return 1
        return 2
    files.sort(key=order)
    done, fail, stopped = 0, 0, None
    t0 = time.time()
    for p, size in files:
        if free_gb() < 25:
            stopped = "空きが25GBを切ったので止めた"
            break
        try:
            with open(p, "rb") as f:
                while f.read(1 << 20):
                    pass
            done += 1
        except Exception:
            fail += 1
        if done % 200 == 0:
            res.update(materialized=done, failed=fail, elapsed_s=int(time.time() - t0), free_gb_now=free_gb())
            save(res)
    tot2, dl2, dlb2, dld2, _ = scan()
    res.update(materialized=done, failed=fail, stopped=stopped, dataless_after=dl2,
               dataless_gb_after=round(dlb2 / 1e9, 2), state="完了", finished=time.strftime("%F %T"),
               free_gb_end=free_gb())
    save(res)


if __name__ == "__main__":
    main()
