#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1059番【サブスクのお知らせ係】更新日の3日前・2日前・前日に、たまごさんへ1行だけ知らせる。

たまごさん（2026-09-24・原文）:
  「全てのサブスク、3日ぐらい前からアナウンスして。もう更新が迫ってるって。
    3日連続お知らせしてくださいね。」

★1回で終わらせない。**3日連続**（3日前・2日前・前日）。
★更新日が過ぎたら止める（同じ月のあいだに4回目を出さない）。
★知らせる文は**1行だけ**：「◯◯があと◯日で更新されます（◯月◯日・約◯円）」
★憶測の金額を1円も書かない。取れないものは「取れていない＋どの口が閉じているか」。
★ドル→円は**その日のレート**で計算し、出どころ（叩いたURL＋HTTPコード＋時刻）を添える。
  レートが取れない日は**円を書かない**（前の日のレートで書くと、数字が静かに古くなる）。
★課金・プラン変更・解約は押さない。止める入り口のURLを台帳に持つだけ。

置き場所:
  台帳     status/subsc.json          … 名前｜月額｜次の更新日｜支払い方法｜使ってる／使ってない
  お知らせ status/dispatch_outbox.jsonl … 1日1行だけ積む（omosa_mihari.py と同じ口）
  紙       status/public/subsc_shirase.json … お金の紙（tools/okane_ichimai.py）が読む
  レート   status/subsc_rate.jsonl    … その日のレートと、叩いた証拠

使い方:
  python3 tools/subsc_shirase.py            … 1日1回だけ本体が走る（心臓に相乗り）
  python3 tools/subsc_shirase.py --force
  python3 tools/subsc_shirase.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")

LEDGER = os.path.join(STATUS, "subsc.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
OUT_JSON = os.path.join(PUBLIC, "subsc_shirase.json")
SENT = os.path.join(STATUS, "subsc_shirase_sent.json")
RATE_LOG = os.path.join(STATUS, "subsc_rate.jsonl")
STAMP = os.path.join(STATUS, ".subsc_shirase_at")

JST = timezone(timedelta(hours=9))
SHIRASERU_HI = (3, 2, 1)          # ★3日前・2日前・前日。増やさない・減らさない
RATE_URL = "https://api.frankfurter.app/latest?from=USD&to=JPY"   # 鍵不要・0円


# ---------------------------------------------------------------------------
def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _hiduke(s):
    """'2026-09-30' → date。日付でないもの（「取れていない」等）は None。"""
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _tsugi_toshi(d):
    """1年進める（年払いのサブスク用。2026-09-24 Typeless Pro で必要になった）。
    2月29日だけは翌年に無いので28日に寄せる。"""
    try:
        return date(d.year + 1, d.month, d.day)
    except ValueError:
        return date(d.year + 1, d.month, 28)


def _tsugi_tsuki(d):
    """1か月進める。月末を越える日（31日など）はその月の末日に寄せる。"""
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in range(d.day, 27, -1):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, d.day)


# ---------------------------------------------------------------------------
def rate(today):
    """その日のUSD→円。★取れなければ取れないと書く。前の日の値で代用しない。"""
    try:
        import urllib.request
        t0 = datetime.now(JST).strftime("%H:%M")
        with urllib.request.urlopen(RATE_URL, timeout=12) as r:
            code = r.getcode()
            body = json.loads(r.read().decode("utf-8"))
        v = float((body.get("rates") or {}).get("JPY"))
        moto = "%s %d %s（レートの日付 %s）" % (RATE_URL, code, t0, body.get("date"))
        try:
            with io.open(RATE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": datetime.now(JST).isoformat(), "date": today,
                                    "usdYen": v, "moto": moto}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return v, moto
    except Exception as e:
        _ = e
        return None, "取れていない（その日のレートの口が開かなかった：%s）" % RATE_URL


def en(usd, v):
    """★レートが取れた日だけ円を出す。取れない日は円を書かない。"""
    if usd is None or v is None:
        return None
    return int(round(float(usd) * v))


