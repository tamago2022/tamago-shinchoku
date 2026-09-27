#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【自動投稿の箱】1本出たら1本繰り上がる。朝は日本の曲・夜は洋楽。

たまごさんの言葉（2026-09-27・原文）:
  「自動投稿の箱を作って、朝と夜の振り分けをお願いします。
    曲は俺が適当に入れていくので、仕組みだけ作っておいてください。」
  「朝9時に日本の曲にしよう。夜は洋楽にしましょう。」
  「朝9:00＝邦楽／夜21:00＝洋楽」
  「10件まで予約投稿できる枠を作る／1個投稿されたら次の1個が繰り上がって、
    途切れなく回る」
  「コピーはチャッピーに相談して整えてもらってから、予約投稿の仕組みに入れる」

■ この係がやること（1回に1本だけ）
  1. Bufferの予約を取り直す（1叩き）
  2. 前回の控えと見比べて、消えている＝もう出たものを見つけ、
     たまごさんの手元へ「投稿されました＋Xのリンク」を押し出す（x_shirase）
  3. 空いている一番手前の枠を探す。その枠の言語（朝=ja／夜=en）を決める
  4. 待機列から、その言語に合う先頭の1本を選ぶ（合わないものは飛ばす。列から消さない）
  5. 関所を全部通ったら入れる（1叩き）→ 取り直して確かめる（1叩き）
  ＝1本につき3叩き。朝夜で1日6叩き。天井は buffer_kura.NORI=20。

■ 投稿前の関所（1つでも欠けたら入れない。理由を必ず残す）
  ① chappie == "ok"       … チャッピー（ChatGPT）のOKが出ていないものは流さない
  ② from が nagekomi/nushi … ★機械が勝手に選んだものは流さない（絢香・Neil Youngの件）
  ③ kanmon_ok == True      … 本人の動画あり／関連4本以上／ページ完成。
                             実測して印を付けるのは tools/1170_nagekomi_nagasu.py
  ④ URLが本文のいちばん最後の行にある
  ⑤ 予約中の本文・もう出した本文と重複していない
  ⑥ 言語が枠と一致している（朝に洋楽を入れない／夜に邦楽を入れない）

■ 使い方
  python3 tools/1170_hako.py          … 1本入れる（間引きあり）
  python3 tools/1170_hako.py --now    … 間引きを無視して今すぐ
  python3 tools/1170_hako.py --miru   … 1叩きもせず、手元の控えだけで今の状態を出す
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
import x_shirase     # noqa: E402

API = "https://api.buffer.com"
JST = datetime.timezone(datetime.timedelta(hours=9))
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
DASHITA = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
LOG = os.path.join(REPO, "status", "1170", "hako.jsonl")
STAMP = os.path.join(REPO, "status", "1170", ".hako_stamp")
WANT = "oasisjoyrelief"
FORBID = ["eggypop2014"]
CAP = 10
KANKAKU = 300          # 5分に1回まで（毎周回叩くと429。2026-09-27 実測）
SLOTS_DEFAULT = [("09:00", "ja"), ("21:00", "en")]
DAREGA_IIKA = ("nagekomi", "nushi")   # ★機械選曲は入れない

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


# ───────────────────────── 道具

def now():
    return datetime.datetime.now(JST)


def kiroku(rec):
    rec = dict(rec)
    rec.setdefault("at", now().strftime("%F %T"))
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def gql(tok, q, v=None, who="1170_hako"):
    """★叩く前に必ず2つの門を通す。天井に当たったら叩かない。"""
    if not buffer_waku.ake():
        raise RuntimeError(buffer_waku.riyuu())
    if not buffer_kura.tsukau(who):
        raise RuntimeError(buffer_kura.riyuu())
    b = {"query": q}
    if v:
        b["variables"] = v
    r = urllib.request.Request(API, data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer %s" % tok,
                                        "User-Agent": "tamago-1170-hako"})
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            buffer_waku.tometa(e.headers, "1170_hako")
        raise


def jst(iso_s):
    for f in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            t = datetime.datetime.strptime(iso_s, f)
            return t.replace(tzinfo=datetime.timezone.utc).astimezone(JST)
        except Exception:
            continue
    return None


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))


