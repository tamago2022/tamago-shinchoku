#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
止まらない工場 / 状態1枚（2026-09-02）

やること（測るだけ。負荷をかける実験はしない・プロセスを止めない）:
  1. /Users/mac/Desktop/machine_load.sh（土台・作り直さない）で負荷1行を取る
  2. 既存の生存確認 tamago_kanshi.py を輸入し、生きている Claude Code セッションを列挙
  3. 各セッションの会話ログ末尾から「作業中／質問して停止／承認待ちで固まり／終わって待機」を判定
  4. 負荷（ロード・メモリ圧・スワップ・ディスク・I/O）から「いま何本まで安全か」= safeMax を出す
  5. 全部を status/machine.json に書く（PWAが読む。既存キーはそのまま残す）

使い方:
  python3 factory_status.py            # JSONを標準出力に出すだけ
  python3 factory_status.py --write    # status/machine.json に書く（machine_status_push.sh から呼ばれる）
  python3 factory_status.py --table    # 人が読む表（止まっているセッション一覧）

上限の考え方（全部この1か所。変えるならここだけ）:
  HARD_MAX      : 何があっても超えない本数。今日14本で2回固まった実績から 8（コア数と同じ）
  LOAD_PER_SESS : 走行中セッション1本あたりのロード見込み（仮定値 0.8。今日の実測: 5本で4.6, 14本で11）
  LOAD_CEIL     : ロード÷コア数 の上限 0.8（machine_load.sh と同じ）
  MEM_PER_SESS  : 1本あたりメモリ 350MB（実測平均341MB）
  DISK_STOP_GB  : 空きがこれ未満なら新規0本（5GB＝machine_load.sh と同じ）
  DISK_WARN_GB  : 空きがこれ未満なら「増やさない」（20GB）
  STALL_MIN     : この分数動きが無ければ「止まり」判定（10分。既存 kanshi の STUCK_MIN と同じ）
  SAFE_FLOOR    : 憲法「常時2本」。ロードが高くても、メモリ赤・ディスク5GB未満でない限り上限は2本を下回らない
                  （下回ると見回り係が永久に着火できず「工場が止まる」逆の事故になる）
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "status", "machine.json")
LOADSH = "/Users/mac/Documents/AI作業/2026-09-02/スクリプト/machine_load.sh"
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
KANSHI = os.path.join(VAULT, ".claude", "hooks", "tamago_kanshi.py")

HARD_MAX = int(os.environ.get("FACTORY_HARD_MAX", "8"))
LOAD_PER_SESS = 0.8
LOAD_CEIL = 0.8
MEM_PER_SESS_MB = 350
DISK_STOP_GB = 5
DISK_WARN_GB = 20
STALL_MIN = 10
SAFE_FLOOR = 2
PAGE = 4096

# 「質問して止まっている」の目印。末尾200字にこれがあれば asked 判定
ASK_PAT = re.compile(r"(続けますか|しますか|でしょうか|ますか[？?]|いかがです|どうしますか|確認してください|"
                     r"教えて(ください|くれれば)|一言(もらえ|ください)|GOなら|判断待ち[：:]\s*(?!なし)|"
                     r"押してください|選んでください|\?\s*$|？\s*$)")


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def top_cpu_procs(n=3):
    """CPU使用率トップn（pid付き）。「重い」記録の原因切り分け用（セッション本数のせいか、他プロセスのせいか）"""
    try:
        out = run(["ps", "-Ao", "pid,pcpu,comm"], 8)
        rows = []
        for ln in out.splitlines()[1:]:
            parts = ln.strip().split(None, 2)
            if len(parts) == 3:
                try:
                    rows.append((float(parts[1]), parts[0], os.path.basename(parts[2])))
                except Exception:
                    pass
        rows.sort(key=lambda x: -x[0])
        return "・".join("%s(pid%s,%.0f%%)" % (name, pid, cpu) for cpu, pid, name in rows[:n])
    except Exception:
        return ""


def load_kanshi():
    try:
        spec = importlib.util.spec_from_file_location("tamago_kanshi", KANSHI)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ---------- 負荷（土台は machine_load.sh） ----------
