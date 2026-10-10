#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1051番【お金の紙・1枚】→ 2026-10-08 作り直し（今月いくら使っているか、証拠つきで一目で）。

たまごさん（2026-09-24）:
  「シンプルに月々いくらかかってるかを目視で確認できるようにしたい」
たまごさん（2026-10-08）:
  「お金周りは全部管理して。サブスクもBufferも含めて全部。今月いくら使ってるか一目で見られる表にして」
  「fal は最優先で監視対象に。1日$3超えや、1回で$2超えの注文があったら進捗表で赤く出す」

★お金の紙は1枚だけ（share/check/1051-okane.html）。新しいページを増やさない。
★数字の出どころは3つだけ：
    status/okane/kakin.json    … カードの利用通知・領収書メール（Gmail）から写した実額＝正本
    status/public/fal_kanshi.json … fal見張り（tools/fal_kanshi.py：API＋画面で見た数字）
    為替（次回の見込みのドル→円だけ。frankfurter.dev の終値・日付つき・1日1回）
★今月の合計は「カードから実際に引かれた円」だけを足す。見込みは別の行に分けて書き、合計に混ぜない。
★分からないものは「不明」と書く。0円と書かない。
★課金・解約はこちらから押さない。「解約候補」の印を付けるだけ。
★氏名・住所・メールアドレスは書かない（公開リポ）。

使い方:
  python3 tools/okane_ichimai.py            … 毎回書き直してよい（心臓から1時間に1回）
  python3 tools/okane_ichimai.py --self-test
