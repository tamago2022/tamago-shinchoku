#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1200番【畳む係】こちら側が掴んだまま離していないものを、機械が畳む。

たまごさん（2026-09-27）:
  「スワップ20.7GB／22.5GB、load 36〜107、claudeの起動に91秒。
    Braveには触らない（たまごさんの場所）。代わりにこちら側で減らせるものを全部減らす。
    『今回落とした』で終わらせない。」

■ 実測で分かった「なぜ溜まるのか」（2026-09-27 15:28〜15:29）
  ① 既にある孤児回収（tools/orphan_reaper.py）のホワイトリストは
     `bun run build` / `npm run build` / `next build` しか見ていない。
     実際に64分居残っていたのは **`node ./node_modules/.bin/vite build`**（素のvite）。
     ＝**一番残るものが、網に一度も掛かっていなかった。**
  ② orphan_reaper は「ppid==1」または「60分以上」でしか動かない。
     心臓（tools/top_status.py の末尾）は15秒ごとに python3 を十数本 Popen する。
     重いときは前の周の1本が終わる前に次の周が来るので、**同じスクリプトが何本も重なる**。
     実測：同時刻に ppid=1 の Python が15本（うち13本が同じ親の子）。
     ＝居残りは「1本が長い」形ではなく「短いものが何本も重なる」形で溜まっていた。
  → ①を網に入れ、②は「重なっているものを畳む」で受ける。
    さらに top_status.py 側に「前の周のが生きていたら起こさない」線を1本入れた（そちらが元栓）。

■ この係が触らないもの（絶対）
  ・Brave（たまごさんの場所。閉じるのは本人だけ）
  ・Claude.app と claude CLI のセッション（たまごさんの画面に出ている会話）
  ・常駐で居てもらう係（*_server.py / *_keeper.py / *_guard.py / *_mihari.py /
    *_shirabe.py / relay / tunnel / zunda / 心臓 / oneshot_runner / caffeinate）

■ 呼ばれ方（3口とも同じ本体を呼ぶ＝二重実装しない）
  python3 tools/1200_tatamu.py --stop-hook   … セッションが終わるたび（Stop/SubagentStopフック）
  python3 tools/1200_tatamu.py --shikii      … 心臓から毎周（スワップ/ロードが閾値を超えた時だけ畳む）
  python3 tools/1200_tatamu.py --dry-run     … 判定だけ（何も殺さない）

出力: status/1200_tatamu.json（進捗表が読む1枚）／status/1200_tatamu.jsonl（畳んだ証拠）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(ST, "1200_tatamu.json")
LOG = os.path.join(ST, "1200_tatamu.jsonl")
GATE = os.path.join(ST, ".1200_tatamu_at")
AKA = os.path.join(ST, "shingou_aka.json")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
BRAVE_ONEGAI = os.path.join(ST, ".1200_brave_onegai")

# ---- 触らないもの（ここに載っているものは何があっても殺さない）----
KEEP = re.compile(
    r"(Brave|Claude\.app|claude-code|/MacOS/claude |chrome-native-host|Electron Framework|"
    r"caffeinate|heartbeat|oneshot_runner|1200_tatamu|"
    r"_server\.py|server\.py|_keeper\.py|_guard\.py|_mihari\.py|_shirabe\.py|_watch\.py|"
    r"relay|tunnel|zunda|lt --port|notion-mcp-server|mcp-server|"
    r"Xcode|Finder|Dock|WindowServer|loginwindow|kernel_task)")

# ---- 一発で終わるはずのコマンド（終わっていないなら居残り）----
HITOTSU = re.compile(
    r"(vite build|\besbuild\b|\btsc\b|\beslint\b|\bjest\b|vitest|webpack|rollup|next build|"
    r"bun run (lint|build|test)|npm run (lint|build|test)|\btsserver\b|/bin/gsk )")
NOKOSU = re.compile(r"(--watch|\bvite dev\b|\bvite serve\b|\bnpm run dev\b|\bnext dev\b|\bbun dev\b)")
DEVSERVER = re.compile(r"(vite dev|vite serve|npm run dev|next dev|bun run dev)")

