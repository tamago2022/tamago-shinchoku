#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【手直し帳】たまごさんの赤入れを1か所に流し込み、同じ直しが2回出たら決まりに足す（手間ゼロ）。

たまごさん（2026-10-24）:
  「手直し帳：たまごさんの過去の赤入れ（記憶・GitHub共有メモ・マガジンの赤入れ記録）を流し込み、
   同じ直しが2回出たら決まりに足す仕組みにする。」

土台はイケハヤの AIクローンメーカー（~/.claude/skills/ai-clone-maker・工程6「手直しを覚える」）。
作業場は ~/jrs-clone/ai-clone（同期されないフォルダ・#1033 の指定どおり）。
  ・ai-clone/手直しの記録/手直し帳.md … 1回の赤入れ＝1つの書き込み（スキルの型）
  ・ai-clone/文体の決まり.md         … 2回出た学びを「手直し帳から足した決まり」の節へ（日付つき）
  ・ai-clone/検品の決まり.json       … 文字で拾えるものは rules に tenaoshi-* として足す（check_style.py が使う）
  ・status/tenaoshi/kimari.json      … 工場の X 投稿の2重検品（tools/x_nijuu_kenpin.py）が読む
  ★スキルの「本人のOKを取ってから足す」は、たまごさんの 2026-10-24 の指示（2回で足す・手間ゼロ）で置き換えた。

流し込む所（毎日1回・心臓から）:
  1. tools/tenaoshi_seed.json        … 過去の赤入れ（CLAUDE.md・スキル・記憶の禁止事項から、出どころつきで写したもの）
  2. GitHub 共有メモ #1040（店主の指示メモ）のコメント … 学びの「sagasu」の言葉が入っていれば1回
  3. Buffer の本文をたまごさんが画面で直した分 … 入れた文（status/x_nijuu/kekka.jsonl）と今の文の差
  数え方：同じ学びで「別の日」か「別の場所」なら別の1回。同じ所を何度読んでも1回。

使い方:
  python3 tools/tenaoshi_chou.py --daily      … 心臓から（20時間に1回に間引く）
  python3 tools/tenaoshi_chou.py --now        … 今すぐ
  python3 tools/tenaoshi_chou.py --self-test
