#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/tana_sekisho.py ── 棚を変える仕事の関所（2026-10-22・たまごさん）

たまごさんの言葉（2026-10-22）：
  「棚に置くのは本当に慎重にしたい。これからも慎重にいきたい」。今ある棚の中身はそのまま（外さない）。

決まり（機械で守る）：
  棚に入れる・置く・移す・並べ替える仕事は、**たまごさんが「その日に」曲名と棚名を名指しした**
  ものだけ発車してよい。前日以前の言葉（判定日赤で積み直された古い依頼・ChatGPTのリサーチ結果・
  古いメモ）を根拠に棚を動かすのは禁止。

名指しの書き方（queue.json の票に1つ足す。Dispatch／投げ込み箱が書く）：
  "tanaMeishi": {"hi": "2026-10-22", "kyoku": "曲名", "tana": "棚の名前",
                 "kotoba": "たまごさんがその日に言った言葉そのまま"}
  hi が発車する日（JST）と同じで、kyoku・tana・kotoba が空でなければ通る。それ以外は保留(hold)。

使い方：
  python3 tools/tana_sekisho.py --mieru     # 保留にする候補を数えるだけ（書かない）
  python3 tools/tana_sekisho.py --horyu     # 発車待ちの棚の依頼を全部「保留」にし、一覧を作り直す
  python3 tools/tana_sekisho.py --ichiran   # 一覧（status/public/tana_horyu.json と share/check/tana-horyu.html）だけ作り直す
  python3 tools/tana_sekisho.py --self-test

組み込み先：
  - tools/auto_launcher.py の launch_one() の頭（全部の発車がここを通る）
  - joy-relief-station の prebuild scripts/patrol/check-tana-shitei.mjs（shitei の行は「言われた日＝足した日」でないと公開が止まる）
