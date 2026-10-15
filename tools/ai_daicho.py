#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""977番【他のAIと連携する仕組み ④死活】投げた回数と返ってきた回数を、両方数える台帳。

たまごさん（2026-09-22・原文）:
  「投げた回数と返ってきた回数の両方を数える。『投げた>0 なのに 返り=0』は赤で出す。」
  「no_credential / 401 / 403 / skip を黙って飲み込まない。嘘のログを書かない。」
  「伝書鳩、卒業させてください。」

■ なぜ台帳が先か
  ①行き（nageru.py）②帰り（github_watch.py）③逆向き（外→工場）は別々のファイルだが、
  **「本当に通っているのか」を判定できるのは、この1枚だけ。**
  台帳が無いと「投げたつもり」「返ってきたつもり」が積み上がり、
  たまごさんが手で運び直す（＝水汲み）状態に戻る。だからここを先に作る。

■ 置き場
  status/ai_daicho.jsonl  … 追記専用の生ログ（1行1件・消さない）
  status/ai_daicho.json   … 上を集計したもの（表示用・毎回作り直す）

■ 1行の形（これ以外の形を書かない）
  {"at": ISO8601, "dir": "out"|"in", "ai": "codex",
   "thread": "gh:tamago2022/joy-relief-station#460",   # 往きと帰りを結ぶ鍵
   "topic": "…お題1行…",
   "ref": "https://github.com/…",                       # 実物のURL（証拠）
   "ok": true, "err": null,                             # ★失敗も必ず1行書く
   "who": "chatgpt-codex-connector[bot]"}               # 帰りのとき誰が書いたか

■ ★失敗を飲み込まない決まり
  投げに行って失敗したときも **必ず ok=false の行を書く。**
  err には生の理由をそのまま入れる（"no_credential" / "HTTP 401 …" / "HTTP 403 …" / "skip:…"）。
  「何も起きなかったから何も書かない」は禁止。書かないと「投げた0・返り0」に見えて、
  壊れていることが死活表から消える（＝嘘のログ）。

■ 使い方
  python3 tools/ai_daicho.py --out  --ai codex --thread gh:owner/repo#460 --topic "…" --ref URL
  python3 tools/ai_daicho.py --out  --ai grok  --topic "…" --fail "no_credential"
  python3 tools/ai_daicho.py --in   --ai jules --thread gh:owner/repo#460 --ref URL --who "google-labs-jules[bot]"
  python3 tools/ai_daicho.py --summary        # 集計を作り直して表示（JSON）
  python3 tools/ai_daicho.py --report         # たまごさんが読む形（赤/緑の1行ずつ）
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "ai_daicho.jsonl")
SUM = os.path.join(REPO, "status", "ai_daicho.json")
JST = timezone(timedelta(hours=9))

# 相手の名札。ここに無い名前は受け付けない（打ち間違いで別の棚が生えるのを防ぐ）。
# githubLogin … その相手がGitHubで名乗る名前。帰りを自動判定するときに使う。
AI = {
    "codex":    {"label": "ChatGPT(Codex)", "githubLogin": ["chatgpt-codex-connector[bot]", "chatgpt-codex[bot]"]},
    # ★2026-09-22（977番）追加。たまごさんが「宛先一覧にチャッピーが無い」と言っていた相手。
    #   Codex（GitHubのbot）とは別人。こちらは **OpenAIのAPIに直接聞く口**で、
    #   投げたその場で返事が返る（実測2.4〜2.6秒）。GitHubのbotを待たない＝返り0が起きない。
    "chappy":   {"label": "チャッピー(ChatGPT直)", "githubLogin": []},
    "jules":    {"label": "Gemini(Jules)",  "githubLogin": ["google-labs-jules[bot]"]},
    "devin":    {"label": "Devin",          "githubLogin": ["devin-ai-integration[bot]"]},
    "grok":     {"label": "Grok",           "githubLogin": ["grok", "grok-bot"]},
    "genspark": {"label": "Genspark",       "githubLogin": ["genspark-ai-developer", "genspark-ai-developer[bot]"]},
    "copilot":  {"label": "GitHub Copilot", "githubLogin": ["copilot-swe-agent[bot]", "Copilot"]},
}
# 返ってきたのが誰か、GitHubの名前から引く逆引き表
BY_LOGIN = {}
for _k, _v in AI.items():
    for _l in _v["githubLogin"]:
        BY_LOGIN[_l.lower()] = _k

