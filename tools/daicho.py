#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【受付台帳】言われたことを、埋もれさせないための1か所。

たまごさんの言葉（2026-09-24）:
  「Spotifyにプレイリスト入れといてって言ったやつ。俺が忘れたら俺は突っ込まないじゃん。
    俺が思い出したときに突っ込むのよ。こういうの、いっぱいあると思うよ、
    埋もれてるもの。俺に気づかれてないだけで。それをゼロに近づけようよ。」
  「できないになったら、Julesなのか Devinなのか、他の担当に再チャレンジさせる。
    そのループ回そうよ。三時間縛りね。」

★この台帳が守る3つ:
  1. **言われたら必ず1行残る。**やるかどうかを判断する前に記録する。
  2. **同じことを2回言われたら、新しい行を作らずに回数を+1する。**回数3以上は最優先。
  3. **1人3時間で交代。**交代のとき「どこまで進んだか」を残さずに終わるのは禁止。
     残っていなければ台帳に「★進捗の記録なし」と赤で残る（隠せない）。

正本: status/daicho.json
画面: share/daicho.html （`--page` で作る。tools/sumaho_gate.py を通すこと）

使い方:
  python3 tools/daicho.py --ireru "Spotifyのプレイリストに入れる"   # 言われた（or 回数+1）
  python3 tools/daicho.py --susumu spotify --made "refresh_tokenの口まで出来た"
  python3 tools/daicho.py --koutai spotify --riyuu 時間切れ          # 次の選手へ
  python3 tools/daicho.py --kigen        # 3時間を過ぎた行を機械で交代させる（心臓から毎回）
  python3 tools/daicho.py --hi           # 「◯日治っていない」を更新（心臓から1日1回）
  python3 tools/daicho.py --page         # 画面を書き出す
  python3 tools/daicho.py --ichiran      # 端末で一覧
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "daicho.json")
PAGE = os.path.join(REPO, "share", "daicho.html")
JST = datetime.timezone(datetime.timedelta(hours=9))

KIGEN_JIKAN = 3  # ★1人あたり3時間（たまごさん指定）

# ---------------------------------------------------------------------------
# 選手の並び（★実測で通ったものだけ使う。通らない選手は飛ばす）
# ---------------------------------------------------------------------------
SENSHU = [
    {"id": "claude-ko", "na": "子セッション（Claude）", "tokui": "判断・配管・原因究明",
     "kane": "0円", "tsukaeru": True},
    {"id": "jules", "na": "Jules", "tokui": "実装・単純作業", "kane": "0円", "tsukaeru": True},
    {"id": "devin", "na": "Devin", "tokui": "1本ずつ投げる実装",
     "kane": "ACU従量", "tsukaeru": True,
     "chui": "★依頼文に「返事を書くな。終わりの合図はPRのURLだけ」を必ず入れる"},
    {"id": "genspark", "na": "Genspark（gsk）", "tokui": "調べもの",
     "kane": "0円（前払い残1924・10/4で消える）", "tsukaeru": True},
    {"id": "jev", "na": "Jev（TypeSafe AI）", "tokui": "判定だけ（yes/no・点数）",
     "kane": "入力100万トークンで約6.6円・出力0円", "tsukaeru": True,
     "chui": "★コピーの書き直しには使えない（点数は返るが直した文は返らない）"},
    {"id": "tamago", "na": "たまごさんの1手", "tokui": "人にしかできない1点",
     "kane": "—", "tsukaeru": True,
     "chui": "★3人目でも駄目ならここへ落とす。押すボタン1つのURLだけを出す。うやむやにしない"},
]
SENSHU_ID = [s["id"] for s in SENSHU]


def senshu_no(sid):
    return SENSHU_ID.index(sid) if sid in SENSHU_ID else 0


def tsugi_no_senshu(sid):
    i = senshu_no(sid)
    for s in SENSHU[i + 1:]:
        if s.get("tsukaeru"):
            return s["id"]
    return "tamago"


# ---------------------------------------------------------------------------
# 読み書き
# ---------------------------------------------------------------------------
def ima():
    return datetime.datetime.now(JST)


def yomu():
    if not os.path.exists(DAICHO):
        return {"updatedAt": "", "rows": []}
    try:
        return json.load(io.open(DAICHO, encoding="utf-8"))
    except Exception:
        return {"updatedAt": "", "rows": []}


