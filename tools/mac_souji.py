#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毎週のMac掃除を「許可の要らない工場側」で回す係。2026-09-21（840番）

■ なぜ作ったか（実測。推測ではない）
  定期タスク `weekly-mac-maintenance`（毎週月曜9時）は **走ってはいた**。
  直近の実行：2026-09-21 09:03（list_scheduled_tasks の lastRunAt）。
  ところが定期実行のスコープには「Macの実ファイルへ触る許可ダイアログ」を押す人が居ないので、
  df も rm も一度も通っていない。結果、毎回「何も実行できなかった」と返り、
  そのうえ毎回たまごさんに質問を投げていた。
  ★これは「動いているのに何も取れていない」＝一番たちの悪い壊れ方。
   走った事実だけがログに残り、**片付いた量がゼロであることを誰も数えていなかった。**

  さらに実測で分かったこと：
   既にある掃除係 tools/disk_guardian.py は、中身は正しいのに
   **空きが25GBを切るまで一切動かない**（WARN_GB=25）。今は約80GB空いているので、
   この半年ずっと cleanup() は1度も呼ばれていない。
   ＝「掃除係が居る」ように見えて、実際には誰も掃いていなかった。

■ 直し方（新しく作り直さない）
  1. 消してよいものの判定は **disk_guardian.py の既存ロジックをそのまま使う**
     （allowed_roots / is_forbidden / candidates / safe_remove）。
     壺と金庫の線引きを二重実装しない。ここが増えると事故が増える。
  2. 空き容量の閾値とは無関係に、**週に1回は必ず掃く**。
     ほこりと落ち葉は、床が見えているうちに掃くから溜まらない。
  3. 許可ダイアログの要る経路（定期タスク）を使わない。
     ★新しい定期タスク・新しいlaunchd便は **作らない。**
     心臓(tools/heartbeat.sh)と5分便(tools/machine_status_push.sh)に1行ずつ相乗りする。
     中でここが週1に間引くので、何回呼ばれても実際に掃くのは週1回だけ。

■ 嘘を書かない（このファイルの一番大事な約束）
  - **走った回数と、実際に片付いたバイト数の両方を数える。**
  - 走行>0 なのに 片付き=0 なら **赤**。「実行しました」では済ませない。
  - 消せなかったものは、理由（例外文字列）を **そのまま** 残す。要約も美化もしない。
  - 測れなかった数字は null。0 とは書かない。

■ 触らないもの
  - Brave（過去に13.58GBを48プロセスで握っていた実測あり）。数えるだけ。
  - たまごさんのアプリ・タブ・ウィンドウ。
  - 作り直せないもの（素材・原稿・台帳・Vault・Drive・音楽）。
    → 判定は disk_guardian.FORBIDDEN_KEYWORDS / allowed_roots に委譲。

使い方:
  python3 tools/mac_souji.py            # 週1に間引いて実行（心臓・5分便から呼ばれる形）
  python3 tools/mac_souji.py --force    # 間引きを無視して今すぐ掃く
  python3 tools/mac_souji.py --dry-run  # 1バイトも消さずに、掃く対象と見込み量だけ出す
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
sys.path.insert(0, HERE)

OUT_JSON = os.path.join(STATUS, "mac_souji.json")
OUT_JSONL = os.path.join(STATUS, "mac_souji.jsonl")
STAMP = os.path.join(STATUS, ".mac_souji_at")

GATE_SECONDS = 7 * 86400          # 週1。これより細かく掃いても落ち葉は溜まっていない
OVERDUE_SECONDS = 8 * 86400       # 8日以上掃けていない＝経路が死んでいる＝赤

HOME = os.path.expanduser("~")

# ---------------------------------------------------------------- 追加で掃く場所
# disk_guardian の allowed_roots に入っていない「定義上まちがいなく作り直せる」キャッシュだけ。
# ここはワイルドカードを使わない。**実在するフルパスを名指しで書く。**
# （globで降りると、その下に何が居るか分からないまま消すことになる）
EXTRA_CACHES = [
    ("npm-npx",      os.path.join(HOME, ".npm", "_npx")),
    ("npm-cacache",  os.path.join(HOME, ".npm", "_cacache")),
    ("pip-cache",    os.path.join(HOME, "Library", "Caches", "pip")),
    ("yarn-cache",   os.path.join(HOME, "Library", "Caches", "Yarn")),
    ("homebrew",     os.path.join(HOME, "Library", "Caches", "Homebrew")),
    ("bun-install",  os.path.join(HOME, ".bun", "install", "cache")),
]

