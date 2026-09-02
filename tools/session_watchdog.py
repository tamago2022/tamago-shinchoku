#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
見張り番（session watchdog）v4  2026-09-03

止まっている Claude Code セッションを機械で検知し、①自動再開 ②自動引き継ぎ ③空きがあれば自動着火 をする。
5分おきの既存 launchd（com.tamago.machine-status → machine_status_push.sh）から factory_status.py の直後に呼ばれる。
新しい常駐は作らない。見張り番自身は数秒で終わる（再開・引き継ぎ・着火したセッションは別プロセスとして走る）。

実験で確認済み（2026-09-02 19:40）:
  `claude -p --resume <cliSessionId> --permission-mode auto "…"` は Desktop 側のプロセスが待機中でも、同じ会話ログの続きとして走る。
  1回の再開で入力5〜9万トークン（会話の再読み込み）⇒ タダではない。回数上限と安全弁が必須。
  Dispatch の send_message は子セッション・定期タスクからは使えない（実測）⇒ 機械の見張り番は CLI 一択。

① 自動再開：Dispatch発の子で STALL_MIN 分進んでいないもの（質問して停止／承認待ち固まり／話し終えて待機で終了報告なし）に「続けて」を送る。
② 自動引き継ぎ（たまごさん 2026-09-03「疲れたら休んでいい。次の人が発射」）：次のどれか1つでも当てはまれば新セッションを立てて続きをやらせる
     a. HANDOFF_HOURS（3時間）経過して進んでいない   b. HANDOFF_TURNS（100ターン）超え   c. 再開 MAX_TRIES（3回）でも動かない
   引き継ぎ文＝どこまで終わったか／次に何をするか／何を試して何がダメだったか／完了条件1行／マニュアル要点。
③ 自動着火（「空きコンロを作らない」）：Macに余裕（machine.json の moreOK>0）があれば、ホワイトボードの取れる最上位1件を新セッションで着火する。
   1回の見張りで1本、IGNITE_INTERVAL_MIN おき、見張り番が立てた headless セッションは同時 MAX_HEADLESS 本まで。

安全弁:
  - Macが危険（メモリ圧=赤／スワップ増加中／ディスク空き5GB未満）なら何もしない
  - 引き継ぎ・着火は固定上限 hardMax（8本）と moreOK を守る。再開は既存の続きなので本数上限では止めない
  - 同じセッションへの再開は MAX_TRIES 回まで。再開後 COOLDOWN_MIN は再判定しない
  - 課金する仕組みは無い（ログイン済みの claude CLI をそのまま使う＝いつもの枠を使う）
  - 見送った時も理由を 見張り番ログ.md に残す（無言の見送り禁止）

記録:
  見張り番ログ.md（1行ずつ）／status/watchdog-state.json（試行回数・累計）／machine.json の watchdog 節と metrics（PWAが読む）
  metrics = 止まった回数(stalls)／自動再開(autoResumes)／引き継ぎ(handoffs)／自動着火(ignitions)／人が押した回数(humanPushes)／自走完了率(autonomy)

