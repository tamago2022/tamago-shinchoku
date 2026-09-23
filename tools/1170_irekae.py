#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【順番の入れ替え】たまごさんが番号を2つ言うだけで入れ替わる。

たまごさんの言葉（2026-09-27・原文）:
  「スカボロー・フェアとかはそれはそれでいい。入れ替えることができるのか？
    Buffer にまだ慣れてないから。」

■ 答え（どちらが簡単か）
  ★待機列（まだBufferに入っていないぶん）の入れ替えが一番簡単で、しかも0叩き。
    こちらの画面の番号を2つ言うだけ。Bufferに触らないので失敗しようがない。
      python3 tools/1170_irekae.py --retsu 3,1     （待機列の3番目を1番目へ）
      python3 tools/1170_irekae.py --retsu-ue 5    （5番目を先頭へ）
  ★もう予約に入っているぶん（10本）の時刻の入れ替えも、この係でできる。
    予約は customScheduled で時刻を固定してあるので、Bufferの画面で
    ドラッグしても思った所に行かないことがある。だからここから入れ替える。
      python3 tools/1170_irekae.py --yoyaku 5,7    （予約の5番目と7番目の時刻を交換）

■ 予約の入れ替えのやり方（安全側に倒す）
  ① まず updatePost 系のmutationで dueAt だけ書き換えられるか試す（1本につき1叩き）。
     使える名前が分かったら .irekae_field.json に覚えて、以後そこだけ使う。
  ② ①がどれも通らなかったときだけ、**先に本文を控えファイルへ保存してから**
     消して作り直す。途中で落ちても status/1170/irekae_hikae.json に本文が残るので、
     投稿が消えて終わりにはならない。
  ★①も②も、やる前と後にBufferから取り直して、本当に入れ替わったかを確かめる。
    自己申告で「入れ替えました」と言わない。

  python3 tools/1170_irekae.py --miru   … 番号つきで今の順番を出す（0叩き）
"""
import datetime
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import buffer_kura   # noqa: E402
import buffer_waku   # noqa: E402
import kagi          # noqa: E402

API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
D = os.path.join(REPO, "status", "1170")
FIELD = os.path.join(D, ".irekae_field.json")
HIKAE = os.path.join(D, "irekae_hikae.json")
LOG = os.path.join(D, "irekae.jsonl")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]

# ★どの名前で通るかは試して確かめる。通った名前だけ覚える。
KOUHO = [
    ("updatePost", "mutation($input: UpdatePostInput!){ updatePost(input:$input){"
                   " __typename ... on PostActionSuccess { post { id dueAt } }"
                   " ... on MutationError { message } } }"),
    ("reschedulePost", "mutation($input: ReschedulePostInput!){ reschedulePost(input:$input){"
                       " __typename ... on PostActionSuccess { post { id dueAt } }"
                       " ... on MutationError { message } } }"),
    ("movePost", "mutation($input: MovePostInput!){ movePost(input:$input){"
                 " __typename ... on PostActionSuccess { post { id dueAt } }"
                 " ... on MutationError { message } } }"),
]
Q_SCHED = """
query($o: OrganizationId!, $c: [ChannelId!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: asc }],
                 filter: { status: [scheduled], channelIds: $c } }) {
    edges { node { id text dueAt channelId status } }
  }
}
"""
M_CREATE = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id text dueAt } }
    ... on MutationError { message }
  }
}
"""
M_DEL = """
mutation($input: DeletePostInput!) {
  deletePost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id } }
    ... on MutationError { message }
  }
}
"""


def now():
    return datetime.datetime.now(JST)


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))


def kiroku(rec):
    rec = dict(rec)
    rec.setdefault("at", now().strftime("%F %T"))
    try:
        os.makedirs(D, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def gql(tok, q, v=None):
    if not buffer_waku.ake():
        raise RuntimeError(buffer_waku.riyuu())
    if not buffer_kura.tsukau("1170_irekae"):
        raise RuntimeError(buffer_kura.riyuu())
    b = {"query": q}
    if v:
        b["variables"] = v
    r = urllib.request.Request(API, data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer %s" % tok,
                                        "User-Agent": "tamago-1170-irekae"})
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            buffer_waku.tometa(e.headers, "1170_irekae")
        raise


def jst(s):
    for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return (datetime.datetime.strptime(s, f)
                    .replace(tzinfo=datetime.timezone.utc).astimezone(JST))
        except Exception:
            continue
    return None


