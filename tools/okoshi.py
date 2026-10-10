#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""起こし役（2026-10-09・たまごさん指示）

たまごさんの言葉：
  「止まっていました、という報告をされても直し方が分からないし何もできない。報告の前に調べて直して。
    Gensparkの作業も、何かあったらノックして起こせる仕組みに。」

何をするか（心臓 tools/heartbeat.sh から5分おき・Mac上で走る・AIを呼ばない・0円）：
  A. Dispatch の子セッション（Cowork）の見回り
     ~/Library/Application Support/Claude/local-agent-mode-sessions/**/local_*.json を読むだけ。
       ・落ちた    … error が付いていて、その後に動いていない
       ・止まった  … 最後が「道具を呼んだまま結果が返っていない」状態で STALL_MIN 分以上動きが無い
                     （許可ポップアップ待ち・道具の固まりはこの形になる。10/8 実測）
     → 1回目：同じ依頼を工場の列（status/queue.json・P1）に「続きから」で積み直す。
              列は claude -p --permission-mode auto で走る＝許可ポップアップが出ない経路。
     → 同じ案件が同じ道具で2回止まった：止まった道具を使わない「別の経路」を指示に書いて積む。
     → 3回目以降は積まない（無限に叩かない）。記録だけ残す。
     ★Dispatch 側が既に同じ題名でやり直していて、そちらが生きていれば積まない（二重発車しない）。
  B. Genspark の依頼の見回り
     status/gsk_daicho.jsonl の task create（projectId 付き）のうち、答えを回収していないもの：
     → 8分以上たったら `gsk task info` で叩いて、終わっていれば答えを status/gsk/kaishuu/<id>.md に回収。
     → 叩くのに2回続けて失敗した／90分たっても終わらない：同じ問いを出し直す（別の経路）。1件1回まで。
  結果：status/okoshi.json と status/public/okoshi.json（進捗表・health.json が読む）に
        「自動で起こした回数」を書く。

使い方：
  python3 tools/okoshi.py            1周
  python3 tools/okoshi.py --dry      積まない・叩かない（判定だけ表示）
  python3 tools/okoshi.py --self-test