# 「投げたのに返ってこない」とみなすまでの時間（時間）。相手ごとに速さが違う。
SILENT_HOURS = {"codex": 6, "jules": 6, "devin": 12, "grok": 24, "genspark": 48, "copilot": 6,
                "chappy": 1}
DEFAULT_SILENT_HOURS = 24


def now_iso():
    return datetime.now(JST).isoformat(timespec="seconds")


def ai_key(name):
    """名札を正規化する。知らない名前は例外にする（黙って別の棚を作らない）。"""
    k = (name or "").strip().lower()
    alias = {"chatgpt": "chappy", "openai": "chappy", "gpt": "chappy",
             "チャッピー": "chappy", "chappie": "chappy",
             "gemini": "jules", "google": "jules", "xai": "grok"}
    k = alias.get(k, k)
    if k not in AI:
        raise SystemExit("知らない相手です: %s（使えるのは %s）" % (name, "/".join(AI)))
    return k


def who_to_ai(login):
    """GitHubの名前から相手を引く。分からなければ None（＝人間かもしれない）。"""
    return BY_LOGIN.get((login or "").strip().lower())


def append(dir_, ai, thread=None, topic=None, ref=None, ok=True, err=None, who=None, extra=None):
    """台帳に1行足す。★失敗のときも必ず呼ぶこと。"""
    row = {"at": now_iso(), "dir": dir_, "ai": ai_key(ai),
           "thread": thread or "", "topic": (topic or "")[:200],
           "ref": ref or "", "ok": bool(ok), "err": err, "who": who or ""}
    if extra:
        row.update(extra)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def already_logged_in(thread, ref):
    """同じ帰りを二度数えない（見張り番が同じコメントを再訪しても増えない）。
    ★ただし『同じIssueへの2通目』は別のrefなので、ちゃんと2件として数える。
      2026-09-19にチャッピーの返信4通が重複判定で捨てられた事故は、
      Issue番号で照合していたのが原因。ここは ref（コメントのURL）で照合する。"""
    if not ref:
        return False
    for r in read_all():
        if r.get("dir") == "in" and r.get("ref") == ref:
            return True
    return False


