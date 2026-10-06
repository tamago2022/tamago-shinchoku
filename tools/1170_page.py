#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1170番【いつでも見える1枚】自動投稿の箱の管制盤。

たまごさんの言葉（2026-09-27・原文）:
  「いつでも俺が確認できるようにしたい。」
  「10件まで予約投稿できる枠を作る／1個投稿されたら次の1個が繰り上がって、
    途切れなく回る」

★Bufferを1回も叩かない。buffer_kura が覚えている控えを読むだけ（＝0叩き）。
  だから何回描き直しても枠を1回も使わない。
  控えがいつのものかを画面に必ず出す。取り直したフリをしない。

出す: status/public/1170_hako.html（暗い配色・スマホ幅）
     status/public/1170_hako.json

使い方: python3 tools/1170_page.py
"""
import datetime
import html as H
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import buffer_kura   # noqa: E402
import buffer_waku   # noqa: E402

JST = datetime.timezone(datetime.timedelta(hours=9))
PUB = os.path.join(REPO, "status", "public")
OUT_HTML = os.path.join(PUB, "1170_hako.html")
OUT_JSON = os.path.join(PUB, "1170_hako.json")
MACHI = os.path.join(REPO, "status", "buffer_queue", "machi.json")
KENPIN = os.path.join(REPO, "status", "public", "1168_kenpin.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")
SHIRASE_ZUMI = os.path.join(REPO, "status", "1170", ".douga_nashi_shirase.json")
TORIKESHI = os.path.join(REPO, "status", "buffer_queue", "torikeshi.json")
CH_MACHI = os.path.join(REPO, "status", "1170", "chappie_machi.json")
NAGEKOMI = os.path.join(REPO, "status", "nagekomi.jsonl")
DAICHO = os.path.join(REPO, "status", "1170", "nagashita.jsonl")
CAP = 10

DARE = {"nagekomi": "たまごさん（投げ込み箱）",
        "nushi": "たまごさん",
        "1166": "機械（旧・自動選曲）",
        "1166_machi_tsumu": "機械（旧・自動選曲）",
        "1170_hako": "箱"}


def now():
    return datetime.datetime.now(JST)


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def jlload(p):
    out = []
    try:
        for ln in io.open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def nihongo_ga_aru(s):
    for c in s or "":
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) \
           or (0x3400 <= o <= 0x4DBF) or (0xFF66 <= o <= 0xFF9D):
            return True
    return False


def kotoba(e):
    v = str((e or {}).get("lang") or "").strip().lower()
    if v in ("ja", "jp", "邦", "邦楽", "日本"):
        return "ja"
    if v in ("en", "洋", "洋楽", "海外"):
        return "en"
    na = "%s %s" % ((e or {}).get("artist") or "", (e or {}).get("song") or "")
    if na.strip():
        return "ja" if nihongo_ga_aru(na) else "en"
    for ln in str((e or {}).get("text") or "").split("\n"):
        if "—" in ln or "–" in ln:
            return "ja" if nihongo_ga_aru(ln) else "en"
    return ""


def slots(m):
    d = (m or {}).get("slots_lang") or {"09:00": "ja", "21:00": "en"}
    return sorted(d.items())


def midashi(t):
    for ln in (t or "").split("\n"):
        if "—" in ln or "–" in ln:
            return ln.strip()
    return (t or "").split("\n")[0][:70]


def tsugi_no_waku(m, taken):
    ss = slots(m)
    day = now().date()
    for _ in range(90):
        for (hhmm, lang) in ss:
            hh, mi = [int(x) for x in hhmm.split(":")]
            c = datetime.datetime(day.year, day.month, day.day, hh, mi, tzinfo=JST)
            if c <= now() + datetime.timedelta(minutes=10):
                continue
            if c.strftime("%F %H:%M") not in taken:
                return c.strftime("%F %H:%M"), lang
        day += datetime.timedelta(days=1)
    return "", ""


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))


def link_hyou():
    """★たまごさん「ページのリンクも全部確認できるようにして」
    1168の検品（1本ずつ実際にページを開いて数えたもの）をそのまま読む＝0叩き。
    """
    k = jload(KENPIN, {})
    rows = []
    for x in k.get("rows") or []:
        rows.append({
            "n": x.get("n"), "due": x.get("due") or "",
            "midashi": x.get("midashi") or x.get("title") or "",
            "honbun_midashi": (x.get("text") or "").split("\n")[0][:70],
            "url": x.get("url") or "",
            "http": x.get("http"),
            "url_owari": bool(x.get("url_owari")),
            "douga": bool(x.get("main_ok")),
            "douga_url": x.get("main") or "",
            "douga_size": x.get("main_size") or "",
            "kanren": int(x.get("kanren") or 0),
            "kanren_ok": bool(x.get("kanren_ok")),
            "ng": x.get("ng") or [],
        })
    return {"at": k.get("at") or "", "itsu": k.get("itsu") or "", "rows": rows}


def douga_nashi_wo_shiraseru(rows):
    """★動画が無いものは待たずに赤で知らせる（同じものは1回だけ）。"""
    nashi = [r for r in rows if r["url"] and not r["douga"]]
    if not nashi:
        return nashi
    zumi = set(jload(SHIRASE_ZUMI, {}).get("url") or [])
    atarashii = [r for r in nashi if r["url"] not in zumi]
    if atarashii:
        honbun = "\n".join(
            "・%s %s\n  %s" % (r["due"], r["honbun_midashi"], r["url"])
            for r in atarashii)
        try:
            os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
            with io.open(OUTBOX, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                    "n": "1170-douga-nashi-%s" % now().strftime("%m%d%H%M"),
                    "type": "douga_nashi",
                    "title": "★動画が貼られていない予約が %d 本あります" % len(atarashii),
                    "message": honbun + "\n\n一覧: status/public/1170_hako.html",
                    "urls": [r["url"] for r in atarashii][:5],
                    "ok": False}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        jsave(SHIRASE_ZUMI, {"url": sorted(zumi | set(r["url"] for r in nashi)),
                             "at": now().strftime("%F %T")})
    return nashi


def atsumeru():
    m = jload(MACHI, {})
    y = buffer_kura.yoyaku_yomu()
    yoyaku = y.get("yoyaku") or []
    taken = set(p.get("due") for p in yoyaku if p.get("due"))
    waku, lang = tsugi_no_waku(m, taken)

    retsu = m.get("machi") or []
    # ★次に繰り上がるのはどれか＝次の枠の言語に合う先頭の1本
    tsugi = None
    for e in retsu:
        if kotoba(e) == lang and e.get("chappie") == "ok" and e.get("kanmon_ok"):
            tsugi = e
            break

    nk = jlload(NAGEKOMI)
    sumi = set(x.get("id") for x in jlload(DAICHO))
    mi_shori = [r for r in nk
                if (r.get("nageta") or "nushi") == "nushi" and r.get("id") not in sumi]

    lh = link_hyou()
    nashi = douga_nashi_wo_shiraseru(lh["rows"])

    return {
        "at": now().strftime("%F %H:%M"),
        "link_hyou": lh,
        "douga_nashi": nashi,
        "hikae_itsu": y.get("at") or "（まだ取り直していない）",
        "waku_riyuu": buffer_waku.riyuu(),
        "tataita": buffer_kura.riyuu(),
        "cap": CAP,
        "slots": [{"jikan": k, "lang": v,
                   "nan": "日本の曲" if v == "ja" else "洋楽"} for k, v in slots(m)],
        "yoyaku": [{"due": p.get("due") or "?", "midashi": midashi(p.get("text")),
                    "lang": "ja" if nihongo_ga_aru(midashi(p.get("text"))) else "en"}
                   for p in sorted(yoyaku, key=lambda x: x.get("due") or "")],
        "tsugi_no_waku": waku, "tsugi_no_lang": lang,
        "tsugi": ({"midashi": midashi(tsugi.get("text")),
                   "dare": DARE.get(tsugi.get("from"), tsugi.get("from") or "不明")}
                  if tsugi else None),
        "machi": [{"midashi": midashi(e.get("text")) or (e.get("song") or ""),
                   "lang": kotoba(e),
                   "dare": DARE.get(e.get("from"), e.get("from") or "不明"),
                   "chappie": e.get("chappie") or "未",
                   "kanmon": bool(e.get("kanmon_ok"))} for e in retsu],
        "chappie_machi": [{"nani": (e.get("youtube_title") or e.get("url") or "")[:90],
                           "url": e.get("url") or "",
                           "chappie": e.get("chappie") or "未",
                           "riyuu": e.get("chappie_riyuu") or e.get("kanmon_riyuu") or ""}
                          for e in (jload(CH_MACHI, {}).get("retsu") or [])],
        "nagekomi_mishori": [{"nani": (r.get("titleRaw") or r.get("title")
                                       or r.get("url") or "")[:90],
                              "url": r.get("url") or "", "at": r.get("at") or ""}
                             for r in mi_shori],
        "torikeshi": jload(TORIKESHI, {}).get("machi") or [],
        "torikeshi_done": jload(TORIKESHI, {}).get("done") or [],
        "horyu": [{"midashi": midashi(e.get("text")), "lang": kotoba(e)}
                  for e in ((m.get("kikai_ga_eranda_horyu") or {}).get("retsu") or [])],
    }


def html(d):
    e = H.escape

    def li_yoyaku():
        if not d["yoyaku"]:
            return '<li class="none">控えが空です</li>'
        return "".join(
            '<li><b>%s</b><i class="%s">%s</i><span>%s</span></li>'
            % (e(x["due"]), x["lang"], "邦" if x["lang"] == "ja" else "洋",
               e(x["midashi"])) for x in d["yoyaku"])

    def aka_douga():
        """★動画が無いものを一番上に赤で出す。"""
        if not d["douga_nashi"]:
            return ('<div class="midori">動画が貼られていない予約は'
                    'ありません（%s 時点でページを1本ずつ開いて数えたもの）</div>'
                    % e(d["link_hyou"]["at"] or "-"))
        li = "".join(
            '<li><b>%s</b><span>%s</span>'
            '<a href="%s" target="_blank" rel="noopener">ページを開く</a></li>'
            % (e(x["due"]), e(x["honbun_midashi"]), e(x["url"]))
            for x in d["douga_nashi"])
        return ('<div class="aka-box"><h3>★動画が貼られていない予約が %d 本</h3>'
                '<p>このままでは出せません。ページに本人の動画を貼るまで止まります。</p>'
                '<ol>%s</ol></div>' % (len(d["douga_nashi"]), li))

    def li_link():
        rows = d["link_hyou"]["rows"]
        if not rows:
            return ('<li class="none">まだ検品していません。'
                    'python3 tools/1168_kenpin_hyou.py を1回走らせると埋まります。</li>')
        out = []
        for x in rows:
            dou = ('<a href="%s" target="_blank" rel="noopener">動画◯ %s</a>'
                   % (e(x["douga_url"]), e(x["douga_size"]))) if x["douga"] \
                else '<u class="ng">動画✕ なし</u>'
            out.append(
                '<li class="%s"><b>%s</b>'
                '<span><a href="%s" target="_blank" rel="noopener">%s</a></span>'
                '%s<u class="%s">HTTP %s</u><u class="%s">関連%d</u>'
                '<u class="%s">URL末尾%s</u></li>'
                % ("warui" if not x["douga"] else "",
                   e(x["due"]), e(x["url"]),
                   e(x["honbun_midashi"] or x["url"]), dou,
                   "ok" if x["http"] == 200 else "ng", e(str(x["http"])),
                   "ok" if x["kanren_ok"] else "ng", x["kanren"],
                   "ok" if x["url_owari"] else "ng",
                   "◯" if x["url_owari"] else "✕"))
        return "".join(out)

    def li_machi():
        if not d["machi"]:
            return ('<li class="none">空です。たまごさんが投げ込み箱に入れたものが'
                    'チャッピーを通るとここに並びます。</li>')
        return "".join(
            '<li><i class="%s">%s</i><span>%s</span>'
            '<em>%s</em><u class="%s">チャッピー%s</u><u class="%s">関所%s</u></li>'
            % (x["lang"] or "x", {"ja": "邦", "en": "洋"}.get(x["lang"], "？"),
               e(x["midashi"]), e(x["dare"]),
               "ok" if x["chappie"] == "ok" else "ng",
               "◯" if x["chappie"] == "ok" else "✕",
               "ok" if x["kanmon"] else "ng", "◯" if x["kanmon"] else "✕")
            for x in d["machi"])

    def li_ch():
        if not d["chappie_machi"]:
            return '<li class="none">ありません</li>'
        return "".join(
            '<li><span>%s</span><u class="%s">%s</u>%s</li>'
            % (e(x["nani"]), "ok" if x["chappie"] == "ok" else "ng",
               e(x["chappie"]),
               ('<em class="ng">%s</em>' % e(x["riyuu"])) if x["riyuu"] else "")
            for x in d["chappie_machi"])

    def li_nk():
        if not d["nagekomi_mishori"]:
            return '<li class="none">ありません（全部流し終わっています）</li>'
        return "".join('<li><b>%s</b><span>%s</span></li>'
                       % (e(x["at"]), e(x["nani"])) for x in d["nagekomi_mishori"])

    def li_tk():
        if not d["torikeshi"]:
            return '<li class="none">ありません</li>'
        out = []
        for x in d["torikeshi"]:
            k = ""
            if x.get("kouho"):
                k = ('<em class="ng">★候補が%d本あって決まらない。'
                     'どれを消すか番号で教えてください。</em><ol class="kouho">%s</ol>'
                     % (len(x["kouho"]),
                        "".join("<li>%s %s</li>" % (e(c.get("due") or ""),
                                                    e(c.get("midashi") or ""))
                                for c in x["kouho"])))
            out.append('<li><span>「%s」を予約から外す</span><em>%s</em>%s</li>'
                       % (e(x.get("sagasu") or ""), e(x.get("naze") or ""), k))
        return "".join(out)

    def li_done():
        if not d["torikeshi_done"]:
            return '<li class="none">まだありません</li>'
        return "".join('<li><span>「%s」</span><em>%s</em></li>'
                       % (e(x.get("sagasu") or ""), e(x.get("kekka") or ""))
                       for x in d["torikeshi_done"])

    def li_horyu():
        if not d["horyu"]:
            return '<li class="none">ありません</li>'
        return "".join('<li><i class="%s">%s</i><span>%s</span></li>'
                       % (x["lang"] or "x",
                          {"ja": "邦", "en": "洋"}.get(x["lang"], "？"),
                          e(x["midashi"])) for x in d["horyu"])

    waku = "".join('<div class="slot"><b>%s</b><span>%s</span></div>'
                   % (e(s["jikan"]), e(s["nan"])) for s in d["slots"])
    tsugi = ('<b>%s</b>（%s）に <span>%s</span> が繰り上がります<em>選んだのは %s</em>'
             % (e(d["tsugi_no_waku"] or "?"),
                "日本の曲" if d["tsugi_no_lang"] == "ja" else "洋楽",
                e(d["tsugi"]["midashi"]), e(d["tsugi"]["dare"]))) \
        if d["tsugi"] else \
        ('<b>%s</b>（%s）の枠に入れられるものが、待機列にまだありません。'
         '<em>投げ込み箱に入れてチャッピーを通ると、ここに出ます。</em>'
         % (e(d["tsugi_no_waku"] or "?"),
            "日本の曲" if d["tsugi_no_lang"] == "ja" else "洋楽"))

    return """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>自動投稿の箱｜1170</title><style>