TOOLS_PY = re.compile(re.escape(os.path.join(REPO, "tools")) + r"/([\w\-]+\.py)")

HITOTSU_MIN = 10.0    # 一発コマンドが これ以上 生きていたら居残り（本来は数分で終わる）
TOOL_MIN = 30.0       # 工場の一発スクリプトが これ以上（心臓の相乗りは全部数秒で終わる作り）
DUP_MIN = 3.0         # 同じスクリプトが重なっている場合、古い方を残して これ以上のものを畳む
MAX_KILL = 12         # 1回に畳む上限（暴走させない）
SWAP_SHIKII = 0.85    # スワップ使用がこの割合を超えたら畳む
LOAD_SHIKII = 0.85    # 5分ロード比が「赤の基準」のこの割合を超えたら畳む
GATE_SEC = 55         # 心臓から毎周呼ばれても、実際に測るのは1分に1回
BRAVE_ONEGAI_GB = 10.0  # これ以上Braveが掴んでいたら、たまごさんへ**1回だけ**お願いする


def sh(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout or ""
    except Exception:
        return ""


def jload(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    tmp = "%s.tmp.%d" % (p, os.getpid())
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def logline(o):
    try:
        o["at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    except Exception:
        pass


def etime_min(et):
    """[[DD-]HH:]MM:SS → 分"""
    try:
        parts = et.strip().split("-")
        days = int(parts[0]) if len(parts) == 2 else 0
        rest = parts[-1].split(":")
        if len(rest) == 3:
            h, m, s = rest
        elif len(rest) == 2:
            h, m, s = "0", rest[0], rest[1]
        else:
            return 0.0
        return days * 1440 + int(h) * 60 + int(m) + int(s) / 60.0
    except Exception:
        return 0.0


def ps_all():
    rows = []
    out = sh(["ps", "-Ao", "pid=,ppid=,etime=,rss=,pcpu=,command="], timeout=20)
    for ln in out.splitlines():
        p = ln.strip().split(None, 5)
        if len(p) < 6:
            continue
        try:
            rows.append({"pid": int(p[0]), "ppid": int(p[1]), "min": etime_min(p[2]),
                         "rss": int(p[3]), "cpu": float(p[4]), "cmd": p[5]})
        except Exception:
            continue
    return rows


# ───────────────────────── 測る ─────────────────────────
OURS = re.compile(r"(Claude\.app|claude-code|/MacOS/claude |tamago-shinchoku|tamago_brain|"
                  r"(^|/| )node |Python\.app|python3|\bnode\b)")


def hakaru(rows):
    d = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    sw = sh(["sysctl", "vm.swapusage"], timeout=10)
    mu = re.search(r"used\s*=\s*([0-9.]+)M", sw)
    mt = re.search(r"total\s*=\s*([0-9.]+)M", sw)
    d["swapUsedGB"] = round(float(mu.group(1)) / 1024.0, 2) if mu else None
    d["swapTotalGB"] = round(float(mt.group(1)) / 1024.0, 2) if mt else None
    la = sh(["sysctl", "-n", "vm.loadavg"], timeout=5).split()
    try:
        d["load1"], d["load5"] = float(la[1]), float(la[2])
    except Exception:
        d["load1"] = d["load5"] = None
    try:
        d["cores"] = int(sh(["sysctl", "-n", "hw.ncpu"], timeout=5) or 8)
    except Exception:
        d["cores"] = 8
    d["loadRatio"] = round(d["load5"] / d["cores"], 2) if d.get("load5") else None

    bp = [r for r in rows if "Brave Browser" in r["cmd"]]
    d["brave"] = {
        "procs": len(bp),
        "rssGB": round(sum(r["rss"] for r in bp) / 1048576.0, 2),
        "tabs": len([r for r in bp if "(Renderer)" in r["cmd"]]),
    }
    # 2026-10-01：Claudeが開いたBraveタブ（セッションファイルを読むだけ。Braveには触らない）。
    # 1枚でもあれば 1373_alert.py が赤を出す。読めなければ None（0と偽装しない）。
    try:
        sys.path.insert(0, HERE)
        import brave_claude_tabs
        s = brave_claude_tabs.summary()
        d["brave"]["claudeTabs"] = s.get("claudeTabs")
        d["brave"]["claudeUrls"] = s.get("claudeUrls") or []
        d["brave"]["sessionTabs"] = s.get("tabsTotal")
    except Exception as e:
        d["brave"]["claudeTabs"] = None
        d["brave"]["claudeTabsErr"] = str(e)[:120]
    op = [r for r in rows if "Brave Browser" not in r["cmd"] and OURS.search(r["cmd"])]
    d["ours"] = {"procs": len(op), "rssGB": round(sum(r["rss"] for r in op) / 1048576.0, 2)}
    return d


def shikii_koeta(m):
    """畳むべき状態か。理由（文字列）またはNone。"""
    riyuu = []
    if m.get("swapUsedGB") and m.get("swapTotalGB"):
        wari = m["swapUsedGB"] / m["swapTotalGB"]
        if wari >= SWAP_SHIKII:
            riyuu.append("スワップ %.1f/%.1fGB（%.0f%%）" % (m["swapUsedGB"], m["swapTotalGB"], wari * 100))
    aka = jload(AKA, {}) or {}
    base = aka.get("loadRatio")
    if m.get("loadRatio") and base and m["loadRatio"] >= base * LOAD_SHIKII:
        riyuu.append("5分ロード比 %.2f（赤の基準 %.2f の85%%以上）" % (m["loadRatio"], base))
    return "／".join(riyuu) or None


# ───────────────────────── 畳む候補を選ぶ ─────────────────────────
def kouho(rows):
    live = {r["pid"] for r in rows}
    dev = any(DEVSERVER.search(r["cmd"]) for r in rows)
    found, seen_script = [], {}

    for r in rows:
        cmd = r["cmd"]
        if KEEP.search(cmd):
            continue
        if HITOTSU.search(cmd) and not NOKOSU.search(cmd):
            # 開発サーバーが生きている間は esbuild の常駐サービスは本物なので触らない
            if "esbuild" in cmd and dev:
                continue
            if r["min"] >= HITOTSU_MIN:
                found.append(dict(r, kind="一発コマンドの居残り"))
                continue
        m = TOOLS_PY.search(cmd)
        if m:
            seen_script.setdefault(m.group(1), []).append(r)
            if r["min"] >= TOOL_MIN:
                found.append(dict(r, kind="工場の一発スクリプトの居残り"))

    picked = {f["pid"] for f in found}
    # 同じスクリプトが重なっている：一番古い1本だけ残して、あとは畳む
    for name, rs in seen_script.items():
        if len(rs) < 2:
            continue
        rs = sorted(rs, key=lambda x: -x["min"])
        for r in rs[1:]:
            if r["pid"] in picked or r["min"] < DUP_MIN:
                continue
            found.append(dict(r, kind="同じものが重なって走っている（%s が%d本）" % (name, len(rs))))
            picked.add(r["pid"])
    # 畳むものの子（esbuildのpingサービス等）も一緒に畳む
    for r in rows:
        if r["pid"] in picked or r["ppid"] not in picked or KEEP.search(r["cmd"]):
            continue
        found.append(dict(r, kind="畳んだものの子"))
        picked.add(r["pid"])

    found.sort(key=lambda x: (-x["rss"], -x["min"]))
    return found


def tatamu(found, dry=False):
    killed = []
    for c in found[:MAX_KILL]:
        rec = {"pid": c["pid"], "rssMB": c["rss"] // 1024, "min": round(c["min"], 1),
               "cpu": c["cpu"], "kind": c["kind"], "cmd": c["cmd"][:140]}
        if dry:
            rec["dry"] = True
            killed.append(rec)
            continue
        try:
            os.kill(c["pid"], 15)
            time.sleep(0.2)
            try:
                os.kill(c["pid"], 0)
                os.kill(c["pid"], 9)   # SIGTERMで死ななければ止めを刺す（居残りが本題なので残さない）
                rec["sigkill"] = True
            except OSError:
                pass
            killed.append(rec)
        except Exception as e:
            rec["shippai"] = str(e)
            killed.append(rec)
    return killed


def brave_onegai(m):
    """Braveは閉じられない。だから**1回だけ**お願いして、あとは進捗表の数字に任せる。"""
    b = m.get("brave") or {}
    if (b.get("rssGB") or 0) < BRAVE_ONEGAI_GB or os.path.exists(BRAVE_ONEGAI):
        return False
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "n": 1200, "ok": True, "kind": "onegai",
                "title": "Braveのタブを減らしてもらえますか（こちらからは閉じられません）",
                "honbun": "Braveが%.1fGBを%d本のプロセスで掴んでいます（タブ%d枚）。"
                          "こちら側で畳めるものは全部畳みました（合計%.1fGB）。"
                          "Braveは たまごさんの場所なので触りません。この1回だけお願いします。"
                          "以後は進捗表の小さい1行に本数とGBを出しておくので、"
                          "文章では言いません。"
                          % ((m["brave"]["rssGB"]), m["brave"]["procs"], m["brave"]["tabs"],
                             (m.get("ours") or {}).get("rssGB") or 0),
            }, ensure_ascii=False) + "\n")
        io.open(BRAVE_ONEGAI, "w").write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
        return True
    except Exception:
        return False


