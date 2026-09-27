#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1168番【✕だった予約のページを直す係】

たまごさんの言葉（2026-09-27）:
  「✕が1本でもあればその1本を予約から外す」

★ただし、外すより**直すほうが良い**。外すと曲が1本減るだけだから。
  だからこの係は、まずページを直しにいく:
    関連動画を4本入れる → ページを開き直して数える → ◯になったら検品表を作り直す
  直らなかったときだけ、予約から外す（外したことも検品表に出る）。

いつ働くか（心臓から呼ばれる。15分に1回まで）:
  ・YouTubeの検索枠が尽きている間は何もしない（枠は太平洋の0時＝JST16時ごろ戻る）
  ・出る24時間前を切ってもまだ✕なら、直すのを諦めて予約から外す

読む: status/public/1168_kenpin.json（検品表。✕の行を見る）
書く: status/1168/naosu.log ／ naosu.jsonl
"""
import io
import json
import os
import subprocess
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

D = os.path.join(REPO, "status", "1168")
KENPIN = os.path.join(REPO, "status", "public", "1168_kenpin.json")
LOG = os.path.join(D, "naosu.log")
JSONL = os.path.join(D, "naosu.jsonl")
STATE = os.path.join(D, "naosu_state.json")
JST = datetime.timezone(datetime.timedelta(hours=9))
AIDA_BYOU = 900
KANREN = 4
ADD_ID = "c48face2f76689376654c71af910f14f7f4c0c314789b24bb968eb252d8b157e"
AKIRAMERU_JIKAN = 24        # 出る何時間前で「直すのを諦めて外す」か


def log(m):
    try:
        os.makedirs(D, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.datetime.now(JST).strftime("%F %T"), m))
    except Exception:
        pass


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run(cmd, byou=180):
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=byou)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 99, str(e)


def id_kara_url(u):
    """cover-guide?artist=..&song=.. から artistId / songId を取る。"""
    import urllib.parse as up
    q = up.parse_qs(up.urlparse(u).query)
    return (q.get("artist") or [""])[0], (q.get("song") or [""])[0]


def main():
    if os.path.exists(os.path.join(REPO, "status", "1168.stop")):
        return 0
    st = jload(STATE, {})
    if "--now" not in sys.argv and time.time() - float(st.get("last", 0)) < AIDA_BYOU:
        return 0

    d = jload(KENPIN, {})
    ng = [r for r in (d.get("rows") or []) if r.get("hantei") == "✕"]
    if not ng:
        return 0

    st["last"] = time.time()
    jsave(STATE, st)

    r = ng[0]
    aid, sid = id_kara_url(r.get("url") or "")
    tag = "%s/%s" % (aid, sid)
    if not aid or not sid:
        log("URLから曲が読めない: %s" % r.get("url"))
        return 1

    # 出るまでの残り時間
    nokori = 999.0
    try:
        t = datetime.datetime.strptime(r["due"], "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        nokori = (t - datetime.datetime.now(JST)).total_seconds() / 3600.0
    except Exception:
        pass

    log("直しにいく %s（出るまで %.1f 時間／%s）" % (tag, nokori, "／".join(r.get("ng") or [])))

    # 1. 関連の候補を仕入れる（YouTubeの枠が尽きていたら今日はここまで）
    kyoku = (r.get("midashi") or sid).strip()
    nushi = (r.get("title") or "").split("—")[-1].split("（")[0].strip() or aid
    queries = ["%s %s live" % (kyoku, nushi), "%s cover" % kyoku,
               "%s %s" % (nushi, kyoku), "%s acoustic" % kyoku]
    chumon = os.path.join(D, "n_chumon.json")
    kouho = os.path.join(D, "n_kouho.json")
    jsave(chumon, [{"n": 1, "artistId": aid, "songId": sid,
                    "main": "", "queries": queries}])
    run(["node", "tools/1165_kanren_kouho.mjs", chumon, kouho])
    rows = (jload(kouho, {}).get("rows") or [{}])[0]
    nokotta = rows.get("nokotta") or []
    errs = rows.get("errs") or []
    if any("429" in str(e.get("err")) for e in errs) and not nokotta:
        log("YouTubeの検索枠が尽きている。枠が戻ってから続きから。")
        return 0

    if len(nokotta) < KANREN:
        log("候補が %d 本しか無い（最低 %d 本）" % (len(nokotta), KANREN))
        if nokori <= AKIRAMERU_JIKAN:
            return hazusu(r, "関連が集まらないまま出る24時間前を切った")
        return 0

    # 2. 本番のページへ関連を入れる
    jobs = [{"name": "%s %s" % (tag, c["youtubeId"]), "id": ADD_ID,
             "data": {"password": "@", "artistId": aid, "songId": sid,
                      "url": "https://www.youtube.com/watch?v=%s" % c["youtubeId"],
                      "kind": "cover" if "cover" in (c.get("title") or "").lower()
                              else "other"}}
            for c in nokotta[:KANREN]]
    addf = os.path.join(D, "n_add.json")
    jsave(addf, jobs)
    rc, out = run(["node", "tools/1165_serverfn.mjs", "--file", addf,
                   "--ledger", os.path.join(D, "n_daicho.jsonl")])
    if rc != 0:
        log("関連を入れられなかった rc=%s %s" % (rc, out[-200:]))
        return 0

    # 3. 検品表を作り直す（★ページを開き直して数える）
    run(["python3", "tools/1168_kenpin_hyou.py", "--hakarinaosu"], byou=600)
    d2 = jload(KENPIN, {})
    ima = next((x for x in (d2.get("rows") or []) if x.get("url") == r.get("url")), None)
    naotta = bool(ima and ima.get("hantei") == "◯")
    with io.open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.datetime.now(JST).strftime("%F %T"),
                            "tag": tag, "naotta": naotta,
                            "kanren": (ima or {}).get("kanren")},
                           ensure_ascii=False) + "\n")
    log("直った %s" % tag if naotta else "まだ✕ %s" % tag)
    if not naotta and nokori <= AKIRAMERU_JIKAN:
        return hazusu(r, "直らないまま出る24時間前を切った")
    return 0


def hazusu(r, naze):
    """諦めて予約から外す。Bufferの枠が空いているときだけ。"""
    # ★1178番（2026-09-28）止め札。ChatGPTが入れた10本を機械が勝手に外さない。
    import buffer_tomeru
    _t = buffer_tomeru.tomete()
    if _t:
        log("外したいが止め札あり。%s" % _t)
        return 0
    import buffer_waku
    if not buffer_waku.ake():
        log("外したいが枠切れ。%s" % buffer_waku.riyuu())
        return 0
    log("予約から外す %s（%s）" % (r.get("due"), naze))
    rc, out = run(["python3", "tools/1168_kenpin_hyou.py", "--hazusu"], byou=600)
    log("外した結果 rc=%s %s" % (rc, out[-200:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