# 工場が自分で太らせたログ。消さずに「末尾だけ残して刈る」（記録は残す・肥大分だけ落とす）
LOG_TRIM_KEEP_LINES = 2000
LOG_TRIM_MIN_BYTES = 5 * 1024 * 1024      # 5MBを超えたものだけ刈る

# 心臓が強制終了したときに置く目印。1時間以上前のものは用済み
KILLED_FLAG_MAX_AGE = 3600


def _b(n):
    """バイトを人が読める形に。数字そのものは必ずバイトで残す（丸めない）。"""
    if n is None:
        return "不明"
    for u in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or u == "GB":
            return "%.1f%s" % (n, u)
        n /= 1024.0


def du_bytes(path):
    """実際に占めているバイト数。測れなければ None（0とは書かない）。"""
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        if os.path.isdir(path):
            r = subprocess.run(["du", "-sk", path], capture_output=True,
                               text=True, timeout=120)
            return int(r.stdout.split()[0]) * 1024
    except Exception:
        return None
    return None


def vm_snapshot():
    """空きメモリとスワップ。sysctl/vm_statだけなので高負荷でも返る。"""
    out = {"freeMB": None, "swapUsedGB": None, "swapFreeGB": None, "compressedMB": None}
    try:
        r = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=15)
        txt = r.stdout
        page = 4096
        m = re.search(r"page size of (\d+) bytes", txt)
        if m:
            page = int(m.group(1))

        def pg(label):
            mm = re.search(re.escape(label) + r":\s+(\d+)", txt)
            return int(mm.group(1)) if mm else None
        free = pg("Pages free")
        spec = pg("Pages speculative")
        comp = pg("Pages occupied by compressor")
        if free is not None:
            out["freeMB"] = round((free + (spec or 0)) * page / 1024.0 / 1024.0, 1)
        if comp is not None:
            out["compressedMB"] = round(comp * page / 1024.0 / 1024.0, 1)
    except Exception:
        pass
    try:
        r = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True,
                           text=True, timeout=10)
        mu = re.search(r"used\s*=\s*([0-9.]+)M", r.stdout)
        mf = re.search(r"free\s*=\s*([0-9.]+)M", r.stdout)
        if mu:
            out["swapUsedGB"] = round(float(mu.group(1)) / 1024.0, 2)
        if mf:
            out["swapFreeGB"] = round(float(mf.group(1)) / 1024.0, 2)
    except Exception:
        pass
    return out


def disk_free_bytes():
    try:
        r = subprocess.run(["df", "-k", "/System/Volumes/Data"],
                           capture_output=True, text=True, timeout=15)
        return int(r.stdout.strip().splitlines()[1].split()[3]) * 1024
    except Exception:
        return None


# ---------------------------------------------------------------- 掃除の中身
def sweep_disk_guardian(dry_run):
    """既存の掃除係の判定をそのまま使う。閾値(25GB)だけ迂回して必ず1回呼ぶ。"""
    item = {"name": "disk_guardian", "freedBytes": 0, "detail": [], "error": None}
    try:
        import disk_guardian as dg
    except Exception as e:
        item["error"] = "disk_guardianを読み込めませんでした: %r" % (e,)
        return item
    try:
        cands = dg.candidates()
    except Exception as e:
        item["error"] = "candidates()が失敗しました: %r" % (e,)
        return item
    for c in cands:
        # 人の目待ちのものは、既存の cleanup() と同じく自動では消さない
        if c.get("kind") == "claude_session_attachments":
            continue
        if c.get("protected") or not c.get("age_ok"):
            continue
        size = du_bytes(c["path"])
        if dry_run:
            item["detail"].append({"path": c["path"], "kind": c["kind"],
                                   "wouldFreeBytes": size})
            continue
        before_exists = os.path.exists(c["path"])
        try:
            dg.safe_remove(c["path"], c["kind"])
        except Exception as e:
            item["detail"].append({"path": c["path"], "kind": c["kind"],
                                   "freedBytes": 0, "error": "%r" % (e,)})
            continue
        gone = before_exists and not os.path.exists(c["path"])
        freed = (size or 0) if gone else 0
        item["freedBytes"] += freed
        item["detail"].append({"path": c["path"], "kind": c["kind"],
                               "freedBytes": freed,
                               "error": None if gone else "消えていません（許可範囲外か使用中）"})
    return item