*{box-sizing:border-box}
body{margin:0;background:#0d0f12;color:#e8e6e1;
 font-family:"Hiragino Sans","Yu Gothic",system-ui,sans-serif;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:.03em}
h2{font-size:14px;color:#8b949e;letter-spacing:.06em;margin:30px 0 10px;
 border-top:1px solid #23272e;padding-top:15px}
.at{color:#7d8590;font-size:13px;margin:0 0 4px}
.waku{font-size:12.5px;color:#e3b341;background:#1c1a12;border:1px solid #3d3417;
 border-radius:10px;padding:9px 12px;margin:10px 0 0}
.slots{display:flex;gap:10px;margin:16px 0 0;flex-wrap:wrap}
.slot{flex:1 1 150px;background:#15181d;border:1px solid #23272e;border-radius:12px;
 padding:12px 14px}
.slot b{display:block;font-size:22px;font-variant-numeric:tabular-nums}
.slot span{font-size:13px;color:#8b949e}
.tsugi{background:#101a14;border:1px solid #1f3d2c;border-radius:12px;
 padding:13px 15px;margin:14px 0 0;font-size:14px}
.tsugi b{font-variant-numeric:tabular-nums;font-size:16px}
.tsugi span{color:#7ee2b8}
.tsugi em{display:block;font-style:normal;font-size:12px;color:#7d8590;margin-top:4px}
ol,ul{list-style:none;margin:0;padding:0}
li{display:flex;flex-wrap:wrap;gap:3px 9px;padding:9px 0;align-items:baseline;
 border-bottom:1px solid #1d2126;font-size:13.5px}
li b{flex:0 0 108px;font-variant-numeric:tabular-nums;font-size:12.5px;color:#8b949e}
li span{flex:1 1 210px}
li em{flex:0 0 auto;font-style:normal;font-size:11.5px;color:#7d8590}
li u{flex:0 0 auto;text-decoration:none;font-size:11px;border-radius:5px;
 padding:1px 6px;border:1px solid #2c3138}
li i{flex:0 0 auto;font-style:normal;font-size:11px;border-radius:5px;padding:1px 6px}
i.ja{background:#1a1420;color:#d9a9ff;border:1px solid #3a2a48}
i.en{background:#101a20;color:#8fd3ff;border:1px solid #23414f}
i.x{background:#1a1a1a;color:#8b949e;border:1px solid #2c3138}
li.none{display:block;color:#7d8590;border:0;font-size:13px}
u.ok{color:#5ddba0}u.ng{color:#ff7b72}
em.ng{color:#ff9d96;flex:1 1 100%%}
ol.kouho{flex:1 1 100%%;margin:6px 0 0;padding-left:0}
ol.kouho li{border:0;padding:2px 0;color:#ff9d96;font-size:12.5px}
.aka{background:#1a1415;border:1px solid #8c3b33;border-radius:12px;padding:4px 14px}
.aka-box{background:#1f1214;border:1px solid #b5453a;border-radius:12px;
 padding:14px 16px;margin:18px 0 0}
.aka-box h3{margin:0 0 4px;font-size:16px;color:#ff9d96}
.aka-box p{margin:0 0 6px;font-size:13px;color:#e8b8b3}
.aka-box li{border-bottom:1px solid #3a2124}
.midori{background:#101a14;border:1px solid #1f3d2c;border-radius:12px;
 padding:11px 15px;margin:18px 0 0;font-size:13px;color:#7ee2b8}
ol.link li.warui{background:#1f1214;border-left:3px solid #b5453a;padding-left:9px}
ol.link li b{flex:0 0 108px}
.dim{color:#7d8590}
a{color:#79b8ff;word-break:break-all}
.n{font-size:22px;font-variant-numeric:tabular-nums}
.sum{background:#15181d;border:1px solid #23272e;border-radius:12px;
 padding:14px 16px;margin:16px 0 0;font-size:14px}
@media(max-width:420px){.wrap{padding:20px 12px 70px}li b{flex:0 0 96px}}
</style></head><body><div class="wrap">
<h1>自動投稿の箱</h1>
<p class="at">%(at)s 作成・@oasisjoyrelief<br>
予約の中身は <b>%(hikae)s</b> にBufferから取り直した控えです。
この画面はBufferを1回も叩きません（枠を使わないため）。</p>
<p class="waku">%(waku_riyuu)s<br>%(tataita)s</p>

<div class="slots">%(slots)s</div>
<div class="tsugi">%(tsugi)s</div>

<div class="sum">予約 <b class="n">%(nyoyaku)d</b> / %(cap)d 本
待機列 <b class="n">%(nmachi)d</b> 本
チャッピー待ち <b class="n">%(nch)d</b> 本
投げ込み箱の未処理 <b class="n">%(nnk)d</b> 本<br>
<span class="dim">1本出たら1本繰り上がります。満杯のあいだは入れません。</span></div>

%(aka)s

<h2>ページのリンク（全部押せます）／動画の有無</h2>
<p class="at">%(link_itsu)s<br>
ページを1本ずつ実際に開いて数えた結果です。推定していません。</p>
<ol class="link">%(link)s</ol>

<h2>いまBufferに入っている予約</h2>
<ol>%(yoyaku)s</ol>

<h2>待機列（次に繰り上がる順）</h2>
<ol>%(machi)s</ol>

<h2>チャッピー待ち（コピーと関連曲を整えてもらっている）</h2>
<ol>%(ch)s</ol>

<h2>投げ込み箱の未処理</h2>
<ol>%(nk)s</ol>

<h2 class="aka">取り消し待ち（枠が戻ったら自動で実行）</h2>
<ol>%(tk)s</ol>

<h2>取り消し済み</h2>
<ol>%(done)s</ol>

<h2>機械が選んで保留にしてあるもの（出しません）</h2>
<p class="at">たまごさんの指示で機械の自動選曲は止めました。捨てていません。
「これは出していい」と言われたものだけ待機列へ戻します。</p>
<ol>%(horyu)s</ol>

<h2>この画面の見かた</h2>
<ul>
<li>朝は日本の曲、夜は洋楽。曲データから自動で振り分けます。</li>
<li>「チャッピー◯」と「関所◯」の両方が付いていないものは予約に流れません。</li>
<li>1本ずつの検品（本人の動画・関連の本数・リンクのHTTP）は
 <a href="./1168_kenpin.html">予約済みの中身（1168）</a>で見られます。</li>
<li>出た投稿とXのリンクは <a href="./1170_deta.html">出た投稿</a>。</li>
<li>Bufferの予約欄：<a href="https://publish.buffer.com/all-channels/queue">publish.buffer.com</a></li>
</ul>
</div></body></html>""" % {
        "at": e(d["at"]), "hikae": e(d["hikae_itsu"]),
        "waku_riyuu": e(d["waku_riyuu"]), "tataita": e(d["tataita"]),
        "slots": waku, "tsugi": tsugi,
        "aka": aka_douga(), "link": li_link(),
        "link_itsu": e(d["link_hyou"]["itsu"] or d["link_hyou"]["at"] or ""),
        "nyoyaku": len(d["yoyaku"]), "cap": d["cap"],
        "nmachi": len(d["machi"]), "nch": len(d["chappie_machi"]),
        "nnk": len(d["nagekomi_mishori"]),
        "yoyaku": li_yoyaku(), "machi": li_machi(), "ch": li_ch(),
        "nk": li_nk(), "tk": li_tk(), "done": li_done(), "horyu": li_horyu()}


def main():
    d = atsumeru()
    os.makedirs(PUB, exist_ok=True)
    json.dump(d, io.open(OUT_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    io.open(OUT_HTML, "w", encoding="utf-8").write(html(d))
    print("書いた:", OUT_HTML)
    print("予約 %d／待機列 %d／チャッピー待ち %d／投げ込み未処理 %d／取消待ち %d"
          % (len(d["yoyaku"]), len(d["machi"]), len(d["chappie_machi"]),
             len(d["nagekomi_mishori"]), len(d["torikeshi"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
