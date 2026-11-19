#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LINE配信の記録係（line_haishin）— 2026-10-25 たまごさん方針確定。

たまごさん（Dispatch経由）：
  「LINEの配信・運営はGrokボットが担当。工場は配信を作らない。代わりに『何が配信され、どんな反応が返ったか』を
    見えるようにしたい（SNSと同じく、改善に使う）。マガジンのネタも差し込んでいく予定」

■ 何をするか（工場は送らない・読むだけ）
  ① Grokボットが共有メモ #1039（joy-relief-station）に1配信1コメントで書く「【LINE配信記録】」を拾う。
       【LINE配信記録】
       日時: 2026-10-25 04:12
       本文: （届いた文そのまま）
       リンク: https://...（複数可・1行に1つ）
       既読: 1      ← 取れたときだけ。取れない数字は書かない（0で埋めない）
       クリック: 0
       友だち: 1
     数字があとで分かったら、同じ日時でもう1件書けばよい（同じ日時は1配信にまとめ、新しい数字で上書き）。
  ② status/line_haishin/kiroku.json（正本）と status/public/line_haishin.json（写し）に1配信1件で残す。
  ③ SNSの反応の台帳 status/sns_hannou.json（＋写し status/public/sns_hannou.json）に platform="line" として並べる
     （X・TikTok・YouTube と同じ形：posts[id].history[]/latest）。
  ④ 週1回（月曜）の週まとめ status/public/sns_shuukei.json：X・TikTok・YouTube・LINE を同じ見え方で1週ずつ。
     進捗表（index.html の「SNS（先週）」）がこれを読む。決まり（週1・金曜20時）とずれた配信は zure に出す。

■ 使い方
  python3 tools/line_haishin.py --tick        # 心臓から。中で6時間に1回へ間引く（gh は Mac だけ）
  python3 tools/line_haishin.py --matome      # 週まとめだけ作り直す（ネット不要）
  python3 tools/line_haishin.py --self-test

