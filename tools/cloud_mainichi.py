#!/usr/bin/env python3
"""クラウド便を毎日2〜3本、自動で起動する（心臓 heartbeat.sh から1時間に1回）。2026-10-22。
- 順番は status/cloud_credit/junban.txt（上から）。起動できた（ログに claude.ai/code の URL が出た）行は done.txt へ。
- 1日（JST）3本まで・1回の呼び出しで1本・7〜23時だけ・2026-11-01 23:59 JST で自動停止（期限 11/5 16:59 の前に使い切る）。
- 起動の中身は tools/cloud_hassha.sh（claude --cloud）。403（ログインの権限不足）なら、その日は6時間おきにだけ試し、Dispatch へ1日1行。
- 依頼文の作り足し（p5〜p12）は Dispatch／子が tools/cloud_prompts/ に置き junban.txt に1行足す。
逆テスト：--self-test"""
import os, sys, json, re, subprocess, datetime, glob
F = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(F, "status", "cloud_credit")
JST = datetime.timezone(datetime.timedelta(hours=9))
END = datetime.datetime(2026, 11, 1, 23, 59, tzinfo=JST)
MAX_DAY = 3
URL_RE = re.compile(r"claude\.ai/code/session_[A-Za-z0-9]+|\bsession_[A-Za-z0-9]{20,}")

def junban(path):
    if not os.path.exists(path): return []
    return [l.split() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#") and len(l.split()) >= 2]

def state_path(): return os.path.join(C, "mainichi_state.json")
def load():
    try: return json.load(open(state_path(), encoding="utf-8"))
    except Exception: return {}

def decide(now, st, todo):
    """次に起動する行（無ければ None と理由）"""
    if now > END: return None, "期限後（11/1で停止）"
    if not (7 <= now.hour < 23): return None, "時間外"
    day = now.strftime("%Y-%m-%d"); d = st.get(day, {})
    if d.get("ok", 0) >= MAX_DAY: return None, "今日は上限"
    last403 = d.get("last403")
    if last403 and (now - datetime.datetime.fromisoformat(last403)).total_seconds() < 6 * 3600: return None, "403のあと6時間待ち"
    if not todo: return None, "順番が空"
    return todo[0], "起動"

def main():
    now = datetime.datetime.now(JST); st = load()
    todo = junban(os.path.join(C, "junban.txt"))
    item, why = decide(now, st, todo)
    if not item: print(now.isoformat(), why); return
    name = now.strftime("%m%d") + "-" + item[0]
    subprocess.run(["bash", os.path.join(F, "tools", "cloud_hassha.sh"), name, item[1]], capture_output=True, timeout=170)
    log = open(os.path.join(C, "log", name + ".log"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(C, "log", name + ".log")) else ""
    day = now.strftime("%Y-%m-%d"); d = st.setdefault(day, {})
    if URL_RE.search(log):
        d["ok"] = d.get("ok", 0) + 1
        lines = open(os.path.join(C, "junban.txt"), encoding="utf-8").read().splitlines()
        lines = [l for l in lines if l.split()[:1] != [item[0]]]
        open(os.path.join(C, "junban.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        open(os.path.join(C, "done.txt"), "a", encoding="utf-8").write(f"{now.isoformat()} {name} {' '.join(item[1:])}\n")
    else:
        if "403" in log:
            d["last403"] = now.isoformat()
            if not d.get("told403"):
                d["told403"] = True
                with open(os.path.join(F, "status", "dispatch_outbox.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"at": now.isoformat(), "type": "cloud_403",
                        "text": "クラウド便が 403（Mac の CLI のログインが推論専用 setup-token。クラウド作成の権限 user:sessions:claude_code が無い）。詳しくは status/cloud_credit/tsumari.txt"}, ensure_ascii=False) + "\n")
        d["ng"] = d.get("ng", 0) + 1
    json.dump(st, open(state_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    subprocess.run(["python3", os.path.join(F, "tools", "cloud_kaishuu.py")], capture_output=True, timeout=60)

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        t = lambda h, d=22: datetime.datetime(2026, 10, d, h, tzinfo=JST)
        ok = (decide(t(10), {}, [["a", "b"]])[0] == ["a", "b"] and decide(t(3), {}, [["a", "b"]])[0] is None
              and decide(t(10), {"2026-10-22": {"ok": 3}}, [["a", "b"]])[0] is None
              and decide(t(10, 2) + datetime.timedelta(days=31), {}, [["a", "b"]])[0] is None
              and decide(t(10), {"2026-10-22": {"last403": t(8).isoformat()}}, [["a", "b"]])[0] is None
              and decide(t(15), {"2026-10-22": {"last403": t(8).isoformat()}}, [["a", "b"]])[0] == ["a", "b"])
        print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
    main()
