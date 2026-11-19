#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1166番【待機列を自分で積む係】たまごさんの操作 0回で 30〜50本まで伸ばす。

たまごさんの条件（2026-09-26〜27）:
  ・本人の動画があること
  ・関連が最低4つ
  ・投稿前にページを1個ずつ全部作る（未完成のページへのリンクを投稿しない）
  ・URLは本文の最後

やること（候補1本ぶんを1周回で1つだけ進める。心臓を重くしない）:
  1. 関連動画の候補を仕入れる（本番の searchYouTubeCandidates）
  2. 素人カバー等を落として上位4本を選び、本番へ入れる（adminAddRelatedVideo）
  3. 本番URLを実際に開いて数える（tools/1164_page_sekisho.mjs）
  4. 4つの条件を全部満たしたものだけ、待機列 machi.json の末尾に足す
     満たさなかったものは status/1166/tsumu_hazure.json に理由1行で残す（列から外す）

止まらないための決まり:
  ・YouTubeの検索枠が尽きた(429)日は、その場で退く。翌日また続きから進む
  ・1本ごとに台帳(status/1166/tsumu.jsonl)へ書くので、途中で殺されても続きから
  ・待機列が TARGET 本に届いたら何もしない
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
D = os.path.join(REPO, "status", "1166")
LIST = os.path.join(D, "kouho_list.json")
DAICHO = os.path.join(D, "tsumu.jsonl")
HAZURE = os.path.join(D, "tsumu_hazure.json")
STATE = os.path.join(D, "tsumu_state.json")
LOG = os.path.join(D, "tsumu.log")
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
JST = datetime.timezone(datetime.timedelta(hours=9))

TARGET = 40          # 待機列の目標（30〜50の真ん中）
AIDA_BYOU = 900      # 1本を進める間隔（15分）。心臓は5分おきに来るので3回に1回だけ働く
ADD_ID = "c48face2f76689376654c71af910f14f7f4c0c314789b24bb968eb252d8b157e"  # adminAddRelatedVideo
KANREN = 4


def log(m):
    try:
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
    io.open(p, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))


def sumi():
    """もう片付いた候補（入れた／外した）の n。"""
    out = set()
    for ln in io.open(DAICHO, encoding="utf-8") if os.path.exists(DAICHO) else []:
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("owatta"):
            out.add(o.get("n"))
    return out


def run(cmd, sec=220):
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=sec)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def erabu(nokotta, main):
    """上位4本。メインと同じものは入れない。同じチャンネルは2本まで。"""
    out, ch = [], {}
    for c in sorted(nokotta, key=lambda x: -int(x.get("views") or 0)):
        if c.get("youtubeId") == main:
            continue
        k = c.get("chId") or ""
        if ch.get(k, 0) >= 2:
            continue
        ch[k] = ch.get(k, 0) + 1
        out.append(c)
        if len(out) >= KANREN:
            break
    return out


def hazusu(r, why):
    h = jload(HAZURE, [])
    h.append({"n": r["n"], "artist": r["artist"], "song": r["song"],
              "url": r["url"], "riyuu": why,
              "at": datetime.datetime.now(JST).strftime("%F %T")})
    jsave(HAZURE, h)


def owari(n, ok, why):
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.datetime.now(JST).strftime("%F %T"),
                            "n": n, "owatta": True, "haitta": ok,
                            "why": why}, ensure_ascii=False) + "\n")