■ 決まり：送らない・有料APIなし・ブラウザなし・LINEの鍵を持たない（数字は Grokボットが書いたものだけ）。
作るもの：status/line_haishin/{kiroku.json,state.json,log} ／ status/public/{line_haishin.json,sns_shuukei.json}
台帳：tools/jidou_daicho.json の "line_haishin.py"
"""
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
D = os.path.join(REPO, "status", "line_haishin")
KIROKU = os.path.join(D, "kiroku.json")
STATE = os.path.join(D, "state.json")
LOG = os.path.join(D, "log")
PUB = os.path.join(REPO, "status", "public", "line_haishin.json")
HANNOU = os.path.join(REPO, "status", "sns_hannou.json")
HANNOU_PUB = os.path.join(REPO, "status", "public", "sns_hannou.json")
SHUUKEI = os.path.join(REPO, "status", "public", "sns_shuukei.json")
REPO_GH = "tamago2022/joy-relief-station"
ISSUE = 1039
MARK = "【LINE配信記録】"
ACCOUNT = "@759fytwa"
GATE_SEC = 6 * 3600
JST = _dt.timezone(_dt.timedelta(hours=9))
KIMARI = {"youbi": 4, "ji": 20, "setsumei": "週1・金曜20時（2026-10-21 たまごさん決定）"}
PATHS = [os.path.expanduser(p) for p in ("~/.local/bin", "~/bin", "~/.npm-global/bin")] + ["/opt/homebrew/bin", "/usr/local/bin"]
ENV = dict(os.environ, PATH=":".join(PATHS + [os.environ.get("PATH", "")]))
NUMS = {"既読": "reads", "開封": "reads", "クリック": "clicks", "友だち": "friends", "友達": "friends", "送信数": "sent", "届いた人": "sent"}


def now():
    return _dt.datetime.now(JST)


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def log(msg):
    os.makedirs(D, exist_ok=True)
    line = "[%s] %s" % (now().strftime("%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG, encoding="utf-8") as f:
            old = f.read().splitlines()[-299:]
    except Exception:
        old = []
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(old + [line]) + "\n")
    print(line)


def _num(s):
    m = re.search(r"\d[\d,]*", s or "")
    return int(m.group(0).replace(",", "")) if m else None


def parse_time(s):
    s = (s or "").strip().replace("/", "-").replace("　", " ")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})[ T]*(\d{1,2})?:?(\d{2})?", s)
    if not m:
        return None
    y, mo, d, h, mi = m.groups()
    return _dt.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=JST)


def parse(body, created_at=""):
    """コメント1件 → 配信1件（dict）。印が無ければ None。"""
    if MARK not in (body or ""):
        return None
    txt = body.split(MARK, 1)[1]
    rec = {"links": []}
    key = None
    for raw in txt.splitlines():
        line = raw.strip()
        m = re.match(r"^[-・*]?\s*([^:：]{1,8})\s*[:：]\s*(.*)$", line)
        if m and (m.group(1) in ("日時", "本文", "リンク") or m.group(1) in NUMS):
            k, v = m.group(1), m.group(2).strip()
            key = k
            if k == "日時":
                t = parse_time(v)
                rec["at"] = t.isoformat(timespec="minutes") if t else None
            elif k == "本文":
                rec["text"] = v
            elif k == "リンク":
                rec["links"] += re.findall(r"https?://\S+", v)
            else:
                n = _num(v)
                if n is not None:
                    rec[NUMS[k]] = n
            continue
        if key == "本文" and line and not line.startswith("<!--"):
            rec["text"] = (rec.get("text", "") + "\n" + line).strip()
        elif key == "リンク":
            rec["links"] += re.findall(r"https?://\S+", line)
    if not rec.get("at"):
        t = None
        try:
            t = _dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(JST)
        except Exception:
            pass
        rec["at"] = t.isoformat(timespec="minutes") if t else None
        rec["at_suitei"] = True  # 日時が書かれていない＝コメントの時刻で代用
    if not rec.get("links") and rec.get("text"):
        rec["links"] = re.findall(r"https?://\S+", rec["text"])
    rec["links"] = list(dict.fromkeys(rec["links"]))
    return rec if rec.get("at") else None


def merge(kiroku, recs):
    """同じ日時（分まで）は1配信。数字は新しいコメントで上書き、本文・リンクは空なら埋める。"""
    by = {r["at"]: r for r in kiroku.get("haishin", [])}
    n_new = 0
    for r in recs:
        old = by.get(r["at"])
        if not old:
            by[r["at"]] = r
            n_new += 1
            continue
        for k, v in r.items():
            if k in ("reads", "clicks", "friends", "sent") or not old.get(k):
                old[k] = v
    kiroku["haishin"] = sorted(by.values(), key=lambda x: x["at"])
    return n_new


def zure(r):
    t = _dt.datetime.fromisoformat(r["at"])
    if t.weekday() != KIMARI["youbi"] or t.hour != KIMARI["ji"]:
        return "%s（%s曜%d時）" % (t.strftime("%m-%d %H:%M"), "月火水木金土日"[t.weekday()], t.hour)
    return ""


def to_hannou(kiroku, h):
    """sns_hannou.json に platform=line で並べる（X・TikTok・YouTube と同じ形）。"""
    posts = h.setdefault("posts", {})
    for r in kiroku.get("haishin", []):
        pid = "line:" + r["at"]
        st = {k: r[k] for k in ("reads", "clicks", "friends", "sent") if r.get(k) is not None}
        rec = posts.setdefault(pid, {"platform": "line", "url": (r.get("links") or [""])[0],
                                     "postedAt": r["at"], "text": (r.get("text") or "")[:300], "history": []})
        rec["account"] = ACCOUNT
        if st:
            day = r.get("kakunin_at", r["at"])[:10]
            rec["history"] = [x for x in rec["history"] if x.get("date") != day] + [dict(date=day, **st)]
            rec["latest"] = dict(date=day, **st)
    return h


def shuukei(h, kiroku, base=None):
    """先週（月〜日）と今週の途中を、全SNS同じ見え方で。"""
    base = base or now()
    mon = (base - _dt.timedelta(days=base.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    weeks = [("先週", mon - _dt.timedelta(days=7), mon), ("今週（途中）", mon, mon + _dt.timedelta(days=7))]
    out = []
    for name, a, b in weeks:
        row = {"week": name, "kara": a.date().isoformat(), "made": (b - _dt.timedelta(days=1)).date().isoformat(), "sns": {}}
        for pid, p in (h.get("posts") or {}).items():
            try:
                t = _dt.datetime.fromisoformat((p.get("postedAt") or "").replace("Z", "+00:00")).astimezone(JST)
            except Exception:
                continue
            if not (a <= t < b):
                continue
            s = row["sns"].setdefault(p.get("platform", "?"), {"honsuu": 0})
            s["honsuu"] += 1
            for k, v in (p.get("latest") or {}).items():
                if k != "date" and isinstance(v, int):
                    if k == "friends":
                        s[k] = max(s.get(k, 0), v)  # 友だち数は足さない（その週のいちばん新しい値）
                    else:
                        s[k] = s.get(k, 0) + v
        out.append(row)
    z = [zure(r) for r in kiroku.get("haishin", []) if zure(r)]
    return {"at": now().isoformat(timespec="seconds"), "what": "SNSの週まとめ（X・TikTok・YouTube・LINE）。数字は取れたものだけ（取れない数字は書かない）。",
            "weeks": out, "line": {"account": ACCOUNT, "tantou": "Grokボット（配信・運営）", "kimari": KIMARI["setsumei"],
                                   "haishin_kaisuu": len(kiroku.get("haishin", [])), "zure": z[-10:],
                                   "kiroku_no_basho": "https://github.com/%s/issues/%d（%s）" % (REPO_GH, ISSUE, MARK)}}


def gh_comments():
    gh = shutil.which("gh", path=ENV["PATH"]) or "gh"
    p = subprocess.run([gh, "api", "--paginate", "repos/%s/issues/%d/comments?per_page=100" % (REPO_GH, ISSUE),
                        "--jq", ".[]|{id,created_at,body}"], capture_output=True, text=True, timeout=120, env=ENV)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[:300])
    return [json.loads(x) for x in p.stdout.splitlines() if x.strip()]


def matome(kiroku=None):
    kiroku = kiroku or load(KIROKU, {"haishin": []})
    h = load(HANNOU, {"what": "SNS投稿の反応（再生数・いいね等）。取れない数字は書かない。", "posts": {}})
    to_hannou(kiroku, h)
    save(HANNOU, h)
    save(HANNOU_PUB, h)
    save(SHUUKEI, shuukei(h, kiroku))
    save(PUB, {"at": now().isoformat(timespec="seconds"), "account": ACCOUNT, "haishin": kiroku.get("haishin", [])[-60:]})


def tick(force=False):
    st = load(STATE, {})
    if not force and time.time() - st.get("last", 0) < GATE_SEC:
        return
    st["last"] = time.time()
    save(STATE, st)
    kiroku = load(KIROKU, {"haishin": []})
    try:
        cs = gh_comments()
    except Exception as e:
        log("#%d を読めなかった：%s" % (ISSUE, e))
        return
    recs = []
    for c in cs:
        r = parse(c.get("body", ""), c.get("created_at", ""))
        if r:
            r["kakunin_at"] = (c.get("created_at") or "")[:10] or r["at"][:10]
            r["comment"] = c.get("id")
            recs.append(r)
    n = merge(kiroku, recs)
    save(KIROKU, kiroku)
    wk = now().strftime("%G-W%V")
    if n or st.get("matome_week") != wk or now().weekday() == 0:
        matome(kiroku)
        st["matome_week"] = wk
        save(STATE, st)
    log("記録 %d件（新しく %d件）" % (len(kiroku["haishin"]), n))


def self_test():
    ok = True

    def eq(a, b, what):
        nonlocal ok
        if a != b:
            ok = False
            print("NG", what, a, "!=", b)

    body = MARK + "\n日時: 2026-10-25 04:12\n本文: Stevie Wonder「Overjoyed」\nhttps://joy-relief-station.lovable.app/cover-guide?artist=stevie-wonder&song=overjoyed\n毎日のネタはXでも → x.com/oasisjoyrelief\nリンク: https://joy-relief-station.lovable.app/cover-guide?artist=stevie-wonder&song=overjoyed\n既読: 1\n友だち: 1"
    r = parse(body, "2026-10-24T19:20:00Z")
    eq(r["at"], "2026-10-25T04:12+09:00", "日時")
    eq((r.get("reads"), r.get("friends"), r.get("clicks")), (1, 1, None), "取れた数字だけ（クリックは書かない）")
    eq(len(r["links"]), 1, "リンク")
    eq("Overjoyed" in r["text"] and "oasisjoyrelief" in r["text"], True, "本文は複数行")
    eq(parse("ただのコメント", ""), None, "印の無いコメントは拾わない")
    eq(parse(MARK + "\n本文: x", "2026-10-30T11:00:00Z")["at"], "2026-10-30T20:00+09:00", "日時が無ければコメントの時刻")
    k = {"haishin": []}
    eq(merge(k, [r]), 1, "1件目")
    eq(merge(k, [dict(r, clicks=3, text="")]), 0, "同じ日時は1件")
    eq((k["haishin"][0]["clicks"], bool(k["haishin"][0]["text"])), (3, True), "数字は上書き・本文は残す")
    eq(zure(r), "10-25 04:12（日曜4時）", "決まりとのずれ")
    eq(zure({"at": "2026-10-30T20:00+09:00"}), "", "金曜20時はずれでない")
    h = to_hannou(k, {"posts": {"x:1": {"platform": "x", "postedAt": "2026-10-23T10:00:00+09:00", "latest": {"likes": 2}}}})
    eq(h["posts"]["line:2026-10-25T04:12+09:00"]["latest"]["reads"], 1, "sns_hannou に line で並ぶ")
    s = shuukei(h, k, base=_dt.datetime(2026, 10, 27, 9, 0, tzinfo=JST))
    eq(s["weeks"][0]["sns"].get("line", {}).get("honsuu"), 1, "先週のLINE 1本")
    eq(s["weeks"][0]["sns"].get("x", {}).get("likes"), 2, "先週のX いいね")
    eq(len(s["line"]["zure"]), 1, "ずれの一覧")
    print("SELF-TEST", "OK" if ok else "NG")
    return 0 if ok else 1


def main(a):
    if not a or a[0] == "--tick":
        tick(force="--force" in a)
    elif a[0] == "--matome":
        matome()
    elif a[0] == "--self-test":
        return self_test()
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