def read_all():
    if not os.path.exists(LOG):
        return []
    out = []
    with io.open(LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue  # 壊れた行は飛ばす。消さない
    return out


def _age_hours(iso):
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        return (datetime.now(JST) - t).total_seconds() / 3600.0
    except Exception:
        return 0.0


def summarize():
    rows = read_all()
    per = {}
    for k in AI:
        per[k] = {"ai": k, "label": AI[k]["label"],
                  "out": 0, "outFail": 0, "in": 0, "blocked": 0, "blockedWhy": "",
                  "lastOutAt": None, "lastInAt": None,
                  "openThreads": [], "errs": [], "state": "未使用", "color": "gray"}
    threads = {}   # thread -> {"ai":…, "outAt":…, "topic":…, "ref":…, "in":0}
    for r in rows:
        k = r.get("ai")
        if k not in per:
            continue
        d = per[k]
        if r.get("dir") == "out":
            # ★2026-09-22（977番）：「閉まっていると分かっていて投げなかった」行は
            #   **投げた回数に数えない。**数えると「投げた>0・返り0＝赤」になり、
            #   直すべき穴（投げたのに返らない）と、判断済みで投げていない口の区別がつかなくなる。
            #   たまごさん「返事が来ないからといって投げる回数を増やさない。素材を替える。」
            #   ＝投げていないことは、投げた回数ではなく『閉鎖』として別に数えるのが正しい。
            if r.get("blocked"):
                d["blocked"] += 1
                d["blockedWhy"] = r.get("err") or ""
                continue
            d["out"] += 1
            d["lastOutAt"] = r["at"]
            if not r.get("ok"):
                d["outFail"] += 1
                # ★失敗の理由は必ず表に出す（飲み込まない）
                d["errs"].append({"at": r["at"], "err": r.get("err") or "理由なし",
                                  "topic": r.get("topic", "")})
            th = r.get("thread")
            if th and r.get("ok"):
                threads[th] = {"ai": k, "outAt": r["at"], "topic": r.get("topic", ""),
                               "ref": r.get("ref", ""), "in": 0}
        elif r.get("dir") == "in":
            d["in"] += 1
            d["lastInAt"] = r["at"]
            th = r.get("thread")
            if th in threads:
                threads[th]["in"] += 1

    # 投げたまま返っていないスレッド
    for th, t in threads.items():
        if t["in"] == 0:
            hrs = _age_hours(t["outAt"])
            limit = SILENT_HOURS.get(t["ai"], DEFAULT_SILENT_HOURS)
            per[t["ai"]]["openThreads"].append(
                {"thread": th, "topic": t["topic"], "ref": t["ref"],
                 "hours": round(hrs, 1), "overdue": hrs > limit, "limitHours": limit})

    for k, d in per.items():
        overdue = [t for t in d["openThreads"] if t["overdue"]]
        if d["blocked"] and d["out"] == 0 and d["in"] == 0:
            # 閉鎖中。赤（直すべき穴）ではなく、黒（判断待ち／投げない）として出す。
            d["state"], d["color"] = "閉鎖中・投げていない（%d回止めた）" % d["blocked"], "black"
        elif d["out"] == 0 and d["in"] == 0:
            d["state"], d["color"] = "未使用", "gray"
        elif d["outFail"] and d["outFail"] == d["out"]:
            # 投げること自体が全部失敗している
            d["state"], d["color"] = "行きが壊れている（%d回全部失敗）" % d["outFail"], "red"
        elif d["out"] > 0 and d["in"] == 0:
            # ★たまごさんが赤で出せと言った状態
            d["state"], d["color"] = "投げた%d・返り0" % d["out"], "red"
        elif overdue:
            d["state"], d["color"] = "返事待ち%d件（%s時間超）" % (len(overdue), overdue[0]["limitHours"]), "yellow"
        elif d["outFail"]:
            d["state"], d["color"] = "双方向◯（ただし行きが%d回失敗）" % d["outFail"], "yellow"
        else:
            d["state"], d["color"] = "双方向◯（投げ%d・返り%d）" % (d["out"], d["in"]), "green"
        if d["blocked"] and d["color"] != "black":
            # 過去に実際に投げた分は残しつつ、「今は閉めてあるので回数は増えない」を明記する
            d["state"] += "／今は閉鎖・投げていない"
        d["errs"] = d["errs"][-5:]

    out = {"updatedAt": now_iso(),
           "totals": {"out": sum(d["out"] for d in per.values()),
                      "outFail": sum(d["outFail"] for d in per.values()),
                      "in": sum(d["in"] for d in per.values()),
                      "blocked": sum(d["blocked"] for d in per.values())},
           "ai": [per[k] for k in AI]}
    tmp = "%s.%d.tmp" % (SUM, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SUM)
    return out


GATE = os.path.join(REPO, "status", ".ai_daicho_collect_at")
GATE_SEC = 150   # 実際に外へ出る間隔。心臓から何度呼ばれてもこれより細かくは出ない


def collect_gated(limit=12):
    """心臓（heartbeat.sh）から何度呼ばれても、実際に外へ出るのは GATE_SEC に1回。
    ★赤（投げたのに返り0）が1件も無いときは、通信を1本も出さずに終わる。
    ＝工場は重くならない。見に行く必要がある時だけ見に行く。"""
    # ★回線が出ないホスト（Cowork/Dispatchのサンドボックス）から呼ばれたら、
    #   間引き用の時刻に触らずに黙って戻る。触ると工場側が150秒空振りする。
    try:
        sys.path.insert(0, HERE)
        import gaibu_kuchi
        if not gaibu_kuchi.net_ok():
            return {"ok": True, "skipped": "回線が出ないホスト（工場側で走ります）"}
    except Exception:
        pass
    s = summarize()
    red = sum(len(d["openThreads"]) for d in s["ai"])
    if red == 0:
        publish()   # 表示用だけは毎回作り直す（通信は出ない・数ミリ秒）
        return {"ok": True, "skipped": "返り待ちが0件"}
    try:
        if os.path.exists(GATE) and (datetime.now(JST).timestamp() - os.path.getmtime(GATE)) < GATE_SEC:
            return {"ok": True, "skipped": "間引き中"}
    except Exception:
        pass
    try:
        with io.open(GATE, "w", encoding="utf-8") as f:
            f.write(now_iso())
    except Exception:
        pass
    return collect(limit=limit)


def collect(limit=12):
    """★取りこぼさないための回収係（977番・工場側でだけ走る）。

    なぜ要るか：帰りを拾うのは本来 tools/github_watch.py の役目だが、あれは
    ETag（条件付きGET）と基準線（since）と1回3件の上限で動いている。
    つまり **『いま見た瞬間に新しかったもの』しか拾わない。**
    タイミングが1秒ずれた／上限に当たった／トークンが取れず寝ていた、のどれかが起きると、
    返事は来ているのに台帳が「返り0」の赤のままになる。それは嘘のログ。

    だからこの回収係は、見張り番とは**別の原理**で動く：
      「こちらが投げて、まだ返りが1件も無いスレッド」だけを名指しで読みに行く。
    ETagも基準線も使わない。何回走らせても、既に台帳にある ref は二重に数えない。
    件数が少ない（＝赤の分だけ）ので、レート制限もほぼ使わない。
    """
    import importlib
    sys.path.insert(0, HERE)
    import _965_keijiban
    importlib.reload(_965_keijiban)

    s = summarize()
    targets = []
    for d in s["ai"]:
        for t in d["openThreads"]:
            if t["thread"].startswith("gh:"):
                targets.append((d["ai"], t["thread"]))
    targets = targets[:limit]

    found, errs = 0, []
    for ai, thread in targets:
        try:
            repo, num = thread[3:].split("#", 1)
        except Exception:
            continue
        r = _965_keijiban.run_job({"repo": repo, "action": "read", "number": int(num)})
        if not r.get("ok"):
            # ★読めなかったことも飲み込まない
            errs.append("%s: %s" % (thread, r.get("error")))
            continue
        for c in r.get("comments") or []:
            k = who_to_ai(c.get("who"))
            if not k:
                continue
            ref = "https://github.com/%s/issues/%s#issuecomment-%s" % (repo, num, c.get("id") or "")
            # id が無い版の結果でも二重計上しないよう、本文の先頭で照合する保険を掛ける
            ref = ref if c.get("id") else "%s|%s" % (thread, (c.get("at") or ""))
            if already_logged_in(thread, ref):
                continue
            append("in", k, thread=thread, topic=(c.get("text") or "")[:120],
                   ref=ref, who=c.get("who"))
            found += 1
    publish()
    return {"ok": True, "checked": len(targets), "found": found, "errors": errs,
            "totalYen": 0.0}


def run_job(payload):
    """gaibu_runner（工場側の代行係）から呼ばれる入口。"""
    return collect(limit=int((payload or {}).get("limit") or 12))


PUBLIC = os.path.join(REPO, "status", "public", "ai_daicho.json")


def publish():
    """977番：たまごさんが見る形（status/public/ai_daicho.json）に書き出す。
    status/ は .gitignore で外れているが status/public/ だけ追跡されている＝ここが唯一の公開経路。
    ★実測の人口調査も一緒に載せる。台帳（この仕組みが出来た後）と
      実測（それ以前も含む）は別の枠で並べる。混ぜると嘘になる。"""
    s = summarize()
    try:
        s["census"] = json.load(io.open(CENSUS, encoding="utf-8")) if os.path.exists(CENSUS) else {}
    except Exception:
        s["census"] = {}
    s["routes"] = {}
    try:
        sys.path.insert(0, HERE)
        import nageru
        for k, r in nageru.ROUTE.items():
            s["routes"][k] = {"how": r["how"], "repo": r.get("repo", ""),
                              "wake": r.get("wake") or ("ラベル %s" % r["labels"][0] if r.get("labels") else None),
                              "note": r.get("note", "")}
    except Exception as e:
        s["routes"] = {"_error": "%s: %s" % (type(e).__name__, e)}
    os.makedirs(os.path.dirname(PUBLIC), exist_ok=True)
    tmp = "%s.%d.tmp" % (PUBLIC, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PUBLIC)
    return s


CENSUS = os.path.join(REPO, "status", "ai_daicho_census.json")


def save_census(rows, repo):
    """★実測の人口調査。GitHubに『実際に書き込んだ相手』を数えたもの。
    台帳（out/in）とは別物。台帳はこの仕組みを作った2026-09-22以降しか無いが、
    それ以前から相手は書き込んでいる。**それを台帳のinとして偽装して足さない**
    （嘘のログを書かないため）。別の枠で、実測として並べて出す。"""
    cur = {}
    if os.path.exists(CENSUS):
        try:
            cur = json.load(io.open(CENSUS, encoding="utf-8"))
        except Exception:
            cur = {}
    cur.setdefault("repos", {})
    cur["repos"][repo] = {"at": now_iso(), "writers": rows}
    cur["updatedAt"] = now_iso()
    tmp = "%s.%d.tmp" % (CENSUS, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CENSUS)
    return cur


def census_lines():
    if not os.path.exists(CENSUS):
        return []
    try:
        c = json.load(io.open(CENSUS, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for repo, d in (c.get("repos") or {}).items():
        got = []
        for w in d.get("writers") or []:
            k = who_to_ai(w.get("login"))
            if not k:
                continue
            n = (w.get("issues") or 0) + (w.get("comments") or 0) + (w.get("commits") or 0)
            if n:
                got.append("%s %d件" % (AI[k]["label"], n))
        out.append("　%s … %s" % (repo, "／".join(got) if got else "外部AIの書き込みは0件"))
    return out


MARK = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⚪"}


def report():
    s = summarize()
    lines = ["【他のAIとの往復】%s 時点" % s["updatedAt"][:16].replace("T", " ")]
    for d in s["ai"]:
        lines.append("%s %s … %s" % (MARK[d["color"]], d["label"], d["state"]))
        for e in d["errs"]:
            lines.append("      ↳ 失敗: %s（%s）" % (e["err"], e["at"][5:16].replace("T", " ")))
        for t in d["openThreads"][:3]:
            if t["overdue"]:
                lines.append("      ↳ %.0f時間返事なし: %s %s" % (t["hours"], t["topic"][:40], t["ref"]))
    t = s["totals"]
    lines.append("合計: 投げ%d（うち失敗%d） / 返り%d" % (t["out"], t["outFail"], t["in"]))
    cl = census_lines()
    if cl:
        lines.append("")
        lines.append("【GitHubでの実測（この台帳より前の分も含む・別枠）】")
        lines += cl
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", action="store_true", help="こちらから投げた1件を記録")
    ap.add_argument("--in", dest="inn", action="store_true", help="向こうから返ってきた1件を記録")
    ap.add_argument("--ai")
    ap.add_argument("--thread", default="")
    ap.add_argument("--topic", default="")
    ap.add_argument("--ref", default="")
    ap.add_argument("--who", default="")
    ap.add_argument("--fail", default=None, help="失敗した理由（これを付けると ok=false で記録）")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--collect", action="store_true", help="返り0のスレッドを名指しで読みに行く（工場側でだけ動く）")
    ap.add_argument("--gated", action="store_true", help="心臓から呼ぶ用。間引きあり・赤が0なら通信しない")
    ap.add_argument("--publish", action="store_true", help="表示用のJSONを書き出す")
    a = ap.parse_args()

    if a.out or a.inn:
        if not a.ai:
            raise SystemExit("--ai が要ります")
        r = append("out" if a.out else "in", a.ai, thread=a.thread, topic=a.topic,
                   ref=a.ref, ok=(a.fail is None), err=a.fail, who=a.who)
        publish()
        print(json.dumps(r, ensure_ascii=False))
        return 0
    if a.publish:
        publish()
        print("status/public/ai_daicho.json を書き出しました")
        return 0
    if a.collect:
        print(json.dumps(collect_gated() if a.gated else collect(), ensure_ascii=False, indent=1))
        return 0
    if a.summary:
        print(json.dumps(summarize(), ensure_ascii=False, indent=1))
        return 0
    print(report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
