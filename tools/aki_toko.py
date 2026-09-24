#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【秋の投稿・1枚】朝と夜に「今日のドラフト」を1本だけ出す係。

たまごさんがやることは2つだけ。
  ・出てきた1本を見て「これでいい」か「これじゃない」か
  ・いいなら .command を1回押す（そのあとXの画面で「ポスト」を1回）

★文面はこちらが書く。たまごさんに書かせない。探させない。
★朝07:30＝日本の秋の名曲を英語で世界へ／夜21:00＝世界の秋の名曲を英語で日本へ。
  ドラフトはその30分前（07:00 / 20:30）に出す。
★在庫を使い切っても止まらない。使い切ったら次の周に入って出し続ける。
★AIを1回も呼ばない・外へ1回も出ない＝0円。新しい常駐も定期タスクも作らない（心臓に相乗り）。

出どころ:
  ・文面と曲の組み合わせ … status/aki_drafts.json（28本）
  ・曲ページのid … status/_1039/lib/coverGuide.ts を実測して取った（存在しないidは入れていない）
  ・280字の判定 … URLは23字固定というXの数え方で計算済み（x_len 欄）

使い方:
  python3 tools/aki_toko.py            … 心臓から。時刻が来ていなければ何もしない
  python3 tools/aki_toko.py --now      … 今すぐ1本出す（時刻を無視）
  python3 tools/aki_toko.py --show     … いま出ている1本を表示するだけ
  python3 tools/aki_toko.py --ok       … 「出した」と記録する（.command から呼ぶ）
  python3 tools/aki_toko.py --kore-ja-nai … 今の1本を捨てて次の1本に差し替える
  python3 tools/aki_toko.py --self-test
