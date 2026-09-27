#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1167番【待機列の先頭を1本だけBufferへ入れる】

たまごさんの言葉（2026-09-27）:
  「ページ作りや予定表より先に、Bufferに実際に入れるのが本体」
  「1本入るごとに報告できる状態にする」

だから この道具は **1回に1本だけ** 入れて、入ったら必ず保存してから終わる。
途中で殺されても、次に呼べば続きから。

実測で分かっていること（2026-09-27）:
  ★Bufferの予約は **10本が上限**。11本目は
    「Scheduled posts limit reached. You have 10 scheduled posts out of 10 allowed.」
    が返る。上限のときは **入れずに退く**（エラーを握りつぶさない）。
  ★時刻は customScheduled + dueAt(UTC) で固定する。queue任せだと前倒しで出る。

使い方:
  python3 tools/1167_ireru1.py          … 1本入れる
  python3 tools/1167_ireru1.py --miru   … 入れずに今の状態だけ見る
"""
import io
import json
import os
import sys
import datetime
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kagi          # noqa: E402
import buffer_waku   # noqa: E402

API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
LOG = os.path.join(REPO, "status", "1166", "ireru1.jsonl")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]
SLOTS = [(9, 0), (20, 0)]
CAP = 10

M_CREATE = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id text dueAt channelId status } }
    ... on MutationError { message }
  }
}
"""
Q_SCHED = """
query($o: OrganizationId!, $c: [ChannelId!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: asc }],
                 filter: { status: [scheduled], channelIds: $c } }) {
    edges { node { id text dueAt channelId status } }
  }
}
"""


def gql(tok, q, v=None):
    b = {"query": q}
    if v:
        b["variables"] = v
    r = urllib.request.Request(API, data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer %s" % tok,
                                        "User-Agent": "tamago-1167-ireru1"})
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            # ★枠切れ。門を閉めて、以降この係も他の係も叩かない
            buffer_waku.tometa(e.headers, "1167_ireru1")
        raise


def jst(iso_s):
    for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            t = datetime.datetime.strptime(iso_s, f)
            return t.replace(tzinfo=datetime.timezone.utc).astimezone(JST)
        except Exception:
            continue
    return None


def tsugi_no_waku(taken):
    """予約で埋まっていない、いちばん手前の枠。"""
    now = datetime.datetime.now(JST)
    day = now.date()
    for _ in range(90):
        for (h, mi) in SLOTS:
            c = datetime.datetime(day.year, day.month, day.day, h, mi, tzinfo=JST)
            if c <= now + datetime.timedelta(minutes=10):
                continue
            if c.strftime("%F %H:%M") not in taken:
                return c
        day += datetime.timedelta(days=1)
    return None