def midashi(t):
    for ln in (t or "").split("\n"):
        if "—" in ln or "–" in ln:
            return ln.strip()
    return (t or "").split("\n")[0][:70]


def hikisuu(name):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return ""


# ───────────────────────── 待機列の入れ替え（0叩き・失敗しようがない）

def retsu_irekae():
    m = jload(MACHI, {})
    r = list(m.get("machi") or [])
    ue = hikisuu("--retsu-ue")
    if ue:
        try:
            i = int(ue) - 1
        except Exception:
            print("番号が読めない"); return 2
        if not (0 <= i < len(r)):
            print("待機列は %d 本。その番号は無い" % len(r)); return 2
        r.insert(0, r.pop(i))
        m["machi"] = r
        jsave(MACHI, m)
        print("待機列の %s 番目を先頭にした" % ue)
        return miru_retsu(m)
    ab = hikisuu("--retsu")
    try:
        a, b = [int(x) - 1 for x in ab.split(",")[:2]]
    except Exception:
        print("--retsu 3,1 の形で言ってください"); return 2
    if not (0 <= a < len(r)) or not (0 <= b < len(r)):
        print("待機列は %d 本。その番号は無い" % len(r)); return 2
    x = r.pop(a)
    r.insert(b, x)
    m["machi"] = r
    jsave(MACHI, m)
    print("待機列の %d 番目を %d 番目へ動かした" % (a + 1, b + 1))
    return miru_retsu(m)


def miru_retsu(m=None):
    m = m or jload(MACHI, {})
    r = m.get("machi") or []
    print("── 待機列（%d 本）" % len(r))
    for i, e in enumerate(r, 1):
        print("  %2d %s %s" % (i, (e.get("lang") or "??"),
                               midashi(e.get("text")) or (e.get("song") or "")))
    return 0


# ───────────────────────── 予約の時刻の入れ替え

def channel(tok):
    c = buffer_kura.ch_yomu()
    if c:
        return c["org"], c["channel_id"]
    orgs = ((gql(tok, "query{account{organizations{id name}}}").get("data") or {})
            .get("account") or {}).get("organizations") or []
    for o in orgs:
        cs = (gql(tok, "query($o:OrganizationId!){channels(input:{organizationId:$o})"
                  "{id name displayName}}", {"o": o["id"]})
              .get("data") or {}).get("channels") or []
        for c in cs:
            ns = [(c.get(k) or "").strip().lstrip("@").lower()
                  for k in ("name", "displayName") if (c.get(k) or "").strip()]
            if any(n in FORBID for n in ns):
                continue
            if WANT in ns:
                buffer_kura.ch_kaku(o["id"], c["id"], WANT)
                return o["id"], c["id"]
    raise RuntimeError("チャンネル %s が見つからない" % WANT)


def dueAt_wo_kaku(tok, post_id, due_utc):
    """★時刻だけ書き換えられるか試す。できたら True。使えた名前は覚える。"""
    d = jload(FIELD, {})
    if d.get("dame"):
        return False
    atari = d.get("atari")
    tameshi = [k for k in KOUHO if (not atari or k[0] == atari)]
    hazure = list(d.get("hazure") or [])
    for name, q in tameshi:
        if name in hazure:
            continue
        try:
            res = gql(tok, q, {"input": {"id": post_id, "dueAt": due_utc}}) or {}
        except Exception as ex:
            kiroku({"result": "書き換え失敗", "name": name, "error": str(ex)[:200]})
            return False
        if res.get("errors"):
            hazure.append(name)
            d["hazure"] = hazure
            d["dame"] = len(hazure) >= len(KOUHO)
            d["errors"] = str(res.get("errors"))[:200]
            jsave(FIELD, d)
            continue
        node = (res.get("data") or {}).get(name) or {}
        if (node.get("post") or {}).get("id"):
            d["atari"] = name
            d["saigo"] = now().strftime("%F %T")
            jsave(FIELD, d)
            return True
        hazure.append(name)
        d["hazure"] = hazure
        d["dame"] = len(hazure) >= len(KOUHO)
        d["message"] = node.get("message") or ""
        jsave(FIELD, d)
    return False


def tsukurinaosu(tok, chid, text, due_utc):
    res = gql(tok, M_CREATE, {"input": {
        "text": text, "channelId": chid, "assets": [],
        "needsApproval": False, "schedulingType": "automatic",
        "mode": "customScheduled", "dueAt": due_utc}})
    cp = (res.get("data") or {}).get("createPost") or {}
    return ((cp.get("post") or {}).get("id") or ""), (cp.get("message") or "")