def base_line():
    line = run(["bash", LOADSH], timeout=30).strip()
    num = lambda key, unit: (re.search(key + r" ([0-9.]+)" + unit, line) or [None, None])[1]
    def f(x):
        try:
            return float(x)
        except Exception:
            return None
    d = {
        "raw": line,
        "load": f(num("負荷", "%")), "cpu": f(num("CPU", "%")), "mem": f(num("メモリ圧迫", "%")),
        "swapGB": f(num("スワップ", "GB")), "diskFreeGB": f(num("ディスク空き", "GB")),
        "sessions": f(num("稼働", "本")),
        "note": line.split("｜")[-1].strip() if line else "",
    }
    for k in ("load", "cpu", "mem", "sessions"):
        if d[k] is not None:
            d[k] = int(d[k])
    return d


def load_avg():
    m = re.search(r"\{ ([0-9.]+) ([0-9.]+) ([0-9.]+) \}", run(["sysctl", "-n", "vm.loadavg"]))
    return [float(x) for x in m.groups()] if m else [None, None, None]


def ncpu():
    try:
        return int(run(["sysctl", "-n", "hw.ncpu"]).strip())
    except Exception:
        return 8


def mem_pressure():
    """アクティビティモニタと同じ判定源（mem_stats.py と同じ）。1=green 2=yellow 他=red"""
    try:
        v = int(run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip())
    except Exception:
        return "unknown"
    return {1: "green", 2: "yellow"}.get(v, "red")


def mem_avail_mb():
    """新規セッションに回せるメモリの目安。free+speculative+purgeable は全部、inactive は半分だけ数える（保守的）"""
    d = {}
    for ln in run(["vm_stat"]).splitlines():
        m = re.match(r"Pages ([a-z ]+):\s+(\d+)\.", ln.strip())
        if m:
            d[m.group(1).strip()] = int(m.group(2))
    mb = lambda k: d.get(k, 0) * PAGE / 1048576.0
    return mb("free") + mb("speculative") + mb("purgeable") + 0.5 * mb("inactive")


def swap_trend():
    """スワップが増えているか（1秒空けて2回読む）"""
    def used():
        m = re.search(r"used = ([0-9.]+)M", run(["sysctl", "-n", "vm.swapusage"]))
        return float(m.group(1)) if m else None
    a = used(); time.sleep(1); b = used()
    if a is None or b is None:
        return None, None
    return b, b > a


def io_mbs():
    """ディスクI/O MB/s（iostat 1秒×2回の2回目）。Googleドライブ転送などの渋滞検知用"""
    out = run(["iostat", "-d", "-w", "1", "-c", "2"], timeout=6).strip().splitlines()
    if len(out) < 2:
        return None
    nums = out[-1].split()
    try:
        # 列は KB/t tps MB/s がディスク数分並ぶ。MB/s（3列目ごと）を合計
        return round(sum(float(nums[i]) for i in range(2, len(nums), 3)), 2)
    except Exception:
        return None


def network_status():
    """2026-09-03 有線LAN診断：デフォルトルートのインターフェース名→サービス名を逆引きし、
    Wi-Fiかそれ以外（有線）かを判定。en0/en1は機種でWi-Fi/Ethernetが入れ替わるのでサービス名で見る。
    ping 5発の平均msも測る（100ms超で黄、300ms超で赤の目安。表示側で判定）。"""
    result = {"iface": None, "serviceName": None, "wired": None, "pingMs": None}
    try:
        m = re.search(r"interface:\s*(\S+)", run(["route", "get", "default"], timeout=5))
        iface = m.group(1) if m else None
        result["iface"] = iface
        if iface:
            order = run(["networksetup", "-listnetworkserviceorder"], timeout=5)
            # "(1) Ethernet\n(Hardware Port: Ethernet, Device: en0)" のペアをブロックごとに突合
            blocks = re.findall(r"\(\d+\)\s+(.+?)\n\(Hardware Port: .+?, Device: (\w+)\)", order)
            svc = next((name for name, dev in blocks if dev == iface), None)
            result["serviceName"] = svc
            if svc:
                result["wired"] = "wi-fi" not in svc.lower()
    except Exception:
        pass
    try:
        out = run(["ping", "-c", "5", "-t", "3", "1.1.1.1"], timeout=8)
        m = re.search(r"= [\d.]+/([\d.]+)/", out)  # min/avg/max/stddev の avg
        if m:
            result["pingMs"] = round(float(m.group(1)), 1)
    except Exception:
        pass
    return result


