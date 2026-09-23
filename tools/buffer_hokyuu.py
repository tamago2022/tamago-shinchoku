#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bufferの予約欄を毎朝ひとりでに埋め直す係（補充便）。

たまごさんの設計（2026-09-24）：
  無料Bufferの10枠は**上限ではなく「同時に待機できる在庫数」**。
  最初に10本 → 1本出たら空く → 11本目を足す、を繰り返す。
  ★常に8〜10本埋まった状態に保つ。
  ★常駐で見張らない。**毎朝6:00に1回**だけ見て、10件未満なら10件まで補充する。
  ★たまごさんがやるのは「この2週間はこの28曲」を決めることだけ。

置き場：
  status/buffer_queue/machi.json      … 投稿待ちの行列（順番に並んだ本文。28本ぶん）
  status/buffer_queue/hokyuu_result.json … 毎回の結果＋検品（★ズレたら aka=true）
  status/buffer_queue/.hokyuu_stamp   … その日もう走ったかの印（1日1回に間引く）

走り方：
  5分便(machine_status_push.sh)に相乗り。★新しいlaunchd便は増やさない（工場の決まり）。
  中で「今日の6:00を過ぎていて、まだ今日走っていないか」を見て、違えば即 return＝無害。

枠の決め方：
  朝 07:30 JST と 夜 21:00 JST の2本立て。今より後の枠を古い順に埋める。
  ★既に予約が入っている時刻は飛ばす（二重に置かない）。