def yoyaku_irekae():
    ab = hikisuu("--yoyaku")
    try:
        a, b = [int(x) - 1 for x in ab.split(",")[:2]]
    except Exception:
        print("--yoyaku 5,7 の形で言ってください")
        return 2
    if not buffer_waku.ake():
        print(buffer_waku.riyuu())
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2
    org, chid = channel(tok)
    e = ((gql(tok, Q_SCHED, {"o": org, "c": [chid]})
          .get("data") or {}).get("posts") or {}).get("edges") or []
    ps = sorted([x["node"] for x in e], key=lambda x: x.get("dueAt") or "")
    if not (0 <= a < len(ps)) or not (0 <= b < len(ps)) or a == b:
        print("予約は %d 本。その番号は入れ替えられない" % len(ps))
        return 3
    A, B = ps[a], ps[b]
    ta, tb = A.get("dueAt"), B.get("dueAt")
    jsave(HIKAE, {"at": now().strftime("%F %T"),
                  "A": {"id": A["id"], "dueAt": ta, "text": A.get("text")},
                  "B": {"id": B["id"], "dueAt": tb, "text": B.get("text")}})
    print("入れ替える:")
    print("  %d) %s %s" % (a + 1, (jst(ta) or now()).strftime("%F %H:%M"),
                           midashi(A.get("text"))))
    print("  %d) %s %s" % (b + 1, (jst(tb) or now()).strftime("%F %H:%M"),
                           midashi(B.get("text"))))

    # ① 時刻だけ書き換えられるか（消さないので安全）
    if dueAt_wo_kaku(tok, A["id"], tb) and dueAt_wo_kaku(tok, B["id"], ta):
        yari = "時刻だけ書き換えた"
    else:
        # ② 消して作り直す。★控えは上に保存済み
        print("  時刻だけの書き換えは通らなかった。消して作り直します（控えは保存済み）")
        for P, t in ((A, tb), (B, ta)):
            r = gql(tok, M_DEL, {"input": {"id": P["id"]}})
            dp = (r.get("data") or {}).get("deletePost") or {}
            if not (dp.get("post") or {}).get("id"):
                print("★消せなかった。ここで止めます:", dp.get("message"))
                kiroku({"result": "消せず中断", "post_id": P["id"],
                        "error": dp.get("message") or ""})
                return 8
            nid, err = tsukurinaosu(tok, chid, P.get("text") or "", t)
            if not nid:
                print("★作り直せなかった。本文は %s に残っています" % HIKAE)
                kiroku({"result": "作り直せず", "error": err, "hikae": HIKAE})
                return 9
        yari = "消して作り直した"

    # ★取り直して確かめる
    e2 = ((gql(tok, Q_SCHED, {"o": org, "c": [chid]})
           .get("data") or {}).get("posts") or {}).get("edges") or []
    ps2 = sorted([x["node"] for x in e2], key=lambda x: x.get("dueAt") or "")
    print("── 入れ替えたあとの順番")
    for i, p in enumerate(ps2, 1):
        print("  %2d %s %s" % (i, (jst(p.get("dueAt")) or now()).strftime("%F %H:%M"),
                               midashi(p.get("text"))))
    ok = (len(ps2) == len(ps))
    kiroku({"result": "入れ替えた" if ok else "★数が合わない", "yarikata": yari,
            "a": a + 1, "b": b + 1, "n_mae": len(ps), "n_ato": len(ps2)})
    buffer_kura.yoyaku_kaku({"cap": 10,
                             "yoyaku": buffer_kura.naraberu(ps2, jst)})
    return 0 if ok else 9


def miru():
    y = buffer_kura.yoyaku_yomu()
    print("Bufferの枠:", buffer_waku.riyuu())
    print("── 予約（%s 時点の控え。番号で言ってください）" % (y.get("at") or "-"))
    for i, p in enumerate(y.get("yoyaku") or [], 1):
        print("  %2d %s %s" % (i, p.get("due") or "?", midashi(p.get("text"))))
    miru_retsu()
    d = jload(FIELD, {})
    if d:
        print("時刻の書き換え：", json.dumps(d, ensure_ascii=False))
    return 0


def main():
    if hikisuu("--retsu") or hikisuu("--retsu-ue"):
        return retsu_irekae()
    if hikisuu("--yoyaku"):
        return yoyaku_irekae()
    return miru()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        kiroku({"result": "落ちた", "error": str(ex)[:300]})
        print("落ちた:", ex)
        sys.exit(1)
