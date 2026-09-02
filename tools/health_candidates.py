#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Macの健康管理：いま何を閉じれば／消せば楽になるか、を実測で出す（2026-09-03）。
推測は書かない。測れないものは載せない。効果はGB／本数で添える。

出力: status/health.json（PWAが読む）
  {"measuredAt": "...", "diskFreeGB": 54, "purgeableGB": 3.1, "items": [
     {"label": "Braveを閉じる", "effect": "メモリ 2.1GB", "gb": 2.1, "safe": true, "kind": "mem", "how": "..."},
     {"label": "~/Library/Caches を空にする", "effect": "空き 8.6GB", "gb": 8.6, "safe": true, "kind": "disk", ...},
     {"label": "Time Machineのローカルスナップショット 11個", "effect": "空き（purgeable）3.1GB", "safe": false, ...}
  ]}
  safe=true  … 作り直せるもの（キャッシュ・ブラウザを閉じる等）。それでも実行はMac側の人かセッションが行う。PWAからは実行しない
  safe=false … 本人の判断が要るもの（削除で戻らない・作業中のものを止める等）

重い計測（du）は30分に1回だけ。それ以外の回は前回の値を使い、メモリ系だけ毎回測り直す。
5分おきの launchd（machine_status_push.sh）から呼ばれる。
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "health.json")
MACHINE = os.path.join(REPO, "status", "machine.json")
HOME = os.path.expanduser("~")
DU_INTERVAL = 1800


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def du_gb(path, timeout=60):
    if not os.path.exists(path):
        return None
    out = run(["du", "-sk", path], timeout=timeout)
    m = re.match(r"(\d+)", out.strip())
    return round(int(m.group(1)) / 1048576.0, 2) if m else None


def rss_gb(pattern):
    """名前に pattern を含むプロセスの常駐メモリ合計（GB）と本数"""
    total = 0; n = 0
    for ln in run(["ps", "-Ao", "rss,comm"]).splitlines()[1:]:
        parts = ln.strip().split(None, 1)
        if len(parts) == 2 and pattern in parts[1]:
            try:
                total += int(parts[0]); n += 1
            except Exception:
                pass
    return round(total / 1048576.0, 2), n


def snapshots():
    out = run(["tmutil", "listlocalsnapshots", "/"])
    return [ln.strip() for ln in out.splitlines() if "com.apple.TimeMachine" in ln]


def purgeable_gb():
    out = run(["diskutil", "info", "/System/Volumes/Data"])
    m = re.search(r"Volume Available Space:\s+[0-9.]+ .B \(([0-9]+) Bytes\)|Container Free Space:\s+[0-9.]+ .B \(([0-9]+) Bytes\)", out)
    # purgeable は "Volume Available Space: 47.9 GB (…) (47.7 GB purgeable)" の形
    m2 = re.search(r"\(([0-9.]+) GB purgeable\)", out) or re.search(r"\(([0-9.]+) MB purgeable\)", out)
    if not m2:
        return None
    v = float(m2.group(1))
    return round(v if "GB purgeable" in out else v / 1024.0, 2)


def node_modules_gb():
    """Desktop 配下の node_modules（深さ3まで）。合計GBとパス一覧"""
    out = run(["find", os.path.join(HOME, "Desktop"), "-maxdepth", "3", "-type", "d", "-name", "node_modules", "-prune"], timeout=60)
    paths = [p for p in out.splitlines() if p.strip()]
    total = 0.0; found = []
    for p in paths:
        g = du_gb(p, timeout=60)
        if g:
            total += g; found.append((p.replace(HOME, "~"), g))
    return round(total, 2), found


