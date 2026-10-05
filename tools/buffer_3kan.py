#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【ところてん#642 投入係】READY・独立QA・最終承認の3つが揃った投稿だけを、Bufferの予約へ流す。

たまごさん／Dispatch（2026-10-05）:
  チャッピー側のBuffer投入経路（iMac）が止まっている。工場（このMac）側でも入れられるようにする。
  出し先は oasisjoyrelief だけ。eggypop2014 は絶対に触らない。

■ 3つの条件（全部そろった曲だけ。1つでも欠けたら入れない）
  ① READY      … 公開リポ ops/social/claude-ready-*.jsonl に status=READY（Claudeがページを整えた印）
                  ＋ いまこの場で本番ページの関所（buffer_page_kanmon）を通る
  ② Jev QA_OK  … 工場で走らせる独立検品。PAGE/VIDEO/COPY/RELATED/COVER_LINK/THUMB の6印。
                  ★本物のJev（TypeSafe API）は鍵が無く栓も0円（金が出るので勝手に開けない）。
                    いまは機械版（0円）。本物が使える時は jev_honnin.py の栓を通す形に差し替える。
  ③ FINAL_OK   … #642 のコメントに「FINAL_OK q4-xxx YYYY-MM-DD HH:MM」の行（チャッピー）。
                  投稿文（英語コピー・ハッシュタグ）は ops/social/buffer-ready.jsonl の copy をそのまま使う。
                  ★ここでは文章を1文字も書かない・直さない。

■ 予約そのものは既存の道具に任せる（新しいBuffer叩きは作らない）
  注文票 status/buffer_queue/<日付>-<時刻>.json を置く → buffer_yoyaku（ページ関所・二重投稿関所・
  止め札・1日の叩き数の枠）が入れて、予約一覧を取り直して照合する。

■ ★外部公開（SNS予約）の承認
  最初の1件は、予約内容（日時・本文・リンク）を first_request.md に書いて止まる。
  Dispatch→たまごさんの許可が出たら:  python3 tools/buffer_3kan.py --shounin "<許可の言葉>" [--hagasu-tomeru]
  （.TOMERU は たまごさんが「二重投稿の心配は無い」と言った時だけ剥がす＝--hagasu-tomeru を付けた時だけ）。
  許可の記録が無い間は、注文票を1枚も置かない。

使い方:
  python3 tools/buffer_3kan.py            # 見るだけ（0円）。状況の1行と一覧を出す
  python3 tools/buffer_3kan.py --book     # 3条件＋許可が揃った分の注文票を置く
  python3 tools/buffer_3kan.py --post     # 状況を #642 にコメント
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SITE = "/Users/mac/Desktop/joy-relief-station"
REPO = "tamago2022/joy-relief-station"
ISSUE = 642
GH = os.path.expanduser("~/.local/bin/gh")
HANDLE = "oasisjoyrelief"
FORBID = ["eggypop2014"]
EARLIEST = "2026-10-09 15:00"  # これより前の枠はチャッピー側が入れている
JST = datetime.timezone(datetime.timedelta(hours=9))
OUT = os.path.join(ROOT, "status", "buffer_queue", "3kan")
QUEUE = os.path.join(ROOT, "status", "buffer_queue")
SHOUNIN = os.path.join(OUT, "shounin.json")
READY_FILES = ["ops/social/claude-ready-prepared-all.jsonl", "ops/social/claude-ready-1009-1011.jsonl"]
COPY_FILE = "ops/social/buffer-ready.jsonl"
SCHEDULE_FILE = "ops/social/october-2026-four-per-day.jsonl"
SKIP_WORDS = re.compile(r"christmas|xmas|クリスマス|santa|サンタ", re.I)
BAD_VIDEO_NOTE = re.compile(r"非公式|ファン|転載|リアクション")


def sh(args, timeout=60):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def site_show(path):
    rc, out, err = sh(["git", "-C", SITE, "show", "origin/main:" + path])
    return out if rc == 0 else ""