# ---------- セッション状態 ----------
def tail_text(path, chunk=200000):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - chunk))
            return f.read().decode("utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def classify(transcript, idle):
    """会話ログ末尾から状態を判定。
    working    : 動いている（idle < STALL_MIN）
    stuck_tool : 最後がtool_useのまま結果が来ない（承認ダイアログ前で固まり）
    asked      : 最後の文章が質問で終わっている（「続けますか」で止まり）
    idle_done  : 話し終えて待機（畳み候補）
    unknown    : 会話ログが特定できない
    """
    if idle is None or transcript is None:
        return "unknown", ""
    if idle < STALL_MIN:
        return "working", ""
    last = None
    for ln in reversed(tail_text(transcript)):
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if e.get("type") in ("assistant", "user"):
            last = e
            break
    if not last:
        return "unknown", ""
    msg = last.get("message") or {}
    content = msg.get("content")
    if last["type"] == "assistant" and isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content):
            return "stuck_tool", ""
        text = "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        tail = text[-200:].replace("\n", " ")
        if ASK_PAT.search(tail):
            return "asked", tail[-80:]
        return "idle_done", tail[-80:]
    if last["type"] == "user":
        # 最後がユーザー/ツール結果で止まっている＝返答を書く前に落ちた可能性
        return "stuck_tool", ""
    return "idle_done", ""


def session_started_at(s):
    """セッションの開始時刻。会話ログ(jsonl)の最初の timestamp を使う（プロセスの起動時刻はターンごとに変わるので使わない）。
    ログが読めなければ ps の起動時刻で代用。"""
    tp = s.get("transcript")
    if tp:
        try:
            with open(tp, "r", encoding="utf-8", errors="ignore") as f:
                for _ in range(20):
                    ln = f.readline()
                    if not ln:
                        break
                    try:
                        ts = json.loads(ln).get("timestamp")
                    except Exception:
                        continue
                    if ts:
                        import datetime
                        d = datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                        return d.astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        except Exception:
            pass
    if s.get("start"):
        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(s["start"]))
    return None


