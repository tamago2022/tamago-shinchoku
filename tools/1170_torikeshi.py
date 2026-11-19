#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【取り消し予約】枠が戻った瞬間に、予約から外す。

たまごさんの言葉（2026-09-27・原文）:
  「とりあえずNeil Youngや絢香は外しておく」
  「今『色彩のブルース』を即時パブリッシュしたので、グリーンでは手動で1回
    取り消してください。これでちょっと組み直します。」

Bufferの枠は 2026-09-27 に尽きている（復帰の見込み 09-28 05:34）。
だから「今すぐ消す」ことはできない。**消したい相手を予約として記録しておき、
枠が戻った瞬間にこの係が自動で実行する。**待っている間もたまごさんは何もしない。

■ 絶対のきまり（勝手に別のものを消さないため）
  ・sagasu（探す文字）が本文に含まれる予約を数える。
    1本に決まったときだけ消す。
    0本 → 「予約に無い（もう出た可能性）」として done へ移す。代わりを消さない。
    2本以上 → ★消さない。候補を書き出して赤で待つ。たまごさんが番号で選ぶ。
  ・消したら done へ移す（何を消したか後から分かるように）。
  ・消したら「取り消しました」をたまごさんの手元へ押し出す。

■ 使い方
  python3 tools/1170_torikeshi.py           … 枠が空いていれば実行、無ければ何もしない
  python3 tools/1170_torikeshi.py --miru    … 1叩きもせず、待っているものを出す
  python3 tools/1170_torikeshi.py --erabu tk-greenday=2
        … 候補が2本以上あったとき、たまごさんが番号で選ぶ（2本目を消す）
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
TORIKESHI = os.path.join(REPO, "status", "buffer_queue", "torikeshi.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
LOG = os.path.join(REPO, "status", "1170", "torikeshi.jsonl")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]