def kaku(d):
    d["updatedAt"] = ima().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    tmp = DAICHO + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DAICHO)


# ---------------------------------------------------------------------------
# 同じ依頼かどうか（★2回目は新しい行を作らず回数を+1する）
# ---------------------------------------------------------------------------
_KESU = re.compile(r"[\s　。、，．,\.！？!?「」『』（）\(\)\[\]【】・:：;；\-—ー_/／]+")


def _tane(s):
    return _KESU.sub("", (s or "")).lower()


def _kotoba(s):
    """意味のかたまりを拾う（2文字以上の連続した同種文字）"""
    return set(w for w in re.findall(r"[ぁ-んァ-ヶ一-龥]{2,}|[A-Za-z]{3,}", s or ""))


def onaji(a, b):
    ta, tb = _tane(a), _tane(b)
    if not ta or not tb:
        return False
    if ta == tb or (len(ta) >= 6 and len(tb) >= 6 and (ta in tb or tb in ta)):
        return True
    wa, wb = _kotoba(a), _kotoba(b)
    # ★言葉が少なすぎるものを重なり率で比べない（短い文どうしが全部「同じ」になる事故）
    if len(wa) < 3 or len(wb) < 3:
        return False
    return len(wa & wb) / float(min(len(wa), len(wb))) >= 0.6


def sagasu(d, moji_or_id, id_dake=False):
    """id_dake=True … idの完全一致だけで探す（種まきのように id を指定して入れるとき）"""
    for r in d["rows"]:
        if r["id"] == moji_or_id:
            return r
    if id_dake:
        return None
    for r in d["rows"]:
        if onaji(r["irai"], moji_or_id) or any(onaji(a, moji_or_id) for a in r.get("iikata", [])):
            return r
    return None


def _atarashii_id(d, irai):
    tane = re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龥]", "", (irai or "").lower())[:14] or "irai"
    i, cand = 1, tane
    while any(r["id"] == cand for r in d["rows"]):
        i += 1
        cand = "%s%d" % (tane, i)
    return cand


# ---------------------------------------------------------------------------
# 言われた（新規 or 回数+1）
# ---------------------------------------------------------------------------
def ireru(irai, hatsu=None, hatsu_kind="実測", moto=None, rid=None, senshu="claude-ko",
          koko="", tsugi="", jotai="順番待ち", url="", kaisu=None):
    d = yomu()
    r = sagasu(d, rid or irai, id_dake=bool(rid))
    t = ima()
    if r:
        r["kaisu"] = int(r.get("kaisu") or 1) + 1
        r.setdefault("iikata", [])
        if irai not in r["iikata"] and irai != r["irai"]:
            r["iikata"].append(irai)
        r["saigo"] = t.strftime("%Y-%m-%d %H:%M")
        kaku(d)
        print(json.dumps({"どうした": "回数を+1しました", "id": r["id"],
                          "回数": r["kaisu"], "最優先": r["kaisu"] >= 3},
                         ensure_ascii=False))
        return r
    r = {
        "id": rid or _atarashii_id(d, irai),
        "irai": irai,
        "iikata": [],
        "kaisu": int(kaisu) if kaisu else 1,
        "hatsu": hatsu or t.strftime("%Y-%m-%d"),
        "hatsuKind": hatsu_kind,
        "naotteinai": 0,
        "senshu": senshu,
        "ninme": 1,
        "koko": koko or "（まだ誰も手を付けていない）",
        "tsugi": tsugi or "1人目を着火する",
        "jotai": jotai,
        "kigen": (t + datetime.timedelta(hours=KIGEN_JIKAN)).isoformat(),
        "url": url,
        "moto": moto or [],
        "saigo": t.strftime("%Y-%m-%d %H:%M"),
        "rireki": [],
    }
    d["rows"].append(r)
    kaku(d)
    print(json.dumps({"どうした": "新しく1行足しました", "id": r["id"]}, ensure_ascii=False))
    return r


