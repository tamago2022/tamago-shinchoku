#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
見張り番（session watchdog）2026-09-02

止まっている Claude Code セッションを機械で検知し、`claude -p --resume <id>` で「続けて」を送って自動再開する。
5分おきの既存 launchd（com.tamago.machine-status → machine_status_push.sh）から factory_status.py の直後に呼ばれる。
新しい常駐は作らない。見張り番自身は数秒で終わる（再開したセッションは別プロセスとして走る）。

実験で確認済み（2026-09-02 19:40）:
  `claude -p --resume <cliSessionId> "…"` は Desktop 側のプロセスが待機中でも、同じ会話ログ（~/.claude/projects/**/<id>.jsonl）
  の続きとして走り、返答を同じログに書く。所要4秒・1回あたり入力5〜9万トークン（会話の再読み込み）。
  ⇒ 再開は「タダではない」。回数上限と負荷ゲートが必須。

判定（factory_status.py の分類を使う。閾値は STALL_MIN）:
  asked      = 質問して止まっている        → 再開する
  stuck_tool = 承認待ち／固まり            → 再開する（承認ダイアログは headless では出ないので auto で進む）
  idle_done  = 話し終えて待機              → 末尾が「完了／判断待ち／畳みます」等の終了報告なら再開しない。それ以外は再開する
  working    = 動いている                  → 触らない
  Dispatch発でないもの（見回り係・たまごさんが直接開いたタブ）は触らない。

安全弁:
  - machine.json の moreOK が 0（＝上限に達している／負荷高）なら再開しない（固まらせない方が優先）
  - 同じセッションへの再開は MAX_TRIES 回まで。超えたら「復旧不能」として記録し Dispatch へ（留守中の判断待ち.md に1行）
  - 1回の実行で再開するのは MAX_PER_RUN 本まで
  - 最後の活動から MAX_IDLE_HOURS 以上経っているものは「放置済み」とみなし触らない（畳み対象。見回り係の仕事）
  - 再開した直後（COOLDOWN_MIN）は同じセッションを再判定しない
  - 課金する仕組みは無い（ログイン済みの claude CLI をそのまま使う＝いつもの枠を使う）

使い方:
  python3 session_watchdog.py            # 判定＋再開（machine.json に watchdog 節を書き足し、ログを1行残す）
  python3 session_watchdog.py --dry-run  # 判定だけ（何も再開しない）
  python3 session_watchdog.py --status   # 現在の試行回数・復旧不能一覧
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MACHINE_JSON = os.path.join(REPO, "status", "machine.json")
STATE_JSON = os.path.join(REPO, "status", "watchdog-state.json")   # 試行回数など（公開リポジトリ内。セッションIDとタイトルのみ）
VAULT = "/Users/mac/Library/Mobile Documents/iCloud~md~obsidian/Documents/tamago_brain"
LOG_MD = os.path.join(VAULT, "AI出力", "_ルール", "見張り番ログ.md")
DISPATCH_INBOX = os.path.join(VAULT, "AI出力", "_ルール", "留守中の判断待ち.md")
SESSIONS_DIR = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
CLAUDE = os.environ.get("CLAUDE_BIN") or (os.path.expanduser("~/.local/bin/claude")
        if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else "claude")

STALL_MIN = 15          # これ以上進んでいなければ止まっている
MAX_TRIES = 3           # 同じセッションへ送る上限
MAX_PER_RUN = 2         # 1回の見張りで再開する本数
MAX_IDLE_HOURS = 6      # これ以上放置されたものは触らない（畳み対象）
COOLDOWN_MIN = 20       # 再開してからこの間は再判定しない
RESUME_MSG = ("【見張り番・自動再開】止まっていたので続けます。止まらずに最後まで走り切ること。"
              "質問で止まらない（仮定を置いて進め、仮定は末尾に1行）。止まってよいのは 削除／課金／外部公開／認証情報 の4つだけ。"
              "もし作業が本当に終わっているなら「完了：」で始まる3行の最終報告だけ書いて終了する。")
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
                f.write("# 見張り番ログ（自動・1行ずつ）\n\n5分おきに `session_watchdog.py` が書く。いつ・どのセッションを・なぜ再開したか。\n\n")
            f.write(line + "\n")
    except Exception:
        pass