# ---------------------------------------------------------------------------
def ichigyou(name, nokori, d, yen, rate_moto):
    """★知らせる文は1行だけ。"""
    if yen is not None:
        kane = "約%s円" % format(yen, ",")
    else:
        kane = "金額は取れていない"
    return "%sがあと%d日で更新されます（%d月%d日・%s）" % (name, nokori, d.month, d.day, kane)


def shiraseru(gyou, ids):
    try:
        with io.open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "1059-subsc-shirase",
                "type": "subsc_koushin_mae",
                "title": "サブスクの更新が近づいています",
                "message": "／".join(gyou),
                "ids": ids,
            }, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
def build(today=None, v=None, rate_moto=""):
    """台帳を読んで「あと何日か」を全部出す。★書き込みはしない（試験で使う）。"""
    t = today or datetime.now(JST).date()
    led = _load(LEDGER, {}) or {}
    rows, sugita = [], []
    for it in led.get("items", []):
        d = _hiduke(it.get("tsugi"))
        yen = it.get("yen") if it.get("yen") is not None else en(it.get("usd"), v)
        row = dict(id=it.get("id"), name=it.get("name"), tsugi=it.get("tsugi"),
                   nokori=None, usd=it.get("usd"), yen=yen, kata=it.get("kata"),
                   harai=it.get("harai"), tsukau=it.get("tsukau"),
                   tsukau_moto=it.get("tsukau_moto"), gaku_moto=it.get("gaku_moto"),
                   tsugi_moto=it.get("tsugi_moto"),
                   yameru=it.get("yameru"), kakunin=bool(it.get("kakunin")),
                   kurikaeshi=it.get("kurikaeshi"))
        if d:
            row["nokori"] = (d - t).days
            if row["nokori"] < 0:
                sugita.append(it.get("id"))
        rows.append(row)
    # ★使っていないものを上に出す＝止めれば減る金。同じ組の中では更新日が近い順。
    rows.sort(key=lambda r: (0 if (r["tsukau"] or "").startswith("使っていない") else 1,
                             999 if r["nokori"] is None else r["nokori"]))
    return rows, sugita


def sugita_wo_susumeru(today):
    """★更新日が過ぎたら止める。確かめた月額のものだけ次の月へ送る。
    確かめていないものは日付を作らない（憶測の日付を置かない）。"""
    led = _load(LEDGER, {}) or {}
    kaita = []
    for it in led.get("items", []):
        d = _hiduke(it.get("tsugi"))
        if not d or (d - today).days >= 0:
            continue
        if it.get("kurikaeshi") in ("monthly", "yearly") and it.get("kakunin"):
            susumu = _tsugi_tsuki if it.get("kurikaeshi") == "monthly" else _tsugi_toshi
            tan = "1か月" if it.get("kurikaeshi") == "monthly" else "1年"
            while (d - today).days < 0:
                d = susumu(d)
            it["tsugi"] = d.isoformat()
            it["tsugi_moto"] = (it.get("tsugi_moto", "") +
                                "／%s に%s進めた（tools/subsc_shirase.py）" % (today.isoformat(), tan))
        else:
            it["tsugi"] = ("取れていない（前の更新日 %s を過ぎた。次の日付は確かめていない）"
                           % d.isoformat())
        kaita.append(it.get("id"))
    if kaita:
        led["updatedAt"] = today.isoformat()
        _save(LEDGER, led)
    return kaita