def main():
    dry = "--dry-run" in sys.argv
    stop_hook = "--stop-hook" in sys.argv
    shikii = "--shikii" in sys.argv

    # 心臓から毎周呼ばれる口だけ間引く（ps を毎15秒叩かない）
    if shikii:
        try:
            if time.time() - os.path.getmtime(GATE) < GATE_SEC:
                return 0
        except Exception:
            pass
        try:
            io.open(GATE, "w").write(str(int(time.time())))
        except Exception:
            pass

    rows = ps_all()
    m = hakaru(rows)
    koeta = shikii_koeta(m)
    found = kouho(rows)

    # 畳むのは①セッション終了時 ②閾値を超えている時 ③手で呼ばれた時。
    yaru = (not shikii) or bool(koeta)
    killed = tatamu(found, dry=dry) if (yaru and found) else []

    prev = jload(OUT, {}) or {}
    total = int(prev.get("killedTotal") or 0) + len([k for k in killed if not k.get("dry")])
    m.update({
        "killedNow": killed,
        "kouhoN": len(found),
        "killedTotal": total,
        "yobareta": "stop-hook" if stop_hook else ("shikii" if shikii else "te"),
        "shikiiKoeta": koeta,
        "ichigyou": "こちら %.1fGB・%d本／Brave タブ%d枚（Claude分 %s）・%.1fGB／スワップ %.1f/%.1fGB" % (
            (m["ours"]["rssGB"]), m["ours"]["procs"], m["brave"]["tabs"],
            ("?" if m["brave"].get("claudeTabs") is None else "%d枚" % m["brave"]["claudeTabs"]),
            m["brave"]["rssGB"],
            m.get("swapUsedGB") or 0, m.get("swapTotalGB") or 0),
    })
    jsave(OUT, m)
    if killed:
        logline({"event": "tatamu", "yobareta": m["yobareta"], "riyuu": koeta,
                 "killed": killed, "swapUsedGB": m.get("swapUsedGB"),
                 "loadRatio": m.get("loadRatio")})
    brave_onegai(m)

    if not shikii:
        print(json.dumps({"ichigyou": m["ichigyou"], "shikiiKoeta": koeta,
                          "kouho": len(found), "killed": killed},
                         ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 関所そのものがセッションを人質にしない。必ず0で抜ける（証拠だけ残す）。
        logline({"event": "error", "why": str(e)})
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(0)