def susumu(rid, made, tsugi=None, url=None, jotai=None):
    d = yomu()
    r = sagasu(d, rid)
    if not r:
        print("その依頼が台帳にありません: %s" % rid)
        return 1
    r["koko"] = made
    if tsugi:
        r["tsugi"] = tsugi
    if url is not None:
        r["url"] = url
    if jotai:
        r["jotai"] = jotai
    r["saigo"] = ima().strftime("%Y-%m-%d %H:%M")
    kaku(d)
    print(json.dumps({"id": r["id"], "今どこ": r["koko"], "状態": r["jotai"]}, ensure_ascii=False))
    return 0


def koutai(rid, riyuu="時間切れ", made=None):
    """★選手交代。どこまで進んだかを必ず残す。残っていなければ赤で残す。"""
    d = yomu()
    r = sagasu(d, rid)
    if not r:
        print("その依頼が台帳にありません: %s" % rid)
        return 1
    t = ima()
    nokosu = made or r.get("koko") or ""
    kiroku_nashi = (not nokosu) or nokosu.startswith("（まだ")
    r.setdefault("rireki", []).append({
        "at": t.strftime("%Y-%m-%d %H:%M"),
        "senshu": r.get("senshu"),
        "ninme": r.get("ninme", 1),
        "made": "★進捗の記録なし（禁止事項）" if kiroku_nashi else nokosu,
        "riyuu": riyuu,
    })
    mae = r.get("senshu", "claude-ko")
    r["senshu"] = tsugi_no_senshu(mae)
    r["ninme"] = int(r.get("ninme") or 1) + 1
    r["kigen"] = (t + datetime.timedelta(hours=KIGEN_JIKAN)).isoformat()
    r["saigo"] = t.strftime("%Y-%m-%d %H:%M")
    r["jotai"] = "たまごさんの1手" if r["senshu"] == "tamago" else "走行中"
    if kiroku_nashi:
        r["koko"] = "★前の選手が進捗を残さず終わった（%s）" % mae
    kaku(d)
    print(json.dumps({"id": r["id"], "交代": "%s → %s" % (mae, r["senshu"]),
                      "何人目": r["ninme"], "理由": riyuu,
                      "進捗の記録": "なし★" if kiroku_nashi else "あり"}, ensure_ascii=False))
    return 0


def kigen_check(dry=False):
    """★3時間を過ぎた行を機械で交代させる。人が判断しない。"""
    d = yomu()
    t = ima()
    kawatta = []
    for r in d["rows"]:
        if r.get("jotai") in ("潰した", "たまごさんの1手", "順番待ち"):
            continue
        k = r.get("kigen")
        if not k:
            continue
        try:
            kd = datetime.datetime.fromisoformat(k)
        except Exception:
            continue
        if t > kd:
            kawatta.append(r["id"])
            if not dry:
                koutai(r["id"], riyuu="3時間の時間切れ")
                d = yomu()
    print(json.dumps({"3時間を過ぎて交代": kawatta, "件数": len(kawatta)}, ensure_ascii=False))
    return 0


def hi_koushin():
    """★「◯日治っていないか」を更新する（心臓に相乗りして1日1回）"""
    d = yomu()
    kyou = ima().date()
    for r in d["rows"]:
        try:
            h = datetime.date.fromisoformat(r["hatsu"])
            r["naotteinai"] = 0 if r.get("jotai") == "潰した" else (kyou - h).days
        except Exception:
            pass
    kaku(d)
    nokori = [r for r in d["rows"] if r.get("jotai") != "潰した"]
    furui = max(nokori, key=lambda r: r.get("naotteinai") or 0) if nokori else None
    print(json.dumps({"更新": len(d["rows"]),
                      "一番古い": (furui or {}).get("irai", ""),
                      "日数": (furui or {}).get("naotteinai", 0)}, ensure_ascii=False))
    return 0