使い方:
  python3 session_watchdog.py            # 判定＋実行
  python3 session_watchdog.py --dry-run  # 判定だけ（何も起動しない）
  python3 session_watchdog.py --status   # 試行回数・累計
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MACHINE_JSON = os.path.join(REPO, "status", "machine.json")
STATE_JSON = os.path.join(REPO, "status", "watchdog-state.json")
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
LOG_MD = os.path.join(VAULT, "AI出力", "_ルール", "見張り番ログ.md")
DISPATCH_INBOX = os.path.join(VAULT, "AI出力", "_ルール", "留守中の判断待ち.md")
HANDOFF_DIR = os.path.join(VAULT, "AI出力", "_ルール", "引き継ぎ_自動")
SESSIONS_DIR = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
WHITEBOARD = "/Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py"
WHITEBOARD_MD = "/Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.md"
STANDARD_MD = os.path.join(VAULT, "AI出力", "_ルール", "セッション標準動作.md")
CLAUDE = os.environ.get("CLAUDE_BIN") or (os.path.expanduser("~/.local/bin/claude")
        if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

EFFORT_DEFAULT = "high"   # 2026-09-03 公式推奨：普段はhigh。max常用をやめる
EFFORT_STUCK = "xhigh"    # 詰まって再開する時だけxhigh
STALL_MIN = 15
MAX_TRIES = 3
MAX_PER_RUN = 2
HANDOFF_HOURS = 3
HANDOFF_TURNS = 100
MAX_HANDOFF_PER_RUN = 1
MAX_IDLE_HOURS = 24
COOLDOWN_MIN = 20
IGNITE_INTERVAL_MIN = 10
MAX_HEADLESS = 3
MANUAL_ESSENTIALS = ("マニュアルの要点：①たまごさんに質問しない。判断が要れば仮定を置いて進み、仮定は末尾に1行。"
                     "②「続けますか」と聞かない。報告のために止まらない。③1つ本番に出たら即Dispatchへ報告（完了／問題／判断待ちの3行・本番の直URL）。"
                     "④Lovableのエージェントとビルドは使わない。⑤公開（Lovable Publish）は聞かずに押す。"
                     "⑥止まってよいのは 削除／課金／外部公開(公開ボタン以外)／認証情報 だけ。⑦完了は本番で別の目が確認して初めて完了（それまでは検証待ち）。"
                     "⑧完了していないのに止まらない。同じ経路で2回失敗したら次へ移る（1引数/ツールを変える→2CLI⇄API⇄ブラウザを乗り換える→"
                     "3問題を分割する→4別Agentに委任→5公式ドキュメントを読む→6目的に戻って迂回する）。"
                     "全部試して1行ずつ結果を書けて初めて『袋小路：◯◯（試した経路：1→…／2→…）』で判断待ちにできる。書式の無い「できません」は差し戻す。"
                     "⑨3時間か100ターンを超えたら休んでよい：最後の報告に「どこまで終わったか／次に何をするか／何を試して何がダメだったか」を書いて終了する（次の人が続ける）。"
                     "⑩(公式推奨・2026-09-02) Before you start, say in a line what you're about to do; brief updates while you work. "
                     "Close with a short recap that stands on its own."
                     "⑪(公式推奨・クレジット節約) when it will not affect the end result, try to surgically edit a file rather than rewrite the entire thing."
                     "⑫(公式推奨・ツール呼び出し) First privately list what you need next; then request every item that doesn't depend on another's result in this one response.")
RESUME_MSG = ("【見張り番・自動再開】止まっていたので続けます。止まらずに最後まで走り切ること。" + MANUAL_ESSENTIALS +
              " もし作業が本当に終わっているなら「完了：」で始まる3行の最終報告だけ書いて終了する。")
DONE_PAT = re.compile(r"(完了[：:]|^完了|判断待ち[：:]\s*なし|畳みます|ここで畳|終了します|以上です|報告は以上|完了／問題／判断待ち)")
EXCLUDE_TITLE = re.compile(r"(mimawari|見回り|watchdog|見張り番)", re.I)


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def load_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def append(path, line):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new and path == LOG_MD:
                f.write("# 見張り番ログ（自動・1行ずつ）\n\n5分おきに `session_watchdog.py` が書く。いつ・どのセッションを・なぜ再開／引き継ぎ／着火したか。見送りも書く。\n\n")
            f.write(line + "\n")
    except Exception:
        pass


def run_cmd(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------- セッション情報 ----------
def cli_index():
    idx = {}
    for root, _, files in os.walk(SESSIONS_DIR):
        for fn in files:
            if not fn.startswith("local_") or not fn.endswith(".json"):
                continue
            d = load_json(os.path.join(root, fn), {})
            cli = d.get("cliSessionId")
            if cli:
                idx[cli] = {"local": d.get("sessionId"), "title": d.get("title") or "", "cwd": d.get("cwd") or "/",
                            "dispatch": bool(d.get("dispatchParentId")), "archived": bool(d.get("isArchived"))}
    return idx


def proc_cwd(pid):
    for ln in run_cmd(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], 8).splitlines():
        if ln.startswith("n/"):
            return ln[1:]
    return None


def scan_transcript(path):
    """会話ログを1回なめて、引き継ぎ判断と引き継ぎ文に要るものを取る"""
    st = {"turns": 0, "lastText": "", "firstUser": "", "errors": [], "tried": [], "model": ""}
    if not path:
        return st
    try:
        with open(path, "rb") as f:
            data = f.read().decode("utf-8", "ignore")
    except Exception:
        return st
    for ln in data.splitlines():
        if '"type":"user"' not in ln and '"type":"assistant"' not in ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        m = e.get("message") or {}
        c = m.get("content")
        if e.get("type") == "assistant":
            # 「ターン」＝話し終えた回数（stop_reason=end_turn）。ツール呼び出し1回ずつ数えると10分で100を超えて引き継ぎが連鎖する（01:31 実測）
            if m.get("stop_reason") == "end_turn":
                st["turns"] += 1
            if m.get("model"):
                st["model"] = m["model"]
            if isinstance(c, list):
                t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                if t.strip():
                    st["lastText"] = t
                    if re.search(r"(できない|できなかった|失敗|エラー|ダメ|うまくいか|見つから)", t):
                        st["tried"].append(t[-160:].replace("\n", " "))
        else:
            if isinstance(c, str):
                t = c
            elif isinstance(c, list):
                t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                        cc = b.get("content")
                        txt = cc if isinstance(cc, str) else "".join(x.get("text", "") for x in cc if isinstance(x, dict)) if isinstance(cc, list) else ""
                        if txt.strip():
                            st["errors"].append(txt[:160].replace("\n", " "))
            else:
                t = ""
            if t.strip() and not st["firstUser"]:
                st["firstUser"] = t[:300]
    st["errors"] = st["errors"][-5:]
    st["tried"] = st["tried"][-3:]
    return st


def synth_meta(s, scan):
    """管理JSONに無いセッション（見張り番が --session-id で立てた子）の meta を作る"""
    t = scan.get("firstUser", "")
    if "【見張り番" in t:
        title = "引き継ぎ子"
        m = re.search(r"「([^」]{1,30})」", t)
        if m:
            title = "引き継ぎ子:" + m.group(1)
        return {"local": None, "title": title, "cwd": proc_cwd(s["pid"]) or os.path.expanduser("~"), "dispatch": True, "archived": False, "headless": True}
    return None


def sessions_with_transcript():
    import importlib.util
    spec = importlib.util.spec_from_file_location("factory_status", os.path.join(HERE, "factory_status.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = []
    for s in mod.raw_sessions():
        kind, tail = mod.classify(s.get("transcript"), s.get("idle"))
        tr = s.get("transcript")
        cli = os.path.basename(tr)[:-6] if tr and tr.endswith(".jsonl") else None
        out.append({"pid": int(s["pid"]), "cli": cli, "idle": s.get("idle"), "kind": kind, "transcript": tr,
                    "headless": bool(s.get("headless"))})
    return out


def machine_unsafe(machine):
    if machine.get("memPressure") == "red":
        return "メモリ圧=赤"
    if machine.get("swapIncreasing"):
        return "スワップ増加中"
    d = machine.get("diskFreeGB")
    if d is not None and d < 5:
        return "ディスク空き5GB未満"
    return ""


def whiteboard_rows_owned(local_id):
    rows = []
    if not local_id:
        return rows
    try:
        for ln in open(WHITEBOARD_MD, encoding="utf-8"):
            if ln.startswith("| T") and ("| %s |" % local_id) in ln:
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                if len(c) >= 9:
                    rows.append({"id": c[0], "task": c[3], "next": c[8]})
                elif len(c) >= 8:
                    rows.append({"id": c[0], "task": c[2], "next": c[7]})
    except Exception:
        pass
    return rows


def standard_six():
    """セッション標準動作の6行（無ければ短縮版）"""
    try:
        txt = open(STANDARD_MD, encoding="utf-8").read()
        m = re.search(r"```\n(【セッション標準動作】.*?)```", txt, re.S)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ("【セッション標準動作】1.憲法とホワイトボードを読む 2.最優先の空き1件を取り自分のIDを書く 3.走り切る 4.止まってよいのは第5条だけ "
            "5.終わったら状態更新して次を取る 6.たまごさんに質問しない・判断はDispatchへ")


def decide(s, meta, scan, state):
    """(動作, 理由)  None / "resume" / "handoff" """
    if not s["cli"] or not meta:
        return None, "会話ログ/管理JSONと突合できない"
    if meta.get("archived"):
        return None, "アーカイブ済み"
    if not meta.get("dispatch"):
        return None, "Dispatch発でない（直接タブ・見回り係）"
    if EXCLUDE_TITLE.search(meta.get("title", "")):
        return None, "見回り系は対象外"
    st = state.get(s["cli"], {})
    if st.get("handedOff"):
        return None, "引き継ぎ済み→%s" % str(st["handedOff"])[:8]
    if s["idle"] is None:
        return None, "動きの時刻が取れない"
    if s["idle"] < STALL_MIN:
        if scan["turns"] >= HANDOFF_TURNS and not DONE_PAT.search(scan["lastText"][-300:]):
            return "handoff", "%dターン超（%d）" % (HANDOFF_TURNS, scan["turns"])
        return None, "動いている（%s分）" % round(s["idle"], 1)
    if s["idle"] > MAX_IDLE_HOURS * 60:
        return None, "放置%.1f時間＝畳み対象" % (s["idle"] / 60)
    if s["kind"] == "idle_done" and DONE_PAT.search(scan["lastText"][-300:]):
        return None, "終了報告済み"
    if st.get("tries", 0) >= MAX_TRIES:
        return "handoff", "%d回再開しても進まない" % MAX_TRIES
    # 週枠 85% 超：走行中の Fable セッションは、話し終えた切りのいいところで Sonnet の新セッションへ交代（本数は減らさない）
    if quota().get("fableLevel") == "stop" and "fable" in (scan.get("model") or "") and not FABLE_OK.search(meta.get("title", "")):
        return "handoff", "Fable週枠%s%%超→Sonnetへ交代" % quota().get("fablePct")
    if s["idle"] >= HANDOFF_HOURS * 60:
        return "handoff", "%.1f時間進んでいない" % (s["idle"] / 60)
    if scan["turns"] >= HANDOFF_TURNS:
        return "handoff", "%dターン超（%d）" % (HANDOFF_TURNS, scan["turns"])
    if time.time() - st.get("lastResumeAt", 0) < COOLDOWN_MIN * 60:
        return None, "再開直後（%d分以内）" % COOLDOWN_MIN
    if s["kind"] in ("asked", "stuck_tool"):
        return "resume", {"asked": "質問して停止", "stuck_tool": "承認待ち/固まり"}[s["kind"]]
    if s["kind"] == "idle_done":
        return "resume", "話し終えて待機（未完了）"
    return None, "判定不能(%s)" % s["kind"]


# ---------- 実行 ----------
# ---------- モデル方針（2026-09-03 たまごさん：既定Sonnet。Fableは判断とセンスが結果に直結するものだけ） ----------
SONNET = "claude-sonnet-5"
FABLE = "claude-fable-5-1"
# たまごさん確定（2026-09-03 01:35）：Fable＝マガジン（記事の執筆）だけ。それ以外は全部 Sonnet。
FABLE_OK = re.compile(r"(マガジン|MAGAZINE|記事の執筆|記事執筆|特集記事)", re.I)
MECHANICAL = re.compile(r"(仕入れ|統一|修正|記録|調査|整理|検証|棚卸|一括|移行|同期|バックアップ|洗い出し|リスト|検品)")
SWITCH_LOG = os.path.join(REPO, "status", "model_switches.jsonl")


def quota():
    return load_json(os.path.join(REPO, "status", "quota.json"), {})


def model_for(task_text, prev_model=None, why=""):
    """(モデル, 理由)。既定Sonnet。Fableはマガジン記事執筆だけ、かつ週枠に余裕がある時だけ。判断は機械。人に聞かない"""
    q = quota()
    level = q.get("fableLevel", "ok")
    t = task_text or ""
    if level == "stop":
        model, reason = SONNET, "Fable週枠%s%%≥%d→Sonnet" % (q.get("fablePct"), q.get("stopPct", STOP_PCT_DEFAULT))
    elif FABLE_OK.search(t) and not MECHANICAL.search(t):
        if level == "warn":
            model, reason = SONNET, "マガジンだがFable枠が警告域（%s%%）→Sonnetで代替" % q.get("fablePct")
        else:
            model, reason = FABLE, "マガジン記事の執筆（唯一のFable例外）"
    else:
        model, reason = SONNET, "マガジン以外→既定Sonnet"
    try:
        with open(SWITCH_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": now(), "task": t[:80], "from": prev_model, "to": model, "why": reason, "fablePct": q.get("fablePct")}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return model, reason


STOP_PCT_DEFAULT = 85


def spawn(cmd, cwd, log_name, tag):
    log_out = os.path.join(REPO, "status", log_name)
    try:
        with open(log_out, "ab") as f:
            f.write(("\n=== %s %s\n" % (now(), tag)).encode())
            p = subprocess.Popen(cmd, cwd=cwd if cwd and os.path.isdir(cwd) else os.path.expanduser("~"),
                                 stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        return p.pid
    except Exception as e:
        append(LOG_MD, "- %s ❌ 起動失敗（%s）: %s" % (now(), tag, e))
        return None


def resume(cli, cwd):
    cmd = [CLAUDE, "-p", "--resume", cli, "--permission-mode", "auto", "--output-format", "json", "--effort", EFFORT_STUCK]
    if quota().get("fableLevel") == "stop":
        cmd += ["--model", SONNET]  # 枠が苦しい時は再開もSonnetで（止めるのではなく置き換える）
    return spawn(cmd + [RESUME_MSG], cwd, "watchdog-resume-%s.log" % cli[:8], "resume " + cli)


def handoff(s, meta, scan, why):
    cli = s["cli"]
    new_id = str(uuid.uuid4())
    me_new = "wd_" + new_id[:8]
    title = meta.get("title") or "（不明）"
    rows = whiteboard_rows_owned(meta.get("local"))
    wb_lines = "\n".join("- %s %s ｜ 完了条件／次の一手: %s" % (r["id"], r["task"], r["next"]) for r in rows) or "- （ホワイトボードに担当行なし）"
    tried = "\n".join("- " + x for x in (scan["tried"] + scan["errors"])) or "- （記録なし）"
    done_cond = rows[0]["next"] if rows else (scan["firstUser"][:200] or "（最初の指示を参照）")
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    path = os.path.join(HANDOFF_DIR, "%s_%s.md" % (time.strftime("%Y%m%d_%H%M"), cli[:8]))
    body = ("# 自動引き継ぎ %s ← 「%s」(%s)\n\n理由: %s（%dターン）\n\n## 最初の指示（何の仕事か）\n\n%s\n\n"
            "## どこまで終わったか（前のセッションの最後の報告）\n\n%s\n\n## 次に何をするか（ホワイトボードの担当行）\n\n%s\n\n"
            "## 何を試して何がダメだったか（同じ失敗を繰り返さない）\n\n%s\n\n## 完了条件（1行）\n\n%s\n\n## 新しいセッション\n\n- session-id: `%s`（ホワイトボード上のID: %s）\n- cwd: `%s`\n"
            % (now(), title, cli[:8], why, scan["turns"], scan["firstUser"] or "（不明）", scan["lastText"][-900:] or "（文章なし）",
               wb_lines, tried, done_cond, new_id, me_new, meta.get("cwd")))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception:
        pass
    for r in rows:
        subprocess.run(["python3", WHITEBOARD, "release", r["id"], "--me", meta.get("local") or "-", "--force",
                        "--note", "%s ｜自動引き継ぎ→%s" % (r["next"], me_new)], capture_output=True, timeout=20)
        subprocess.run(["python3", WHITEBOARD, "take", r["id"], "--me", me_new], capture_output=True, timeout=20)
    prompt = ("【見張り番・自動引き継ぎ】前のセッション「%s」が%s。前の人は休み。あなたが続きを最後までやる。\n"
              "引き継ぎ書: %s（同じ内容を下に貼る）\n\n%s\n\n%s\n\n"
              "あなたのID: %s（ホワイトボードの担当は付け替え済み。終わったら `python3 %s set <ID> --me %s --state 検証待ち --note \"…\"`、次は `next --me %s`）\n%s\n"
              "最後は「完了：／問題：／判断待ち：」の3行で終了する。"
              % (title, why, path, body, standard_six(), me_new, WHITEBOARD, me_new, me_new, MANUAL_ESSENTIALS))
    model, mwhy = model_for(title + " " + (rows[0]["task"] if rows else "") + " " + scan.get("firstUser", "")[:200])
    append(LOG_MD, "- %s 🎛 引き継ぎ先のモデル: %s（%s）" % (now(), model, mwhy))
    pid = spawn([CLAUDE, "-p", "--session-id", new_id, "--model", model, "--effort", EFFORT_DEFAULT,
                "--permission-mode", "auto", "--output-format", "json", prompt],
                meta.get("cwd"), "watchdog-handoff-%s.log" % new_id[:8], "handoff from " + cli)
    return new_id, pid, path


def ignite(machine):
    """ホワイトボードの取れる最上位1件を新セッションで着火する。(new_id, pid, 行の文字列) / (None, None, 理由)"""
    new_id = str(uuid.uuid4())
    me_new = "wd_" + new_id[:8]
    out = run_cmd(["python3", WHITEBOARD, "next", "--me", me_new], 30).strip()
    if not out or "取れる仕事なし" in out or "--me" in out:
        return None, None, out or "ホワイトボード応答なし"
    row = out.splitlines()[-1]
    m = re.search(r"(T\d{3})", row)
    tid = m.group(1) if m else "?"
    note = ""
    try:
        for ln in open(WHITEBOARD_MD, encoding="utf-8"):
            if ln.startswith("| %s " % tid):
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                note = c[-1]
    except Exception:
        pass
    prompt = ("【見張り番・自動着火】空きがあるのでホワイトボードの最上位を取った。あなたのID: %s\n仕事: %s\n完了条件／次の一手: %s\n\n%s\n\n%s\n"
              "終わったら `python3 %s set %s --me %s --state 検証待ち --note \"本番URL…\"`。その後 `python3 %s next --me %s` で次を取る（空きを作らない）。"
              "最後は「完了：／問題：／判断待ち：」の3行で終了する。"
              % (me_new, row, note, standard_six(), MANUAL_ESSENTIALS, WHITEBOARD, tid, me_new, WHITEBOARD, me_new))
    cwd = "/Users/mac/Desktop/joy-relief-station" if "joy-relief-station" in note or "本番" in note else os.path.expanduser("~/Desktop")
    model, mwhy = model_for(row + " " + note)
    append(LOG_MD, "- %s 🎛 着火のモデル: %s（%s）" % (now(), model, mwhy))
    pid = spawn([CLAUDE, "-p", "--session-id", new_id, "--model", model, "--effort", EFFORT_DEFAULT,
                "--permission-mode", "auto", "--output-format", "json", prompt],
                cwd, "watchdog-ignite-%s.log" % new_id[:8], "ignite " + tid)
    if not pid:
        subprocess.run(["python3", WHITEBOARD, "release", tid, "--me", me_new, "--note", note], capture_output=True, timeout=20)
        return None, None, "起動失敗"
    return new_id, pid, row


def main():
    dry = "--dry-run" in sys.argv
    state = load_json(STATE_JSON, {})
    totals = state.setdefault("_totals", {"stalls": 0, "autoResumes": 0, "handoffs": 0, "ignitions": 0, "gated": 0})
    if "--status" in sys.argv:
        print(json.dumps(state, ensure_ascii=False, indent=1)); return 0
    machine = load_json(MACHINE_JSON, {})
    idx = cli_index()
    ss = sessions_with_transcript()
    resumed, skipped, unrec, handed, ignited = [], [], [], [], []
    n = h = 0
    unsafe = machine_unsafe(machine)
    headless_alive = sum(1 for s in ss if s.get("headless"))
    for s in ss:
        scan = scan_transcript(s["transcript"]) if s["transcript"] else {"turns": 0, "lastText": "", "firstUser": "", "errors": [], "tried": []}
        meta = (idx.get(s["cli"]) if s["cli"] else None) or synth_meta(s, scan)
        action, why = decide(s, meta, scan, state)
        title = (meta or {}).get("title", "（不明）")
        if action is None:
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": why}); continue
        totals["stalls"] += 1
        if unsafe:
            totals["gated"] += 1
            append(LOG_MD, "- %s ⏸ 見送り: 「%s」(%s) %s だが Mac が危険（%s）" % (now(), title, s["cli"][:8], why, unsafe))
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "安全弁: %s" % unsafe}); continue
        st = state.setdefault(s["cli"], {"tries": 0})
        if action == "handoff":
            alive = machine.get("sessions") or len(ss)
            if alive >= machine.get("hardMax", 8):
                append(LOG_MD, "- %s ⏸ 引き継ぎ見送り: 「%s」(%s) %s だが生存%d本で固定上限" % (now(), title, s["cli"][:8], why, alive))
                skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "固定上限（生存%d本）" % alive}); continue
            if h >= MAX_HANDOFF_PER_RUN or headless_alive >= MAX_HEADLESS:
                skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "今回の引き継ぎ上限／headless %d本" % headless_alive}); continue
            if dry:
                handed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "dry": True}); h += 1; continue
            new_id, pid, path = handoff(s, meta, scan, why)
            st["handedOff"] = new_id or "failed"; st["handedOffAt"] = time.time(); st["title"] = title
            totals["handoffs"] += 1; headless_alive += 1
            unrec.append({"cli": s["cli"], "title": title, "idleMin": round(s["idle"] or 0), "handedOffTo": new_id})
            handed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "newSession": new_id, "newPid": pid, "handoffFile": path})
            append(LOG_MD, "- %s 🔁 引き継ぎ: 「%s」(%s) 理由=%s → 新セッション %s（%s）" % (now(), title, s["cli"][:8], why, (new_id or "起動失敗")[:8], os.path.basename(path)))
            append(DISPATCH_INBOX, "| %s | 見張り番: 「%s」(%s) を自動引き継ぎ（%s）→ 新セッション %s。前のセッションは畳んでよい | 記録のみ・判断不要 |" % (now(), title, s["cli"][:8], why, (new_id or "起動失敗")[:8]))
            h += 1; continue
        if n >= MAX_PER_RUN:
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "今回の再開上限%d本" % MAX_PER_RUN}); continue
        if dry:
            resumed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "dry": True}); n += 1; continue
        pid = resume(s["cli"], meta.get("cwd"))
        st["tries"] = st.get("tries", 0) + 1; st["lastResumeAt"] = time.time(); st["title"] = title
        totals["autoResumes"] += 1
        resumed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "try": st["tries"], "resumePid": pid})
        append(LOG_MD, "- %s ▶ 再開 %d/%d: 「%s」(%s) 理由=%s 放置%d分 %dターン 負荷=%s%%" % (now(), st["tries"], MAX_TRIES, title, s["cli"][:8], why, round(s["idle"] or 0), scan["turns"], machine.get("load")))
        n += 1
    # 進んだセッションの試行回数はリセット
    for s in ss:
        stt = state.get(s["cli"]) if s["cli"] else None
        if stt and s["idle"] is not None and s["idle"] < STALL_MIN and stt.get("tries") and time.time() - stt.get("lastResumeAt", 0) > COOLDOWN_MIN * 60:
            stt["tries"] = 0
    # ③ 本数維持：目標（target＝実測上限の8割）を下回っていれば着火して埋める。上限を超えて予兆が出ていれば1本落とす
    more_ok = machine.get("moreOK") or 0
    alive_n = machine.get("sessions") or len(ss)
    target = machine.get("target") or 2
    below = max(0, target - alive_n)
    last_ign = state.get("_lastIgnitionAt", 0)
    shed_done = None
    # 落とす：上限超過＋予兆（メモリ黄／スワップ増／ロード比1.5超）または Mac 危険。落とすのは Dispatch発で「終わって待機」のものだけ（--resume で戻せる）
    if (unsafe or machine.get("predict")) and alive_n > (machine.get("safeMax") or 0) and machine.get("shedCandidates"):
        c = machine["shedCandidates"][0]
        if not dry:
            try:
                os.kill(int(c["pid"]), 15)
                shed_done = c
                totals["sheds"] = totals.get("sheds", 0) + 1
                append(LOG_MD, "- %s 🔻 1本落とした: 「%s」(pid %s・終わって待機%d分) 理由=%s（生存%d本＞上限%s本）" % (
                    now(), c["title"], c["pid"], round(c.get("idleMin") or 0), unsafe or "・".join(machine.get("predict") or []), alive_n, machine.get("safeMax")))
            except Exception as e:
                append(LOG_MD, "- %s ❌ 落とせず pid %s: %s" % (now(), c.get("pid"), e))
    if unsafe:
        ign_why = "Mac危険（%s）" % unsafe
    elif more_ok <= 0:
        ign_why = "空きなし（上限%s本・目標%s本・生存%s本）" % (machine.get("safeMax"), target, alive_n)
    elif below <= 0:
        ign_why = "目標%d本を満たしている（生存%d本）" % (target, alive_n)
    elif headless_alive >= MAX_HEADLESS:
        ign_why = "見張り番の子が既に%d本" % headless_alive
    elif time.time() - last_ign < IGNITE_INTERVAL_MIN * 60:
        ign_why = "前回着火から%d分未満（目標まであと%d本）" % (IGNITE_INTERVAL_MIN, below)
    elif dry:
        ign_why = "dry-run（着火可・目標まであと%d本）" % below
    else:
        fired = 0
        ign_why = "着火せず"
        for _ in range(min(below, more_ok, 2, MAX_HEADLESS - headless_alive)):
            new_id, pid, row = ignite(machine)
            if not new_id:
                ign_why = "着火せず: %s" % row; break
            fired += 1; totals["ignitions"] += 1
            ignited.append({"newSession": new_id, "pid": pid, "row": row})
            append(LOG_MD, "- %s 🔥 自動着火: %s → 新セッション %s（目標%d本・生存%d本・空き%d本）" % (now(), row, new_id[:8], target, alive_n, more_ok))
            alive_n += 1
        if fired:
            state["_lastIgnitionAt"] = time.time(); ign_why = "着火した（%d本）" % fired
    if not dry:
        save_json(STATE_JSON, state)
        machine["watchdog"] = {"lastRun": now(), "resumed": resumed, "handedOff": handed, "ignited": ignited, "unrecoverable": unrec,
                               "ignite": ign_why, "shed": shed_done,
                               "keep": {"target": target, "alive": alive_n, "below": max(0, target - alive_n),
                                        "line": "現在%d本／上限%s本／目標%d本／あと%d本いける" % (alive_n, machine.get("safeMax"), target, max(0, more_ok))},
                               "stalledSkipped": [x for x in skipped if x["kind"] in ("asked", "stuck_tool", "idle_done")
                                                  and not x["why"].startswith(("動いている", "Dispatch発でない", "見回り系", "終了報告済み"))]}
        sl = machine.get("sessionList") or []
        done = [x for x in sl if x.get("done")]
        auto = [x for x in done if (x.get("humanPushes", 0) + x.get("dispatchPushes", 0)) == 0]
        machine["metrics"] = {"stalls": totals["stalls"], "autoResumes": totals["autoResumes"], "handoffs": totals["handoffs"],
                              "ignitions": totals["ignitions"], "gated": totals["gated"],
                              "humanPushes": sum(x.get("humanPushes", 0) + x.get("dispatchPushes", 0) for x in sl),
                              "doneAlive": len(done), "doneWithoutHumanPush": len(auto),
                              "autonomyRatio": round(len(auto) / len(done), 2) if done else None,
                              "note": "累計は watchdog-state.json（見張り番が動き出した 2026-09-02 夜から）。自走完了率＝終了報告済みのうち人に押されず完了した割合"}
        machine["quota"] = quota()  # 利用枠の推定（PWAが読む）
        try:  # 自動でモデルを切り替えた記録（直近10件）
            sw = [json.loads(x) for x in open(SWITCH_LOG, encoding="utf-8").read().splitlines()[-10:] if x.strip()]
            machine["quota"]["switches"] = sw
        except Exception:
            pass
        if os.path.exists(MACHINE_JSON):
            save_json(MACHINE_JSON, machine)
    print(json.dumps({"resumed": resumed, "handedOff": handed, "ignited": ignited, "ignite": ign_why, "unrecoverable": unrec, "skipped": skipped}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        append(LOG_MD, "- %s ❌ 見張り番エラー: %s" % (now(), e))
        print(json.dumps({"error": str(e)}))
        sys.exit(0)