def jsonl(text):
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def fetch_site():
    sh(["git", "-C", SITE, "fetch", "-q", "origin", "main"], timeout=90)


def issue_comments():
    rc, out, err = sh([GH, "api", "repos/%s/issues/%d/comments" % (REPO, ISSUE), "--paginate",
                       "--jq", ".[] | {id:.id, user:.user.login, at:.created_at, body:.body} | @json"], timeout=90)
    res = []
    for ln in out.splitlines():
        try:
            res.append(json.loads(ln))
        except Exception:
            pass
    return res


FINAL = re.compile(r"^\s*FINAL_OK[\s:：]+(q4-[0-9a-z-]+)(?:[\s,、]+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}))?", re.M)


def final_ok_map(comments):
    """id -> (時刻 or None, コメントid)。後から出た FINAL_NG があれば取り消す。"""
    m = {}
    for c in comments:
        body = c.get("body") or ""
        for mt in FINAL.finditer(body):
            m[mt.group(1)] = ((mt.group(2) or "").replace("T", " ") or None, c.get("id"))
        for mt in re.finditer(r"^\s*FINAL_NG[\s:：]+(q4-[0-9a-z-]+)", body, re.M):
            m.pop(mt.group(1), None)
    return m


def tweet_len(text):
    """Xの数え方に近い値：URLは23、全角などは2、半角は1。"""
    urls = re.findall(r"https?://\S+", text)
    t = text
    for u in urls:
        t = t.replace(u, "")
    n = 23 * len(urls)
    for ch in t:
        n += 1 if ord(ch) < 0x1100 else 2
    return n


def lint_copy(copy, row):
    why = []
    if not copy or len(copy) < 30:
        return ["投稿文が無い／短すぎる"]
    urls = re.findall(r"https://joy-relief-station\.lovable\.app/\S+", copy)
    if len(urls) != 1:
        why.append("うちのURLが%d個（1個だけ）" % len(urls))
    else:
        a = urllib.parse.unquote(urls[0].rstrip("）)、。,."))
        b = urllib.parse.unquote(row.get("url") or "")
        if b and a != b:
            why.append("投稿文のURLがREADYの曲ページと違う")
    if re.search(r"youtube\.com|youtu\.be", copy):
        why.append("YouTube直リンク（禁止）")
    if tweet_len(copy) > 280:
        why.append("280字を超える（%d）" % tweet_len(copy))
    tags = re.findall(r"(?<!\w)#\w+", copy)
    if not tags or len(tags) > 4:
        why.append("ハッシュタグ%d個（1〜4個）" % len(tags))
    if SKIP_WORDS.search(copy) or SKIP_WORDS.search(row.get("song") or ""):
        why.append("クリスマス曲は10月に出さない（季節ルール）")
    return why


def jev_machine_qa(row, copy):
    """独立検品（機械版・0円）。6印を返す。理由が1つでもあれば QA_OK にしない。"""
    import buffer_page_kanmon as k
    r = k.shiraberu(row["url"])
    rs = r.get("riyuu") or []
    pick = lambda *keys: [x for x in rs if any(key in x for key in keys)]
    marks = {
        "PAGE_OK": pick("ページが", "曲ページにならない", "返ってこない", "返るまで"),
        "VIDEO_OK": pick("動画"),
        "COPY_OK": pick("本文") + lint_copy(copy, row),
        "RELATED_OK": pick("この流れで"),
        "COVER_LINK_OK": [],
        "THUMB_OK": pick("og:image", "サムネ", "画像", "空っぽ"),
    }
    note = row.get("video_note") or ""
    if BAD_VIDEO_NOTE.search(note):
        marks["VIDEO_OK"].append("動画の注意書き: " + note)
    other = [x for x in rs if not any(x in v for v in marks.values())]
    if other:
        marks["PAGE_OK"] += other
    ok = all(not v for v in marks.values())
    return {"qa": "QA_OK" if ok else "QA_NG", "marks": {k2: (not v) for k2, v in marks.items()},
            "problems": [x for v in marks.values() for x in v], "engine": "機械版（本物のJevは鍵・栓なし）"}