"""
import glob
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SESS_ROOT = os.path.expanduser("~/Library/Application Support/Claude/local-agent-mode-sessions")
ST_DIR = os.path.join(REPO, "status", "okoshi")
STATE = os.path.join(ST_DIR, "state.json")
LOG = os.path.join(ST_DIR, "okoshi.log")
OUT = os.path.join(REPO, "status", "okoshi.json")
PUB = os.path.join(REPO, "status", "public", "okoshi.json")
GSK_DAICHO = os.path.join(REPO, "status", "gsk_daicho.jsonl")
GSK_OUT = os.path.join(REPO, "status", "gsk", "kaishuu")
GSK_IRAI = os.path.join(REPO, "status", "gsk", "irai.jsonl")   # genspark_tanomu.py が問い・置き場所を残す

STALL_MIN = 20          # 道具を呼んだまま20分動かない＝止まった
LOOKBACK_H = 36         # これより古い子は見ない
GSK_FIRST_MIN = 8       # 出してから8分は待つ
GSK_GIVEUP_MIN = 90     # 90分終わらなければ出し直す
MAX_PER_KEY = 3         # 同じ案件×同じ道具は3回まで

# 止まった道具 → 別の経路（2回目からの指示に入れる）
BETSU = [
    ("web_fetch", "web_fetch／WebFetch は使わない。取りたいURLは status/mac_jobs/pending/<名前>.sh に curl を書いて置き、"
                  "15秒後に status/mac_jobs/done/<名前>.out を読む（Macが取る・許可ポップアップが出ない）。"),
    ("WebFetch", "WebFetch は使わない。status/mac_jobs/pending/<名前>.sh に curl を置いて Mac に取らせる。"),
    ("create_draft", "Gmail の道具は使わない。文面は status/shitagaki/<日付>_<宛先>.md にファイルで残す（送信しない）。"),
    ("gmail", "Gmail の道具は使わない。文面は status/shitagaki/ にファイルで残す（送信しない）。"),
    ("1eb9c4c0", "Lovable の道具は使わない。joy-relief-station は GitHub 経由（git push）で反映する。"),
    ("scheduled-tasks", "定期タスクの道具は使わない。繰り返しは心臓（tools/heartbeat.sh）に1行足して回す。"),
    ("workspace__bash", "長い処理を1回のbashで待たない。status/mac_jobs/pending/ に置いて、結果ファイルを後で読む。"),
    ("Bash", "長い処理を1回のBashで待たない。nohup で裏に回してログを後で読む。"),
]


def now():
    return time.time()


def log(msg):
    os.makedirs(ST_DIR, exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), msg))


def load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(obj, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ───────── A. Dispatch の子セッション ─────────
def transcript_last(dirpath):
    """会話ログの最後で、結果が返っていない道具呼び出し（名前・入力）と更新時刻"""
    fs = glob.glob(os.path.join(dirpath, ".claude", "projects", "*", "*.jsonl"))
    if not fs:
        return None, None
    f = max(fs, key=os.path.getmtime)
    pend = {}
    for ln in io.open(f, encoding="utf-8", errors="ignore"):
        try:
            o = json.loads(ln)
        except Exception:
            continue
        c = (o.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for x in c:
            if x.get("type") == "tool_use":
                pend[x.get("id")] = (x.get("name") or "", json.dumps(x.get("input"), ensure_ascii=False)[:200])
            elif x.get("type") == "tool_result":
                pend.pop(x.get("tool_use_id"), None)
    last = list(pend.values())[-1] if pend else None
    return last, os.path.getmtime(f)


def children(root=SESS_ROOT):
    out = []
    lim = now() - LOOKBACK_H * 3600
    for j in glob.glob(os.path.join(root, "*", "*", "local_*.json")):
        if "local_ditto" in j:
            continue
        try:
            if os.path.getmtime(j) < lim:
                continue
            d = json.load(io.open(j, encoding="utf-8"))
        except Exception:
            continue
        if d.get("sessionType") != "dispatch_child":
            continue
        sid = d.get("sessionId") or ""
        short = sid.replace("local_", "")[:8]
        last, tmt = transcript_last(os.path.join(os.path.dirname(j), short))
        out.append({
            "sid": sid, "title": d.get("title") or "", "msg": d.get("initialMessage") or "",
            "created": (d.get("createdAt") or 0) / 1000.0,
            "lastAct": (d.get("lastActivityAt") or 0) / 1000.0,
            "errorAt": (d.get("errorAt") or 0) / 1000.0, "error": d.get("error"),
            "errorCategory": d.get("errorCategory"),
            "pending": last, "tmtime": tmt,
        })
    return out


def judge(c, t=None):
    """'ochita' / 'tomatta' / None"""
    t = t or now()
    if c.get("error") and c["errorAt"] >= c["lastAct"] - 1:
        return "ochita"
    if c.get("pending") and c.get("tmtime") and (t - c["tmtime"]) >= STALL_MIN * 60:
        return "tomatta"
    return None


def place_of(c):
    p = c.get("pending")
    if p:
        return p[0]
    return c.get("errorCategory") or "不明"


def betsu_keiro(tool):
    for k, v in BETSU:
        if k in tool:
            return v
    return "前回止まった道具（%s）は使わず、工場の口（status/mac_jobs・status/gaibu_jobs）か git で同じことをする。" % tool


def redone_by_dispatch(c, allc):
    """同じ題名の子が後から立っていて、まだ生きている／ちゃんと終わったなら、Dispatch が既にやり直している"""
    base = c["title"][:8]
    for o in allc:
        if o["sid"] == c["sid"] or o["created"] <= max(c["errorAt"], c["lastAct"]):
            continue
        if base and (base in o["title"] or base in o["msg"][:300]):
            if judge(o) is None:
                return o["sid"]
    return None


def queue_okosu(c, n, tool, dry=False):
    lines = [
        "【自動で起こした（%d回目）】%s" % (n, c["title"]),
        "前回の子セッション %s は「%s」の途中で%s（%s）。" % (
            c["sid"], tool, "落ちた" if judge(c) == "ochita" else "止まった",
            c.get("error") or "道具の結果が%d分以上返らない＝許可待ちか固まり" % STALL_MIN),
        "status/ と git log で前回どこまで進んだかを先に確かめ、終わっている工程はやり直さず、続きからやる。",
        "許可ポップアップが出る道具（内蔵ブラウザ・computer-use・request_access・osascript）は使わない。たまごさんに質問しない。",
    ]
    if n >= 2:
        lines.append("★同じ所で%d回止まったので経路を変える：%s" % (n, betsu_keiro(tool)))
    lines += ["", "――元の依頼――", c["msg"][:6000]]
    body = "\n".join(lines)
    if dry:
        return "dry"
    import command_ingest
    s, msg = command_ingest.queue_add(body, priority=1,
                                      label=("起こし｜" + c["title"])[:60] + "（重複OK）",
                                      origin="factory")
    return "%s:%s" % (s, msg)


def mimawari_children(st, dry=False, allc=None):
    allc = children() if allc is None else allc
    since = st.setdefault("since", now())   # 起こし役を入れる前に落ちた分は積まない（Dispatchが既に扱った）
    done = st.setdefault("handled", {})
    keys = st.setdefault("keys", {})
    ev = []
    for c in allc:
        j = judge(c)
        if not j or c["sid"] in done:
            continue
        tool = place_of(c)
        if max(c["errorAt"], c["tmtime"] or 0, c["lastAct"]) < since - 60:
            done[c["sid"]] = {"at": now(), "what": "基準線より前"}
            continue
        if redone_by_dispatch(c, allc):
            done[c["sid"]] = {"at": now(), "what": "Dispatchがやり直し済み"}
            continue
        key = hashlib.md5((c["title"][:8] + "|" + tool).encode("utf-8")).hexdigest()[:12]
        n = keys.get(key, 0) + 1
        if n > MAX_PER_KEY:
            done[c["sid"]] = {"at": now(), "what": "上限%d回を超えたので積まない" % MAX_PER_KEY}
            log("上限 %s %s %s" % (c["sid"], c["title"], tool))
            continue
        r = queue_okosu(c, n, tool, dry=dry)
        if not dry:
            keys[key] = n
            done[c["sid"]] = {"at": now(), "what": r, "tool": tool, "n": n, "j": j}
            log("起こした %s「%s」%s@%s n=%d → %s" % (c["sid"], c["title"], j, tool, n, r))
        ev.append({"kind": "子セッション", "title": c["title"], "j": j, "tool": tool, "n": n,
                   "betsu": n >= 2, "r": r, "at": time.strftime("%F %T")})
    return ev


# ───────── B. Genspark ─────────
def gsk_irai():
    out = []
    for ln in io.open(GSK_DAICHO, encoding="utf-8", errors="ignore") if os.path.exists(GSK_DAICHO) else []:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if str(d.get("nani", "")).startswith("task create/") and d.get("projectId"):
            out.append(d)
    return out


def gsk_irai_map():
    m = {}
    if os.path.exists(GSK_IRAI):
        for ln in io.open(GSK_IRAI, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(ln)
                m[d["pid"]] = d
            except Exception:
                pass
    return m


def _run_gsk(payload):
    import importlib
    import gsk_kuchi
    importlib.reload(gsk_kuchi)
    return gsk_kuchi.run_job(payload)


def mimawari_gsk(st, dry=False, runner=None):
    runner = runner or _run_gsk
    g = st.setdefault("gsk", {})
    since = st.setdefault("since", now())   # 起こし役を入れる前の依頼は数えない（基準線）
    irai = gsk_irai_map()
    ev = []
    for d in gsk_irai():
        pid = d["projectId"]
        s = g.setdefault(pid, {"fails": 0, "state": "machi"})
        kaishuu_moto = (irai.get(pid) or {}).get("out")
        if kaishuu_moto and os.path.exists(os.path.join(REPO, kaishuu_moto) if not os.path.isabs(kaishuu_moto) else kaishuu_moto):
            s["state"] = "kaishuu"   # 頼んだ本人が回収済み
            continue
        if s["state"] in ("kaishuu", "dashinaoshi_zumi", "akirame"):
            continue
        try:
            t0 = time.mktime(time.strptime(d["at"], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        age = (now() - t0) / 60.0
        if t0 < since - 60:
            s["state"] = "akirame" if s["state"] == "machi" else s["state"]
            continue
        if age < GSK_FIRST_MIN or age > 72 * 60:
            continue
        if dry:
            ev.append({"kind": "Genspark", "pid": pid, "dry": True})
            continue
        r = runner({"op": "shigoto_miru", "sub": "info", "id": pid, "timeoutSec": 120}) or {}
        state, text = None, ""
        if r.get("ok"):
            try:
                dd = (json.loads(r.get("stdout") or "{}").get("data") or {})
                state = dd.get("state")
                c = (dd.get("result_content") or {}).get("content")
                text = "\n".join(c) if isinstance(c, list) else (c or "")
            except Exception:
                state = None
        if state in ("finished", "succeeded", "completed") and text:
            os.makedirs(GSK_OUT, exist_ok=True)
            fn = os.path.join(GSK_OUT, pid + ".md")
            if not os.path.exists(fn):
                io.open(fn, "w", encoding="utf-8").write(
                    "<!-- Genspark %s の答え原文（起こし役が回収）project=%s -->\n%s" % (d.get("nani"), pid, text))
                o = (irai.get(pid) or {}).get("out")
                if o:
                    o = o if os.path.isabs(o) else os.path.join(REPO, o)
                    if not os.path.exists(o):
                        os.makedirs(os.path.dirname(o), exist_ok=True)
                        io.open(o, "w", encoding="utf-8").write(
                            "<!-- Genspark の答え原文（起こし役が回収）project=%s -->\n%s" % (pid, text))
                ev.append({"kind": "Genspark回収", "pid": pid, "name": d.get("taskName"), "at": time.strftime("%F %T")})
                log("Genspark回収 %s %s" % (pid, d.get("taskName")))
            s["state"] = "kaishuu"
            continue
        if not r.get("ok"):
            s["fails"] += 1
        if s["fails"] >= 2 or age > GSK_GIVEUP_MIN:
            q = (irai.get(pid) or {}).get("q")
            if not q:
                # 台帳に問いが無い古い依頼は出し直せない。答えの元がGenspark側に残るので記録だけ
                s["state"] = "akirame"
                log("Genspark 出し直し不可（問いが台帳に無い）%s" % pid)
                continue
            r2 = runner({"op": "shigoto_dasu", "taskType": d["nani"].split("/", 1)[1], "query": q,
                         "instructions": "日本語で。出典URLを必ず付ける。", "taskName": (d.get("taskName") or "") + "（出し直し）",
                         "timeoutSec": 200}) or {}
            s["state"] = "dashinaoshi_zumi"
            ev.append({"kind": "Genspark出し直し", "pid": pid, "new": r2.get("projectId"), "at": time.strftime("%F %T")})
            log("Genspark出し直し %s → %s" % (pid, r2.get("projectId")))
    return ev


def kaku(st, ev):
    hist = st.setdefault("history", [])
    hist.extend(ev)
    st["history"] = hist[-200:]
    today = time.strftime("%F")
    cnt = {"total": 0, "today": 0, "kosession": 0, "genspark": 0, "betsu": 0}
    for e in st["history"]:
        if e.get("dry"):
            continue
        cnt["total"] += 1
        if str(e.get("at", "")).startswith(today):
            cnt["today"] += 1
        if e["kind"] == "子セッション":
            cnt["kosession"] += 1
            cnt["betsu"] += 1 if e.get("betsu") else 0
        else:
            cnt["genspark"] += 1
    res = {"label": "自動で起こした回数", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "count": cnt, "last": st["history"][-5:]}
    save(OUT, res)
    save(PUB, {k: res[k] for k in ("label", "at", "count")})
    return res


def main():
    dry = "--dry" in sys.argv
    if "--self-test" in sys.argv:
        return self_test()
    st = load(STATE, {})
    ev = []
    try:
        ev += mimawari_children(st, dry=dry)
    except Exception as e:
        log("子セッション見回りで例外 %r" % e)
    try:
        ev += mimawari_gsk(st, dry=dry)
    except Exception as e:
        log("Genspark見回りで例外 %r" % e)
    if dry:
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        return
    save(STATE, st)
    r = kaku(st, ev)
    if ev:
        print("起こし役：今回 %d件／累計 %d件" % (len(ev), r["count"]["total"]))


def self_test():
    """偽の子セッションで判定を確かめる（積まない・叩かない）"""
    import tempfile
    t = now()
    root = tempfile.mkdtemp()
    org = os.path.join(root, "acct", "org")
    os.makedirs(org)

    def mk(short, title, err=None, pend=False, age_min=30):
        sid = "local_%s-0000" % short
        d = {"sessionId": sid, "title": title, "initialMessage": title + "をやる", "sessionType": "dispatch_child",
             "createdAt": int((t - 3600) * 1000), "lastActivityAt": int((t - age_min * 60) * 1000)}
        if err:
            d.update(error=err, errorAt=int((t - age_min * 60 + 5) * 1000), errorCategory="process_interrupted")
        json.dump(d, io.open(os.path.join(org, sid + ".json"), "w", encoding="utf-8"))
        tp = os.path.join(org, short, ".claude", "projects", "s")
        os.makedirs(tp)
        f = os.path.join(tp, "x.jsonl")
        rec = [{"message": {"content": [{"type": "tool_use", "id": "a", "name": "mcp__workspace__web_fetch", "input": {}}]}}]
        if not pend:
            rec.append({"message": {"content": [{"type": "tool_result", "tool_use_id": "a"}]}})
        io.open(f, "w").write("\n".join(json.dumps(r) for r in rec))
        os.utime(f, (t - age_min * 60, t - age_min * 60))

    mk("aaaaaaaa", "落ちた子", err="Claude Code process exited with code 143", pend=True)
    mk("bbbbbbbb", "固まった子", pend=True, age_min=30)
    mk("cccccccc", "元気な子", pend=False, age_min=1)
    mk("dddddddd", "まだ待ってよい子", pend=True, age_min=5)
    cs = {c["title"]: judge(c) for c in children(root)}
    ok1 = cs == {"落ちた子": "ochita", "固まった子": "tomatta", "元気な子": None, "まだ待ってよい子": None}
    st = {"since": t - 7200}
    ev1 = mimawari_children(st, dry=True, allc=children(root))
    ok2 = sorted(e["title"] for e in ev1) == ["固まった子", "落ちた子"]
    ok3 = "mac_jobs" in betsu_keiro("mcp__workspace__web_fetch") and "Gmail" in betsu_keiro("mcp__x__create_draft")
    print(json.dumps({"判定": cs, "判定OK": ok1, "起こす対象OK": ok2, "別経路OK": ok3}, ensure_ascii=False))
    print("SELFTEST", "PASS" if (ok1 and ok2 and ok3) else "FAIL")
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