"""
import datetime
import html
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
ST = os.path.join(REPO, "status")
OUT_JSON = os.path.join(ST, "public", "tana_horyu.json")
OUT_HTML = os.path.join(REPO, "share", "check", "tana-horyu.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/tana-horyu.html"
HOLD_MARK = "棚の関所（2026-10-22）"
JST = datetime.timezone(datetime.timedelta(hours=9))

# 棚を動かす言い回し（棚の中身を足す・置く・移す・棚を新しく作る）
_TANA_UGOKASU = re.compile(
    r"棚[^。\n]{0,20}?(作っ|作る|作り|作成|つくっ|新設|入れ|いれ|入$|置い|置く|置き|置$|並べ|ならべ|追加|移動|移し|移す|"
    r"集め|複製|載せ|のせ|足し|足す|加え|配置|登録|出し|出す)"
    r"|(新しい|新規|新設の?)[^。\n]{0,6}棚"
    r"|名カバー(の棚)?[にへ]"
)
# 棚の字はあっても「棚を変える仕事」ではないもの（直す・調べる・数える・画面・決まりづくり）
_TANA_SOTO = re.compile(
    r"棚編集|棚卸|棚一覧|別人混入|倉庫|件数|数え|一覧に|一覧で|一覧表示|調査|報告書|検査|洗い出|"
    r"コピー|サムネ|導線|表示|バッジ|索引|再生|候補|企画書|案を|案のみ|ルート案|画面|"
    r"置いている|やめ|禁止|だけにして|しないで|しない[。、]?$|検品要人手|検品不合格|"
    r"いけない|被らない|注意して|モーダル|喋"
)


def _tana_text_ok(text):
    text = text.replace("棚卸し", "棚卸").replace("仕入れ", "仕込")
    return bool(_TANA_UGOKASU.search(text)) and not _TANA_SOTO.search(text)
_HANTEI = re.compile(r"^判定日赤｜|【判定日で赤になった案件】")


def today():
    return datetime.datetime.now(JST).strftime("%Y-%m-%d")


def _kotoba(it):
    """たまごさんの元の言葉に近い部分だけ（定型の注意書きで誤判定しないため）。"""
    title = str(it.get("title") or "")
    what = str(it.get("what") or "")
    head = what.split("\n【自動やり直し")[0].split("\n【来ない通知")[0][:1500]
    orig = str(it.get("original_text") or "")[:1500]
    return title, head, orig


def is_tana(it):
    """題名・判定日赤の元の言葉・original_text だけで見る（本文の定型・技術メモでは判定しない）。"""
    title, head, orig = _kotoba(it)
    m = re.search(r"【判定日で赤になった案件】(.*)", head)
    moto = m.group(1) if m else ""
    if _tana_text_ok(title) or _tana_text_ok(moto):
        return True
    # original_text はたまごさんの短い言葉のときだけ見る（長い依頼文・技術メモでは判定しない）
    return len(orig) <= 300 and _tana_text_ok(orig) and not _TANA_SOTO.search(title)


def is_hantei(it):
    title, head, _ = _kotoba(it)
    return bool(_HANTEI.search(title) or _HANTEI.search(head))


def meishi_today(it, hi=None):
    m = it.get("tanaMeishi")
    if not isinstance(m, dict):
        return False
    hi = hi or today()
    return (str(m.get("hi") or "")[:10] == hi
            and all(str(m.get(k) or "").strip() for k in ("kyoku", "tana", "kotoba")))


def gate(it, hi=None):
    """発車してよければ None。止めるなら保留の理由（holdNote）を返す。"""
    if it.get("test") or it.get("keepalive"):
        return None
    if not is_tana(it):
        return None
    if meishi_today(it, hi):
        return None
    return ("%s：棚を変える仕事は、たまごさんがその日に曲名と棚名を名指ししたものだけ発車します。"
            "前日以前の言葉では動かしません。一覧→ %s" % (HOLD_MARK, PAGE_URL))


# ---- 一覧の中身 ----
def _iwareta_hi(it):
    _, head, _ = _kotoba(it)
    m = re.search(r"【言われた日時】\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[^（\n]*)", head)
    if m:
        return m.group(1).strip()
    for k in ("firstSaid", "queuedAt", "createdAt", "addedAt", "saidAt"):
        if it.get(k):
            return str(it.get(k))[:16].replace("T", " ")
    m = re.search(r"(20[0-9]{2}-[0-9]{2}-[0-9]{2})", "\n".join([head, str(it.get("why") or "")]))
    if m:
        return m.group(1) + "ごろ"
    for k in ("startedAt", "restoredAt", "finishedAt"):
        if it.get(k):
            return str(it.get(k))[:10] + "より前"
    return ""


def _moto_kotoba(it):
    title, head, orig = _kotoba(it)
    m = re.search(r"【判定日で赤になった案件】(.*)", head)
    if m:
        return m.group(1).strip()[:400]
    if orig.strip() and len(orig) <= 300:
        return orig.strip()
    return re.sub(r"^(【[^】]*】)?判定日赤｜", "", title)[:400]


def _kyoku(text):
    names = re.findall(r"[「『]([^」』]{1,60})[」』]", text)
    names = [n for n in names if "棚" not in n][:4]
    return "／".join(names)


def _tana_mei(text):
    m = re.findall(r"([^\s、。「」『』（）()をにへはがと]{1,16}?)の棚", text)
    m = [x for x in m if x not in ("この", "その", "あの", "どの", "同じ", "別")]
    return "／".join(dict.fromkeys(m[:3]))


def kouho(items):
    out = []
    for it in items:
        if it.get("status") not in ("waiting", "stuck", "hold"):
            continue
        if not is_tana(it):
            continue
        if it.get("status") == "hold" and HOLD_MARK not in str(it.get("holdNote") or ""):
            continue  # 別の理由で保留中のものは触らない
        out.append(it)
    return out


def row(it):
    k = _moto_kotoba(it)
    return {"n": it.get("n"), "kyoku": _kyoku(k), "tana": _tana_mei(k), "kotoba": k,
            "hi": _iwareta_hi(it), "hantei": is_hantei(it),
            "title": str(it.get("title") or "")[:120], "maeStatus": it.get("tanaMaeStatus") or it.get("status")}


def write_ichiran(items):
    rows = [row(it) for it in items
            if it.get("status") == "hold" and HOLD_MARK in str(it.get("holdNote") or "")]
    rows.sort(key=lambda r: (str(r["hi"]), int(r["n"] or 0)))
    data = {"updatedAt": datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
            "kazu": len(rows), "hantei": sum(1 for r in rows if r["hantei"]),
            "kimari": "棚を変える仕事は、たまごさんがその日に曲名と棚名を名指ししたものだけ。今ある棚の中身はそのまま。",
            "url": PAGE_URL, "rows": rows}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    e = html.escape
    trs = "\n".join(
        "<tr><td class=n>%s</td><td>%s</td><td>%s</td><td class=k>%s</td><td class=d>%s%s</td></tr>" % (
            e(str(r["n"])), e(r["kyoku"]) or "<span class=m>（曲名の名指しなし）</span>",
            e(r["tana"]) or "<span class=m>（棚名なし）</span>", e(r["kotoba"]),
            e(r["hi"]) or "日付不明", "<br><span class=m>判定日赤</span>" if r["hantei"] else "")
        for r in rows)
    page = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>保留にした棚の依頼（%(kazu)d件）</title>
<style>
body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:0;padding:16px;color:#222;background:#fafaf7}
h1{font-size:20px;margin:0 0 6px}p{margin:4px 0 12px;font-size:14px;line-height:1.6}
table{border-collapse:collapse;width:100%%;font-size:13px;background:#fff}
th,td{border-bottom:1px solid #e5e5e0;padding:8px 6px;text-align:left;vertical-align:top}
th{background:#f0efe8;position:sticky;top:0}td.n{color:#888;white-space:nowrap}
td.k{line-height:1.5;max-width:520px}td.d{white-space:nowrap;font-size:12px}.m{color:#999;font-size:12px}
</style></head><body>
<h1>保留にした棚の依頼　%(kazu)d件</h1>
<p>2026-10-22 たまごさん「棚に置くのは本当に慎重にしたい」。棚に入れる・置く・移す依頼は全部止めています（今ある棚の中身はそのまま）。<br>
動かすのは、<b>たまごさんがその日に曲名と棚名を名指ししたもの</b>だけ。ここに並んだものは、名指しが無い限り発車しません。<br>
<span class=m>更新 %(updatedAt)s ／ うち判定日赤で積み直されたもの %(hantei)d件 ／ 古い順</span></p>
<table><thead><tr><th>番号</th><th>曲名</th><th>棚</th><th>元の言葉</th><th>言われた日</th></tr></thead>
<tbody>
%(trs)s
</tbody></table>
<p class=m>関所：tools/tana_sekisho.py（発車の頭）／joy-relief-station scripts/patrol/check-tana-shitei.mjs（公開の前）<br>
全AI向けの決まり：<a href="https://github.com/tamago2022/joy-relief-station/issues/1046">店主の指示メモ #1046</a>（全体像 <a href="https://github.com/tamago2022/joy-relief-station/issues/1040">#1040</a>）／<a href="https://tamago2022.github.io/tamago-shinchoku/">進捗表へ戻る</a></p>
</body></html>
""" % {"kazu": data["kazu"], "updatedAt": data["updatedAt"], "hantei": data["hantei"], "trs": trs}
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    return data