def cli_index():
    """pid→cliSessionId は直接取れないので、会話ログのパスから cli id を、local_*.json から title/cwd/dispatch を引く"""
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


def transcript_tail_text(path, n=300):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - 200000))
            lines = f.read().decode("utf-8", "ignore").splitlines()
        for ln in reversed(lines):
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if e.get("type") == "assistant":
                c = (e.get("message") or {}).get("content")
                if isinstance(c, list):
                    t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                    if t.strip():
                        return t[-n:]
    except Exception:
        pass
    return ""


def sessions_with_transcript():
    """factory_status.py と同じ生存判定（kanshi）で、pid・idle・transcript を取る"""
    import importlib.util
    fs = os.path.join(HERE, "factory_status.py")
    spec = importlib.util.spec_from_file_location("factory_status", fs)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    k = mod.load_kanshi()
    if not k:
        return []
    ss = k.enrich(k.idle_min(k.sessions()))
    out = []
    for s in ss:
        kind, tail = mod.classify(s.get("transcript"), s.get("idle"))
        tr = s.get("transcript")
        cli = os.path.basename(tr)[:-6] if tr and tr.endswith(".jsonl") else None
        out.append({"pid": int(s["pid"]), "cli": cli, "idle": s.get("idle"), "kind": kind, "transcript": tr})
    return out


def decide(s, meta, state):
    """(再開するか, 理由)"""
    if not s["cli"] or not meta:
        return False, "会話ログ/管理JSONと突合できない"
    if meta["archived"]:
        return False, "アーカイブ済み"
    if not meta["dispatch"]:
        return False, "Dispatch発でない（直接タブ・見回り係）"
    if EXCLUDE_TITLE.search(meta["title"]):
        return False, "見回り系は対象外"
    if s["idle"] is None or s["idle"] < STALL_MIN:
        return False, "動いている（%s分）" % (round(s["idle"], 1) if s["idle"] is not None else "?")
    if s["idle"] > MAX_IDLE_HOURS * 60:
        return False, "放置%.1f時間＝畳み対象" % (s["idle"] / 60)
    st = state.get(s["cli"], {})
    last = st.get("lastResumeAt", 0)
    if time.time() - last < COOLDOWN_MIN * 60:
        return False, "再開直後（%d分以内）" % COOLDOWN_MIN
    if st.get("tries", 0) >= MAX_TRIES:
        return False, "復旧不能（%d回送っても動かない）" % MAX_TRIES
    if s["kind"] in ("asked", "stuck_tool"):
        return True, {"asked": "質問して停止", "stuck_tool": "承認待ち/固まり"}[s["kind"]]
    if s["kind"] == "idle_done":
        tail = transcript_tail_text(s["transcript"])
        if DONE_PAT.search(tail):
            return False, "終了報告済み"
        return True, "話し終えて待機（未完了）"
    return False, "判定不能(%s)" % s["kind"]