★AIを呼ばない・0円。鍵は読まない（gh は工場のログインをそのまま使う）。投稿しない。
"""
from __future__ import annotations

import datetime
import difflib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SEED = os.path.join(HERE, "tenaoshi_seed.json")
D = os.path.join(REPO, "status", "tenaoshi")
DAICHO = os.path.join(D, "daicho.jsonl")      # 流し込んだ赤入れの台帳（1行1回）
KIMARI = os.path.join(D, "kimari.json")
STAMP = os.path.join(D, ".at")
PUB = os.path.join(REPO, "status", "public", "tenaoshi.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
KEKKA = os.path.join(REPO, "status", "x_nijuu", "kekka.jsonl")
CLONE = os.path.expanduser("~/jrs-clone/ai-clone")
REPO_GH = "tamago2022/joy-relief-station"
MEMO_ISSUE = 1040
JST = datetime.timezone(datetime.timedelta(hours=9))
MARK_S = "<!-- tenaoshi-chou:start -->"
MARK_E = "<!-- tenaoshi-chou:end -->"


def _now():
    return datetime.datetime.now(JST)


def _seed():
    return json.load(io.open(SEED, encoding="utf-8"))


def _read_daicho():
    rows = []
    try:
        for l in io.open(DAICHO, encoding="utf-8"):
            rows.append(json.loads(l))
    except Exception:
        pass
    return rows


def _uid(r):
    return "%s|%s|%s" % (r["gakubi"], r.get("hi"), r.get("doko"))


# ---------------------------------------------------------------- 流し込む
def from_seed(seed):
    return [dict(a, moto="seed") for a in seed["akaire"]]


def from_memo(seed):
    """GitHub 共有メモ #1040 のコメント。工場の自分の書き込み（<!-- tamago-factory -->）も、たまごさんの決定の写しなので読む。"""
    try:
        r = subprocess.run(["gh", "api", "--paginate", "repos/%s/issues/%d/comments" % (REPO_GH, MEMO_ISSUE),
                            "--jq", ".[] | {u: .html_url, at: .created_at, b: .body}"],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return [], "gh が走らない"
    if r.returncode != 0:
        return [], "gh：%s" % (r.stderr or "")[:120]
    out = []
    for l in r.stdout.splitlines():
        try:
            c = json.loads(l)
        except Exception:
            continue
        for k, g in seed["gakubi"].items():
            m = re.search(g["sagasu"], c.get("b") or "")
            if m:
                s = c["b"]
                i = m.start()
                out.append({"hi": (c.get("at") or "")[:10], "doko": "共有メモ#1040 " + c["u"],
                            "kotoba": re.sub(r"\s+", " ", s[max(0, i - 40): i + 80]).strip(), "gakubi": k, "moto": "memo"})
    return out, "コメント%d件を読んだ" % len(r.stdout.splitlines())


def _diff_kind(old, new):
    """入れた文 → たまごさんが直した文。どんな直しかを機械で名付ける（学びの種類）。"""
    kinds = []
    lo, ln = len(old), len(new)
    if ln < lo * 0.8:
        kinds.append("tenaoshi-kezuru")
    o_last = [x for x in re.split(r"\n", old) if x.strip() and not x.strip().startswith(("http", "#"))][-1:]
    n_last = [x for x in re.split(r"\n", new) if x.strip() and not x.strip().startswith(("http", "#"))][-1:]
    if o_last != n_last:
        kinds.append("tenaoshi-shime")
    if len(re.findall(r"[\U0001F300-\U0001FAFF]", new)) < len(re.findall(r"[\U0001F300-\U0001FAFF]", old)):
        kinds.append("tenaoshi-emoji")
    if set(re.findall(r"#\S+", old)) != set(re.findall(r"#\S+", new)):
        kinds.append("tenaoshi-tag")
    return kinds or ["tenaoshi-sonota"]


DIFF_NAMAE = {
    "tenaoshi-kezuru": "たまごさんがBufferで2割以上削った＝長すぎる",
    "tenaoshi-shime": "たまごさんがBufferで締めの一文を直した",
    "tenaoshi-emoji": "たまごさんがBufferで絵文字を減らした",
    "tenaoshi-tag": "たまごさんがBufferでハッシュタグを直した",
    "tenaoshi-sonota": "たまごさんがBufferで本文を直した（その他）",
}


def from_buffer():
    """入れた文（2重検品を通った文）と、Bufferの今の文（予約中・出した分）の差。"""
    ireta = {}
    try:
        for l in io.open(KEKKA, encoding="utf-8"):
            r = json.loads(l)
            if r.get("ok") and r.get("zenbun"):
                ireta[r["zenbun"]] = r.get("at", "")[:10]
    except Exception:
        pass
    if not ireta:
        return [], "入れた文の控えが無い（まだ0本）"
    try:
        sys.path.insert(0, HERE)
        import buffer_yoyaku as by
        import buffer_sekisho
        tok = by.token()
        if not tok:
            return [], "Bufferの鍵なし"
        orgs = ((by.gql(tok, by.Q_ORGS).get("data") or {}).get("account") or {}).get("organizations") or []
        chans = []
        for o in orgs:
            for c in (by.gql(tok, by.Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}).get("channels") or []:
                c["_org"] = o["id"]
                chans.append(c)
        ch = by.pick_channel(chans, "oasisjoyrelief", ["eggypop2014"])
        q = by.gql(tok, buffer_sekisho.Q_ALL, {"o": ch["_org"], "c": [ch["id"]], "s": ["scheduled", "sent"]})
        now = [e["node"] for e in ((q.get("data") or {}).get("posts") or {}).get("edges") or []]
    except Exception as e:
        return [], "Bufferが読めない：%s" % str(e)[:100]
    out = []
    for p in now:
        t = p.get("text") or ""
        if t in ireta:
            continue
        best, ratio = None, 0.0
        for o in ireta:
            x = difflib.SequenceMatcher(None, o, t).ratio()
            if x > ratio:
                best, ratio = o, x
        if best and ratio >= 0.6:
            for k in _diff_kind(best, t):
                out.append({"hi": (p.get("dueAt") or "")[:10], "doko": "Buffer 投稿 %s" % p["id"],
                            "kotoba": "前：%s ／ 後：%s" % (best[:60].replace("\n", " "), t[:60].replace("\n", " ")),
                            "gakubi": k, "moto": "buffer"})
    return out, "Bufferの%d本を入れた文と比べた" % len(now)


# ---------------------------------------------------------------- 決まりにする
def kimari_tsukuru(rows, seed):
    by = {}
    for r in rows:
        by.setdefault(r["gakubi"], {})[(r.get("hi"), r.get("doko"))] = r
    kim, yousumi = [], []
    for k, occ in sorted(by.items()):
        g = seed["gakubi"].get(k) or {"namae": DIFF_NAMAE.get(k, k), "regex": None, "level": "check"}
        item = {"id": k, "namae": g["namae"], "regex": g.get("regex"), "level": g.get("level", "check"),
                "kaisu": len(occ), "akaire": [{"hi": h, "doko": d, "kotoba": v.get("kotoba")} for (h, d), v in occ.items()]}
        (kim if len(occ) >= 2 else yousumi).append(item)
    return kim, yousumi


def _write(path, s):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(s)
    os.replace(tmp, path)


def clone_ni_kaku(kim, yousumi, rows, clone=CLONE):
    """スキルの作業場へ。無ければ何もしない（作るのは init_clone.py の仕事）。"""
    if not os.path.isdir(clone):
        return "作業場が無い（%s）" % clone
    hi = _now().strftime("%F")
    # 手直し帳（スキルの書き込みの型。台帳から毎回作り直す＝二重に書かない）
    head = io.open(os.path.join(clone, "手直しの記録", "手直し帳.md"), encoding="utf-8").read() \
        if os.path.exists(os.path.join(clone, "手直しの記録", "手直し帳.md")) else "# 手直し帳\n\n---\n"
    head = head.split(MARK_S)[0].rstrip() + "\n\n"
    body = [MARK_S, "<!-- tools/tenaoshi_chou.py が台帳 status/tenaoshi/daicho.jsonl から作り直す所。手で書くならこの外へ -->", ""]
    for r in sorted(rows, key=lambda x: (str(x.get("hi")), x["gakubi"])):
        body += ["## %s %s" % (r.get("hi"), r.get("doko")),
                 "- 直した所: %s" % r.get("kotoba"),
                 "- 学び（文体）: %s" % r["gakubi"],
                 "- どうしたか: %s" % ("決まりへ足した（%s回）" % next(k["kaisu"] for k in kim if k["id"] == r["gakubi"])
                                    if any(k["id"] == r["gakubi"] for k in kim) else "様子見（1回目）"), ""]
    body.append(MARK_E)
    _write(os.path.join(clone, "手直しの記録", "手直し帳.md"), head + "\n".join(body) + "\n")
    # 文体の決まり（節を1つ持ち、毎回入れ替える）
    p = os.path.join(clone, "文体の決まり.md")
    s = io.open(p, encoding="utf-8").read() if os.path.exists(p) else "# 文体の決まり\n"
    s = re.sub(re.escape(MARK_S) + r".*?" + re.escape(MARK_E), "", s, flags=re.S).rstrip() + "\n\n"
    sec = [MARK_S, "## 手直し帳から足した決まり（同じ赤入れが2回出たもの・自動・%s）" % hi, "",
           "たまごさんの指示（2026-10-24）で、2回出たら本人のOK待ちをせずに足す。出どころは手直し帳。", ""]
    for k in kim:
        sec.append("- **%s**（%d回：%s）" % (k["namae"], k["kaisu"], "／".join("%s %s" % (a["hi"], a["doko"]) for a in k["akaire"][:3])))
    sec += ["", "様子見（1回だけ）：" + ("、".join(y["namae"] for y in yousumi) or "なし"), MARK_E]
    _write(p, s + "\n".join(sec) + "\n")
    # 検品の決まり（tenaoshi-* を入れ替え）
    p = os.path.join(clone, "検品の決まり.json")
    try:
        rj = json.load(io.open(p, encoding="utf-8"))
        rj["rules"] = [r for r in rj.get("rules", []) if not str(r.get("id", "")).startswith("tenaoshi-")]
        for k in kim:
            if k.get("regex"):
                rj["rules"].append({"id": "tenaoshi-" + k["id"], "level": k["level"], "regex": k["regex"],
                                    "reason": "手直し帳：%s（%d回）" % (k["namae"], k["kaisu"]),
                                    "hint": "たまごさんの赤入れ。言い換えずに、事実か本音で書き直す"})
        _write(p, json.dumps(rj, ensure_ascii=False, indent=2))
    except Exception as e:
        return "検品の決まりに書けない：%s" % str(e)[:80]
    return "作業場へ書いた（%s）" % clone


def run(force=False):
    if not force and os.path.exists(STAMP) and time.time() - os.path.getmtime(STAMP) < 20 * 3600:
        return {"result": "今日はもう走った"}
    seed = _seed()
    have = {_uid(r) for r in _read_daicho()}
    new, notes = [], {}
    for name, fn in (("seed", lambda: (from_seed(seed), "種")), ("memo", lambda: from_memo(seed)), ("buffer", from_buffer)):
        try:
            got, why = fn()
        except Exception as e:
            got, why = [], "失敗：%s" % str(e)[:100]
        notes[name] = why
        for r in got:
            if _uid(r) not in have:
                have.add(_uid(r))
                r["ireta"] = _now().isoformat(timespec="seconds")
                new.append(r)
    os.makedirs(D, exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    rows = _read_daicho()
    old_ids = set()
    try:
        old_ids = {k["id"] for k in json.load(io.open(KIMARI, encoding="utf-8")).get("kimari", [])}
    except Exception:
        pass
    kim, yousumi = kimari_tsukuru(rows, seed)
    _write(KIMARI, json.dumps({"at": _now().isoformat(timespec="seconds"), "kimari": kim, "yousumi": yousumi},
                              ensure_ascii=False, indent=1))
    clone = clone_ni_kaku(kim, yousumi, rows)
    added = [k for k in kim if k["id"] not in old_ids]
    if added and old_ids:
        io.open(OUTBOX, "a", encoding="utf-8").write(json.dumps({
            "at": _now().isoformat(timespec="seconds"), "type": "tenaoshi_kimari", "from": "tenaoshi_chou",
            "text": "手直し帳：同じ赤入れが2回出たので決まりに足した → " + "、".join(k["namae"] for k in added)},
            ensure_ascii=False) + "\n")
    out = {"at": _now().isoformat(timespec="seconds"), "akaire": len(rows), "atarashii": len(new),
           "kimari": [{"id": k["id"], "namae": k["namae"], "kaisu": k["kaisu"]} for k in kim],
           "yousumi": [{"id": y["id"], "namae": y["namae"]} for y in yousumi], "yonda": notes, "sagyouba": clone}
    _write(PUB, json.dumps(out, ensure_ascii=False, indent=1))
    io.open(STAMP, "w").write(out["at"])
    return out


def self_test():
    global DAICHO, KIMARI, STAMP, PUB, OUTBOX
    bad = []
    tmp = tempfile.mkdtemp(prefix="tenaoshi_t_")
    try:
        DAICHO, KIMARI, STAMP, PUB, OUTBOX = (os.path.join(tmp, x) for x in ("d.jsonl", "k.json", ".at", "p.json", "o.jsonl"))
        seed = {"gakubi": {"a": {"namae": "A", "sagasu": "x", "regex": "ダメ語", "level": "ng"},
                           "b": {"namae": "B", "sagasu": "y", "regex": None, "level": "check"}},
                "akaire": [{"hi": "1", "doko": "p", "kotoba": "", "gakubi": "a"},
                           {"hi": "2", "doko": "p", "kotoba": "", "gakubi": "a"},
                           {"hi": "1", "doko": "p", "kotoba": "", "gakubi": "b"},
                           {"hi": "1", "doko": "p", "kotoba": "", "gakubi": "b"}]}
        kim, you = kimari_tsukuru(seed["akaire"], seed)
        if [k["id"] for k in kim] != ["a"]:
            bad.append("2回出た学びだけを決まりにできない：%s" % kim)
        if [y["id"] for y in you] != ["b"]:
            bad.append("同じ所の2回を2回と数えた")
        c = os.path.join(tmp, "ai-clone")
        os.makedirs(os.path.join(c, "手直しの記録"))
        io.open(os.path.join(c, "検品の決まり.json"), "w").write('{"rules":[{"id":"x"}]}')
        clone_ni_kaku(kim, you, seed["akaire"], c)
        clone_ni_kaku(kim, you, seed["akaire"], c)          # 2回走っても二重にならない
        rj = json.load(io.open(os.path.join(c, "検品の決まり.json")))
        if [r["id"] for r in rj["rules"]] != ["x", "tenaoshi-a"]:
            bad.append("検品の決まりへの足し方がおかしい：%s" % rj["rules"])
        s = io.open(os.path.join(c, "文体の決まり.md")).read()
        if s.count(MARK_S) != 1:
            bad.append("文体の決まりの節が二重になった")
        if _diff_kind("aaa\nWho?\n#X", "aaa\nWhich?\n#X") != ["tenaoshi-shime"]:
            bad.append("締めの直しを見分けられない")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST", "PASS" if not bad else "FAIL", bad)
    return 0 if not bad else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--daily" in a or "--now" in a:
        print(json.dumps(run(force="--now" in a), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