def raw_sessions():
    """kanshi の生存一覧＋会話ログ突合（--resume 起動も解決済み）。session_watchdog.py もこれを使う"""
    k = load_kanshi()
    if not k:
        return []
    try:
        ss = k.sessions()
        # 2026-09-03 追加：見張り番が CLI（~/.local/bin/claude -p …）で立てた再開・引き継ぎ・着火セッションは
        # kanshi の「claude-code/…MacOS/claude」条件に当たらず数えられない。ここで拾って同じ形で足す（headless=True）。
        seen = {str(s["pid"]) for s in ss}
        for ln in run(["ps", "-Ao", "pid,lstart,etime,rss,args"]).splitlines():
            if " -p " not in ln or "MacOS/claude" in ln or "Helpers/disclaimer" in ln:
                continue
            if not re.search(r"(^|\s|/)claude(\s|$)", ln) or not re.search(r"--(resume|session-id)\s", ln):
                continue
            p = ln.split()
            if len(p) < 9 or p[0] in seen:
                continue
            try:
                st = time.mktime(time.strptime(" ".join(p[1:6]), "%a %b %d %H:%M:%S %Y"))
            except Exception:
                st = None
            m = re.search(r"--(?:resume|session-id)\s+([0-9a-f-]{36})", ln)
            ss.append({"pid": p[0], "etime": p[6], "mb": int(p[7]) / 1024.0, "start": st, "headless": True,
                       "cli_hint": m.group(1) if m else None})
        ss = k.idle_min(ss)
        # 2026-09-02 追加：Desktopが --resume=<id> で立て直したセッションは会話ログの先頭時刻が古く、
        # kanshi の「起動時刻±3分」照合で（不明）になる。ps の引数から id を直接取って突合する。
        resume_map = {}
        for ln in run(["ps", "-Ao", "pid,args"]).splitlines():
            m = re.search(r"^\s*(\d+)\s.*MacOS/claude .*--resume=([0-9a-f-]{36})", ln)
            if m and "Helpers/disclaimer" not in ln:
                resume_map[m.group(1)] = m.group(2)
        for s in ss:
            if s.get("cli_hint"):
                resume_map[str(s["pid"])] = s["cli_hint"]
        if resume_map:
            jl = {}
            for root, _, files in os.walk(os.path.expanduser("~/.claude/projects")):
                for fn in files:
                    if fn.endswith(".jsonl"):
                        jl[fn[:-6]] = os.path.join(root, fn)
            for s in ss:
                cid = resume_map.get(str(s["pid"]))
                if cid and cid in jl and (s.get("transcript") is None):
                    s["transcript"] = jl[cid]
                    try:
                        s["idle"] = (time.time() - os.path.getmtime(jl[cid])) / 60.0
                    except Exception:
                        pass
        # 2026-09-03 追加：それでも突合できない（不明）プロセスは、作業ディレクトリ（lsof cwd）に対応する
        # 会話ログ置き場から「まだ誰にも紐づいていない・プロセス起動後に更新された」最新の jsonl を当てる。
        claimed = {s.get("transcript") for s in ss if s.get("transcript")}
        for s in ss:
            if s.get("transcript"):
                continue
            try:
                out = run(["lsof", "-a", "-p", str(s["pid"]), "-d", "cwd", "-Fn"], timeout=8)
                cwd = next((ln[1:] for ln in out.splitlines() if ln.startswith("n/")), None)
                if not cwd:
                    continue
                pdir = os.path.expanduser("~/.claude/projects/" + re.sub(r"[^A-Za-z0-9]", "-", cwd))
                cands = []
                for fn in os.listdir(pdir) if os.path.isdir(pdir) else []:
                    if fn.endswith(".jsonl"):
                        p = os.path.join(pdir, fn)
                        if p in claimed:
                            continue
                        mt = os.path.getmtime(p)
                        if s.get("start") and mt < s["start"] - 60:
                            continue
                        cands.append((mt, p))
                if cands:
                    cands.sort(reverse=True)
                    s["transcript"] = cands[0][1]
                    s["idle"] = (time.time() - cands[0][0]) / 60.0
                    claimed.add(cands[0][1])
            except Exception:
                pass
        ss = k.enrich(ss)
    except Exception:
        return []
    return ss


URL_PAT = re.compile(r"https?://[^\s)\]>」』]+")
REPORT_HOURS = 3  # これ以上「報告」（assistantの文章）が無ければ赤
# 2026-09-03 「反映されたのに無言」検知（温泉棚・マガジン・PWAで3連続発生。たまごさんが自分で画面を見て気づいた実害）。
# 最後の報告文だけでなく会話全体からURL・公開/反映の痕跡を探し、正式な「完了：」報告が無いまま終わっていたら機械が拾う。
DEPLOY_PAT = re.compile(r"(公開|反映|デプロイ|Publish|Pages|本番|x-deployment-id)")


def transcript_stats(path):
    """会話ログ全体を1回なめて、PWAが要る数字を出す（開始・最後の報告・押された回数・誰が押したか・成果URL・完了報告か）"""
    st = {"firstAt": None, "lastReportAt": None, "lastReportText": "", "humanPushes": 0, "dispatchPushes": 0,
          "watchdogResumes": 0, "urls": [], "done": False, "failed": False, "model": None,
          "turns": 0, "lastActivityAt": None}
    if not path:
        return st
    try:
        with open(path, "rb") as f:
            data = f.read().decode("utf-8", "ignore")
    except Exception:
        return st
    first_user = True
    all_text_parts = []
    for ln in data.splitlines():
        if '"type":"user"' not in ln and '"type":"assistant"' not in ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        ts = e.get("timestamp")
        if ts and not st["firstAt"]:
            st["firstAt"] = ts
        m = e.get("message") or {}
        c = m.get("content")
        if e.get("type") == "user":
            if isinstance(c, str):
                text = c
            elif isinstance(c, list):
                text = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            else:
                text = ""
            if not text.strip():
                continue  # tool_result
            if first_user:
                first_user = False
                continue  # 最初の指示は「押した」に数えない
            if "【見張り番" in text:
                st["watchdogResumes"] += 1
            elif text.startswith("From ") or "From " in text[:60]:
                st["dispatchPushes"] += 1
            else:
                st["humanPushes"] += 1
        elif e.get("type") == "assistant" and isinstance(c, list):
            mdl = m.get("model")
            if mdl:
                st["model"] = mdl
            st["turns"] += 1
            if ts:
                st["lastActivityAt"] = ts
            text = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                all_text_parts.append(text)
            if text.strip() and m.get("stop_reason") == "end_turn":
                st["lastReportAt"] = ts
                st["lastReportText"] = text[-200:].replace("\n", " ")
    t = st["lastReportText"]
    st["done"] = bool(re.search(r"(完了[：:]|^\s*完了|✅)", t))
    st["failed"] = bool(re.search(r"(できない[：:]|❌|失敗[：:]|エラーで止|中止)", t)) and not st["done"]
    st["urls"] = list(dict.fromkeys(URL_PAT.findall(t)))[:3]
    # 最後の報告文だけでなく会話全体を見る。「公開/反映」の痕跡＋URLが会話のどこかにあるのに、
    # 最後の報告（完了：）にそのURLが無い＝「自分のところで完結して黙って終わった」の機械的な定義
    all_text = "\n".join(all_text_parts)
    all_urls = list(dict.fromkeys(URL_PAT.findall(all_text)))
    has_deploy_word = bool(DEPLOY_PAT.search(all_text))
    st["deployUrls"] = [u for u in all_urls if u not in st["urls"]][:5]
    st["unreportedDeploy"] = bool((all_urls or has_deploy_word) and not st["done"] and (st["deployUrls"] or (has_deploy_word and not st["urls"])))
    return st


