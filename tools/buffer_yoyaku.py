#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bufferへの予約投稿係。★たまごさんは「9/24 21:00 これ予約して」だけ言えばいい。

仕組み：
  Cowork/Dispatch側は **注文票(JSON)を status/buffer_queue/ に1枚置くだけ**。
  5分便がこの係を呼び、Mac側（鍵がある側）で実際にBufferへ予約を入れ、
  ★予約一覧を取り直して照合した結果を status/buffer_queue/done/ に書き戻す。
  → サンドボックスから鍵を触らない／たまごさんにログインを頼まない。

注文票（status/buffer_queue/20260924-2100.json）:
  {
    "channel_handle": "oasisjoyrelief",
    "forbid": ["eggypop2014"],
    "due_jst": "2026-09-24 21:00",
    "text": "本文（1文字も変えない）"
  }

★即時投稿はしない（mode は customScheduled 固定）。
★forbid に入っている相手には絶対に入れない（handle一致で止める）。
★登録して終わりにしない。必ず一覧を取り直して本文・日時・相手を照合する。
"""
import io
import json
import os
import re
import sys
import time
import datetime
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TAMAGO = os.path.expanduser("~/.tamago")
KEYS = os.path.join(TAMAGO, "keys", "api_keys.env")
QUEUE = os.path.join(REPO, "status", "buffer_queue")
DONE = os.path.join(QUEUE, "done")
LOG = os.path.join(REPO, "status", "kagi_daicho.log")
API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s [buffer_yoyaku] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass
    print(msg)


def token():
    """★鍵の読み口は tools/kagi.py 1本だけ（1132番）。
       BUFFER_TOKEN / BUFFER_ACCESS_TOKEN どちらの名前で書かれていても拾う。"""
    sys.path.insert(0, HERE)
    import kagi
    return kagi.get("BUFFER_ACCESS_TOKEN")


def gql(tok, query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % tok,
                 "User-Agent": "tamago-buffer-yoyaku"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ★公式ドキュメント（developers.buffer.com）のとおりの形。推測で書かない。
Q_ORGS = """
query GetOrganizations { account { organizations { id name ownerEmail } } }
"""

Q_CHANNELS = """
query GetChannels($orgId: String!) {
  channels(input: { organizationId: $orgId }) {
    id name displayName service isQueuePaused
  }
}
"""

M_CREATE = """
mutation CreatePost($input: PostCreateInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id text dueAt channelId status } }
    ... on MutationError { message }
  }
}
"""

Q_POSTS = """
query GetScheduledPosts($orgId: String!, $channelIds: [String!]) {
  posts(input: {
    organizationId: $orgId,
    sort: [{ field: dueAt, direction: asc }],
    filter: { status: [scheduled], channelIds: $channelIds }
  }) {
    edges { node { id text dueAt channelId status } }
  }
}
"""


def norm(s):
    """比較用。Bufferが前後の空白を落とすことがあるので、そこだけ揃える。"""
    return (s or "").replace("\r\n", "\n").strip()


def due_utc_iso(due_jst):
    """'2026-09-24 21:00' (JST) → '2026-09-24T12:00:00.000Z'。★変換を目で追えるように残す。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})", due_jst.strip())
    if not m:
        raise ValueError("due_jst の形が違います: %r" % due_jst)
    y, mo, d, h, mi = (int(x) for x in m.groups())
    local = datetime.datetime(y, mo, d, h, mi, tzinfo=JST)
    return local.astimezone(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"), local


def names_of(c):
    """Bufferはアカウント名の置き場が name / displayName に割れている。両方見る。"""
    out = []
    for k in ("name", "displayName"):
        v = (c.get(k) or "").strip().lstrip("@").lower()
        if v:
            out.append(v)
    return out


def pick_channel(channels, handle, forbid):
    want = (handle or "").lstrip("@").lower()
    ban = [f.lstrip("@").lower() for f in (forbid or [])]
    hit = None
    for c in channels:
        ns = names_of(c)
        if any(n in ban for n in ns):
            continue                      # ★禁止の相手は候補にすら入れない
        if want in ns:
            hit = c
    return hit


def fukumen_kanmon(text):
    """1076番【覆面客の関所】投稿文に入っている うちのURL が、覆面客を通っているか。

    たまごさん（2026-09-24）:「Xに投稿する曲が決まったら、その曲ページを必ず覆面客に通す。
    通す前に本番へ出さない。」
    ★通っていなければ予約しない。★判定に金は1円もかからない（台帳を読むだけ）。
    ★環境変数 FUKUMEN_SKIP=1 のときだけ素通りさせる（緊急用。使ったら報告する）。
    """
    if os.environ.get("FUKUMEN_SKIP") == "1":
        return True, "関所を素通り（FUKUMEN_SKIP=1）"
    urls = re.findall(r"https://joy-relief-station\.lovable\.app/\S+", text or "")
    if not urls:
        return True, "うちのURLが入っていないので関所の対象外"
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import fukumen_kyaku
    except Exception as e:
        return False, "覆面客の道具が読めません：%s" % str(e)[:120]
    for u in urls:
        u = u.rstrip("）)、。,.")
        r = fukumen_kyaku.kanmon(u)
        if not r:
            return False, ("覆面客に通していません: %s\n"
                           "  python3 tools/fukumen_kyaku.py --url \"%s\" --x \"<投稿文>\"" % (u, u))
        t = r.get("ten") or {}
        if not r.get("ok"):
            return False, "覆面客が不合格: %s（%s）" % (u, "、".join(r.get("fugoukakuRiyuu") or []))
        return True, "覆面客を通過（軽さ%s／楽しさ%s／美しさ%s・%s）" % (
            t.get("karusa"), t.get("tanoshisa"), t.get("utsukushisa"), r.get("at"))
    return True, ""


def run_one(job_path):
    job = json.load(io.open(job_path, encoding="utf-8"))
    out = {"job": os.path.basename(job_path), "at": time.strftime("%F %T %z")}

    # ★1076番：本番に出す前に覆面客の関所を通す（鍵を見に行くより前に止める）
    ok, why = fukumen_kanmon(job.get("text") or "")
    out["fukumen"] = why
    if not ok:
        out["result"] = "覆面客の関所で止めた"
        out["fix"] = why
        return out

    tok = token()
    if not tok:
        out["result"] = "鍵なし"
        out["fix"] = ("publish.buffer.com/settings/api で1回だけ鍵を作り、"
                      "~/Desktop/buffer_token.txt に貼って保存（あとは自動）")
        return out

    orgs = (((gql(tok, Q_ORGS).get("data") or {}).get("account") or {})
            .get("organizations") or [])
    if not orgs:
        out["result"] = "組織が取れない（鍵が通っていない可能性）"
        return out
    chans, org_id = [], None
    for o in orgs:
        got = (gql(tok, Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}
               ).get("channels") or []
        for c in got:
            c["_org"] = o["id"]
        chans += got
    out["channels_seen"] = [
        {"name": c.get("name"), "displayName": c.get("displayName"),
         "service": c.get("service"), "id": c.get("id")} for c in chans]
    ch = pick_channel(chans, job["channel_handle"], job.get("forbid"))
    if not ch:
        out["result"] = "チャンネルが見つからない（または禁止リストに入っている）"
        return out
    org_id = ch["_org"]
    out["channel"] = {"name": ch.get("name"),
                      "displayName": ch.get("displayName"), "id": ch["id"]}

    due_iso, local = due_utc_iso(job["due_jst"])
    out["due_jst"] = local.strftime("%F %H:%M %Z")
    out["due_utc"] = due_iso

    res = gql(tok, M_CREATE, {"input": {
        "text": job["text"],
        "channelId": ch["id"],
        "schedulingType": "automatic",
        "mode": "customScheduled",       # ★即時投稿にしない
        "dueAt": due_iso,
    }})
    cp = (res.get("data") or {}).get("createPost") or {}
    if cp.get("message") or res.get("errors"):
        out["result"] = "登録できず"
        out["error"] = cp.get("message") or str(res.get("errors"))[:300]
        return out
    post = cp.get("post") or {}
    out["post_id"] = post.get("id")
    out["result"] = "登録済み"

    # ---- ★ここからが本番：一覧を取り直して照合する ----
    time.sleep(2)
    q = gql(tok, Q_POSTS, {"orgId": org_id, "channelIds": [ch["id"]]})
    edges = ((q.get("data") or {}).get("posts") or {}).get("edges") or []
    found = None
    for e in edges:
        n = e.get("node") or {}
        if n.get("id") == post.get("id"):
            found = n
    if not found:
        out["kenpin"] = "不一致（予約一覧に見つからない）"
        return out
    same_text = norm(found.get("text")) == norm(job["text"])
    same_time = (found.get("dueAt") or "")[:16] == due_iso[:16]
    same_chan = found.get("channelId") == ch["id"]
    out["kenpin"] = "一致" if (same_text and same_time and same_chan) else "不一致"
    out["kenpin_detail"] = {"text": same_text, "dueAt": same_time,
                            "channel": same_chan,
                            "dueAt_api": found.get("dueAt")}
    return out


def main():
    if not os.path.isdir(TAMAGO):
        print("鍵の置き場(~/.tamago)が見えないので、何もせず退きました")
        return 3
    os.makedirs(DONE, exist_ok=True)
    # ★注文票だけを拾う。machi.json（行列）や hokyuu_result.json（結果）は注文票ではない。
    #   2026-09-24 実測：これを見ずに *.json を全部読んで、結果ファイルにまで
    #   「鍵なし」を書き戻していた＝done/ にゴミが増えていた。名前で線を引く。
    def is_job(fn):
        return (re.match(r"^\d{8}-", fn) and fn.endswith(".json")
                and not fn.startswith("."))
    jobs = sorted(f for f in os.listdir(QUEUE)
                  if is_job(f)) if os.path.isdir(QUEUE) else []
    if not jobs:
        return 0
    for fn in jobs:
        p = os.path.join(QUEUE, fn)
        try:
            out = run_one(p)
        except Exception as e:
            out = {"job": fn, "result": "落ちた", "error": repr(e)[:300]}
        dst = os.path.join(DONE, fn)
        tmp = "%s.%d.tmp" % (dst, os.getpid())
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=2))
        os.replace(tmp, dst)
        if out.get("result") in ("登録済み",):
            os.remove(p)                 # ★済んだ注文票だけ引っ込める
        log("%s → %s / 検品:%s" % (fn, out.get("result"), out.get("kenpin")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