def buffer_scheduled(max_age=1200):
    """予約中の時刻一覧。Bufferは1日250回の枠があるので、読んだ結果を20分だけ覚えて使い回す。"""
    cache = os.path.join(OUT, "buffer_cache.json")
    try:
        c = json.load(io.open(cache, encoding="utf-8"))
        if now_jst().timestamp() - c["t"] < max_age:
            return [datetime.datetime.fromisoformat(x).astimezone(JST) for x in c["due"]], ""
    except Exception:
        pass
    try:
        import buffer_waku
        if not buffer_waku.ake():
            return None, "Bufferの枠が戻るまで読まない（%s）" % str(buffer_waku.riyuu())[:60]
        import buffer_yokoku as b
        posts = b.yomu()
    except Exception as e:
        return None, "Bufferの一覧が読めない: %s" % repr(e)[:80]
    ds = []
    for p in posts:
        if p.get("status") == "scheduled" and p.get("dueAt"):
            ds.append(datetime.datetime.fromisoformat(p["dueAt"].replace("Z", "+00:00")).astimezone(JST))
    ds.sort()
    try:
        io.open(cache, "w", encoding="utf-8").write(json.dumps({"t": now_jst().timestamp(), "due": [d.isoformat() for d in ds]}))
    except Exception:
        pass
    return ds, ""


def load_state():
    fetch_site()
    ready = {}
    for f in READY_FILES:
        for r in jsonl(site_show(f)):
            if r.get("status") == "READY":
                ready[r["id"]] = r
    copies = {r["id"]: r for r in jsonl(site_show(COPY_FILE)) if r.get("copy")}
    sched = {r["id"]: r for r in jsonl(site_show(SCHEDULE_FILE))}
    return ready, copies, sched


def now_jst():
    return datetime.datetime.now(JST)