"""
from __future__ import annotations

import html
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")

DRAFTS = os.path.join(STATUS, "aki_drafts.json")
STATE = os.path.join(STATUS, "aki_toko.json")
PUB_JSON = os.path.join(PUBLIC, "aki_toko.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1074-aki-toko.html")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
LEDGER = os.path.join(STATUS, "aki_toko_daicho.jsonl")

JST = timezone(timedelta(hours=9))

# 出す時刻（ドラフトが出る時刻。投稿そのものは たまごさん が押した時）
ASA_FROM, ASA_TO = 7, 10      # 07:00〜09:59
YORU_FROM_H, YORU_FROM_M = 20, 30   # 20:30〜23:59


def _now():
    return datetime.now(JST)


def _load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _slot_now(now):
    """いま出す便。まだなら None。"""
    if ASA_FROM <= now.hour < ASA_TO:
        return "asa"
    if now.hour > YORU_FROM_H or (now.hour == YORU_FROM_H and now.minute >= YORU_FROM_M):
        return "yoru"
    return None


def _items():
    d = _load(DRAFTS, {}) or {}
    return list(d.get("items") or [])


def _state():
    return _load(STATE, {}) or {}


def _erabu(slot, st, items, skip_n=None):
    """その便の、まだ出していない一番若い1本。使い切ったら次の周に入る（止まらない）。"""
    kouho = [it for it in items if it.get("slot") == slot]
    if not kouho:
        return None, st
    sumi = set(st.get("sumi", {}).get(slot, []))
    if skip_n is not None:
        sumi.add(skip_n)
    nokori = [it for it in kouho if it["n"] not in sumi]
    if not nokori:
        # ★使い切った。次の周に入る。ここで止めない。
        st.setdefault("shuu", {})
        st["shuu"][slot] = int(st["shuu"].get(slot, 1)) + 1
        st.setdefault("sumi", {})[slot] = []
        nokori = kouho
    return nokori[0], st


def _ninnoko(slot, st, items):
    kouho = [it for it in items if it.get("slot") == slot]
    sumi = set(st.get("sumi", {}).get(slot, []))
    return len([it for it in kouho if it["n"] not in sumi])


def _outbox(text, title):
    try:
        os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _now().isoformat(), "from": "aki_toko",
                                "type": "aki_toko_draft", "title": title,
                                "message": text}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _daicho(rec):
    try:
        with io.open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 紙を1枚だけ書く
# ---------------------------------------------------------------------------
def _kaku(cur, st, items):
    nokori_asa = _ninnoko("asa", st, items)
    nokori_yoru = _ninnoko("yoru", st, items)
    pub = {
        "asOf": _now().strftime("%Y-%m-%d %H:%M:%S"),
        "ima": cur,
        "nokori": {"asa": nokori_asa, "yoru": nokori_yoru},
        "shuu": st.get("shuu", {"asa": 1, "yoru": 1}),
        "tsukaikata": "「これでいい」なら 秋の投稿_これを出す.command をダブルクリック。「これじゃない」なら 秋の投稿_これじゃない.command。",
    }
    _save(PUB_JSON, pub)

    slot_ja = "朝07:30（日本の曲を英語で世界へ）" if cur["slot"] == "asa" else "夜21:00（世界の曲を英語で日本へ）"
    h = []
    h.append("<!doctype html><html lang=\"ja\"><meta charset=\"utf-8\">")
    h.append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    h.append("<title>秋の投稿・今日の1本</title>")
    h.append("<style>body{font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;"
             "max-width:680px;margin:0 auto;padding:24px 18px 80px;line-height:1.8;color:#1b1b1b;background:#fbf9f5}"
             "h1{font-size:19px;margin:0 0 4px}.sub{color:#777;font-size:13px;margin:0 0 22px}"
             ".card{background:#fff;border:1px solid #e6e0d6;border-radius:12px;padding:20px;margin:0 0 18px}"
             ".slot{font-size:12px;color:#a07b3c;letter-spacing:.06em;margin:0 0 10px}"
             ".honbun{font-size:16px;white-space:pre-wrap;margin:0 0 14px}"
             ".meta{font-size:12px;color:#888}"
             "a{color:#0b6}.oshi{font-size:13px;color:#444;background:#fff6e5;border:1px solid #f0dfba;"
             "border-radius:10px;padding:14px 16px}</style>")
    h.append("<h1>秋の投稿 ― 今日の1本</h1>")
    h.append("<p class=\"sub\">%s 更新／たまごさんがやるのは「これでいい」か「これじゃない」かだけ</p>"
             % html.escape(_now().strftime("%m月%d日 %H:%M")))
    h.append("<div class=\"card\">")
    h.append("<p class=\"slot\">%s</p>" % html.escape(slot_ja))
    h.append("<p class=\"honbun\">%s</p>" % html.escape(cur["text"]))
    h.append("<p><a href=\"%s\">%s</a></p>" % (html.escape(cur["url"]), html.escape(cur["label"])))
    h.append("<p class=\"meta\">%s ／ 本文%d字・X換算%d字（280字以内）</p>"
             % (html.escape(" ".join(cur["tags"])), cur["honbun_len"], cur["x_len"]))
    h.append("</div>")
    h.append("<div class=\"oshi\">これでよければ <b>秋の投稿_これを出す.command</b> をダブルクリック。"
             "Xの投稿画面が文面入りで開くので「ポスト」を1回押すだけです。<br>"
             "これじゃないときは <b>秋の投稿_これじゃない.command</b>。すぐ次の1本に差し替わります。</div>")
    h.append("<p class=\"meta\">残りの在庫：朝%d本／夜%d本（%d周目・%d周目）。使い切っても止まりません。</p>"
             % (nokori_asa, nokori_yoru,
                int(st.get("shuu", {}).get("asa", 1)), int(st.get("shuu", {}).get("yoru", 1))))
    h.append("</html>")
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(h))


# ---------------------------------------------------------------------------
def dasu(force=False, skip=False):
    now = _now()
    items = _items()
    if not items:
        return 0
    st = _state()

    if skip:
        cur = st.get("ima")
        if not cur:
            return 0
        slot = cur["slot"]
        # 捨てた分は「出した」扱いにして二度と出さない
        st.setdefault("sumi", {}).setdefault(slot, [])
        if cur["n"] not in st["sumi"][slot]:
            st["sumi"][slot].append(cur["n"])
        tsugi, st = _erabu(slot, st, items)
        st["ima"] = tsugi
        st["imaAt"] = now.isoformat()
        _save(STATE, st)
        _kaku(tsugi, st, items)
        _daicho({"at": now.isoformat(), "how": "kore-ja-nai", "suteta": cur["n"], "tsugi": tsugi["n"]})
        print("差し替えました → #%d %s" % (tsugi["n"], tsugi["label"]))
        return 0

    slot = "asa" if force and now.hour < 12 else (_slot_now(now) or ("yoru" if force else None))
    if slot is None:
        return 0
    key = now.strftime("%F") + "/" + slot
    if st.get("lastKey") == key and not force:
        return 0

    cur, st = _erabu(slot, st, items)
    if not cur:
        return 0
    st["lastKey"] = key
    st["ima"] = cur
    st["imaAt"] = now.isoformat()
    _save(STATE, st)
    _kaku(cur, st, items)

    jikoku = "07:30" if slot == "asa" else "21:00"
    _outbox("【秋の投稿・%s】今日の1本ができています。%s ／ %s\n"
            "これでよければ 秋の投稿_これを出す.command を1回。これじゃないなら 秋の投稿_これじゃない.command。"
            % (jikoku, cur["label"], cur["url"]),
            "秋の投稿・今日の1本（%s）" % jikoku)
    _daicho({"at": now.isoformat(), "how": "draft", "n": cur["n"], "slot": slot, "label": cur["label"]})
    print("今日の1本 #%d %s" % (cur["n"], cur["label"]))
    return 0


def show():
    st = _state()
    cur = st.get("ima")
    if not cur:
        print("まだ今日の1本が出ていません。（朝07:00／夜20:30に出ます）")
        return 1
    print("── %s ──" % ("朝07:30 日本の曲を英語で世界へ" if cur["slot"] == "asa"
                        else "夜21:00 世界の曲を英語で日本へ"))
    print()
    print(cur["full"])
    print()
    print("（本文%d字・X換算%d字／280字以内）" % (cur["honbun_len"], cur["x_len"]))
    return 0


def ok():
    st = _state()
    cur = st.get("ima")
    if not cur:
        return 1
    slot = cur["slot"]
    st.setdefault("sumi", {}).setdefault(slot, [])
    if cur["n"] not in st["sumi"][slot]:
        st["sumi"][slot].append(cur["n"])
    st["lastOk"] = {"n": cur["n"], "at": _now().isoformat(), "label": cur["label"]}
    _save(STATE, st)
    _daicho({"at": _now().isoformat(), "how": "ok", "n": cur["n"], "label": cur["label"]})
    print("記録しました：#%d %s" % (cur["n"], cur["label"]))
    return 0


def self_test():
    items = _items()
    ng = []
    if len(items) < 14:
        ng.append("ドラフトが14本未満（%d本）" % len(items))
    for it in items:
        if it["x_len"] > 280:
            ng.append("#%d が280字超（%d）" % (it["n"], it["x_len"]))
        if len(it.get("tags") or []) != 3:
            ng.append("#%d のタグが3つでない" % it["n"])
        if not it.get("url", "").startswith("https://joy-relief-station.lovable.app/cover-guide?"):
            ng.append("#%d のリンクが曲ページでない" % it["n"])
        if not it["full"].rstrip().endswith(" ".join(it["tags"])):
            ng.append("#%d はリンクの下にタグが来ていない" % it["n"])
    print("見本試験 %d本中 不合格 %d件" % (len(items), len(ng)))
    for x in ng:
        print("  NG", x)
    return 1 if ng else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--show" in a:
        sys.exit(show())
    if "--ok" in a:
        sys.exit(ok())
    if "--kore-ja-nai" in a:
        sys.exit(dasu(skip=True))
    sys.exit(dasu(force="--now" in a))
