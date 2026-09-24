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
    Q_ORGS, Q_CHANNELS, M_CREATE, Q_POSTS, log,
)

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
    added, failed = [], []
    for (iso, local), item in zip(slots, machi[:len(slots)]):
        text = item["text"] if isinstance(item, dict) else str(item)
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
            continue
        added.append({"id": post["id"], "due_jst": local.strftime("%F %H:%M"),
                      "due_utc": iso, "text": text})

    # ★行列から出した分だけ引っ込める（失敗した分は行列に残す）
    d["machi"] = machi[len(added):]
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