def status_of(kind, idle, st):
    """PWA用の状態: 作業中(緑)／承認待ち(黄)／止まっている・報告なし3時間超・失敗(赤)／完了(青)"""
    if st["done"]:
        return "完了", "blue"
    if st["failed"]:
        return "失敗", "red"
    if kind == "working":
        return "作業中", "green"
    if idle is not None and idle >= REPORT_HOURS * 60:
        return "報告なし%d時間超" % REPORT_HOURS, "red"
    if kind == "stuck_tool":
        return "承認待ち", "yellow"
    if kind in ("asked", "idle_done") and st.get("unreportedDeploy"):
        return "反映済み・報告なし", "red"
    if kind in ("asked", "idle_done"):
        return "止まっている", "red"
    return "不明", "gray"


def local_id_index():
    idx = {}
    try:
        for root, _, files in os.walk(os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")):
            for fn in files:
                if fn.startswith("local_") and fn.endswith(".json"):
                    try:
                        d = json.load(open(os.path.join(root, fn), encoding="utf-8"))
                        if d.get("cliSessionId"):
                            idx[d["cliSessionId"]] = d.get("sessionId")
                    except Exception:
                        pass
    except Exception:
        pass
    return idx


def sessions():
    out = []
    watchdog_state = {}
    try:
        with open(os.path.join(REPO, "status", "watchdog-state.json"), encoding="utf-8") as f:
            watchdog_state = json.load(f)
    except Exception:
        pass
    idx = local_id_index()
    for s in raw_sessions():
        kind, tail = classify(s.get("transcript"), s.get("idle"))
        tr = s.get("transcript")
        cli = os.path.basename(tr)[:-6] if tr and tr.endswith(".jsonl") else None
        st = transcript_stats(tr)
        label, color = status_of(kind, s.get("idle"), st)
        started = s.get("start")
        wd = watchdog_state.get(cli or "", {})
        out.append({
            "cli": cli,
            "localId": idx.get(cli),
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)) if started else None,
            "elapsedMin": int((time.time() - started) / 60) if started else None,
            "lastReportAt": st["lastReportAt"],
            "lastReport": st["lastReportText"][-100:],
            "status": label, "color": color,
            "urls": st["urls"],
            "unreportedDeploy": st.get("unreportedDeploy", False), "deployUrls": st.get("deployUrls", []),
            "humanPushes": st["humanPushes"], "dispatchPushes": st["dispatchPushes"],
            "watchdogResumes": max(st["watchdogResumes"], wd.get("tries", 0)),
            "done": st["done"],
            "pid": int(s["pid"]),
            "title": s.get("title") or "（不明）",
            "dispatch": bool(s.get("dispatch")),
            "mb": int(s.get("mb") or 0),
            "idleMin": round(s["idle"], 1) if s.get("idle") is not None else None,
            "kind": kind,
            "tail": tail,
            "model": st.get("model"),
            "turns": st.get("turns", 0),
            "lastActivityAt": st.get("lastActivityAt"),
            # 2026-09-02 PWA第2段階：開始時刻（ps の lstart）と会話ログID。経過時間・3h/6h札は画面側で計算
            "startedAt": session_started_at(s),
            "cli": os.path.splitext(os.path.basename(s["transcript"]))[0] if s.get("transcript") else None,
        })
    out.sort(key=lambda x: -(x["idleMin"] or 0))
    return out