"""
from __future__ import annotations

import html as H
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
KAKIN = os.path.join(STATUS, "okane", "kakin.json")
KAWASE = os.path.join(STATUS, "okane", "kawase.json")
FAL = os.path.join(PUBLIC, "fal_kanshi.json")
OUT_JSON = os.path.join(PUBLIC, "okane_ichimai.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1051-okane.html")
JST = timezone(timedelta(hours=9))
SERVICE_IGAI = ("kaimono", "idou", "charge")   # サービス以外（買い物・移動・チャージ）


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def e(s):
    return H.escape(str(s if s is not None else ""))


def yen(n):
    return "{:,}円".format(int(round(n)))


def dollar(x):
    return ("-$%.2f" % -x) if x < 0 else ("$%.2f" % x)


def kawase(today):
    """1ドル何円か。1日1回だけ外へ出る。取れなければ前回の値を日付つきで使う。"""
    k = _load(KAWASE, {}) or {}
    if k.get("kakunin") == today and k.get("jpy"):
        return k
    try:
        with urllib.request.urlopen("https://api.frankfurter.dev/v1/latest?from=USD&to=JPY", timeout=15) as r:
            j = json.loads(r.read().decode("utf-8"))
        k = dict(jpy=float(j["rates"]["JPY"]), date=j.get("date"), kakunin=today,
                 moto="frankfurter.dev（欧州中央銀行の参照レート・%s）" % j.get("date"))
        os.makedirs(os.path.dirname(KAWASE), exist_ok=True)
        json.dump(k, io.open(KAWASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass
    return k if k.get("jpy") else None


def build():
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    kon = now.strftime("%Y-%m")
    sen = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    k = _load(KAKIN, {}) or {}
    harai = k.get("harai") or []
    svcs = k.get("services") or []
    fal = _load(FAL, {}) or {}
    kw = kawase(today)

    def tsuki(m, service=True):
        return [h for h in harai if h["d"][:7] == m and ((h["svc"] not in SERVICE_IGAI) == service)]

    kon_s, sen_s = tsuki(kon), tsuki(sen)
    kon_igai = tsuki(kon, service=False)
    gokei = sum(h["yen"] for h in kon_s)
    gokei_sen = sum(h["yen"] for h in sen_s)
    card_all = gokei + sum(h["yen"] for h in kon_igai)

    rows = []
    mikomi_kon = []      # 今月中にまだ引かれる予定（見込み）
    for s in svcs:
        hs = [h for h in kon_s if h["svc"] == s["id"]]
        prev = sorted([h for h in harai if h["svc"] == s["id"] and h["d"][:7] < kon], key=lambda h: h["d"])
        y = sum(h["yen"] for h in hs)
        usd = sum(h.get("usd") or 0 for h in hs)
        if hs:
            kingaku = yen(y) + (" ／ $%.2f" % usd if usd else "")
            if len(hs) > 1:
                kingaku += "（%d回）" % len(hs)
        elif s.get("muryo"):
            kingaku = "0円（無料プラン）"
        elif s.get("shurui") == "不明" and not prev:
            kingaku = "不明"
        else:
            kingaku = "0円（今月はまだ）"
        # 次回の見込み
        t = s.get("tsugi") or "不明"
        mk = None
        if s.get("tsugi_yen"):
            mk = (s["tsugi_yen"], "%s" % yen(s["tsugi_yen"]))
        elif s.get("tsugi_usd"):
            if kw:
                mk = (s["tsugi_usd"] * kw["jpy"], "$%.2f（約%s・1ドル%.2f円 %s）" % (
                    s["tsugi_usd"], yen(s["tsugi_usd"] * kw["jpy"]), kw["jpy"], kw["date"]))
            else:
                mk = (None, "$%.2f（円は為替が取れず不明）" % s["tsugi_usd"])
        elif prev and t[:4].isdigit():
            last = prev[-1]
            mk = (last["yen"], "前回 %s と同じなら %s（前回の額・確定ではない）" % (last["d"][5:].replace("-", "/"), yen(last["yen"])))
        if s.get("owari"):
            mk = None
            t = t + "で終了（更新しない指示）"
        tsugi_txt = t + ("：" + mk[1] if mk else "")
        if t[:7] == kon and t >= today and mk and mk[0]:
            mikomi_kon.append(dict(name=s["name"], d=t, yen=mk[0], kouho=bool(s.get("kouho"))))
        # 証拠
        sh = []
        for h in hs + prev[-1:]:
            sh.append('<a href="%s">%s %s %s</a>' % (e(h["url"]), e(h["d"][5:].replace("-", "/")), e(h["mise"]), e(yen(h["yen"]))))
            if h.get("hosoku"):
                sh.append('<span class="k">%s</span>' % e(h["hosoku"]))
        if s.get("tsugi_moto"):
            sh.append('<span class="k">次回の根拠：%s</span>' % e(s["tsugi_moto"]))
        rows.append(dict(id=s["id"], name=s["name"], shurui=s.get("shurui"), kubun=s.get("kubun"),
                         kingaku=kingaku, yenKon=y, tsugi=tsugi_txt, tsugiDate=t, tsukau=s.get("tsukau") or "不明",
                         shouko="<br>".join(sh) or '<span class="k">請求の記録が見つからない</span>',
                         kouho=bool(s.get("kouho")), riyuu=s.get("riyuu") or "", riyuu2=s.get("riyuu2") or "",
                         yameru=s.get("yameru") or ""))
    rows.sort(key=lambda r: (0 if r["kubun"] == "AI・工場" else 1, -r["yenKon"], r["name"]))

    # 赤：7日以内に更新が来る解約候補
    lim = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    semaru = [r for r in rows if r["kouho"] and r["tsugiDate"][:4].isdigit() and today <= r["tsugiDate"] <= lim]

    fal_row = next((r for r in rows if r["id"] == "fal"), None)
    if fal_row:
        z = (fal.get("zandaka") or {})
        zz = z.get("api") or z.get("mita")
        add = []
        if zz:
            add.append("残高 %s（%s・%s）" % (dollar(zz["usd"]), zz["at"], "API" if z.get("api") else "画面で見た値"))
        for c in fal.get("charge") or []:
            if not c.get("hanei"):
                add.append("$%.0fチャージ：反映待ち" % c["usd"])
        hd = (fal.get("hibetsu") or [])[:1]
        if hd and hd[0]["date"] == today:
            add.append("今日 $%.2f" % hd[0]["usd"])
        if add:
            fal_row["kingaku"] += '<br><span class="k">%s</span>' % e("・".join(add))

    d = dict(generatedAt=now.strftime("%Y-%m-%d %H:%M"), kon=kon, sen=sen, today=today,
             gokei=gokei, gokeiSen=gokei_sen, cardAll=card_all, kensuu=len(kon_s),
             mikomi=sorted(mikomi_kon, key=lambda x: x["d"]),
             mikomiYen=sum(x["yen"] for x in mikomi_kon),
             rows=rows, semaru=[dict(name=r["name"], d=r["tsugiDate"], riyuu=r["riyuu"]) for r in semaru],
             igai=sorted(kon_igai, key=lambda h: h["d"]), kawase=kw, card=k.get("card"),
             gmail=k.get("gmail_kakunin"), fal=fal,
             kouhoN=sum(1 for r in rows if r["kouho"]))
    return d


CSS = """*{box-sizing:border-box}body{margin:0;padding:12px 12px 40px;background:#111;color:#eee;
font:14px/1.6 -apple-system,"Hiragino Sans",sans-serif}a{color:#8ab4f8}
.big{background:#1b1b1b;border-radius:14px;padding:16px 14px;text-align:center;margin:0 0 10px}
.big .l{color:#aaa;font-size:13px}.big b{display:block;font-size:38px;line-height:1.2;margin:4px 0;font-variant-numeric:tabular-nums}
.sub{display:flex;gap:8px;margin:0 0 10px}.sub div{flex:1;background:#1b1b1b;border-radius:10px;padding:8px;text-align:center;font-size:12px;color:#aaa}
.sub b{display:block;color:#eee;font-size:17px;font-variant-numeric:tabular-nums}
.aka{background:#b3261e;color:#fff;border-radius:10px;padding:10px 12px;margin:0 0 8px;font-weight:700;line-height:1.5}
h2{font-size:15px;margin:18px 0 6px}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:10px;border:1px solid #2a2a2a}
table{border-collapse:collapse;min-width:900px;width:100%}
th,td{border-bottom:1px solid #2a2a2a;padding:8px;text-align:left;vertical-align:top;font-size:13px}
th{color:#999;font-weight:normal;white-space:nowrap;background:#161616}
td:first-child,th:first-child{position:sticky;left:0;background:#141414;min-width:120px;max-width:140px}
td.n{white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:700}
.tag{display:inline-block;background:#b3261e;color:#fff;border-radius:6px;padding:0 6px;font-size:11px;margin-top:3px}
.k{color:#999;font-size:12px}.sec td{background:#202020;color:#bbb;font-weight:700}
details{background:#181818;border-radius:10px;padding:8px 10px;margin:8px 0}summary{cursor:pointer;color:#ccc}
ul{margin:6px 0;padding-left:18px}li{margin:2px 0}"""


def html(d):
    h = []
    a = h.append
    a('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="robots" content="noindex,nofollow"><title>お金｜今月いくら</title><style>%s</style></head><body>' % CSS)
    a('<p class="k" style="margin:0 0 6px"><a href="../../index.html">← 進捗表</a></p>')
    a('<div class="big"><div class="l">今月（%s）のサービス代・カードから実際に引かれた額</div><b id="gokei">%s</b>'
      '<div class="l">%d件・%s 1日〜%s／出どころ：カードの利用通知と領収書メール</div></div>'
      % (e(d["kon"].replace("-", "年") + "月"), e(yen(d["gokei"])), d["kensuu"], e(d["kon"][5:].lstrip("0") + "月"),
         e(d["today"][8:].lstrip("0") + "日")))
    a('<div class="sub"><div>このあと今月中に来る予定<b>約%s</b>（見込み・合計に入れていない）</div>'
      '<div>先月（%s）のサービス代<b>%s</b></div><div>カード利用ぜんぶ（買い物・移動込み）<b>%s</b></div></div>'
      % (e(yen(d["mikomiYen"])), e(d["sen"][5:].lstrip("0") + "月"), e(yen(d["gokeiSen"])), e(yen(d["cardAll"]))))
    for a_ in (d["fal"].get("aka") or []):
        a('<div class="aka">fal：%s</div>' % e(a_))
    for s in d["semaru"]:
        a('<div class="aka">解約候補：%s が %s に更新されます。%s</div>' % (e(s["name"]), e(s["d"][5:].replace("-", "/")), e(s["riyuu"])))

    a('<h2>サービスごと（%d件・解約候補 %d件）</h2>' % (len(d["rows"]), d["kouhoN"]))
    a('<div class="wrap"><table><tr><th>サービス</th><th>種類</th><th>今月の金額（円・ドル）</th>'
      '<th>更新日・次回請求日</th><th>何に使っているか</th><th>証拠（押すと元のメール）</th></tr>')
    cur = None
    for r in d["rows"]:
        if r["kubun"] != cur:
            cur = r["kubun"]
            a('<tr class="sec"><td>%s</td><td colspan="5"></td></tr>' % e(cur))
        nm = e(r["name"])
        if r["kouho"]:
            nm += '<br><span class="tag">解約候補</span>'
        tsu = e(r["tsukau"])
        if r["kouho"] and r["riyuu"]:
            tsu += '<br><span class="k" style="color:#f2a3a0">%s</span>' % e(r["riyuu"])
        if r["riyuu2"]:
            tsu += '<br><span class="k" style="color:#f2a3a0">%s</span>' % e(r["riyuu2"])
        if r["yameru"]:
            tsu += '<br><a class="k" href="%s">止める・確かめる入口</a>' % e(r["yameru"])
        a('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
          % (nm, e(r["shurui"]), r["kingaku"], e(r["tsugi"]), tsu, r["shouko"]))
    a('</table></div>')
    a('<p class="k">表は横にスクロールできます。</p>')

    if d["mikomi"]:
        a('<details open><summary>今月このあと来る予定（%d件・約%s）</summary><ul>' % (len(d["mikomi"]), e(yen(d["mikomiYen"]))))
        for m in d["mikomi"]:
            a('<li>%s %s 約%s%s</li>' % (e(m["d"][5:].replace("-", "/")), e(m["name"]), e(yen(m["yen"])),
                                        ' <span class="tag">解約候補</span>' if m["kouho"] else ""))
        a('</ul></details>')

    f = d["fal"]
    a('<h2>fal（最優先で見張り中・毎時）</h2><details open><summary>残高・日ごと・モデル別・誰が発注したか</summary>')
    z = f.get("zandaka") or {}
    if z.get("api"):
        a('<p>残高 <b>%s</b>（%s・fal API）</p>' % (dollar(z["api"]["usd"]), e(z["api"]["at"])))
    elif z.get("mita"):
        a('<p>残高 <b>%s</b>（%s・%s）</p>' % (dollar(z["mita"]["usd"]), e(z["mita"]["at"]), e(z["mita"]["moto"])))
    for c in f.get("charge") or []:
        a('<p class="k">チャージ $%.2f（%s）：%s</p>' % (c["usd"], e(c["at"]), e(c["moto"])))
    sj = f.get("sanjuunichi")
    if sj:
        a('<p class="k">過去30日 $%.2f（1日平均 $%.2f）・%s</p>' % (sj["usd"], sj["nichiheikin_usd"], e(sj["moto"])))
    a('<ul>')
    for dd in (f.get("hibetsu") or [])[:7]:
        ms = "／".join("%s $%.2f" % (m["model"], m["usd"]) for m in dd["models"])
        a('<li%s>%s 合計 $%.2f：%s</li>' % (' style="color:#f2777a"' if dd["aka"] else "", e(dd["date"]), dd["usd"], e(ms)))
    a('</ul><p class="k">出どころ：%s</p>' % e(f.get("hibetsuMoto") or "不明"))
    for x in f.get("hacchuu") or []:
        a('<p>%s の $%.2f（%s）を発注したのは：<b>%s</b><br><span class="k">%s<br>次：%s</span></p>'
          % (e(x["date"]), x["usd"], e(x["models"]), e(x["dare"]), e(x["shirabeta"]), e(x["tsugi"])))
    if f.get("torenai"):
        a('<p class="k">APIで取れていない部分：</p><ul class="k">%s</ul>' % "".join("<li>%s</li>" % e(t) for t in f["torenai"]))
    a('<p class="k">赤くする基準：1日 $%.0f 超／1回 $%.0f 超（進捗表の一番上にも赤で出る）。最後に見た時刻 %s</p>'
      % (f.get("kijun", {}).get("ichinichi_usd", 3), f.get("kijun", {}).get("ikkai_usd", 2), e(f.get("generatedAt") or "まだ走っていない")))
    a('</details>')

    if d["igai"]:
        a('<details><summary>サービス以外のカード利用（今月・%d件・%s）</summary><ul>'
          % (len(d["igai"]), e(yen(sum(x["yen"] for x in d["igai"])))))
        for x in d["igai"]:
            a('<li><a href="%s">%s %s %s</a></li>' % (e(x["url"]), e(x["d"][5:].replace("-", "/")), e(x["mise"]), e(yen(x["yen"]))))
        a('</ul><p class="k">Amazonの中に Kindle Unlimited・Audible が入っているかは、通知だけでは分からない（不明）。</p></details>')

    kw = d["kawase"]
    a('<p class="k">円は「カードから実際に引かれた円」をそのまま使っている（換算していない）。'
      'ドルの見込みだけ1ドル=%s円（%s）で換算。<br>カード：%s<br>'
      'Gmailから台帳（status/okane/kakin.json）へ最後に写した時刻：%s。この紙は tools/okane_ichimai.py が毎時書き直す（最後 %s）。</p>'
      % (e("%.2f" % kw["jpy"] if kw else "不明"), e(kw["moto"] if kw else "為替が取れていない"), e(d["card"] or "不明"),
         e(d["gmail"] or "不明"), e(d["generatedAt"])))
    a('</body></html>')
    return "\n".join(h)


def run():
    d = build()
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    slim = {k: v for k, v in d.items() if k not in ("fal",)}
    json.dump(slim, io.open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmp = OUT_HTML + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(html(d))
    os.replace(tmp, OUT_HTML)
    return d


def self_test():
    ng = []
    d = build()
    k = _load(KAKIN, {}) or {}
    kon = d["kon"]
    want = sum(h["yen"] for h in k.get("harai", []) if h["d"][:7] == kon and h["svc"] not in SERVICE_IGAI)
    if d["gokei"] != want:
        ng.append("今月の合計が台帳の足し算と合わない")
    page = html(d)
    if "@" in page.replace("&#x27;", ""):
        ng.append("メールアドレスらしき文字が紙に出ている")
    for bad in ("宗像", "上鷺宮"):
        if bad in page:
            ng.append("個人情報（%s）が紙に出ている" % bad)
    ids = {s["id"] for s in k.get("services", [])}
    for h in k.get("harai", []):
        if h["svc"] not in ids and h["svc"] not in SERVICE_IGAI:
            ng.append("台帳の支払い %s %s の行き先が無い" % (h["d"], h["svc"]))
    print("自己試験 %s（%d件）今月 %s" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng), yen(d["gokei"])))
    for x in ng:
        print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    got = run()
    print("書いた %s ／ 今月 %s（%d件）・先月 %s ／ 解約候補 %d件"
          % (OUT_HTML, yen(got["gokei"]), got["kensuu"], yen(got["gokeiSen"]), got["kouhoN"]))
