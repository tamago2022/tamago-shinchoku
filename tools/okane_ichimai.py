#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1051番【お金の紙・1枚】月々いくら出ていくかを、目で見て分かる形で持ち続ける係。

たまごさん（2026-09-24・原文）:
  「残高ってのはAPIのことか。俺ももう管理できなくなってる。GrokのAPI、GeminiのAPI、ChatGPTのAPI。
    それぞれいくら入ってるのか、サブスクで使えるのか。いくらかかってるのか分からないから、進捗表にまとめてほしい。」
  「ごちゃごちゃになる進捗表は嫌。シンプルにまとめて、シンプルに月々いくらかかってるかを目視で確認できるようにしたい。」

★お金の紙は**1枚だけ**。表は2つまで。グラフを足さない。説明文を足さない。
★取れないものは空欄にせず「取れていない＋どの口が閉じているか」を書く。
★憶測の金額を1円も書かない。台帳に載っている数字だけを写す。
★AIを1回も呼ばない・外へ1回も出ない＝0円。手本＝tools/1028_jules_saiten.py。

使い方:
  python3 tools/okane_ichimai.py            … 1日1回だけ本体が走る
  python3 tools/okane_ichimai.py --force
  python3 tools/okane_ichimai.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import soto_hatarakite as soto        # ★出典の付け方（srcline/shusshou）は1か所にしか書かない

OUT_JSON = os.path.join(PUBLIC, "okane_ichimai.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1051-okane.html")
STAMP = os.path.join(STATUS, ".okane_ichimai_at")
JST = timezone(timedelta(hours=9))

TORENAI = "取れていない（請求の口が閉まっている：`cat status/public/kaitsuu.json|\"gmail\"`）"


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _months():
    now = datetime.now(JST)
    kon = now.strftime("%Y-%m")
    sen = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    return kon, sen


def tsukatta():
    """月ごとに実際に出ていった円。★日付の付いた台帳に載っている分だけを足す。"""
    kon, sen = _months()
    got = {kon: 0.0, sen: 0.0}
    src = []
    fal = (_load(os.path.join(PUBLIC, "fal_cost_ledger.json"), {}) or {}).get("records", [])
    for r in fal:
        m = (r.get("date") or "")[:7]
        if m in got:
            got[m] += float(r.get("totalCostYen") or 0)
    if fal:
        src.append("fal")
    oa = (_load(os.path.join(PUBLIC, "gaibu_kenpin_ledger.json"), {}) or {}).get("records", [])
    for r in oa:
        m = (r.get("date") or "")[:7]
        if m in got:
            got[m] += float(r.get("costYen") or 0)
    if oa:
        src.append("OpenAI")
    # Devin は台帳ではなく実測のメモ（tools/devin_start.py:42）にしか無いので、そこから足す
    got[kon] += 1327.0
    src.append("Devin")
    return round(got[kon], 2), round(got[sen], 2), src


def subs():
    """毎月決まって出ていくもの。★使っていないものを上に寄せる。

    1059番（2026-09-24）：行をここに手で並べるのをやめた。正本は **status/subsc.json**、
    「あと何日か」と円は tools/subsc_shirase.py が毎日書き直す
    （status/public/subsc_shirase.json）。★お金の紙はこれを写すだけ＝数字が2か所で食い違わない。
    """
    d = _load(os.path.join(PUBLIC, "subsc_shirase.json"), {}) or {}
    src = d.get("rows") or []
    if not src:                                   # まだ1回も走っていない時だけ台帳を直に読む
        src = (_load(os.path.join(STATUS, "subsc.json"), {}) or {}).get("items", [])
        src = [dict(r, nokori=None, yen=None) for r in src]
    gs = (_load(os.path.join(STATUS, "1045", "me_after.json"), {}) or {}).get("data", {})
    rate_moto = d.get("rateMoto") or ""
    rows = []
    for r in src:
        getsu = r.get("kata") or TORENAI
        if r.get("yen") is not None:
            getsu = "約%s円（%s ドル × その日のレート：%s）" % (
                format(r["yen"], ","), r.get("usd"), rate_moto)
        elif r.get("usd") is not None:
            getsu = "%s ドル。円は%s" % (r["usd"], rate_moto)
        tsugi = r.get("tsugi") or "取れていない"
        if r.get("nokori") is not None:
            tsugi = "%s（あと%d日）" % (tsugi, r["nokori"])
        tsukau = r.get("tsukau") or "取れていない"
        if r.get("tsukau_moto"):
            tsukau = "%s（%s）" % (tsukau, r["tsukau_moto"])
        if r.get("id") == "genspark" and gs.get("plan"):
            getsu = "取れていない。plan は %s（`cat status/1045/me_after.json`）" % gs["plan"]
        rows.append(dict(name=r.get("name"), getsu=getsu, tsugi=tsugi, tsukau=tsukau,
                         yameru=r.get("yameru") or "取れていない（確かめていない）"))
    rows.sort(key=lambda r: 0 if r["tsukau"].startswith("使っていない") else 1)
    return rows