def main():
    prev = {}
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        pass
    now = time.time()
    last_du = prev.get("_duAt", 0)
    do_du = (now - last_du) >= DU_INTERVAL
    disk = prev.get("_du") or {}
    if do_du:
        disk = {
            "caches": du_gb(os.path.join(HOME, "Library", "Caches"), 120),
            "npx": du_gb(os.path.join(HOME, ".npm", "_npx"), 60),
            "trash": du_gb(os.path.join(HOME, ".Trash"), 60),
            "driveCache": du_gb(os.path.join(HOME, "Library", "Application Support", "Google", "DriveFS"), 60),
        }
        nm_total, nm_list = node_modules_gb()
        disk["nodeModules"] = nm_total
        disk["nodeModulesList"] = nm_list
        last_du = now

    machine = {}
    try:
        machine = json.load(open(MACHINE, encoding="utf-8"))
    except Exception:
        pass

    items = []
    # ── メモリ（毎回測る・閉じれば戻る＝安全） ──
    for label, pat, app in (("Braveを閉じる", "Brave Browser", "Brave Browser"), ("Chromeを閉じる", "Google Chrome", "Google Chrome"),
                             ("Spotifyを閉じる", "Spotify", "Spotify"), ("Notionを閉じる", "Notion", "Notion"), ("LINEを閉じる", "LINE", "LINE")):
        gb, n = rss_gb(pat)
        if n and gb >= 0.3:
            items.append({"label": label, "effect": f"メモリ {gb}GB", "gb": gb, "kind": "mem", "safe": True, "app": app,
                          "how": f"{n}プロセス。閉じれば戻る。作業中のタブがあれば先に保存"})
    # セッション：終わって待機しているものを畳む（machine.json の sessionList から）
    idle = [s for s in (machine.get("sessionList") or []) if s.get("kind") == "idle_done"]
    if idle:
        gb = round(sum((s.get("mb") or 0) for s in idle) / 1024.0, 2)
        items.append({"label": f"終わって待機中のセッション {len(idle)}本を畳む", "effect": f"メモリ {gb}GB・負荷↓", "gb": gb, "kind": "mem", "safe": True,
                      "how": "、".join((s.get("title") or "?")[:14] for s in idle[:4])})
    over = (machine.get("sessions") or 0) - (machine.get("safeMax") or 0)
    if machine.get("safeMax") and over > 0:
        items.append({"label": f"セッションを{over}本減らす（上限{machine['safeMax']}本）", "effect": f"負荷 {machine.get('load','?')}%→上限内", "gb": 0, "kind": "load", "safe": False,
                      "how": "どれを止めるかは作業内容次第。止めるなら引き継ぎメモを書かせてから"})
    # ── ディスク（30分ごとに実測） ──
    def disk_item(label, key, safe, how):
        g = disk.get(key)
        if g and g >= 0.2:
            items.append({"label": label, "effect": f"空き {g}GB", "gb": g, "kind": "disk", "safe": safe, "how": how})
    disk_item("~/Library/Caches を空にする", "caches", True, "アプリのキャッシュ。作り直される。使用中のものは飛ばす")
    disk_item("~/.npm/_npx を空にする", "npx", True, "npx の一時置き場。作り直される")
    disk_item("ゴミ箱を空にする", "trash", False, "捨てたつもりのもの。中身を一度見てから")
    disk_item("Googleドライブのローカルキャッシュ", "driveCache", False, "アップロード待ちが残っていると消せない")
    if disk.get("nodeModules"):
        items.append({"label": f"node_modules を消す（{len(disk.get('nodeModulesList') or [])}箇所）", "effect": f"空き {disk['nodeModules']}GB", "gb": disk["nodeModules"], "kind": "disk", "safe": True,
                      "how": "npm install で戻る。" + "、".join(p for p, _ in (disk.get("nodeModulesList") or [])[:3])})
    snaps = snapshots()
    pg = purgeable_gb()
    if snaps:
        items.append({"label": f"Time Machineのローカルスナップショット {len(snaps)}個", "effect": f"空き（purgeable）{pg}GB" if pg is not None else "空き（自動解放待ち）", "gb": pg or 0, "kind": "disk", "safe": False,
                      "how": "tmutil deletelocalsnapshots（sudo不要）。消すと復元点が減る。時間で自然に減る"})

    items.sort(key=lambda x: -(x.get("gb") or 0))
    out = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "diskFreeGB": machine.get("diskFreeGB"), "purgeableGB": pg, "snapshots": len(snaps),
        "load": machine.get("load"), "memPressure": machine.get("memPressure"), "memAvailGB": machine.get("memAvailGB"),
        "sessions": machine.get("sessions"), "safeMax": machine.get("safeMax"), "moreOK": machine.get("moreOK"),
        # 2026-09-03 本数維持：目標本数・実測上限・校正根拠・あと何本・何を落とせば空くか（PWA表示用。machine.jsonの写し）
        "target": machine.get("target"), "cap": machine.get("cap"), "calibratedSafeN": machine.get("calibratedSafeN"),
        "below": machine.get("below"), "shedCandidates": machine.get("shedCandidates"),
        "items": items,
        "_duAt": last_du, "_du": disk,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print(f"health.json: {len(items)}件（du{'再計測' if do_du else '前回値'}）")


if __name__ == "__main__":
    main()