def tsubushita(rid, url):
    """★潰した＝本番に出てURLで開ける、まで。URLが無いものは潰したことにしない。"""
    d = yomu()
    r = sagasu(d, rid)
    if not r:
        print("その依頼が台帳にありません: %s" % rid)
        return 1
    if not (url or "").startswith("http"):
        print("★URLが無いので「潰した」にできません。pushだけは潰したではありません。")
        return 1
    r["jotai"] = "潰した"
    r["url"] = url
    r["naotteinai"] = 0
    r["koko"] = "本番で開ける（%s）" % url
    r["tsugi"] = "—"
    r["saigo"] = ima().strftime("%Y-%m-%d %H:%M")
    kaku(d)
    print(json.dumps({"id": r["id"], "潰した": url}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# 画面（★スマホ1画面。古い順・回数の多い順）
# ---------------------------------------------------------------------------
CSS = """:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;padding:12px 12px 40px;color:#1c1a17;background:#faf8f4;
font:15px/1.6 -apple-system,"Hiragino Sans",system-ui,sans-serif}
h1{font-size:17px;margin:0 0 2px}
.sub{font-size:12px;color:#7a736a;margin:0 0 10px}
.top{background:#fff;border:1px solid #e6e0d6;border-radius:12px;padding:10px 12px;margin-bottom:12px}
.top div{font-size:13px;margin:3px 0}
.top b{font-size:15px}
.c{background:#fff;border:1px solid #e6e0d6;border-left:4px solid #cfc7ba;border-radius:10px;
margin-bottom:7px;overflow:hidden}
.c.akai{border-left-color:#c0392b}
.c.kiiro{border-left-color:#d19a1d}
.c.sumi{opacity:.45;border-left-color:#5a9b5a}
summary{list-style:none;padding:9px 11px;cursor:pointer;display:flex;flex-wrap:wrap;
align-items:baseline;gap:6px}
summary::-webkit-details-marker{display:none}
.n{flex:0 0 auto;font-weight:700;font-size:12px;background:#1c1a17;color:#fff;
border-radius:99px;padding:1px 8px}
.akai .n{background:#c0392b}
.sumi .n{background:#5a9b5a}
.t{flex:1 1 58%;font-weight:600;font-size:14px}
.m{flex:0 0 auto;font-size:11px;color:#7a736a}
.b{padding:2px 11px 11px;font-size:13px;border-top:1px solid #f0ece4}
.k{margin:6px 0}
.k b{display:inline-block;min-width:6.5em;color:#7a736a;font-weight:600;font-size:12px}
.rr{margin-top:8px;border-top:1px dashed #e6e0d6;padding-top:6px;font-size:12px}
.rr b{color:#7a736a;font-size:11px}
.r{margin:4px 0;color:#4a453e}
.y{color:#8a8278}
.ashi{margin-top:14px;font-size:11px;color:#8a8278;line-height:1.7}
a{color:#0a58ca;word-break:break-all}"""

ASHI = ("<div class=ashi>回数＝この件に触れている仕事票の本数＋引き継ぎメモの本数（機械で数えた）。"
        "日付に「頃」が付くものは推定。<br>"
        "1人3時間で選手交代。交代のときは「どこまで進んだか」を必ず残す。"
        "URLが無いものは「潰した」にできない。</div>")


def _narabi(rows):
    """回数の多い順 → 古い順。潰したものは下。"""
    return sorted(rows, key=lambda r: (r.get("jotai") == "潰した",
                                       -(r.get("kaisu") or 1),
                                       -(r.get("naotteinai") or 0)))


def _senshu_na(sid):
    for s in SENSHU:
        if s["id"] == sid:
            return s["na"]
    return sid


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def page():
    d = yomu()
    rows = _narabi(d["rows"])
    ikiteru = [r for r in rows if r.get("jotai") != "潰した"]
    furui = max(ikiteru, key=lambda r: r.get("naotteinai") or 0) if ikiteru else None
    nan3 = [r for r in ikiteru if (r.get("kaisu") or 1) >= 3]
    tama = [r for r in ikiteru if r.get("jotai") == "たまごさんの1手"]

    ko = []
    for r in rows:
        sumi = r.get("jotai") == "潰した"
        kaisu = r.get("kaisu") or 1
        hi = r.get("naotteinai") or 0
        iro = "sumi" if sumi else ("akai" if kaisu >= 3 else ("kiiro" if hi >= 7 else ""))
        rireki = "".join(
            '<div class=r>%s 　%s（%s人目）　%s<span class=y>%s</span></div>'
            % (_esc(x.get("at", "")[5:]), _esc(_senshu_na(x.get("senshu"))),
               _esc(x.get("ninme", "")), _esc(x.get("riyuu", "")),
               "　→ " + _esc(x.get("made", "")))
            for x in r.get("rireki", []))
        ko.append("""<details class="c %s"%s>
<summary><span class=n>%s回</span><span class=t>%s</span>
<span class=m>%s日　%s（%s人目）</span></summary>
<div class=b>
<div class=k><b>なぜ治らない</b>　%s</div>
<div class=k><b>今どこまで</b>　%s</div>
<div class=k><b>潰す手</b>　%s</div>
<div class=k><b>最初に言われた</b>　%s%s</div>
%s
%s
</div></details>""" % (
            # ★スマホ1画面：全部畳む。開くのは今走っている1行だけ。
            iro, " open" if (r.get("jotai") == "走行中" and not sumi) else "",
            kaisu, _esc(r["irai"]),
            hi, _esc(_senshu_na(r.get("senshu"))), r.get("ninme", 1),
            _esc(r.get("naze") or "—"),
            _esc(r.get("koko")), _esc(r.get("tsugi")),
            _esc(r.get("hatsu")), "頃" if r.get("hatsuKind") == "推定" else "",
            ('<div class=k><b>開ける</b>　<a href="%s">%s</a></div>'
             % (_esc(r["url"]), _esc(r["url"]))) if r.get("url") else "",
            ("<div class=rr><b>交代の記録</b>%s</div>" % rireki) if rireki else ""))

    atama = """<h1>受付台帳</h1>
<p class=sub>言われたことが埋もれないための1か所。回数の多い順→古い順。{updated} 現在</p>
<div class=top>
<div>まだ治っていない　<b>{ikiteru}件</b>　／　潰した <b>{sumi}件</b></div>
<div>一番古いのは <b>{hi}日前</b>の「{furui}」</div>
<div>3回以上言われた（最優先）　<b>{nan3}件</b></div>
<div>たまごさんにしか押せない　<b>{tama}件</b></div>
</div>""".format(
        updated=d.get("updatedAt", ""), ikiteru=len(ikiteru), sumi=len(rows) - len(ikiteru),
        hi=(furui or {}).get("naotteinai", 0), furui=_esc((furui or {}).get("irai", "")),
        nan3=len(nan3), tama=len(tama))

    html = ("<!doctype html><html lang=ja><head>"
            "<meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>受付台帳｜言われたことを埋もれさせない</title>\n<style>\n"
            + CSS + "\n</style></head><body>\n" + atama + "\n"
            + "\n".join(ko) + "\n" + ASHI + "\n</body></html>")

    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with io.open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({"書いた": PAGE, "行": len(rows),
                      "URL": "https://tamago2022.github.io/tamago-shinchoku/share/daicho.html"},
                     ensure_ascii=False))
    return 0


def ichiran():
    d = yomu()
    for r in _narabi(d["rows"]):
        print("%2s回 %3s日 %-9s(%s人目) %-11s %s"
              % (r.get("kaisu"), r.get("naotteinai"), r.get("senshu"),
                 r.get("ninme"), r.get("jotai"), r["irai"][:42]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ireru")
    ap.add_argument("--hatsu")
    ap.add_argument("--suitei", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--susumu")
    ap.add_argument("--made")
    ap.add_argument("--tsugi")
    ap.add_argument("--url")
    ap.add_argument("--koutai")
    ap.add_argument("--riyuu", default="時間切れ")
    ap.add_argument("--tsubushita")
    ap.add_argument("--kigen", action="store_true")
    ap.add_argument("--hi", action="store_true")
    ap.add_argument("--page", action="store_true")
    ap.add_argument("--ichiran", action="store_true")
    ap.add_argument("--senshu-ichiran", action="store_true")
    a = ap.parse_args()

    if a.senshu_ichiran:
        print(json.dumps(SENSHU, ensure_ascii=False, indent=1))
        return 0
    if a.ireru:
        ireru(a.ireru, hatsu=a.hatsu, hatsu_kind="推定" if a.suitei else "実測", rid=a.id)
        return 0
    if a.susumu:
        return susumu(a.susumu, a.made or "", tsugi=a.tsugi, url=a.url)
    if a.koutai:
        return koutai(a.koutai, riyuu=a.riyuu, made=a.made)
    if a.tsubushita:
        return tsubushita(a.tsubushita, a.url or "")
    if a.kigen:
        return kigen_check()
    if a.hi:
        return hi_koushin()
    if a.page:
        return page()
    if a.ichiran:
        return ichiran()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