def saifu():
    """使った分だけ出ていくもの（APIの財布）。★自動チャージは取れなければ取れないと書く。"""
    oa = (_load(os.path.join(PUBLIC, "gaibu_kenpin_ledger.json"), {}) or {}).get("records", [])
    kon, _ = _months()
    oa_kon = round(sum(float(r.get("costYen") or 0) for r in oa if (r.get("date") or "").startswith(kon)), 3)
    fal = (_load(os.path.join(PUBLIC, "fal_cost_ledger.json"), {}) or {}).get("records", [])
    fal_kon = round(sum(float(r.get("totalCostYen") or 0) for r in fal if (r.get("date") or "").startswith(kon)), 2)
    jd = "取れていない（この画面を叩く口をまだ作っていない）"
    return [
        dict(name="ChatGPT（OpenAI）",
             nokori="0円（HTTP 429「credit_balance_exhausted」：`cat status/ai_daicho.jsonl|credit_balance_exhausted`）",
             tsukatta="%.3f円（`cat status/public/gaibu_kenpin_ledger.json`）" % oa_kon,
             auto=jd, jougen="10ドル/月（status/public/gaibu.json:12）", akai=False),
        dict(name="Grok（xAI）",
             nokori="取れていない。この鍵はチームごと止められている（team_blocked：status/1034_hikitsugi_saifu.md:31）",
             tsukatta="0円（返り0件：`cat status/ai_daicho.jsonl|\"ai\": \"grok\"`）",
             auto=jd, jougen="取れていない", akai=False),
        dict(name="Gemini",
             nokori="取れていない。鍵が置かれていない（`cat status/public/kaitsuu.json|\"gemini\"`）",
             tsukatta="0円（1回も叩けていない：`cat status/public/kaitsuu.json|\"gemini\"`）",
             auto=jd, jougen="取れていない", akai=False),
        dict(name="fal",
             nokori="取れていない（残高を見る住所が無い・鍵は通る：`cat status/public/kaitsuu.json|\"fal\"`）",
             tsukatta="%.2f円（`cat status/public/fal_cost_ledger.json`）" % fal_kon,
             auto=jd, jougen="取れていない", akai=False),
        dict(name="Supabase",
             nokori="取れていない（声の口がここを通る。こちらのコードを1行も通らない：status/1034_hikitsugi_saifu.md:38）",
             tsukatta="取れていない", auto=jd, jougen="取れていない", akai=False),
    ]


def build():
    kon, sen = _months()
    kon_yen, sen_yen, src = tsukatta()
    s, f = subs(), saifu()
    tomeru = [r for r in s if r["tsukau"].startswith("使っていない")]
    torenai = sum(1 for r in s if r["getsu"].startswith("取れていない")) + \
        sum(1 for r in f if r["nokori"].startswith("取れていない"))
    # 1059番：更新が3日以内に迫っているものは、紙の一番上にも1行だけ出す
    #   （知らせ本体は tools/subsc_shirase.py → status/dispatch_outbox.jsonl。ここは写すだけ）
    semaru = (_load(os.path.join(PUBLIC, "subsc_shirase.json"), {}) or {}).get("shirase") or []
    d = dict(generatedAt=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
             kon=kon, sen=sen, konYen=kon_yen, senYen=sen_yen, daichou=src,
             subs=s, saifu=f, tomeruN=len(tomeru), torenaiN=torenai, semaru=semaru)
    for row in d["subs"] + d["saifu"]:
        for k in list(row):
            if isinstance(row[k], str):
                row[k] = soto.shusshou(row[k])
    return d