def kiroku(rec):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    if not buffer_waku.ake():          # ★枠切れの間は1回も叩かない
        print(buffer_waku.riyuu())
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    orgs = ((gql(tok, "query{account{organizations{id name}}}").get("data") or {})
            .get("account") or {}).get("organizations") or []
    ch = org = None
    for o in orgs:
        cs = (gql(tok, "query($o:OrganizationId!){channels(input:{organizationId:$o})"
                  "{id name displayName}}", {"o": o["id"]})
              .get("data") or {}).get("channels") or []
        for c in cs:
            ns = [(c.get(k) or "").strip().lstrip("@").lower()
                  for k in ("name", "displayName") if (c.get(k) or "").strip()]
            if any(n in FORBID for n in ns):      # ★eggypop2014には絶対入れない
                continue
            if WANT in ns:
                ch, org = c, o["id"]
    if not ch:
        print("チャンネル %s が見つからない" % WANT)
        return 4

    def yoyaku():
        e = ((gql(tok, Q_SCHED, {"o": org, "c": [ch["id"]]})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return [x["node"] for x in e]

    ima = yoyaku()
    taken = set()
    honbun = set()
    for p in ima:
        t = jst(p.get("dueAt") or "")
        if t:
            taken.add(t.strftime("%F %H:%M"))
        honbun.add((p.get("text") or "").strip())

    print("いま予約 %d 本／上限 %d 本" % (len(ima), CAP))
    for i, p in enumerate(sorted(ima, key=lambda x: x.get("dueAt") or ""), 1):
        t = jst(p.get("dueAt") or "")
        print("  %2d %s %s" % (i, t.strftime("%F %H:%M") if t else "?",
                               (p.get("text") or "").split("\n")[0][:52]))

    if "--miru" in sys.argv:
        return 0

    if len(ima) >= CAP:
        print("★満杯（%d/%d）。1本出て空くまで入れられない。" % (len(ima), CAP))
        kiroku({"at": datetime.datetime.now(JST).strftime("%F %T"),
                "result": "満杯で入れず", "yoyaku": len(ima), "cap": CAP})
        return 3

    m = json.load(io.open(MACHI, encoding="utf-8"))
    retsu = m.get("machi") or []
    if not retsu:
        print("待機列が空。入れるものが無い。")
        return 5

    tsugi = retsu[0]
    text = (tsugi.get("text") or "").strip()

    # ★二重投稿の関所：同じ本文が既に予約に居たら入れない
    if text in honbun:
        print("同じ本文が既に予約に居る。列から外す:", tsugi.get("song_key"))
        m["machi"] = retsu[1:]
        json.dump(m, io.open(MACHI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return 6

    # ★Xの型の関所：URLは本文の最後
    lines = [x for x in text.split("\n") if x.strip()]
    if "http" not in lines[-1]:
        print("URLが本文の最後に無い。入れない:", tsugi.get("song_key"))
        return 7

    waku = tsugi_no_waku(taken)
    due = waku.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    res = gql(tok, M_CREATE, {"input": {
        "text": text, "channelId": ch["id"], "assets": [],
        "needsApproval": False, "schedulingType": "automatic",
        "mode": "customScheduled", "dueAt": due}})
    cp = (res.get("data") or {}).get("createPost") or {}
    post = cp.get("post") or {}
    err = cp.get("message") or (str(res.get("errors"))[:300] if res.get("errors") else "")

    rec = {"at": datetime.datetime.now(JST).strftime("%F %T"),
           "song_key": tsugi.get("song_key"), "due_jst": waku.strftime("%F %H:%M"),
           "due_utc": due, "post_id": post.get("id"),
           "result": "入った" if post.get("id") else "入らなかった", "error": err}
    kiroku(rec)

    if not post.get("id"):
        print("★入らなかった:", err or res)
        return 8

    # ★入った。列から外して保存する（ここを先にやらないと二度入れの事故になる）
    m["machi"] = retsu[1:]
    m.setdefault("sumi", []).append(text)
    json.dump(m, io.open(MACHI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with io.open(DASHITA, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": rec["at"], "song_key": rec["song_key"],
                            "due_utc": due, "post_id": post["id"],
                            "where": "1167_ireru1",
                            "head": text[:60]}, ensure_ascii=False) + "\n")

    # ★自己申告にしない。Bufferから取り直して確かめる
    ato = yoyaku()
    mita = [p for p in ato if p.get("id") == post["id"]]
    ok = bool(mita) and (mita[0].get("dueAt") == due) \
        and ((mita[0].get("text") or "").strip() == text) \
        and (mita[0].get("channelId") == ch["id"])
    print("入った: %s / %s" % (rec["song_key"], waku.strftime("%F %H:%M")))
    print("取り直して確認: %s（予約は %d 本になった）"
          % ("一致" if ok else "★ずれている", len(ato)))
    return 0 if ok else 9


STAMP = os.path.join(REPO, "status", "1166", ".ireru1_stamp")
KANKAKU = 300   # ★5分に1回まで。毎周回叩くとBufferが429を返す（2026-09-27 実測）


def mabiku():
    """--now が無いときは KANKAKU 秒あけないと働かない。"""
    if "--now" in sys.argv:
        return False
    import time
    try:
        if time.time() - os.path.getmtime(STAMP) < KANKAKU:
            return True
    except Exception:
        pass
    return False


def han():
    try:
        os.makedirs(os.path.dirname(STAMP), exist_ok=True)
        io.open(STAMP, "w", encoding="utf-8").write(
            datetime.datetime.now(JST).strftime("%F %T"))
    except Exception:
        pass


if __name__ == "__main__":
    # ★2026-09-27 この係は tools/1170_hako.py に置き換わった。
    #   1170は「朝09:00＝邦楽／夜21:00＝洋楽」の振り分けと、チャッピーの関所を持つ。
    #   両方走ると同じ本文を二度入れる事故になるので、ここは何もしないで退く。
    #   （中の関数は 1170 から読まれるので消していない。手で使うときは --dashite）
    if "--dashite" not in sys.argv:
        print("この係は tools/1170_hako.py に置き換わりました。"
              "python3 tools/1170_hako.py --miru")
        sys.exit(0)
    if mabiku():
        sys.exit(0)
    try:
        rc = main()
    except Exception as _e:
        kiroku({"at": datetime.datetime.now(JST).strftime("%F %T"),
                "result": "落ちた", "error": str(_e)[:300]})
        rc = 1
    han()          # ★失敗しても判子を押す。押さないと次の周回でまた叩く
    sys.exit(rc)