# ───────────────────────── 朝は日本の曲・夜は洋楽

def slots(m):
    """machi.json の slots_lang から [(時刻, 言語)] を作る。無ければ既定。"""
    d = (m or {}).get("slots_lang") or {}
    if not isinstance(d, dict) or not d:
        return list(SLOTS_DEFAULT)
    out = []
    for k in sorted(d.keys()):
        try:
            hh, mm = [int(x) for x in str(k).split(":")[:2]]
        except Exception:
            continue
        out.append(("%02d:%02d" % (hh, mm), str(d[k] or "").strip().lower()))
    return out or list(SLOTS_DEFAULT)


def nihongo_ga_aru(s):
    """ひらがな・カタカナ・漢字が1文字でもあれば True。"""
    for c in s or "":
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) \
           or (0x3400 <= o <= 0x4DBF) or (0xFF66 <= o <= 0xFF9D):
            return True
    return False


def kotoba(e):
    """その1本が日本の曲(ja)か洋楽(en)か。

    ★まず本人が書いた lang を尊重する（機械の推測より人の指定が上）。
      無いときだけ、アーティスト名・曲名に日本語の文字があるかで決める。
      どちらとも言えないものは "" を返す（＝どの枠にも入れない。勝手に決めない）。
    """
    v = str((e or {}).get("lang") or "").strip().lower()
    if v in ("ja", "jp", "邦", "邦楽", "日本"):
        return "ja"
    if v in ("en", "洋", "洋楽", "海外"):
        return "en"
    na = "%s %s" % ((e or {}).get("artist") or "", (e or {}).get("song") or "")
    if na.strip():
        return "ja" if nihongo_ga_aru(na) else "en"
    # 名前が無いときは本文の2行目（「Artist — Song」の行）を見る
    for ln in str((e or {}).get("text") or "").split("\n"):
        if "—" in ln or "–" in ln:
            return "ja" if nihongo_ga_aru(ln) else "en"
    return ""


def tsugi_no_waku(m, taken):
    """予約で埋まっていない、いちばん手前の枠。(時刻, 言語) を返す。"""
    ss = slots(m)
    day = now().date()
    for _ in range(90):
        for (hhmm, lang) in ss:
            hh, mm = [int(x) for x in hhmm.split(":")]
            c = datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=JST)
            if c <= now() + datetime.timedelta(minutes=10):
                continue
            if c.strftime("%F %H:%M") not in taken:
                return c, lang
        day += datetime.timedelta(days=1)
    return None, ""


# ───────────────────────── 投稿前の関所

def kanmon(e, lang, honbun_zumi, sumi_zumi):
    """通らない理由を並べて返す。空っぽなら通った。"""
    ng = []
    text = str((e or {}).get("text") or "").strip()
    if not text:
        ng.append("本文が空")
        return ng
    if str(e.get("chappie") or "").lower() != "ok":
        ng.append("チャッピーのOKが出ていない（chappie=%s）"
                  % (e.get("chappie") or "未"))
    if str(e.get("from") or "") not in DAREGA_IIKA:
        ng.append("機械が選んだもの（from=%s）。たまごさんが投げたものだけ流す"
                  % (e.get("from") or "不明"))
    if not e.get("kanmon_ok"):
        ng.append("ページの関所が未確認（本人の動画・関連4本・ページ完成）")
    lines = [x for x in text.split("\n") if x.strip()]
    if not lines or "http" not in lines[-1]:
        ng.append("URLが本文のいちばん最後に無い")
    if text in honbun_zumi:
        ng.append("同じ本文がもう予約に居る")
    if text in sumi_zumi:
        ng.append("同じ本文をもう出している")
    k = kotoba(e)
    if not k:
        ng.append("日本の曲か洋楽かが決まらない（lang を書いてください）")
    elif lang and k != lang:
        ng.append("枠は %s／この曲は %s" % (lang, k))
    return ng


# ───────────────────────── 出たものに気づいて押し出す