"""
import io
import json
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)

from buffer_yoyaku import (  # noqa: E402  同じ鍵・同じ照合を使い回す（2つ目の実装を作らない）
    JST, TAMAGO, QUEUE, API, token, gql, norm, due_utc_iso, pick_channel,
    Q_ORGS, Q_CHANNELS, M_CREATE, M_EDIT, Q_POSTS, log,
)
import x_kata  # noqa: E402  ★1153番【Xの投稿の型】URLを必ず一番最後に置く係
import buffer_sekisho  # noqa: E402  ★1164番【二重投稿の関所】同じ本文・同じ曲は二度と入れない

MACHI = os.path.join(QUEUE, "machi.json")
RESULT = os.path.join(QUEUE, "hokyuu_result.json")
STAMP = os.path.join(QUEUE, ".hokyuu_stamp")

TARGET = 10          # ★満タン＝10本（無料枠の在庫数）
FLOOR = 8            # ★8本を切ったら必ず足す（8〜10で回す）
SLOTS = [(7, 30), (21, 0)]   # 朝・夜のJST
HOUR = 6             # 毎朝6:00


def ran_today():
    try:
        d = io.open(STAMP, encoding="utf-8").read().strip()
    except Exception:
        return False
    return d == datetime.datetime.now(JST).strftime("%F")


def stamp():
    os.makedirs(QUEUE, exist_ok=True)
    tmp = "%s.%d.tmp" % (STAMP, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(datetime.datetime.now(JST).strftime("%F"))
    os.replace(tmp, STAMP)


def load_machi():
    if not os.path.exists(MACHI):
        return {"channel_handle": "oasisjoyrelief",
                "forbid": ["eggypop2014"], "machi": [], "sumi": []}
    return json.load(io.open(MACHI, encoding="utf-8"))


def save_machi(d):
    tmp = "%s.%d.tmp" % (MACHI, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))
    os.replace(tmp, MACHI)


def write_result(d):
    tmp = "%s.%d.tmp" % (RESULT, os.getpid())
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))
    os.replace(tmp, RESULT)


def next_slots(taken_iso, how_many):
    """今より後の 07:30 / 21:00 を、既に埋まっている時刻を飛ばしながら拾う。"""
    now = datetime.datetime.now(JST)
    taken = set(t[:16] for t in taken_iso if t)   # UTCのISOで比較
    out, day = [], now.date()
    for _ in range(60):                            # 最大30日ぶん見れば足りる
        for (h, mi) in SLOTS:
            cand = datetime.datetime(day.year, day.month, day.day, h, mi,
                                     tzinfo=JST)
            if cand <= now + datetime.timedelta(minutes=10):
                continue
            iso, _local = due_utc_iso(cand.strftime("%F %H:%M"))
            if iso[:16] in taken:
                continue
            out.append((iso, cand))
            if len(out) >= how_many:
                return out
        day += datetime.timedelta(days=1)
    return out


def main():
    if not os.path.isdir(TAMAGO):
        print("鍵の置き場(~/.tamago)が見えないので、何もせず退きました")
        return 3
    now = datetime.datetime.now(JST)
    force = "--now" in sys.argv
    if not force and (now.hour < HOUR or ran_today()):
        return 0                                   # ★1日1回。それ以外は完全に無害

    # ★1137番：下の「鍵なし」「チャンネルが見つからない」で抜ける道に判子が無く、
    #   失敗している間だけ5分おきに叩き直していた（＝Buffer 24時間枠250回の食い潰しの一因）。
    #   叩く前に押す。通っても通らなくても、その日はもう叩かない。
    if not force:
        stamp()

    res = {"at": now.strftime("%F %T %z"), "aka": False}
    tok = token()
    if not tok:
        res.update(result="鍵なし", aka=True,
                   fix="publish.buffer.com/settings/api の鍵を "
                       "~/Desktop/buffer_token.txt へ（あとは自動）")
        write_result(res)
        return 2

    d = load_machi()
    handle, forbid = d.get("channel_handle"), d.get("forbid") or []

    orgs = (((gql(tok, Q_ORGS).get("data") or {}).get("account") or {})
            .get("organizations") or [])
    chans = []
    for o in orgs:
        got = (gql(tok, Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}
               ).get("channels") or []
        for c in got:
            c["_org"] = o["id"]
        chans += got
    ch = pick_channel(chans, handle, forbid)
    if not ch:
        res.update(result="チャンネルが見つからない", aka=True,
                   handle=handle,
                   channels_seen=[c.get("name") for c in chans])
        write_result(res)
        return 2
    org_id = ch["_org"]
    res["channel"] = {"handle": handle, "id": ch["id"]}

    def scheduled():
        q = gql(tok, Q_POSTS, {"orgId": org_id, "channelIds": [ch["id"]]})
        return [(e.get("node") or {}) for e in
                (((q.get("data") or {}).get("posts") or {}).get("edges") or [])]

    before = scheduled()
    res["before"] = len(before)

    # ★1153番【Xの投稿の型】すでに予約に入っているものも直す。
    #   たまごさんがBufferの画面から入れた投稿は、この道具を通っていないので型が崩れる。
    #   「入るときに直す」だけでは漏れるので、**毎回、入っているものも測って直す**。
    #   使う口は editPost（スキーマに聞いて確定：editPost(input: EditPostInput{ id, text, ... })）。
    #   ★消さない・作り直さない＝dueAtも相手も動かない。書き替えるのは text だけ。
    naoshita = []
    for p in before:
        old = p.get("text") or ""
        if x_kata.check(old):
            continue
        new = x_kata.normalize(old)
        r = gql(tok, M_EDIT, {"input": {"id": p["id"], "text": new}})
        ok = bool(((r.get("data") or {}).get("editPost") or {}).get("post"))
        naoshita.append({"id": p["id"], "due": p.get("dueAt"),
                         "naotta": ok,
                         "why": None if ok else json.dumps(r, ensure_ascii=False)[:200]})
    if naoshita:
        res["kata_naoshita"] = naoshita
        before = scheduled()          # ★直したら取り直して照合する
        res["kata_kenpin"] = ("全部 型OK" if all(x_kata.check(p.get("text") or "") for p in before)
                              else "★まだ型に合っていないものが残っている")

    if len(before) >= FLOOR and len(before) >= TARGET:
        res.update(result="満タン（補充なし）", after=len(before), kenpin="一致")
        write_result(res); stamp()
        return 0

    need = TARGET - len(before)
    machi = d.get("machi") or []
    if not machi:
        res.update(result="行列が空（★たまごさんが次の28本を決める番）",
                   after=len(before), aka=(len(before) < FLOOR),
                   nokori=0)
        write_result(res); stamp()
        return 0

    slots = next_slots([p.get("dueAt") for p in before], min(need, len(machi)))

    # ★★1164番【二重投稿の関所】2026-09-26、同じ投稿が2本出た（松任谷由実）。
    #   原因は、ここが「いま予約に並んでいるもの(scheduled)」しか見ていなかったこと。
    #   1本目が出て予約欄が空になった瞬間、行列に残っていた同じ本文が2本目として入った。
    #   → 入れる前に **予約中・出した分(sent)・失敗分・台帳** を全部突き合わせる。
    mon = buffer_sekisho.Mon(lambda q, v=None: gql(tok, q, v))
    mon.load(org_id, ch["id"])
    res["sekisho_mita"] = mon.mita

    added, failed = [], []
    tsukatta = 0          # 行列の先頭から何本ぶん処理したか（弾いた分も含めて引っ込める）
    si = 0                # 次に使う枠
    for item in machi:
        if si >= len(slots):
            break
        text = item["text"] if isinstance(item, dict) else str(item)
        # ★1153番【Xの投稿の型】URLを必ず一番最後に置く（status/X_TOUKOU_KATA.md）。
        #   URLが末尾でないと、Xはカードを出した上に本文のURLの文字列も残す＝「リンクが2回」。
        #   言葉は1文字も書き替えない。動かすのはURLの行の位置だけ。
        text = x_kata.normalize(text)
        iso, local = slots[si]
        ok, why = mon.tsukaeru(text, iso)
        if not ok:
            mon.hajiku(text, why, iso)
            tsukatta += 1                     # ★弾いたものは行列から捨てる（次も弾かれるだけ）
            continue                           # ★枠は使わない（次の曲に回す）
        r = gql(tok, M_CREATE, {"input": {
            "text": text, "channelId": ch["id"],
            "schedulingType": "automatic",
            "mode": "customScheduled",        # ★即時投稿にしない
            "dueAt": iso}})
        cp = (r.get("data") or {}).get("createPost") or {}
        post = cp.get("post") or {}
        if cp.get("message") or r.get("errors") or not post.get("id"):
            failed.append({"due_jst": local.strftime("%F %H:%M"),
                           "error": cp.get("message") or str(r.get("errors"))[:200]})
            break                              # ★失敗したらそこで止める（行列は減らさない）
        mon.kiroku(text, iso, post["id"], "hokyuu")
        added.append({"id": post["id"], "due_jst": local.strftime("%F %H:%M"),
                      "due_utc": iso, "text": text})
        tsukatta += 1
        si += 1

    res["hajiita"] = mon.hajiita
    res["hajiita_kazu"] = mon.hajiita_kazu

    # ★行列から使った分（入れた分＋弾いた分）だけ引っ込める。失敗した分は行列に残す
    d["machi"] = machi[tsukatta:]
    d.setdefault("sumi", [])
    d["sumi"] = (d["sumi"] + [a["text"] for a in added])[-200:]
    save_machi(d)

    # ---- ★登録して終わりにしない。取り直して照合する ----
    time.sleep(3)
    after = scheduled()
    by_id = {p.get("id"): p for p in after}
    zure = []
    for a in added:
        p = by_id.get(a["id"])
        if not p:
            zure.append({"id": a["id"], "why": "予約一覧に無い"})
            continue
        if norm(p.get("text")) != norm(a["text"]):
            zure.append({"id": a["id"], "why": "本文が違う"})
        if (p.get("dueAt") or "")[:16] != a["due_utc"][:16]:
            zure.append({"id": a["id"], "why": "日時が違う",
                         "api": p.get("dueAt"), "tanomi": a["due_utc"]})
        if p.get("channelId") != ch["id"]:
            zure.append({"id": a["id"], "why": "★相手が違う"})

    res.update(result="補充した", tashita=len(added), shippai=failed,
               after=len(after), added=added,
               nokori=len(d["machi"]),
               kenpin="一致" if not zure else "不一致",
               zure=zure,
               aka=bool(zure or failed or len(after) < FLOOR))
    write_result(res)
    stamp()
    log("補充 %d本 / 予約 %d本 / 残り行列 %d / 検品:%s"
        % (len(added), len(after), len(d["machi"]), res["kenpin"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