def main():
    if os.path.exists(os.path.join(REPO, "status", "1166.stop")):
        return 0
    st = jload(STATE, {})
    if time.time() - float(st.get("last", 0)) < AIDA_BYOU:
        return 0

    machi = jload(MACHI, {})
    nokori = len(machi.get("machi") or [])
    if nokori >= TARGET:
        return 0

    kouho = jload(LIST, [])
    done = sumi()
    tsugi = next((r for r in kouho if r["n"] not in done), None)
    if not tsugi:
        return 0

    st["last"] = time.time()
    jsave(STATE, st)
    tag = "%s/%s" % (tsugi["artistId"], tsugi["songId"])
    log("はじめ %s" % tag)

    # 1. 候補を仕入れる
    chumon = os.path.join(D, "t_chumon.json")
    kouho_out = os.path.join(D, "t_kouho.json")
    jsave(chumon, [{"n": tsugi["n"], "artistId": tsugi["artistId"],
                    "songId": tsugi["songId"], "main": "",
                    "queries": tsugi["queries"]}])
    rc, out = run(["node", "tools/1165_kanren_kouho.mjs", chumon, kouho_out])
    rows = (jload(kouho_out, {}).get("rows") or [{}])[0]
    errs = rows.get("errs") or []
    if any("429" in str(e.get("err")) for e in errs) and not (rows.get("nokotta") or []):
        log("YouTubeの検索枠が尽きた。今日はここまで（明日また続きから）")
        return 0
    nokotta = rows.get("nokotta") or []
    if len(nokotta) < KANREN:
        hazusu(tsugi, "関連に置ける動画が%d本しか見つからない（最低%d本）" % (len(nokotta), KANREN))
        owari(tsugi["n"], False, "候補不足")
        log("外した %s 候補不足" % tag)
        return 0

    # 2. 本番へ入れる
    erabi = erabu(nokotta, "")
    jobs = [{"name": "%s %s" % (tag, c["youtubeId"]), "id": ADD_ID,
             "data": {"password": "@", "artistId": tsugi["artistId"],
                      "songId": tsugi["songId"],
                      "url": "https://www.youtube.com/watch?v=%s" % c["youtubeId"],
                      "kind": "cover" if "cover" in (c.get("title") or "").lower() else "other"}}
            for c in erabi]
    addf = os.path.join(D, "t_add.json")
    jsave(addf, jobs)
    rc, out = run(["node", "tools/1165_serverfn.mjs", "--file", addf,
                   "--ledger", os.path.join(D, "add_daicho.jsonl")])
    if rc != 0:
        log("入れられなかった %s rc=%s %s" % (tag, rc, out[-200:]))
        return 0

    # 3. 本番のページを開いて数える
    uf = os.path.join(D, "t_url.txt")
    io.open(uf, "w", encoding="utf-8").write(tsugi["url"] + "\n")
    pf = os.path.join(D, "t_page.json")
    env = dict(os.environ, SEKISHO_SETTLE_MS="22000")
    p = subprocess.run(["node", "tools/1164_page_sekisho.mjs", uf, pf],
                       cwd=REPO, capture_output=True, text=True, timeout=120, env=env)

    import importlib.util
    hp = os.path.join(REPO, "status", "1135", "1165_hantei.py")
    sp = importlib.util.spec_from_file_location("h1165", hp)
    H = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(H)
    row = (jload(pf, {}).get("rows") or [None])[0]
    j = H.judge(row, tsugi["artist"])
    if not j.get("goukaku"):
        hazusu(tsugi, "ページの関所：" + "／".join(j.get("naze") or ["未測定"]))
        owari(tsugi["n"], False, "ページの関所")
        log("外した %s %s" % (tag, j.get("naze")))
        return 0

    # 4. 待機列の末尾へ
    import x_kata
    text = x_kata.normalize(tsugi["text"])
    nok, nwhy = x_kata.nagasa_ok(text)
    if not nok:
        hazusu(tsugi, "長さの関所：" + nwhy)
        owari(tsugi["n"], False, "長さ")
        return 0
    machi = jload(MACHI, {})
    ima = [(m.get("text") if isinstance(m, dict) else str(m))
           for m in (machi.get("machi") or [])]
    if text in ima or any((m.get("song_key") == tag) for m in (machi.get("machi") or [])
                          if isinstance(m, dict)):
        owari(tsugi["n"], False, "もう列にある")
        return 0
    machi.setdefault("machi", []).append(
        {"text": text, "song_key": tag, "from": "1166_machi_tsumu",
         "artist": tsugi["artist"], "song": tsugi["song"]})
    jsave(MACHI, machi)
    owari(tsugi["n"], True, "")
    log("入れた %s ／ 待機列 %d 本" % (tag, len(machi["machi"])))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        log("落ちた: %s" % ex)
        sys.exit(1)