def status_rows(do_qa=True):
    ready, copies, sched = load_state()
    final = final_ok_map(issue_comments())
    rows = []
    t0 = now_jst()
    for sid, r in sorted(ready.items(), key=lambda kv: kv[1]["target_at_jst"]):
        slot = r["target_at_jst"]
        if slot < EARLIEST:
            continue
        due = datetime.datetime.strptime(slot, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        item = {"id": sid, "slot": slot, "artist": r["artist"], "song": r["song"], "url": r["url"],
                "ready": True, "copy": bool(copies.get(sid)), "final_ok": False, "qa": None, "past": due <= t0 + datetime.timedelta(minutes=20)}
        fo = final.get(sid)
        if fo and (fo[0] is None or fo[0] == slot):
            item["final_ok"] = True
            item["final_comment_id"] = fo[1]
        elif fo:
            item["final_note"] = "FINAL_OKの時刻(%s)が枠(%s)と違う" % (fo[0], slot)
        c = copies.get(sid)
        if c and do_qa and not item["past"]:
            rr = dict(r)
            q = jev_machine_qa(rr, c["copy"])
            item.update(q)
            if c.get("target_at_jst") and c["target_at_jst"] != slot:
                item["qa"] = "QA_NG"
                item.setdefault("problems", []).append("copyの枠(%s)とREADYの枠(%s)が違う" % (c["target_at_jst"], slot))
            item["text"] = c["copy"]
        rows.append(item)
    return rows, sched


def hold_count(sched):
    return sum(1 for r in sched.values() if r.get("state") in ("HOLD", "PLANNED_NEEDS_REPAIR") and r.get("target_at_jst", "") >= EARLIEST)


def summary(rows, sched):
    ds, why = buffer_scheduled()
    booked = len(ds) if ds is not None else -1
    last = ds[-1].strftime("10/%d %H:%M").replace("10/0", "10/") if ds else "なし"
    if ds:
        last = "%d/%d %02d:%02d" % (ds[-1].month, ds[-1].day, ds[-1].hour, ds[-1].minute)
    waiting = sum(1 for x in rows if not x["past"] and not (x["copy"] and x["final_ok"] and x.get("qa") == "QA_OK"))
    go = [x for x in rows if x["copy"] and x["final_ok"] and x.get("qa") == "QA_OK" and not x["past"]]
    line = "予約済み%s件／最終予約 %s／READY待ち%d件／HOLD%d件" % (booked if booked >= 0 else "?(読めない)", last, waiting, hold_count(sched))
    return line, go, why


def write_first_request(item):
    os.makedirs(OUT, exist_ok=True)
    txt = ("# 最初の1件の予約内容（許可待ち）\n\n- 出し先: @%s（%s は触らない）\n- 日時: %s JST\n- ページ: %s\n"
           "- 3条件: READY◎ / Jev QA_OK(機械版)◎ / FINAL_OK◎（#642 コメント id=%s）\n\n## 本文（1文字も変えない）\n\n%s\n"
           % (HANDLE, ",".join(FORBID), item["slot"], item["url"], item.get("final_comment_id"), item["text"]))
    open(os.path.join(OUT, "first_request.md"), "w", encoding="utf-8").write(txt)
    return txt


def book(go, force_now=False):
    import buffer_tomeru
    made = []
    t = buffer_tomeru.tomete()
    if t:
        return made, "止め札あり: %s" % str(t)[:120]
    for it in go:
        d = datetime.datetime.strptime(it["slot"], "%Y-%m-%d %H:%M")
        fn = os.path.join(QUEUE, d.strftime("%Y%m%d-%H%M") + ".json")
        if os.path.exists(fn):
            continue
        job = {"channel_handle": HANDLE, "forbid": FORBID, "due_jst": it["slot"], "text": it["text"],
               "from": "buffer_3kan", "id": it["id"], "final_ok_comment": it.get("final_comment_id")}
        io.open(fn, "w", encoding="utf-8").write(json.dumps(job, ensure_ascii=False, indent=1))
        made.append(fn)
    return made, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", action="store_true")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--shounin", default="")
    ap.add_argument("--hagasu-tomeru", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if a.shounin:
        io.open(SHOUNIN, "w", encoding="utf-8").write(json.dumps(
            {"at": now_jst().strftime("%F %T"), "words": a.shounin}, ensure_ascii=False, indent=1))
        print("許可を記録しました:", a.shounin[:80])
        if a.hagasu_tomeru:
            tf = os.path.join(QUEUE, ".TOMERU")
            if os.path.exists(tf):
                os.replace(tf, os.path.join(OUT, "TOMERU.hagashita_%s.txt" % now_jst().strftime("%m%d%H%M")))
                print("止め札を剥がしました（控えは 3kan/ に残してあります）")

    rows, sched = status_rows()
    line, go, why = summary(rows, sched)
    json.dump({"at": now_jst().strftime("%F %T"), "line": line, "rows": rows}, io.open(os.path.join(OUT, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(line)
    for x in rows:
        if x["past"]:
            continue
        gates = "READY◯ copy%s QA:%s FINAL%s" % ("◯" if x["copy"] else "✕", (x.get("qa") or "-"), "◯" if x["final_ok"] else "✕")
        print("- %s %s「%s」 %s %s" % (x["slot"], x["artist"], x["song"], gates, "；".join(x.get("problems") or [])[:90]))
    if why:
        print("※", why)

    if a.post:
        body = "【工場の投入係｜%s】%s\n\n3条件が揃った（Buffer投入待ち）: %s\n欠けている条件の一覧は status/buffer_queue/3kan/report.json（工場）。" % (
            now_jst().strftime("%m/%d %H:%M"), line, "、".join(x["id"] for x in go) or "なし")
        sh([GH, "issue", "comment", str(ISSUE), "--repo", REPO, "--body", body])

    if go:
        approved = os.path.exists(SHOUNIN)
        if not approved:
            print(write_first_request(go[0]))
            print("★外部公開（SNS予約）のため、最初の1件は許可待ち。Dispatchへ報告して止まります。")
            return 3
        if a.book:
            made, why2 = book(go)
            print("注文票 %d 枚%s" % (len(made), ("（%s）" % why2) if why2 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