KIND_LABEL = {
    "working": "🟢作業中", "asked": "🟡質問して停止", "stuck_tool": "🔴承認待ち/固まり",
    "idle_done": "⚪終わって待機", "unknown": "（不明）",
}


# ---------- 安全上限 ----------
def safe_max(base, ss, la1, cores, pressure, avail_mb, swap_up, iomb):
    alive = len(ss)
    working = sum(1 for s in ss if s["kind"] == "working")
    reasons = []
    disk = base.get("diskFreeGB")

    # ロードから：あと何本足せるか（走行中1本≒LOAD_PER_SESS）
    more_load = None
    if la1 is not None:
        more_load = int((cores * LOAD_CEIL - la1) / LOAD_PER_SESS)
        if more_load < 0:
            reasons.append("5分平均ロード%.1f（コア%d×%.1f超）" % (la1, cores, LOAD_CEIL))
    # メモリから
    more_mem = None
    if pressure == "red":
        more_mem = 0; reasons.append("メモリ圧=赤")
    elif pressure == "yellow":
        more_mem = 0; reasons.append("メモリ圧=黄")
    else:
        more_mem = int(avail_mb / MEM_PER_SESS_MB)
    if swap_up:
        more_mem = min(more_mem, 0); reasons.append("スワップ増加中")
    # ディスク
    if disk is not None:
        if disk < DISK_STOP_GB:
            reasons.append("ディスク空き%dGB未満" % DISK_STOP_GB)
            return 0, reasons, alive, working
        if disk < DISK_WARN_GB:
            reasons.append("ディスク空き%dGB未満（増やさない）" % DISK_WARN_GB)
            more_load = min(more_load or 0, 0); more_mem = min(more_mem or 0, 0)

    mores = [x for x in (more_load, more_mem) if x is not None]
    more = min(mores) if mores else 0
    more = max(more, -alive)
    sm = min(HARD_MAX, alive + more)
    if sm < SAFE_FLOOR and pressure != "red":
        sm = SAFE_FLOOR  # 常時2本は守る（赤・ディスク切れ以外）
    if sm == HARD_MAX and alive + more > HARD_MAX:
        reasons.append("上限%d本（固定）" % HARD_MAX)
    return max(sm, 0), reasons, alive, working