Q_SCHED = """
query($o: OrganizationId!, $c: [ChannelId!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: asc }],
                 filter: { status: [scheduled], channelIds: $c } }) {
    edges { node { id text dueAt channelId status } }
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
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def oshidasu(title, message, urls=None):
    """たまごさんの手元へ1行。"""
    try:
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "1170-torikeshi-%s" % now().strftime("%H%M%S"),
                "type": "yoyaku_torikeshi", "title": title,
                "message": message,
                "urls": urls or ["https://publish.buffer.com/all-channels/queue"],
                "ok": True}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def gql(tok, q, v=None):
    if not buffer_waku.ake():
        raise RuntimeError(buffer_waku.riyuu())
    if not buffer_kura.tsukau("1170_torikeshi"):
        raise RuntimeError(buffer_kura.riyuu())
    b = {"query": q}
    if v:
        b["variables"] = v
    r = urllib.request.Request(API, data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer %s" % tok,
                                        "User-Agent": "tamago-1170-torikeshi"})
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            buffer_waku.tometa(e.headers, "1170_torikeshi")
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


def miru():
    d = jload(TORIKESHI, {})
    print("Bufferの枠:", buffer_waku.riyuu())
    print("叩いた回数:", buffer_kura.riyuu())
    m = d.get("machi") or []
    print("取り消し待ち: %d 件" % len(m))
    for e in m:
        print("  %-14s 探す文字「%s」 %s"
              % (e.get("id"), e.get("sagasu"),
                 ("★候補が%d本あって決まらない" % len(e["kouho"]))
                 if e.get("kouho") else (e.get("yoyaku_de_no_ichi") or "")))
        for i, k in enumerate(e.get("kouho") or [], 1):
            print("      %d) %s %s" % (i, k.get("due"), k.get("midashi")))
    print("済み: %d 件" % len(d.get("done") or []))
    return 0


def erabu_hikisuu():
    """--erabu tk-greenday=2 → {"tk-greenday": 2}"""
    out = {}
    for i, a in enumerate(sys.argv):
        if a == "--erabu" and i + 1 < len(sys.argv):
            for kv in sys.argv[i + 1].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    try:
                        out[k.strip()] = int(v)
                    except Exception:
                        pass
    return out


def main():
    if "--miru" in sys.argv:
        return miru()
    d = jload(TORIKESHI, {})
    machi = d.get("machi") or []
    if not machi:
        return 0
    # ★1178番（2026-09-28）止め札。取り消しも「消す」＝札があるあいだは待たせる。
    import buffer_tomeru
    _t = buffer_tomeru.tomete()
    if _t:
        print("%s → 取り消し待ちはそのまま待たせる" % _t)
        return 0
    if not buffer_waku.ake():
        print("枠が閉まっている。待つ。", buffer_waku.riyuu())
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    org, chid = channel(tok)
    e = ((gql(tok, Q_SCHED, {"o": org, "c": [chid]})
          .get("data") or {}).get("posts") or {}).get("edges") or []
    yoyaku = [x["node"] for x in e]
    print("いま予約 %d 本" % len(yoyaku))

    erabi = erabu_hikisuu()
    nokori, done = [], list(d.get("done") or [])
    for t in machi:
        sagasu = str(t.get("sagasu") or "").strip()
        if not sagasu:
            nokori.append(t)
            continue
        atari = [p for p in yoyaku if sagasu in (p.get("text") or "")]

        if len(atari) == 0:
            t["kekka"] = "予約に無い（もう出た／すでに消えている）。代わりのものは消していない。"
            t["at"] = now().strftime("%F %T")
            done.append(t)
            kiroku({"id": t.get("id"), "result": "予約に無い", "sagasu": sagasu})
            oshidasu("取り消すものが予約に無い",
                     "「%s」は予約に居ませんでした（もう出たと思われます）。"
                     "代わりに別のものは消していません。" % sagasu)
            continue

        if len(atari) > 1:
            n = erabi.get(t.get("id"))
            if not n or n < 1 or n > len(atari):
                t["kouho"] = [{"post_id": p.get("id"),
                               "due": (jst(p.get("dueAt") or "") or now()).strftime("%F %H:%M"),
                               "midashi": midashi(p.get("text"))} for p in atari]
                t["kekka"] = ("★候補が %d 本あって1本に決まらない。勝手に消さずに待つ。"
                              "どれを消すか番号で教えてください。" % len(atari))
                nokori.append(t)
                kiroku({"id": t.get("id"), "result": "候補が複数で待機",
                        "n": len(atari)})
                continue
            atari = [atari[n - 1]]

        p = atari[0]
        r = gql(tok, M_DEL, {"input": {"id": p.get("id")}})
        dp = (r.get("data") or {}).get("deletePost") or {}
        ok = bool((dp.get("post") or {}).get("id"))
        due = (jst(p.get("dueAt") or "") or now()).strftime("%F %H:%M")
        mi = midashi(p.get("text"))
        kiroku({"id": t.get("id"), "result": "消した" if ok else "消せなかった",
                "post_id": p.get("id"), "due": due, "midashi": mi,
                "error": dp.get("message") or ""})
        if ok:
            t["kekka"] = "取り消した（%s ／ %s）" % (due, mi)
            t["at"] = now().strftime("%F %T")
            t.pop("kouho", None)
            done.append(t)
            oshidasu("予約を取り消しました",
                     "取り消しました：%s ／ %s\n理由：%s" % (due, mi, t.get("naze") or ""))
            print("消した:", due, mi)
        else:
            t["kekka"] = "消せなかった：%s" % (dp.get("message") or "")
            nokori.append(t)
            print("消せなかった:", dp.get("message"))

    d["machi"], d["done"] = nokori, done
    d["at"] = now().strftime("%F %H:%M")
    jsave(TORIKESHI, d)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        kiroku({"result": "落ちた", "error": str(ex)[:300]})
        print("落ちた:", ex)
        sys.exit(1)