def horyu(dry=False):
    import queue_store
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        items = q.get("items") or []
        hi = today()
        tometa = []
        for it in kouho(items):
            if it.get("status") == "hold":
                continue
            note = gate(it, hi)
            if not note:
                continue
            tometa.append(it)
            if not dry:
                it["tanaMaeStatus"] = it.get("status")
                it["status"] = "hold"
                it["holdNote"] = note
                it["tanaHoryuAt"] = datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        if not dry and tometa:
            ok = queue_store.save_queue(q, snapshot=snap)
            if not ok:
                raise SystemExit("queue.json への書き込みが拒否されました")
    data = None if dry else write_ichiran(items)
    return tometa, data


def horyu_1ken(n, note):
    """発車の直前に止めた1件を、鍵を取り直して保留にする（auto_launcher から呼ぶ）。"""
    import queue_store
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        for it in q.get("items") or []:
            if it.get("n") == n and it.get("status") in ("waiting", "stuck"):
                it["tanaMaeStatus"] = it.get("status")
                it["status"] = "hold"
                it["holdNote"] = note
                it["tanaHoryuAt"] = datetime.datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                queue_store.save_queue(q, snapshot=snap)
                break
        try:
            write_ichiran(q.get("items") or [])
        except Exception:
            pass


def self_test():
    ng = 0
    hi = "2026-10-22"
    cases = [
        ({"title": "判定日赤｜この曲をアジアの風の棚に入れて", "status": "waiting"}, True),
        ({"title": "「Lemon」を名カバーの棚へ置く", "status": "waiting"}, True),
        ({"title": "棚卸し：未完了を全部", "status": "waiting"}, False),
        ({"title": "曲ページの関連曲を直す", "status": "waiting"}, False),
        ({"title": "棚の表示が崩れているのを直す", "status": "waiting"}, False),
        ({"title": "新しい棚を作って並べる", "what": "棚を新しく作る", "status": "waiting"}, True),
    ]
    for it, want in cases:
        if is_tana(it) != want:
            ng += 1
            print("NG is_tana", it["title"], want)
    base = {"title": "「bad」をアジアの風の棚に入れて", "status": "waiting"}
    if gate(base, hi) is None:
        ng += 1; print("NG 名指しなしが通った")
    old = dict(base, tanaMeishi={"hi": "2026-10-21", "kyoku": "bad", "tana": "アジアの風", "kotoba": "入れて"})
    if gate(old, hi) is None:
        ng += 1; print("NG 前日の名指しが通った")
    ok = dict(base, tanaMeishi={"hi": hi, "kyoku": "bad", "tana": "アジアの風", "kotoba": "入れて"})
    if gate(ok, hi) is not None:
        ng += 1; print("NG 当日の名指しが止まった")
    empty = dict(base, tanaMeishi={"hi": hi, "kyoku": "", "tana": "アジアの風", "kotoba": "入れて"})
    if gate(empty, hi) is None:
        ng += 1; print("NG 曲名なしが通った")
    if gate({"title": "曲ページを直す", "status": "waiting"}, hi) is not None:
        ng += 1; print("NG 棚以外が止まった")
    r = row({"n": 1, "title": "判定日赤｜「bad」をアジアの風の棚に入れて",
             "what": "【判定日で赤になった案件】「bad」をアジアの風の棚に入れて\n【言われた日時】2026-09-01(月) 10:00（1回）"})
    if r["kyoku"] != "bad" or r["tana"] != "アジアの風" or not r["hi"].startswith("2026-09-01"):
        ng += 1; print("NG 一覧の行", r)
    print("SELF_TEST", "PASS" if ng == 0 else "FAIL %d" % ng)
    return 0 if ng == 0 else 1


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        return self_test()
    if "--mieru" in a:
        tometa, _ = horyu(dry=True)
        import collections
        print("保留にする候補", len(tometa), "件（うち判定日赤", sum(1 for x in tometa if is_hantei(x)), "件）")
        print(collections.Counter(x.get("status") for x in tometa))
        for x in tometa[:40]:
            print(" #%s %s" % (x.get("n"), str(x.get("title"))[:70]))
        return 0
    if "--horyu" in a:
        tometa, data = horyu()
        print("保留にした", len(tometa), "件／一覧", data["kazu"], "件", data["url"])
        return 0
    if "--ichiran" in a:
        import queue_store
        data = write_ichiran(queue_store.load_queue().get("items") or [])
        print("一覧", data["kazu"], "件", data["url"])
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