def build():
    base = base_line()
    la = load_avg(); cores = ncpu()
    pressure = mem_pressure(); avail = mem_avail_mb()
    swap_gb, swap_up = swap_trend()
    iomb = io_mbs()
    net = network_status()
    ss = sessions()
    # 上限は5分平均ロード（la[1]）で決める。1分平均は瞬間的に跳ねて上限が0↔6と暴れるため。1分平均はJSONに load1 として残す
    sm, reasons, alive, working = safe_max(base, ss, la[1] if la[1] is not None else la[0], cores, pressure, avail, swap_up, iomb)
    # ---- 2026-09-03 本数維持：実測校正（calibration.json）・人が操作中なら1本下げる・予兆で減らす ----
    calib = {}
    try:
        calib = json.load(open(os.path.join(REPO, "status", "calibration.json"), encoding="utf-8"))
    except Exception:
        pass
    cap = min(HARD_MAX, int(calib.get("safeN") or HARD_MAX))
    target = max(2, int(calib.get("target") or max(2, int(cap * 0.8))))
    user_active = False
    try:
        idle_ns = int(re.search(r'"HIDIdleTime" = (\d+)', run(["ioreg", "-c", "IOHIDSystem"])).group(1))
        user_active = idle_ns < 300 * 1e9  # 5分以内にキーボード/マウス操作あり＝たまごさんがPCを使っている
    except Exception:
        pass
    if user_active and cap > 2:
        cap -= 1; reasons.append("たまごさん操作中（上限-1）")
    load_ratio5 = (la[1] / cores) if la[1] is not None and cores else None
    predict = []
    if pressure == "yellow":
        predict.append("メモリ圧=黄")
    if swap_up:
        predict.append("スワップ増加")
    if load_ratio5 is not None and load_ratio5 > 1.5:
        predict.append("5分ロード比%.1f" % load_ratio5)
    if predict and alive > 0:
        sm = min(sm, alive - 1)
        reasons.append("予兆（%s）→1本減らす" % "・".join(predict))
    if sm > cap:
        sm = cap
        reasons.append("実測上限%d本" % cap)
    if sm < SAFE_FLOOR and pressure != "red":
        sm = SAFE_FLOOR
    target = min(target, cap)
    # 2026-09-03 枠の下振れ＝失点（たまごさん訂正：週枠も「使い切ったら終わり」ではなく火曜17:59直前99%が正解。
    # 曲線を大きく下回るのも上回るのと同じく損）。5時間枠のもったいない度、または全モデル週枠の曲線下振れがあれば、
    # 安全上限(cap)の範囲内で本数を増やす方向に倒す。上振れ側は本数を減らさない（Fableを絞るのはmodel_for()側の役目）
    try:
        qj = json.load(open(os.path.join(REPO, "status", "quota.json"), encoding="utf-8"))
    except Exception:
        qj = {}
    q5 = qj.get("session5h") or {}
    all_curve = qj.get("allCurve") or {}
    if q5.get("mottainai") and cap > target:
        target = cap
        reasons.append("5時間枠もったいない度%s%%→本数を上限%d本まで増やす" % (q5.get("wasteRiskPct"), cap))
    elif all_curve.get("state") == "under" and cap > target:
        target = cap
        reasons.append("週枠(全モデル)が曲線を%spt下振れ→本数を上限%d本まで増やす" % (-(all_curve.get("overPct") or 0), cap))
    # 落とすなら誰か：Dispatch発で「終わって待機」のもの（会話は残る・--resume で戻せる）。動いているものは落とさない
    shed = [s for s in ss if s["kind"] == "idle_done" and s.get("dispatch")]
    shed.sort(key=lambda x: -(x["idleMin"] or 0))
    if pressure == "red" or (load_ratio5 is not None and load_ratio5 > 2.0):
        try:
            subprocess.run(["python3", os.path.join(HERE, "mark_heavy.py"), "自動検知: %s" % ("メモリ赤" if pressure == "red" else "5分ロード比%.1f" % load_ratio5),
                            "--auto", "--top-cpu", top_cpu_procs()], capture_output=True, timeout=10)
        except Exception:
            pass
    stalled = [s for s in ss if s["kind"] in ("asked", "stuck_tool")]
    waiting = [s for s in ss if s["kind"] == "idle_done"]
    more_ok = max(0, sm - alive)

    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    now = now[:-2] + ":" + now[-2:]
    parts = ["負荷 %s%%" % (base["load"] if base["load"] is not None else "測定不可")]
    parts.append("セッション%d本（作業中%d・止まり%d）" % (alive, working, len(stalled)))
    if sm < alive:
        parts.append("上限%d本・%d本超過（畳め）" % (sm, alive - sm))
    elif more_ok > 0:
        parts.append("上限%d本・あと%d本OK" % (sm, more_ok))
    else:
        parts.append("上限%d本・増やすな" % sm)
    parts.append("空き%sGB" % (base["diskFreeGB"] if base["diskFreeGB"] is not None else "測定不可"))
    line = " ｜ ".join(parts)

    d = dict(base)
    d.update({
        "measuredAt": now,
        "sessions": alive if ss else base.get("sessions"),
        "working": working,
        "stalled": len(stalled),
        "waiting": len(waiting),
        "safeMax": sm,
        "moreOK": more_ok,
        "hardMax": HARD_MAX,
        "cap": cap, "target": target, "calibratedSafeN": calib.get("safeN"), "calibrationBasis": calib.get("basis"),
        "userActive": user_active, "predict": predict,
        "shedCandidates": [{"pid": s["pid"], "title": s["title"], "idleMin": s["idleMin"]} for s in shed[:3]],
        "below": max(0, target - alive),
        "blockReason": "、".join(reasons),
        "load1": la[0], "load5": la[1], "load15": la[2], "cores": cores,
        "loadRatio": round(la[0] / cores, 2) if la[0] is not None else None,
        "memPressure": pressure, "memAvailGB": round(avail / 1024.0, 1),
        "swapGB": swap_gb if swap_gb is not None else base.get("swapGB"),
        "swapIncreasing": swap_up,
        "ioMBs": iomb,
        "network": net,
        "stalledList": [{k: s[k] for k in ("pid", "title", "kind", "idleMin", "dispatch")} for s in stalled],
        # 2026-09-02 PWA用の全項目（名前/ID・開始・最後の報告・経過・状態色・成果URL・押された回数/再開回数）。tail（本文断片）だけ落とす
        "sessionList": [{k: v for k, v in s.items() if k != "tail"} for s in ss],
        "line": line,
    })
    # 2026-09-03 モデル選択の判断材料：走行中セッションのモデル別本数（machine.jsonで見える化。quotaの曲線判定と突き合わせる）
    mc = {}
    for s in ss:
        mdl = s.get("model") or "不明"
        mc[mdl] = mc.get(mdl, 0) + 1
    d["modelCounts"] = mc
    d["note"] = "上限%d本・あと%d本OK" % (sm, more_ok) + ("（%s）" % d["blockReason"] if reasons else "")
    done = [s for s in ss if s.get("done")]
    auto = [s for s in done if (s.get("humanPushes", 0) + s.get("dispatchPushes", 0)) == 0]
    d["autonomy"] = {"alive": len(ss), "done": len(done), "doneWithoutHumanPush": len(auto),
                     "ratio": round(len(auto) / len(done), 2) if done else None,
                     "note": "終了報告済みのうち、人（たまご/Dispatch）に押されずに完了した割合。見張り番の再開は機械なので人に数えない"}
    return d