# ---------------------------------------------------------------------------
def run(force=False, today=None):
    """today は試験のときだけ渡す（「その日が来たらどうなるか」を機械で確かめるため）。"""
    now = datetime.now(JST)
    today = today or now.date()
    if not force:
        try:
            if io.open(STAMP, encoding="utf-8").read().strip() == today.isoformat():
                return None
        except Exception:
            pass

    susumeta = sugita_wo_susumeru(today)
    v, rate_moto = rate(today.isoformat())
    rows, _ = build(today, v, rate_moto)

    sent = _load(SENT, {}) or {}
    gyou, ids = [], []
    for r in rows:
        if r["nokori"] in SHIRASERU_HI:
            kagi = "%s:%s:%d" % (r["id"], r["tsugi"], r["nokori"])
            if sent.get(kagi):
                continue                      # 同じ日に2回言わない
            d = _hiduke(r["tsugi"])
            gyou.append(ichigyou(r["name"], r["nokori"], d, r["yen"], rate_moto))
            ids.append(r["id"])
            sent[kagi] = today.isoformat()
    # 古い印は90日で捨てる（台帳が太り続けない）
    kiru = (today - timedelta(days=90)).isoformat()
    sent = {k: x for k, x in sent.items() if x >= kiru}

    okutta = bool(gyou) and shiraseru(gyou, ids)
    if okutta:
        _save(SENT, sent)

    d = dict(generatedAt=now.strftime("%Y-%m-%d %H:%M:%S"),
             today=today.isoformat(), usdYen=v, rateMoto=rate_moto,
             rows=rows, shirase=gyou, susumeta=susumeta)
    _save(OUT_JSON, d)
    io.open(STAMP, "w", encoding="utf-8").write(today.isoformat())
    return d


# ---------------------------------------------------------------------------
def self_test(verbose=True):
    ng = []
    led = _load(LEDGER, {}) or {}
    if len(led.get("items", [])) < 8:
        ng.append("台帳の行が足りない（全部のサブスクが入っていない）")

    # ① 3日前・2日前・前日の3日連続で必ず出る。4日前と当日は出ない
    t = date(2026, 9, 27)
    kari = [dict(id="x", name="ためし", tsugi="2026-09-30", kurikaeshi="monthly",
                 usd=100.0, yen=None, kata="月額", harai="", tsukau="使っている",
                 yameru="", kakunin=True)]
    def nokori(today):
        d = _hiduke("2026-09-30")
        return (d - today).days
    deta = [nokori(date(2026, 9, x)) in SHIRASERU_HI for x in (26, 27, 28, 29, 30)]
    if deta != [False, True, True, True, False]:
        ng.append("3日連続になっていない（%s）" % deta)

    # ② 更新日を過ぎたら止まる
    if nokori(date(2026, 10, 1)) in SHIRASERU_HI:
        ng.append("更新日を過ぎても知らせが止まらない")

    # ③ レートが取れない日は円を書かない
    if en(100.0, None) is not None:
        ng.append("レートが取れないのに円を書いている")
    if en(100.0, 150.0) != 15000:
        ng.append("円の計算が合わない")

    # ④ 知らせる文は1行・決められた形
    g = ichigyou("Claude", 3, date(2026, 9, 30), 17638, "")
    if g != "Claudeがあと3日で更新されます（9月30日・約17,638円）":
        ng.append("知らせる文の形が違う：%s" % g)
    if "\n" in g:
        ng.append("知らせる文が1行になっていない")
    g2 = ichigyou("Suno", 1, date(2026, 10, 13), None, "")
    if "金額は取れていない" not in g2:
        ng.append("金額が取れないのに空欄で出している")

    # ⑤ 使っていないものが上に来る
    rows, _ = build(t, 150.0, "")
    if rows and not (rows[0]["tsukau"] or "").startswith("使っていない"):
        ng.append("使っていないものが上に来ていない")

    # ⑥ 月送りが月末をはみ出さない
    if _tsugi_tsuki(date(2026, 1, 31)) != date(2026, 2, 28):
        ng.append("月送りが月末をはみ出す")

    # ⑦ 台帳に「押してしまう」ものが混ざっていない
    for it in led.get("items", []):
        if not isinstance(it.get("yameru"), str):
            ng.append("止める入り口の欄が無い：%s" % it.get("id"))

    if verbose:
        print("自己試験 %s（%d件）" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng)))
        for x in ng:
            print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    got = run(force="--force" in sys.argv)
    if got is None:
        print("今日はもう見た（--force で今すぐ）")
    else:
        print("見た %s ／ レート %s ／ 知らせ %d件" %
              (got["today"], got["usdYen"] if got["usdYen"] else "取れていない",
               len(got["shirase"])))
        for g in got["shirase"]:
            print("  -", g)