def deta_wo_oshidasu(tok, ima_posts):
    """前回の控えに居て、今の予約から消えているもの＝もう出たもの。"""
    furui = buffer_kura.yoyaku_yomu().get("yoyaku") or []
    ima_id = set(p.get("id") for p in ima_posts)
    deta = [y for y in furui if y.get("id") and y["id"] not in ima_id]
    for y in deta:
        url = ""
        try:
            url = x_shirase.x_link(gql, tok, y["id"])
        except Exception:
            url = ""
        try:
            x_shirase.hitotsu(y["id"], y.get("due") or "", y.get("text") or "", url)
        except Exception:
            pass
        kiroku({"result": "出たので押し出した", "post_id": y["id"],
                "due": y.get("due"), "x_url": url})
    return deta


# ───────────────────────── 本体

def channel(tok):
    """組織IDとチャンネルID ★一度見つけたら以後0叩き（buffer_kura に覚える）。"""
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
            if any(n in FORBID for n in ns):     # ★eggypop2014には絶対入れない
                continue
            if WANT in ns:
                buffer_kura.ch_kaku(o["id"], c["id"], WANT)
                return o["id"], c["id"]
    raise RuntimeError("チャンネル %s が見つからない" % WANT)


def miru():
    """1叩きもしないで、覚えてある控えだけで今の状態を出す。"""
    m = jload(MACHI, {})
    y = buffer_kura.yoyaku_yomu()
    print("Bufferの枠:", buffer_waku.riyuu())
    print("叩いた回数:", buffer_kura.riyuu())
    print("枠の割り当て:", "／".join("%s=%s" % s for s in slots(m)))
    print("予約（%s 時点の控え）: %d 本"
          % (y.get("at") or "-", len(y.get("yoyaku") or [])))
    retsu = m.get("machi") or []
    print("待機列: %d 本" % len(retsu))
    for i, e in enumerate(retsu, 1):
        print("  %2d %s %-4s chappie=%-4s 関所=%s %s"
              % (i, kotoba(e) or "??", e.get("from") or "?",
                 e.get("chappie") or "未", "◯" if e.get("kanmon_ok") else "✕",
                 (e.get("artist") or "") + " / " + (e.get("song") or "")))
    ho = ((m.get("kikai_ga_eranda_horyu") or {}).get("retsu") or [])
    print("機械が選んで保留にしてあるもの: %d 本（たまごさんのOKを待つ）" % len(ho))
    return 0