def table(d):
    print(d["line"])
    if d["blockReason"]:
        print("理由: " + d["blockReason"])
    print("ロード %s/%dコア（比%.2f）・メモリ圧=%s・空きメモリ目安%sGB・I/O %sMB/s" % (
        d["load1"], d["cores"], d["loadRatio"] or 0, d["memPressure"], d["memAvailGB"], d["ioMBs"]))
    print()
    print("| PID | 状態 | 動きなし | タイトル | 発生元 | メモリ |")
    print("|---|---|---|---|---|---|")
    for s in d["sessionList"]:
        print("| %d | %s | %s分 | %s | %s | %dMB |" % (
            s["pid"], KIND_LABEL.get(s["kind"], s["kind"]),
            "%.0f" % s["idleMin"] if s["idleMin"] is not None else "?",
            s["title"], "Dispatch" if s["dispatch"] else "直接", s["mb"]))


def main():
    d = build()
    if "--table" in sys.argv:
        table(d)
        return 0
    js = json.dumps(d, ensure_ascii=False)
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(js)
        os.replace(tmp, OUT)
        # 実測校正用の時系列（5分おき1行・3日分）。本数と負荷の対応をここに溜め、calibrate.py が上限を出す
        try:
            hp = os.path.join(os.path.dirname(OUT), "load_history.jsonl")
            row = {"t": d["measuredAt"], "n": d.get("sessions"), "working": d.get("working"),
                   "loadRatio": round(d["load5"] / d["cores"], 2) if d.get("load5") and d.get("cores") else None,
                   "cpu": d.get("cpu"), "mem": d.get("memPressure"), "memAvailGB": d.get("memAvailGB"),
                   "swapGB": d.get("swapGB"), "swapUp": d.get("swapIncreasing"), "ioMBs": d.get("ioMBs"),
                   "userActive": d.get("userActive"), "predict": d.get("predict")}
            lines = []
            if os.path.exists(hp):
                lim = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))
                for ln in open(hp, encoding="utf-8"):
                    try:
                        if (json.loads(ln).get("t") or "")[:10] >= lim:
                            lines.append(ln if ln.endswith("\n") else ln + "\n")
                    except Exception:
                        pass
            lines.append(json.dumps(row, ensure_ascii=False) + "\n")
            with open(hp, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass
        print(d["line"])
    else:
        print(js)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 測れなくても止まらない
        print(json.dumps({"error": str(e), "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}))
        sys.exit(0)