def sweep_extra_caches(dry_run):
    """npm/pip/yarn/homebrew/bun のキャッシュ。無ければ「無い」と正直に書く。"""
    item = {"name": "extra_caches", "freedBytes": 0, "detail": [], "error": None}
    for name, path in EXTRA_CACHES:
        if not os.path.exists(path):
            item["detail"].append({"name": name, "path": path,
                                   "freedBytes": 0, "error": "存在しません（掃除対象なし）"})
            continue
        size = du_bytes(path)
        if dry_run:
            item["detail"].append({"name": name, "path": path, "wouldFreeBytes": size})
            continue
        err = None
        try:
            # 入れ物は残して中身だけ空にする（次に使うときに作り直される）
            for child in os.listdir(path):
                p = os.path.join(path, child)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
        except Exception as e:
            err = "%r" % (e,)
        after = du_bytes(path)
        freed = (size - after) if (size is not None and after is not None) else None
        if freed and freed > 0:
            item["freedBytes"] += freed
        item["detail"].append({"name": name, "path": path,
                               "beforeBytes": size, "afterBytes": after,
                               "freedBytes": freed, "error": err})
    return item


def sweep_our_logs(dry_run):
    """工場が自分で太らせたログの肥大分だけ落とす。記録（末尾2000行）は必ず残す。

    ★.jsonl は対象にしない。あの拡張子には台帳（fal_cost_ledger・machine_health等）が
      混ざっている。台帳は金庫であって落ち葉ではない。刈ってよいのは .log だけ。
    """
    item = {"name": "factory_logs", "freedBytes": 0, "detail": [], "error": None}
    try:
        names = sorted(os.listdir(STATUS))
    except Exception as e:
        item["error"] = "%r" % (e,)
        return item
    for n in names:
        if not n.endswith(".log"):
            continue
        p = os.path.join(STATUS, n)
        try:
            size = os.path.getsize(p)
        except Exception:
            continue
        if size < LOG_TRIM_MIN_BYTES:
            continue
        if dry_run:
            item["detail"].append({"path": p, "beforeBytes": size, "wouldTrim": True})
            continue
        err = None
        try:
            with io.open(p, "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-LOG_TRIM_KEEP_LINES:]
            tmp = p + ".trim"
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.writelines(tail)
            os.replace(tmp, p)
        except Exception as e:
            err = "%r" % (e,)
        try:
            after = os.path.getsize(p)
        except Exception:
            after = None
        freed = (size - after) if after is not None else None
        if freed and freed > 0:
            item["freedBytes"] += freed
        item["detail"].append({"path": p, "beforeBytes": size,
                               "afterBytes": after, "freedBytes": freed, "error": err})
    return item


def sweep_own_junk(dry_run):
    """自分たちが撒いた一時ファイル（心臓の強制終了フラグ・.tmp の取り残し）。"""
    item = {"name": "own_junk", "freedBytes": 0, "detail": [], "error": None}
    now = time.time()
    try:
        names = os.listdir(STATUS)
    except Exception as e:
        item["error"] = "%r" % (e,)
        return item
    for n in names:
        if not (n.startswith(".heartbeat_killed_") or n.endswith(".tmp")):
            continue
        p = os.path.join(STATUS, n)
        try:
            if now - os.path.getmtime(p) < KILLED_FLAG_MAX_AGE:
                continue
            size = os.path.getsize(p)
        except Exception:
            continue
        if dry_run:
            item["detail"].append({"path": p, "wouldFreeBytes": size})
            continue
        err = None
        try:
            os.remove(p)
        except Exception as e:
            err = "%r" % (e,)
        freed = size if not os.path.exists(p) else 0
        item["freedBytes"] += freed
        item["detail"].append({"path": p, "freedBytes": freed, "error": err})
    return item


# ---------------------------------------------------------------- 自分たちの孤児プロセス
# ★たまごさんのアプリは一切触らない。落とすのは「工場が自分で立てて、工場自身が
#   『止まっている』と判定したセッション」だけ。判定は新しく作らず、
#   status/machine.json の stalledList（factory_status.pyが毎回書いている）をそのまま読む。
# 2026-09-21（986番）実測で下げた。360分（6時間）では、15時間46分まったく動いていない
#   "Rusuban mimawari 30min"(pid 99564) すら**1回も回収されていなかった**。
#   machine.json が自分で color:red / kind:stuck_tool と書いているものを6時間見逃す意味は無い。
#   120分＝2時間、一度も動いていないものだけ。これ未満には触らない。
ORPHAN_IDLE_MIN = 120


def reap_our_orphans(dry_run):
    item = {"name": "orphan_sessions", "freedBytes": 0, "detail": [], "error": None}
    mj = os.path.join(STATUS, "machine.json")
    try:
        data = json.load(io.open(mj, encoding="utf-8"))
    except Exception as e:
        item["error"] = "machine.jsonを読めませんでした: %r" % (e,)
        return item
    for s in (data.get("stalledList") or []):
        pid = s.get("pid")
        idle = s.get("idleMin")
        if not pid or idle is None or idle < ORPHAN_IDLE_MIN:
            continue
        if s.get("kind") not in ("stuck_tool", "idle_done"):
            continue
        # 本当にまだ居るか・本当に自分たちのものかを、落とす直前にもう一度確かめる
        # ★2026-09-21（986番）ここに実害のあるバグがあった。
        #   `ps -o command=` は **幅で切り詰める**。実測の戻り値は
        #     "/Users/mac/Libra 127748"
        #   だった（/Users/mac/Library/... が "Libra" で切れている）。
        #   その結果、下の身元確認 "claude" in cmd.lower() が偽になり、
        #   本物のclaudeセッションを「claudeのプロセスではない」として**毎回見逃していた。**
        #   status/mac_souji.json の orphan_sessions が freedBytes:0 だったのはこれが理由。
        #   -ww を付けて切り詰めを止める。
        try:
            cmd = subprocess.run(["ps", "-ww", "-o", "command=,rss=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception as e:
            item["detail"].append({"pid": pid, "error": "psが失敗: %r" % (e,)})
            continue
        if not cmd:
            item["detail"].append({"pid": pid, "error": "既に居ません（掃除不要）"})
            continue
        if "claude" not in cmd.lower():
            item["detail"].append({"pid": pid, "error": "claudeのプロセスではないので触りません: %s"
                                                        % cmd[:120]})
            continue
        try:
            rss = int(cmd.split()[-1]) * 1024
        except Exception:
            rss = None
        entry = {"pid": pid, "title": s.get("title"), "idleMin": idle,
                 "rssBytes": rss, "cmd": cmd[:160]}
        if dry_run:
            entry["wouldKill"] = True
            item["detail"].append(entry)
            continue
        try:
            os.kill(pid, 15)
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)
            except OSError:
                pass
            entry["killed"] = True
            entry["freedBytes"] = rss or 0
            item["freedBytes"] += rss or 0
        except Exception as e:
            entry["killed"] = False
            entry["error"] = "%r" % (e,)
        item["detail"].append(entry)
    return item


# ---------------------------------------------------------------- Braveは数えるだけ
def count_untouched():
    """触らないが食っているものの内訳。**数えるだけ。1プロセスも落とさない。**"""
    out = {"note": "数えただけ。1つも終了させていない", "apps": {}}
    try:
        raw = subprocess.run(["ps", "-Ao", "rss=,command="],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception as e:
        out["error"] = "%r" % (e,)
        return out
    buckets = (
        ("Brave", "Brave Browser"),
        ("Cowork/Claudeの仮想マシン", "com.apple.Virtualization"),
        ("Claude.app", "Claude.app"),
        ("Obsidian", "Obsidian.app"),
        ("Google Drive", "Google Drive"),
        ("Chrome", "Google Chrome"),
    )
    for line in raw.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        try:
            rss = int(parts[0]) * 1024
        except Exception:
            continue
        cmd = parts[1]
        for label, needle in buckets:
            if needle in cmd:
                b = out["apps"].setdefault(label, {"procs": 0, "rssBytes": 0})
                b["procs"] += 1
                b["rssBytes"] += rss
                break
    for label, b in out["apps"].items():
        b["rssHuman"] = _b(b["rssBytes"])
    return out


# ---------------------------------------------------------------- 台帳
def load_ledger():
    try:
        return json.load(io.open(OUT_JSON, encoding="utf-8"))
    except Exception:
        return {"runs": 0, "totalFreedBytes": 0, "runsWithZeroFreed": 0}


def save(obj):
    tmp = OUT_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_JSON)


def main():
    args = sys.argv[1:]
    force = "--force" in args
    dry = "--dry-run" in args

    # 週1に間引く。★間引きで戻ったときも「呼ばれたことは数える」。
    #   呼ばれているのに一度も掃けていない、という状態を見えるようにするため。
    ledger = load_ledger()
    ledger["calls"] = ledger.get("calls", 0) + 1
    last = 0
    try:
        last = os.path.getmtime(STAMP)
    except OSError:
        pass
    due = force or (time.time() - last) >= GATE_SECONDS
    if not due:
        ledger["lastCallAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        ledger["nextDueAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                            time.localtime(last + GATE_SECONDS))
        try:
            save(ledger)
        except Exception:
            pass
        return

    started = time.time()
    before_disk = disk_free_bytes()
    before_vm = vm_snapshot()

    items = [
        sweep_disk_guardian(dry),
        sweep_extra_caches(dry),
        sweep_our_logs(dry),
        sweep_own_junk(dry),
        reap_our_orphans(dry),
    ]
    freed = sum((i.get("freedBytes") or 0) for i in items)

    time.sleep(2)
    after_disk = disk_free_bytes()
    after_vm = vm_snapshot()

    if not dry:
        try:
            io.open(STAMP, "w").write(time.strftime("%F %T"))
        except Exception:
            pass
        ledger["runs"] = ledger.get("runs", 0) + 1
        ledger["totalFreedBytes"] = ledger.get("totalFreedBytes", 0) + freed
        if freed <= 0:
            ledger["runsWithZeroFreed"] = ledger.get("runsWithZeroFreed", 0) + 1

    # ---- 赤/緑の判定。★「走った」だけでは緑にしない ----
    runs = ledger.get("runs", 0)
    total = ledger.get("totalFreedBytes", 0)
    if runs > 0 and total <= 0:
        color, reason = "red", "走った回数%d回・片付いたバイト数0。動いているのに何も取れていない" % runs
    elif freed <= 0 and not dry:
        color, reason = "yellow", "今回は掃く対象が無かった（累計では%s片付いている）" % _b(total)
    else:
        color, reason = "green", "今回%s・累計%s片付いた" % (_b(freed), _b(total))

    ledger.update({
        "schemaVersion": 2,
        "lastRunAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lastRunSeconds": round(time.time() - started, 1),
        "dryRun": dry,
        "lastFreedBytes": freed,
        "lastFreedHuman": _b(freed),
        "totalFreedHuman": _b(ledger.get("totalFreedBytes", 0)),
        "color": color,
        "reason": reason,
        "gateSeconds": GATE_SECONDS,
        "overdueSeconds": OVERDUE_SECONDS,
        "nextDueAt": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                   time.localtime(time.time() + GATE_SECONDS)),
        "disk": {"beforeBytes": before_disk, "afterBytes": after_disk,
                 "deltaBytes": (after_disk - before_disk)
                 if (before_disk is not None and after_disk is not None) else None},
        "memory": {"before": before_vm, "after": after_vm},
        "items": items,
        "untouched": count_untouched(),
        "route": "心臓(heartbeat.sh)＋5分便(machine_status_push.sh)に相乗り。"
                 "許可ダイアログの要る定期タスクは使っていない",
    })
    save(ledger)

    try:
        with io.open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "t": ledger["lastRunAt"], "dryRun": dry, "runs": runs,
                "freedBytes": freed, "totalFreedBytes": ledger.get("totalFreedBytes", 0),
                "color": color,
                "diskFreeBeforeBytes": before_disk, "diskFreeAfterBytes": after_disk,
                "memFreeMBBefore": before_vm.get("freeMB"),
                "memFreeMBAfter": after_vm.get("freeMB"),
                "swapUsedGBBefore": before_vm.get("swapUsedGB"),
                "swapUsedGBAfter": after_vm.get("swapUsedGB"),
                "perItem": {i["name"]: i.get("freedBytes") for i in items},
                "errors": [{"item": i["name"], "error": i["error"]}
                           for i in items if i.get("error")],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

    print("[%s] 今回%s / 累計%s（%s）" % (color, _b(freed),
                                        _b(ledger.get("totalFreedBytes", 0)), reason))


if __name__ == "__main__":
    # 呼び出し側は全て >/dev/null なので、落ちたら誰も気づけない。
    # ★落ちた事実だけは必ず残す（黙って死なない）。
    try:
        main()
    except Exception:
        import traceback
        try:
            with io.open(OUT_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                    "crash": traceback.format_exc()},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        raise
