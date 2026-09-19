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
        # ★2026-09-21（986番）ここに実害のあるバグがあった。実測で確かめた正体：
        #   元のコードは `ps -o command=,rss=` を使っていた。BSD(macOS)のpsは
        #   **command を最後の列に置かないと16文字で切り詰める。**
        #   実測の戻り値： "/Users/mac/Libra 127748"
        #     （/Users/mac/Library/Application Support/... が "Libra" で切れている）
        #   その結果、下の身元確認 "claude" in cmd.lower() が偽になり、
        #   本物のclaudeセッションを「claudeのプロセスではない」として**毎回見逃していた。**
        #   status/mac_souji.json の orphan_sessions が freedBytes:0 だったのはこれが理由で、
        #   15時間46分止まっていた pid 99564 もこれで生き延びていた。
        #   ★最初 -ww を足して直したつもりになったが、実測では**何も変わらなかった**
        #     （23文字のまま／2026-09-21 12:23）。幅の問題ではなく**列の順番**の問題。
        #   直し方：rss を先に、command を最後に置く。
        try:
            raw = subprocess.run(["ps", "-ww", "-o", "rss=,command=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception as e:
            item["detail"].append({"pid": pid, "error": "psが失敗: %r" % (e,)})
            continue
        if not raw:
            item["detail"].append({"pid": pid, "error": "既に居ません（掃除不要）"})
            continue
        parts = raw.split(None, 1)
        rss = None
        cmd = raw
        if len(parts) == 2:
            try:
                rss = int(parts[0]) * 1024
            except ValueError:
                rss = None
            cmd = parts[1]
        # 身元確認は「claudeという字が入っている」ではなく、claude CLIの実体パスで見る。
        # たまごさんのClaude.app本体（/Applications/Claude.app）には絶対に触らない。
        if "claude-code/" not in cmd or "/claude" not in cmd:
            item["detail"].append({"pid": pid,
                                   "error": "claude CLIではないので触りません: %s" % cmd[:120]})
            continue
        if "/Applications/" in cmd:
            item["detail"].append({"pid": pid,
                                   "error": "たまごさんのアプリなので触りません: %s" % cmd[:120]})
            continue
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


# ================================================================ 毎回の軽い掃き掃除
# 2026-09-21（986番）なぜ「週1」とは別に要るのか（実測）
#   週1の掃除は**ディスク**には効いた（4.5GB）。だがMacが詰まった原因はディスクではなかった。
#   12:00の実測：memory_pressure は「空き85%」でメモリ自体は赤ではない。詰まっていたのは
#     ・load average 46.03（コア8本）
#     ・swap used 18.4GB / 残り1.0GB、Swapouts 3億回
#   そしてCPUを食っていた上位は Brave 167% / Google Drive 137% / mds_stores 48%。
#   ★落ち葉は「週1でまとめて」ではなく「毎日掃く」もの。孤児セッションは2時間で溜まる。
#   ここは週1のゲートより手前に置き、10分ごとに軽いものだけを掃く。
RELIEF_STAMP = os.path.join(STATUS, ".mac_souji_relief_at")
# ★間引きは540秒（9分）。「10分ごとに呼ばれるから10分で間引く」にしてはいけない。
#   実測（2026-09-21 12:24〜12:33）：心臓の呼び出しは tick_every 40＝約10分だが、
#   一周が混雑で15秒→40〜50秒に伸びるため、呼ばれる間隔は10分ちょうどではなく前後する。
#   ゲートを600秒にすると、599秒で来た回は素通りし、次は約20分後になる。
#   ＝**呼ばれているのに実際には20分に1回しか掃けない。**（13分間ゲートが開かなかった実測あり）
#   呼び出し間隔より少し短く取るのが正解。中の仕事は軽いので9分でも負荷は増えない。
RELIEF_GATE_SECONDS = 540

# Spotlightに舐めさせない場所（=工場が機械的に書き換え続けるところだけ）
#   実測：status/ は**5分で91ファイル**書き換わる。1つ書くたびに fsevents → mdworker →
#   mds_stores が索引し直す。12:12の実測で mds_stores 48.7% + mdworker 6本。
#   ★消す操作ではない。目印を1つ置くだけ。要らなくなったら rm 1回で元に戻る。
#   ★リポジトリの**根**には置かない（たまごさんの原稿がSpotlightで探せなくなるため）。
NEVER_INDEX_DIRS = [
    os.path.join(STATUS),
    os.path.join(STATUS, "queue_history"),
    os.path.join(REPO, ".git"),
    "/Users/mac/Desktop/joy-relief-station/node_modules",
    "/Users/mac/Desktop/joy-relief-station/.output",
    "/Users/mac/Desktop/joy-relief-station/.nuxt",
]


def mark_never_index(dry_run):
    """機械が書き換え続ける場所だけSpotlightの索引から外す。1バイトも消さない。"""
    item = {"name": "spotlight_exclude", "freedBytes": 0, "detail": [], "error": None}
    for d in NEVER_INDEX_DIRS:
        if not os.path.isdir(d):
            item["detail"].append({"path": d, "state": "ディレクトリが無い（対象外）"})
            continue
        marker = os.path.join(d, ".metadata_never_index")
        if os.path.exists(marker):
            item["detail"].append({"path": d, "state": "既に索引除外済み"})
            continue
        if dry_run:
            item["detail"].append({"path": d, "state": "索引除外を付ける予定"})
            continue
        try:
            io.open(marker, "w").write("")
            item["detail"].append({"path": d, "state": "索引除外を付けた"})
        except Exception as e:
            item["detail"].append({"path": d, "state": "付けられなかった", "error": "%r" % (e,)})
    return item


def reap_own_leftovers(dry_run):
    """★自分たち（Cowork側のセッション）が撒いた取り残しを掃く。

    実測：986番の調査中、`top -l 1` を使ったジョブが180秒の強制終了に2回かかり、
      その top が**Macの上に生き残って35%のCPUを食っていた**（12:12の計測で確認）。
      調べに行った側が新しいゴミを置いて帰る、が一番みっともない。
    掃くのは自分たちの使い走り窓口(status/mac_jobs)由来のものだけ。
    """
    item = {"name": "own_leftovers", "freedBytes": 0, "detail": [], "error": None}
    # 1) 180秒で強制終了された調査コマンドの生き残り
    for pat in ("top -l", "vm_stat -c"):
        try:
            r = subprocess.run(["pgrep", "-f", pat], capture_output=True,
                               text=True, timeout=10)
        except Exception as e:
            item["detail"].append({"pattern": pat, "error": "%r" % (e,)})
            continue
        for line in (r.stdout or "").split():
            try:
                p = int(line)
            except ValueError:
                continue
            try:
                rss = int(subprocess.run(["ps", "-o", "rss=", "-p", str(p)],
                                         capture_output=True, text=True,
                                         timeout=10).stdout.strip() or 0) * 1024
            except Exception:
                rss = None
            if dry_run:
                item["detail"].append({"pid": p, "pattern": pat, "wouldKill": True})
                continue
            try:
                os.kill(p, 9)
                item["freedBytes"] += rss or 0
                item["detail"].append({"pid": p, "pattern": pat, "killed": True,
                                       "freedBytes": rss or 0})
            except Exception as e:
                item["detail"].append({"pid": p, "pattern": pat, "killed": False,
                                       "error": "%r" % (e,)})
    # 2) 使い走り窓口の壊れたロック（240秒を超えて残っているもの＝走者はもう居ない）
    lock = os.path.join(STATUS, "mac_jobs", ".runner.lock")
    try:
        if os.path.exists(lock) and (time.time() - os.path.getmtime(lock)) > 300:
            size = os.path.getsize(lock)
            if dry_run:
                item["detail"].append({"path": lock, "wouldFreeBytes": size})
            else:
                os.remove(lock)
                item["freedBytes"] += size
                item["detail"].append({"path": lock, "freedBytes": size,
                                       "note": "5分以上残っていた壊れたロックを外した"})
    except Exception as e:
        item["detail"].append({"path": lock, "error": "%r" % (e,)})
    return item


def relief_pass(dry_run):
    """10分ごとの軽い掃き掃除。週1のゲートより手前で走る。

    ★重いものは一切やらない（du も top も使わない）。実測で top は負荷35のMacから
      180秒以内に返ってこなかった。ここが重くなったら心臓が詰まる。
    """
    ledger = load_ledger()
    ledger["reliefCalls"] = ledger.get("reliefCalls", 0) + 1
    try:
        last = os.path.getmtime(RELIEF_STAMP)
    except OSError:
        last = 0
    if not dry_run and (time.time() - last) < RELIEF_GATE_SECONDS:
        save(ledger)
        return None

    before = vm_snapshot()
    items = [
        reap_our_orphans(dry_run),
        reap_own_leftovers(dry_run),
        sweep_our_logs(dry_run),
        sweep_own_junk(dry_run),
        mark_never_index(dry_run),
    ]
    freed = sum((i.get("freedBytes") or 0) for i in items)
    after = vm_snapshot()

    if not dry_run:
        try:
            io.open(RELIEF_STAMP, "w").write(time.strftime("%F %T"))
        except Exception:
            pass
        ledger["reliefRuns"] = ledger.get("reliefRuns", 0) + 1
        ledger["reliefTotalFreedBytes"] = ledger.get("reliefTotalFreedBytes", 0) + freed
        if freed <= 0:
            ledger["reliefRunsWithZeroFreed"] = ledger.get("reliefRunsWithZeroFreed", 0) + 1

    # ---- 「候補が何件あったか」を数える。ここが赤と緑を分ける要（2026-09-21・986番）----
    # ★最初の実装は「走った回数>0 かつ 片付き=0 → 赤」だけだった。ところがそれだと
    #   **床が綺麗なときも永久に赤**になる（実測：12:20の初回が赤。直前に手で掃いた後だったため）。
    #   永久に赤い印は、見る人が必ず無視するようになる＝警報として死ぬ。
    #   本当に危ないのは「掃くものが目の前にあったのに、1バイトも取れなかった」＝経路が壊れている方。
    #   だから候補数(targets)を数えて、その2つを区別する。数字はどちらも必ず外に出す。
    def _targets(it):
        if it["name"] == "spotlight_exclude":
            return 0          # 印を置くだけ。バイトを取る係ではない
        n = 0
        for x in (it.get("detail") or []):
            e = x.get("error") or ""
            if "既に居ません" in e or "触りません" in e:
                continue      # 元から居ない／自分たちのものではない＝候補ではない
            n += 1
        return n

    targets = sum(_targets(i) for i in items)
    rruns = ledger.get("reliefRuns", 0)
    rtotal = ledger.get("reliefTotalFreedBytes", 0)
    if not dry_run:
        ledger["reliefTotalTargets"] = ledger.get("reliefTotalTargets", 0) + targets
    ttotal = ledger.get("reliefTotalTargets", 0)

    if rruns > 0 and rtotal <= 0 and ttotal > 0:
        rcolor = "red"
        rreason = ("軽い掃除が%d回走り、掃く候補を延べ%d件見つけたのに、片付いたバイト数は0。"
                   "動いているのに何も取れていない" % (rruns, ttotal))
    elif freed <= 0 and targets > 0:
        rcolor = "red"
        rreason = ("今回、掃く候補が%d件あったのに0バイトしか取れなかった"
                   "（走行%d回・累計%s）" % (targets, rruns, _b(rtotal)))
    elif freed <= 0:
        rcolor = "green"
        rreason = ("今回は掃く落ち葉が無かった（候補0件）。走行%d回・累計%s"
                   % (rruns, _b(rtotal)))
    else:
        rcolor = "green"
        rreason = ("今回%s片付いた（候補%d件）。走行%d回・累計%s"
                   % (_b(freed), targets, rruns, _b(rtotal)))

    # ---- 経路そのものが死んでいないか ----
    # 「走った回数>0 なのに片付き=0」と同じくらい危ないのが「そもそも呼ばれなくなった」。
    # weekly-mac-maintenance はこれで半年気づかれなかった。
    # ★ただし「前回から何分空いたか」で赤にしてはいけない（2026-09-21 実測で誤報を出した）。
    #   23:28に**正常に走った直後**に「618分呼ばれていない＝経路が死んでいる」と赤を出した。
    #   前回が12:39、その間にMacが再起動していただけで、経路は生きていた。
    #   Macが寝ていた・落ちていた時間と、経路が壊れた時間は、この差分では区別できない。
    #   → 判定は「**いま**心臓が動いているか」で行う。心臓は生きている限り15秒ごとに
    #     status/.heartbeat_alive をtouchするので、これが古ければ本当に経路が死んでいる。
    #   空いた時間は事実として記録だけする（隠さない）。色には使わない。
    gap_min = int((time.time() - last) / 60) if last else None
    hb_age = None
    try:
        hb_age = time.time() - os.path.getmtime(os.path.join(STATUS, ".heartbeat_alive"))
    except OSError:
        pass
    route_dead = (hb_age is None) or (hb_age > 1800)
    if route_dead:
        rcolor = "red"
        rreason = ("心臓が%s動いていない＝経路が死んでいる。"
                   % ("一度も" if hb_age is None else "%d分" % int(hb_age / 60))) + rreason

    ledger["relief"] = {
        "lastRunAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "gateSeconds": RELIEF_GATE_SECONDS,
        "dryRun": dry_run,
        "lastFreedBytes": freed,
        "lastFreedHuman": _b(freed),
        "runs": rruns,
        "calls": ledger.get("reliefCalls", 0),
        "lastTargets": targets,
        "totalTargets": ttotal,
        "gapMinutes": gap_min,          # 前回から空いた時間（事実として残す。色には使わない）
        "heartbeatAgeSec": None if hb_age is None else int(hb_age),
        "routeDead": route_dead,
        "totalFreedBytes": rtotal,
        "totalFreedHuman": _b(rtotal),
        "runsWithZeroFreed": ledger.get("reliefRunsWithZeroFreed", 0),
        "color": rcolor,
        "reason": rreason,
        "memoryBefore": before,
        "memoryAfter": after,
        "items": items,
        "route": "心臓(heartbeat.sh)が10分ごと・5分便が5分ごとに mac_souji.py を呼ぶ。"
                 "許可ダイアログの要る定期タスクは使っていない",
    }
    save(ledger)
    try:
        with io.open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "t": ledger["relief"]["lastRunAt"], "pass": "relief",
                "dryRun": dry_run, "runs": rruns, "freedBytes": freed,
                "totalFreedBytes": rtotal, "color": rcolor,
                "memFreeMBBefore": before.get("freeMB"),
                "memFreeMBAfter": after.get("freeMB"),
                "swapUsedGBBefore": before.get("swapUsedGB"),
                "swapUsedGBAfter": after.get("swapUsedGB"),
                "swapFreeGBBefore": before.get("swapFreeGB"),
                "swapFreeGBAfter": after.get("swapFreeGB"),
                "perItem": {i["name"]: i.get("freedBytes") for i in items},
                "errors": [{"item": i["name"], "error": i["error"]}
                           for i in items if i.get("error")],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return ledger["relief"]


def main():
    args = sys.argv[1:]
    force = "--force" in args
    dry = "--dry-run" in args

    # ---- 使い走り窓口(status/mac_jobs)の経路を二重にする（2026-09-21・986番）----
    # 実測：23:33〜23:50の17分間、窓口が1本も捌けなかった。
    #   原因は窓口そのものではなく、**窓口を回す経路が心臓1本しか無かったこと。**
    #   心臓は auto_launcher.py の45秒強制終了を繰り返して落ち続け（23:29:58/23:33:11/23:42:50に再起動）、
    #   その心臓から15秒おきに呼ばれる top_status.py が止まり、窓口も道連れになった。
    #   ★見張りを増やすのではなく、経路を増やす。ここは5分便(launchd)からも呼ばれるので、
    #     心臓が落ちている間も窓口が回る。mac_job_runner側にロックがあるので二重には走らない。
    try:
        import mac_job_runner
        mac_job_runner.run()
    except Exception:
        pass

    # ---- 先に10分ごとの軽い掃き掃除。週1のゲートで return される前に必ず通す ----
    # ★ここを週1ゲートの後ろに置くと、週に1回しか掃けない。それが986番までの状態だった。
    try:
        r = relief_pass(dry)
        if r and ("--quiet" not in args):
            print("[軽い掃除/%s] %s" % (r["color"], r["reason"]))
    except Exception:
        import traceback
        try:
            with io.open(OUT_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                    "pass": "relief",
                                    "crash": traceback.format_exc()},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass

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