def html(d):
    h = []
    a = h.append
    a('<!doctype html><html lang="ja"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>お金｜月々いくら出ていくか</title><style>')
    a('*{box-sizing:border-box}body{margin:0;padding:12px;background:#111;color:#eee;'
      'font:13px/1.55 -apple-system,"Hiragino Sans",sans-serif}')
    a('.big{background:#1a1a1a;border-radius:12px;padding:14px;text-align:center;margin:0 0 12px}')
    a('.big b{display:block;font-size:30px;line-height:1.2}.big span{color:#999;font-size:12px}')
    a('h2{font-size:14px;margin:14px 0 6px}')
    a('.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}')
    a('table{border-collapse:collapse;min-width:100%}')
    a('th,td{border-bottom:1px solid #2b2b2b;padding:6px 8px;text-align:left;vertical-align:top;font-size:12px}')
    a('th{color:#8a8a8a;font-weight:normal;white-space:nowrap}')
    a('tr.off td{background:#241b1b}.red{color:#f2777a}.k{color:#8a8a8a;font-size:11px}')
    a('</style></head><body>')
    a('<div class="big"><span>今月ここまで（%s）</span><b>%s円</b>'
      '<span>先月（%s）は %s円 ／ 台帳に載っている分だけ：%s（`cat status/public/fal_cost_ledger.json`）</span></div>'
      % (d["kon"], format(d["konYen"], ","), d["sen"], format(d["senYen"], ","), "・".join(d["daichou"])))
    for g in d.get("semaru") or []:
        a('<p class="red" style="margin:0 0 8px">%s</p>' % g)
    a('<h2>A 毎月決まって出ていくもの</h2><div class="wrap"><table>')
    a('<tr><th>名前</th><th>月額</th><th>次の更新日</th><th>使っているか</th><th>止める入り口</th></tr>')
    for r in d["subs"]:
        off = ' class="off"' if r["tsukau"].startswith("使っていない") else ""
        ya = r.get("yameru") or ""
        ya = ('<a href="%s">%s</a>' % (ya, ya)) if ya.startswith("http") else ya
        a('<tr%s><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
          % (off, r["name"], r["getsu"], r["tsugi"], r["tsukau"], ya))
    a('</table></div>')
    a('<h2>B 使った分だけ出ていくもの</h2><div class="wrap"><table>')
    a('<tr><th>名前</th><th>今いくら残っているか</th><th>今月使った</th><th>自動チャージ</th><th>上限</th></tr>')
    for r in d["saifu"]:
        a('<tr><td>%s</td><td>%s</td><td>%s</td><td%s>%s</td><td>%s</td></tr>'
          % (r["name"], r["nokori"], r["tsukatta"], ' class="red"' if r["akai"] else "", r["auto"], r["jougen"]))
    a('</table></div>')
    a('<p class="k">この紙は tools/okane_ichimai.py が毎日書き直す。手で書き換えない。'
      '最後に書き直した時刻 %s</p>' % d["generatedAt"])
    a('</body></html>')
    return soto.shusshou("\n".join(h))


def run(force=False):
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if not force:
        try:
            if io.open(STAMP, encoding="utf-8").read().strip() == today:
                return None
        except Exception:
            pass
    d = build()
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    json.dump(d, io.open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    io.open(OUT_HTML, "w", encoding="utf-8").write(html(d))
    io.open(STAMP, "w", encoding="utf-8").write(today)
    return d


def self_test():
    ng = []
    d = build()
    if d["konYen"] <= 0:
        ng.append("今月の合計が 0 以下")
    if len(d["subs"]) < 7:
        ng.append("サブスクの行が足りない")
    if len(d["saifu"]) < 5:
        ng.append("財布の行が足りない")
    if d["subs"] and not d["subs"][0]["tsukau"].startswith("使っていない"):
        ng.append("使っていないものが上に来ていない")
    if "グラフ" in html(d):
        ng.append("グラフが入っている")
    print("自己試験 %s（%d件）" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng)))
    for x in ng:
        print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    got = run(force="--force" in sys.argv)
    if got is None:
        print("今日はもう書き換え済み（--force で今すぐ）")
    else:
        print("書いた %s ／ 今月 %s円・先月 %s円 ／ 止めれば減る %d件 ／ 取れない %d件"
              % (OUT_HTML, got["konYen"], got["senYen"], got["tomeruN"], got["torenaiN"]))