def main():
    if "--miru" in sys.argv:
        return miru()

    m = jload(MACHI, {})
    # ★1178番（2026-09-28）止め札。ChatGPTが先に10本入れた＝こちらが1本足すと二重投稿。
    import buffer_tomeru
    _t = buffer_tomeru.tomete()
    if _t:
        print(_t)
        kiroku({"result": "止め札で退いた", "riyuu": _t})
        return 0
    if not buffer_waku.ake():
        print(buffer_waku.riyuu())
        kiroku({"result": "枠切れで何もしない", "riyuu": buffer_waku.riyuu()})
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    org, chid = channel(tok)

    def yoyaku():
        e = ((gql(tok, Q_SCHED, {"o": org, "c": [chid]})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return [x["node"] for x in e]

    ima = yoyaku()

    # ★出たものに気づいて押し出す（たまごさんが見に行かなくていいように）
    deta = deta_wo_oshidasu(tok, ima)

    # 控えを更新（画面を描く係はこれを読むだけ＝0叩き）
    buffer_kura.yoyaku_kaku({
        "cap": CAP,
        "yoyaku": buffer_kura.naraberu(ima, jst),
        "slots": ["%s=%s" % s for s in slots(m)],
    })

    taken, honbun_zumi = set(), set()
    for p in ima:
        t = jst(p.get("dueAt") or "")
        if t:
            taken.add(t.strftime("%F %H:%M"))
        honbun_zumi.add((p.get("text") or "").strip())

    print("いま予約 %d 本／上限 %d 本（出た %d 本）" % (len(ima), CAP, len(deta)))
    if len(ima) >= CAP:
        print("★満杯。1本出て空くまで入れない。")
        kiroku({"result": "満杯で入れず", "yoyaku": len(ima), "cap": CAP})
        return 3

    waku, lang = tsugi_no_waku(m, taken)
    if not waku:
        print("空いている枠が見つからない")
        return 4
    print("次の空き枠: %s ＝ %s" % (waku.strftime("%F %H:%M"),
                                   "日本の曲" if lang == "ja" else "洋楽"))

    retsu = list(m.get("machi") or [])
    if not retsu:
        print("★待機列が空。たまごさんが投げ込み箱に入れたものが流れてきたら入る。")
        kiroku({"result": "待機列が空", "waku": waku.strftime("%F %H:%M"),
                "lang": lang})
        return 5

    sumi_zumi = set(str(x).strip() for x in (m.get("sumi") or []))
    erabi = hazure = None
    for i, e in enumerate(retsu):
        ng = kanmon(e, lang, honbun_zumi, sumi_zumi)
        if not ng:
            erabi = (i, e)
            break
        if hazure is None:
            hazure = (i, e, ng)
        print("  飛ばす %d本目 %s：%s"
              % (i + 1, e.get("song_key") or e.get("song") or "?", "／".join(ng)))
    if not erabi:
        print("★この枠（%s）に入れられるものが待機列に無い。1本も入れない。" % lang)
        kiroku({"result": "枠に合うものが無い", "lang": lang,
                "waku": waku.strftime("%F %H:%M"),
                "sentou_no_riyuu": (hazure[2] if hazure else [])})
        return 6

    i, e = erabi
    text = str(e.get("text") or "").strip()
    due = waku.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    res = gql(tok, M_CREATE, {"input": {
        "text": text, "channelId": chid, "assets": [],
        "needsApproval": False, "schedulingType": "automatic",
        "mode": "customScheduled", "dueAt": due}})
    cp = (res.get("data") or {}).get("createPost") or {}
    post = cp.get("post") or {}
    err = cp.get("message") or (str(res.get("errors"))[:300] if res.get("errors") else "")

    rec = {"song_key": e.get("song_key"), "lang": lang,
           "due_jst": waku.strftime("%F %H:%M"), "due_utc": due,
           "post_id": post.get("id"), "from": e.get("from"),
           "result": "入った" if post.get("id") else "入らなかった", "error": err}
    kiroku(rec)
    if not post.get("id"):
        print("★入らなかった:", err or res)
        return 8

    # ★入った。先に列から外して保存する（ここを後にすると二度入れの事故になる）
    m["machi"] = retsu[:i] + retsu[i + 1:]
    m.setdefault("sumi", []).append(text)
    jsave(MACHI, m)
    with io.open(DASHITA, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": rec["at"] if "at" in rec else now().strftime("%F %T"),
                            "song_key": rec["song_key"], "due_utc": due,
                            "post_id": post["id"], "where": "1170_hako",
                            "lang": lang, "head": text[:60]},
                           ensure_ascii=False) + "\n")

    # ★自己申告にしない。Bufferから取り直して確かめる
    ato = yoyaku()
    mita = [p for p in ato if p.get("id") == post["id"]]
    ok = bool(mita) and (mita[0].get("dueAt") == due) \
        and ((mita[0].get("text") or "").strip() == text) \
        and (mita[0].get("channelId") == chid)
    buffer_kura.yoyaku_kaku({"cap": CAP,
                             "yoyaku": buffer_kura.naraberu(ato, jst),
                             "slots": ["%s=%s" % s for s in slots(m)]})
    print("入った: %s（%s／%s）" % (rec["song_key"], waku.strftime("%F %H:%M"), lang))
    print("取り直して確認: %s（予約は %d 本になった）"
          % ("一致" if ok else "★ずれている", len(ato)))
    return 0 if ok else 9


def mabiku():
    if "--now" in sys.argv or "--miru" in sys.argv:
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
        io.open(STAMP, "w", encoding="utf-8").write(now().strftime("%F %T"))
    except Exception:
        pass


if __name__ == "__main__":
    if mabiku():
        sys.exit(0)
    try:
        rc = main()
    except Exception as _e:
        kiroku({"result": "落ちた", "error": str(_e)[:300]})
        print("落ちた:", _e)
        rc = 1
    han()          # ★失敗しても判子を押す。押さないと次の周回でまた叩く
    sys.exit(rc)