def resume(cli, cwd):
    """claude -p --resume で「続けて」を送る。子プロセスは切り離して走らせる（見張り番は待たない）"""
    log_out = os.path.join(REPO, "status", "watchdog-resume-%s.log" % cli[:8])
    cmd = [CLAUDE, "-p", "--resume", cli, "--permission-mode", "auto", "--output-format", "json", RESUME_MSG]
    try:
        with open(log_out, "ab") as f:
            f.write(("\n=== %s resume %s\n" % (now(), cli)).encode())
            p = subprocess.Popen(cmd, cwd=cwd if os.path.isdir(cwd) else os.path.expanduser("~"),
                                 stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
        return p.pid
    except Exception as e:
        append(LOG_MD, "- %s ❌ %s 再開コマンド失敗: %s" % (now(), cli[:8], e))
        return None


def main():
    dry = "--dry-run" in sys.argv
    state = load_json(STATE_JSON, {})
    if "--status" in sys.argv:
        for k, v in sorted(state.items(), key=lambda kv: -kv[1].get("lastResumeAt", 0)):
            print(k[:8], v)
        return 0
    machine = load_json(MACHINE_JSON, {})
    more_ok = machine.get("moreOK")
    idx = cli_index()
    ss = sessions_with_transcript()
    resumed, skipped, unrec = [], [], []
    n = 0
    for s in ss:
        meta = idx.get(s["cli"]) if s["cli"] else None
        ok, why = decide(s, meta, state)
        title = (meta or {}).get("title", "（不明）")
        if not ok:
            if why.startswith("復旧不能") and s["cli"] not in [u["cli"] for u in unrec]:
                unrec.append({"cli": s["cli"], "title": title, "idleMin": round(s["idle"] or 0)})
                st = state.setdefault(s["cli"], {})
                if not st.get("reported"):
                    st["reported"] = True
                    append(DISPATCH_INBOX, "| %s | 見張り番: 「%s」(%s) を%d回再開しても進まない。復旧不能。畳むか手で押すかDispatch判断 | 自動では復旧できないため |" % (now(), title, s["cli"][:8], MAX_TRIES))
                    append(LOG_MD, "- %s 🛑 復旧不能: %s (%s) %d回送っても進まず。Dispatchへ" % (now(), title, s["cli"][:8], MAX_TRIES))
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": why})
            continue
        if n >= MAX_PER_RUN:
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "今回の上限%d本に達した" % MAX_PER_RUN}); continue
        if more_ok is not None and more_ok <= 0:
            skipped.append({"pid": s["pid"], "title": title, "kind": s["kind"], "why": "負荷ゲート（moreOK=0）: %s" % machine.get("blockReason", "")}); continue
        st = state.setdefault(s["cli"], {"tries": 0})
        if dry:
            resumed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "dry": True}); n += 1; continue
        pid = resume(s["cli"], meta["cwd"])
        st["tries"] = st.get("tries", 0) + 1
        st["lastResumeAt"] = time.time()
        st["title"] = title
        resumed.append({"pid": s["pid"], "cli": s["cli"], "title": title, "why": why, "try": st["tries"], "resumePid": pid})
        append(LOG_MD, "- %s ▶ 再開 %d/%d: 「%s」(%s) 理由=%s 放置%d分 負荷=%s%% moreOK=%s" % (
            now(), st["tries"], MAX_TRIES, title, s["cli"][:8], why, round(s["idle"] or 0), machine.get("load"), more_ok))
        n += 1
    # 動いている（idle<STALL）セッションの試行回数はリセット（進んだ＝復旧した）
    for s in ss:
        if s["cli"] in state and s["idle"] is not None and s["idle"] < STALL_MIN and state[s["cli"]].get("tries"):
            if time.time() - state[s["cli"]].get("lastResumeAt", 0) > COOLDOWN_MIN * 60:
                state[s["cli"]]["tries"] = 0
                state[s["cli"]].pop("reported", None)
    if not dry:
        save_json(STATE_JSON, state)
        machine["watchdog"] = {"lastRun": now(), "resumed": resumed, "unrecoverable": unrec,
                               "stalledSkipped": [x for x in skipped if x["kind"] in ("asked", "stuck_tool", "idle_done") and not x["why"].startswith(("動いている", "Dispatch発でない", "見回り系", "終了報告済み"))]}
        if os.path.exists(MACHINE_JSON):
            save_json(MACHINE_JSON, machine)
        if not resumed and not unrec:
            pass  # 変化なしはログを汚さない
    print(json.dumps({"resumed": resumed, "unrecoverable": unrec, "skipped": skipped}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        append(LOG_MD, "- %s ❌ 見張り番エラー: %s" % (now(), e))
        print(json.dumps({"error": str(e)}))
        sys.exit(0)
