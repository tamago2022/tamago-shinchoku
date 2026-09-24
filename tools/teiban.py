#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1081番【定番の棚卸し】その国の「絶対に押さえるべき」と、いまの棚を突き合わせる。

━━ なぜ作ったか（2026-09-24・たまごさん原文）━━

  「マニアックなのは後回しでいい。でも『これないんですか』はなしだよ。
    日本人が来て『桑田佳祐ありますか』『ありません』、もうそのレベルはダメ。」
  「それぞれの国の歌姫が当然ある。全曲じゃなくていい。宇多田ヒカルなら
    First Love / Automatic / Beautiful World / Fly Me to the Moon、それぐらいはあって欲しい。
    それを各国ぶん。」
  「南米系の人が来たら在庫あるのかな。ボサノバがちょっとあるだけなんじゃないの。
    それぞれの国のスターはちゃんと取り揃えてるのか。定番は抑えてるのか。」
  「今3万曲でしょう。次とりあえず5万曲、10万曲まで行こうよ。」
  「覆面テストはGensparkじゃなくて各AIにやってもらっていい。仲間だから、いろんな意見があっていい。」

■ ★この道具の考え方：**足りないものを「誰かが来てから」知るのをやめる**

  1080番（50人の客）は**客が来てから**足りないものを見つける。速いが、来た客のぶんしか出ない。
  こちらは**客が来る前に**、国・ジャンルの定番を先に並べて、棚と突き合わせる。
  「桑田佳祐ありますか」「ありません」は、客が来る前に潰せる。

■ ★決まり（たまごさん指定）

  ① **定番は外のAIに作らせる。こちらが決めない。**★1つのAIに決めさせない。
     codex(ChatGPT) と gsk(Genspark) の**両方に同じ問いを投げて、答えを並べる。**
     ★どちらが正解かをこちらが決めない。**食い違いはそのまま残して出す。**
  ② **アーティストごとに代表曲3〜5曲だけ。全曲は要らない。**（宇多田ヒカルの例がそれ）
  ③ **マニアックは後回し。定番から。**
  ④ **棚との突き合わせは機械がやる。**AIに「あると思います」を言わせない。
     索引（953番の head.json / t/NN.json ＝案内人が引くのと同じ索引）に無ければ「無い」。
  ⑤ ★**買い物リストは工場のキューに自動で積む。**人が写し替えない。
  ⑥ ★**積むのは「候補」であって棚ではない。**棚に入れるときは必ず入荷の関所
     （tools/nyuka_sekisho.py ＝ sekisho-artist-song / sekisho-jijitsu-shutten /
     bonjovi-ojisan-kobun の機械版）を通す。**入れてから直すのではなく、入る前に止める。**
     たまごさん「いっぱい入れたいけど入り口は狭くして。間違えない仕組みにして。」

■ 走らせ方（★Macの上でしか動かない。サンドボックスからは codex にも gsk にも届かない）

    python3 tools/teiban.py --kuni 日本                  # 1か国ぶん通す
    python3 tools/teiban.py --kuni ブラジル --ai codex    # 口を1つに絞る
    python3 tools/teiban.py --page                      # 1枚にして公開
    python3 tools/teiban.py --ichiran                   # 今までの棚卸しの結果（0円）
    python3 tools/teiban.py --tana "桑田佳祐"            # この名前は棚にあるか（0円）

■ 置き場所
  status/teiban/<国>.json      … その国の正本（AIごとの答えを分けて残す・要約しない）
  status/teiban/daicho.jsonl   … 1回＝1行。定番◯曲のうち棚に無いのは◯曲
  status/teiban/index.html     … 公開に出す1枚の控え
"""
from __future__ import annotations

import argparse
import glob
import html
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import kyaku50  # noqa: E402  ★棚の照合は1か所だけ（tana_ni_aruka をここに書き写さない）

OUT = os.path.join(REPO, "status", "teiban")
DAICHO = os.path.join(OUT, "daicho.jsonl")
KOUKAI_REPO = "tamago2022/ai-kaigi"
KOUKAI_PATH = "teiban/index.html"
KOUKAI_URL = "https://tamago2022.github.io/ai-kaigi/teiban/"

AI_ALL = ("codex", "gsk")

# ★この国を頼むときの手がかり。AIに「その国らしさ」を自分で決めさせると、
#   どの国でも英語圏の有名人を並べてくる（実測されている偏り）。ここで縛る。
KUNI_HINT = {
    "日本": "歌謡曲・J-POP・シティポップ・演歌・アイドル・ロック・ヒップホップを必ず混ぜる。"
            "★桑田佳祐・宇多田ヒカルのような『誰でも名前を知っている人』を落とさない。",
    "アメリカ": "ソウル／R&B／ロック／カントリー／ヒップホップ／ジャズを必ず混ぜる。",
    "イギリス": "60〜70年代のロックだけに寄せない。ソウル／エレクトロ／現行のポップも入れる。",
    "韓国": "K-POPだけに寄せない。トロット・バラード・70〜90年代の歌手も入れる。",
    "中華圏": "台湾・香港・中国本土を必ず全部入れる。広東語の歌手を落とさない。",
    "ブラジル": "ボサノヴァだけに寄せない。サンバ・MPB・セルタネージョ・ファンキも入れる。",
    "南米": "ブラジル以外（アルゼンチン・チリ・コロンビア・ペルー・メキシコ）を必ず入れる。"
            "タンゴ・クンビア・サルサ・ヌエバ・カンシオンを混ぜる。",
    "東南アジア": "インドネシア・フィリピン・タイ・ベトナム・ミャンマーを必ず全部入れる。",
    "フランス": "シャンソンだけに寄せない。イエイエ・フレンチタッチ・現行のポップも入れる。",
    "イタリア": "カンツォーネ／サンレモ／現行のポップを混ぜる。",
    "アフリカ": "ナイジェリア・セネガル・マリ・南アフリカ・エチオピアを必ず入れる。"
                "アフロビーツだけに寄せない。",
    "インド": "映画音楽（ボリウッド）と古典・地方語の歌手の両方を入れる。",
}


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rows(path):
    out = []
    try:
        for ln in io.open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    except Exception:
        pass
    return out


# ═════════════════════════ 外のAIに定番を作らせる ═════════════════════════

SYSTEM = ("あなたは世界中の音楽に詳しい、正直なレコード店の仕入れ担当です。"
          "知らないものを知っているふりをしません。"
          "マニアックな通好みではなく、**その国の人なら誰でも名前を知っている定番**から並べます。")


def _toi(kuni, n):
    hint = KUNI_HINT.get(kuni, "その国の中で世代とジャンルを散らす。")
    return "\n".join([
        "「%s」の音楽で、**絶対に押さえるべき定番**のアーティストを %d組 挙げてください。" % (kuni, n),
        "",
        "条件:",
        "・★マニアックなものは要りません。**その国の人が来て『無いんですか』と言う顔になる人**だけ。",
        "・★アーティスト1組につき、**代表曲は3〜5曲だけ。**全曲は要りません。",
        "　（例：宇多田ヒカルなら First Love / Automatic / Beautiful World / Fly Me to the Moon）",
        "・★世代を散らす（古い人だけ・今の人だけ、にしない）。",
        "・★%s" % hint,
        "・★曲名は**その曲が実際に出たときの表記**で書く（勝手に英訳・和訳しない）。",
        "・★自信が無いものは入れない。埋めるために思いつきを足さない。",
        "",
        "下の形の **JSONだけ**を返してください。説明文・前置き・```は付けないでください。",
        '{"kuni":"%s","list":[{"artist":"アーティスト名","yomi":"日本語での呼び方",'
        '"aliases":["別表記","原語表記"],"jyanru":"ジャンル",'
        '"songs":["代表曲1","代表曲2","代表曲3"]}]}' % kuni,
    ])


def kiku_codex(kuni, n, timeout=300):
    """codex（ChatGPTのログインで動く口。1回ごとの課金なし＝0円）に聞く。"""
    import gaibu_kuchi as g
    d, who, err = g.kiku_codex(SYSTEM, _toi(kuni, n), timeout=timeout)
    if d is None:
        return {"ok": False, "ai": "codex", "error": err or "codexが答えませんでした"}
    return {"ok": True, "ai": who or "codex", "kane": "0円", "data": d}


def kiku_gsk(kuni, n, timeout=420):
    """Genspark に聞く。★残クレジットの差を必ず記録する（減っていない＝通っていない）。

    ★2026-09-24 実測：`summarize <url> --question` は**ページの要約しか返さない。**
      渡した問いがページと関係ないと、問いを無視して「このページはこういうページです」と返す
      （1.1クレジット使って、定番の話が1文字も返ってこなかった）。
      定番は**ページの話ではない**ので、ここは `search`（問いだけの口・実測1クレジット）を使う。
      ★`search` は問いが2048字までしか通らない（超えると serper_http_400 で1クレジット無駄になる）。
      だから字数をここで必ず測ってから投げる。"""
    import genspark_nagashi as gn
    toi = _toi(kuni, n)
    if len(toi) > 2000:
        return {"ok": False, "ai": "genspark",
                "error": "問いが%d字で、gsk search の上限2048字を超えます（投げていません＝0クレジット）"
                         % len(toi)}
    zen = gn.zandaka(record=False).get("zan")
    t0 = time.time()
    raw = gn.gsk_run(["search", toi], timeout=timeout)
    byou = round(time.time() - t0, 1)
    ato = gn.zandaka(record=True).get("zan")
    tsukatta = (round(zen - ato, 3) if (zen is not None and ato is not None) else None)
    _append(os.path.join(REPO, "status", "gsk_daicho.jsonl"),
            {"at": _now(), "nani": "定番の棚卸し・%s" % kuni, "kuchi": "search",
             "ok": bool(raw.get("ok")), "残クレジット前": zen, "残クレジット": ato,
             "使ったクレジット": tsukatta, "秒": byou})
    r = {"r": raw, "zen": zen, "ato": ato, "tsukatta": tsukatta}
    kotae = kyaku50._kotae_toridasu((raw.get("stdout") or "").strip())
    if r["tsukatta"] is None or r["tsukatta"] <= 0:
        return {"ok": False, "ai": "genspark", "kotae": kotae[:2000],
                "error": "クレジットが1つも減っていない＝Gensparkを通っていない（前%s→後%s）"
                         % (r["zen"], r["ato"])}
    m = re.search(r"\{.*\}", kotae, re.S)
    if not m:
        return {"ok": False, "ai": "genspark", "kotae": kotae[:3000],
                "error": "JSONが読めませんでした", "使ったクレジット": r["tsukatta"]}
    try:
        d = json.loads(m.group(0))
    except Exception as ex:
        return {"ok": False, "ai": "genspark", "kotae": kotae[:3000],
                "error": "JSONが壊れています: %s" % ex, "使ったクレジット": r["tsukatta"]}
    return {"ok": True, "ai": "genspark", "kane": "前払い済みクレジット %s" % r["tsukatta"],
            "data": d, "使ったクレジット": r["tsukatta"]}


def kiku_zenbu(kuni, n, ais):
    """★1つのAIに決めさせない。同じ問いを全部の口に投げて、答えを**並べて**残す。
    ★食い違いをこちらで揃えない（たまごさん「いろんな意見があっていい」）。"""
    out = []
    for a in ais:
        print("  %s に聞いています…" % a, flush=True)
        try:
            r = kiku_codex(kuni, n) if a == "codex" else kiku_gsk(kuni, n)
        except Exception as ex:
            r = {"ok": False, "ai": a, "error": "%s: %s" % (type(ex).__name__, str(ex)[:200])}
        print("    → %s %s" % ("○" if r.get("ok") else "×", r.get("error") or ""), flush=True)
        out.append(r)
    return out


# ═════════════════════════ 棚と突き合わせる（0円） ═════════════════════════

def awaseru(kotae_tachi):
    """AIごとの答えを1つの表にまとめ、棚と突き合わせる。
    ★同じアーティストを複数のAIが挙げたら、**何人が挙げたか**を残す（強さの目安）。
    ★曲は和集合。AがXを挙げてBが挙げなくても、Xは定番の候補として残す。"""
    art = {}
    for k in kotae_tachi:
        if not k.get("ok"):
            continue
        ai = k["ai"]
        for row in ((k.get("data") or {}).get("list") or []):
            if not isinstance(row, dict) or not row.get("artist"):
                continue
            name = str(row["artist"]).strip()
            key = kyaku50._norm(name)
            a = art.setdefault(key, {"artist": name, "yomi": row.get("yomi") or "",
                                     "aliases": [], "jyanru": row.get("jyanru") or "",
                                     "dareaga": [], "songs": []})
            if ai not in a["dareaga"]:
                a["dareaga"].append(ai)
            for al in (row.get("aliases") or []):
                if al and al not in a["aliases"]:
                    a["aliases"].append(str(al))
            for s in (row.get("songs") or [])[:5]:
                s = str(s).strip()
                if s and all(kyaku50._norm(s) != kyaku50._norm(x["song"]) for x in a["songs"]):
                    a["songs"].append({"song": s, "ai": [ai]})
                else:
                    for x in a["songs"]:
                        if kyaku50._norm(s) == kyaku50._norm(x["song"]) and ai not in x["ai"]:
                            x["ai"].append(ai)

    # ── ここから棚との突き合わせ。★推測しない。索引に無ければ「無い」 ──
    for a in art.values():
        tana = kyaku50.tana_ni_aruka(a["artist"])
        for al in a["aliases"]:
            if not tana:
                tana = kyaku50.tana_ni_aruka(al)
        a["artistTana"] = tana
        for s in a["songs"]:
            s["tana"] = kyaku50.tana_ni_aruka(s["song"])
        # ★3つに分ける。「判定できない」を「ある」にも「無い」にも混ぜない。
        a["nai"] = [s["song"] for s in a["songs"] if not s["tana"]]
        a["aru"] = [s["song"] for s in a["songs"]
                    if s["tana"] and s["tana"] != kyaku50.FUMEI]
        a["fumei"] = [s["song"] for s in a["songs"] if s["tana"] == kyaku50.FUMEI]
    return sorted(art.values(), key=lambda a: (-len(a["dareaga"]), -len(a["nai"])))


# ═════════════════════════ 1か国ぶん通す ═════════════════════════

def tanaoroshi(kuni, n=30, ais=AI_ALL, koukai=True, tsumu=True):
    os.makedirs(OUT, exist_ok=True)
    print("【%s】の定番を %s に聞きます（%d組）" % (kuni, "・".join(ais), n), flush=True)
    kotae = kiku_zenbu(kuni, n, ais)
    hyou = awaseru(kotae)

    kyoku = sum(len(a["songs"]) for a in hyou)
    nai = sum(len(a["nai"]) for a in hyou)
    fumei = sum(len(a.get("fumei") or []) for a in hyou)
    art_nai = [a["artist"] for a in hyou if not a["artistTana"]]

    rec = {"at": _now(), "kuni": kuni, "kiita": list(ais),
           "kotaeta": [k["ai"] for k in kotae if k.get("ok")],
           "kotaenakatta": [{"ai": k["ai"], "error": k.get("error")}
                            for k in kotae if not k.get("ok")],
           "アーティスト数": len(hyou), "定番の曲数": kyoku,
           "棚に無い曲数": nai, "判定できない曲数": fumei,
           "棚に1曲も無いアーティスト": art_nai,
           "使ったクレジット": round(sum(k.get("使ったクレジット") or 0 for k in kotae), 3)}

    json.dump({**rec, "hyou": hyou, "nama": kotae},
              io.open(os.path.join(OUT, "%s.json" % kuni), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    _append(DAICHO, rec)

    if tsumu:
        rec["仕入れに積んだ"] = shiire_tsumu(kuni, hyou)
    if koukai:
        rec["koukaiUrl"] = page_dasu()
    return rec


# ═════════════════════════ 仕入れのキューに積む ═════════════════════════

SEKISHO = [
    "■ ★棚に入れる前に必ず通す門（たまごさん「いっぱい入れたいけど入り口は狭くして」）",
    "  ・tools/nyuka_sekisho.py（入荷の関所）を通す。通らなかったものは入れない。",
    "  ・★skill sekisho-artist-song：**名前が一致しただけで本人の棚に入れない。**",
    "    本人だという証拠（公式チャンネルID・動画ID等の識別子）を1つ以上取る。",
    "    前例：akikoの棚に矢野顕子／NON STYLEの棚にHarry Styles／Sugar BabeにSugababes。",
    "  ・★skill sekisho-jijitsu-shutten：出典の取れない断定を書かない。取れなければ空欄で出す。",
    "  ・★skill bonjovi-ojisan-kobun：「代表曲のひとつ。」のような水道水コピーを書かない。",
    "  ・★入れてから直すのではなく、**入る前に止める。**",
]


def shiire_tsumu(kuni, hyou):
    """★アーティスト1組＝1件で積む（曲ごとにバラすと、同じ人の調べ物を何度もやることになる）。
    ★既に積んだものは二度積まない。"""
    try:
        import command_ingest as ci
    except Exception as ex:
        return {"ok": False, "error": "キューに積めませんでした: %s" % str(ex)[:160]}

    sudeni = set()
    for r in _rows(os.path.join(OUT, "tsunda.jsonl")):
        sudeni.add(kyaku50._norm(r.get("artist")))

    tsunda = []
    for a in hyou:
        if not a["nai"] or kyaku50._norm(a["artist"]) in sudeni:
            continue
        maru = "★棚に1曲も無い" if not a["artistTana"] else "棚には居るが代表曲が欠けている"
        label = "仕入れ｜%s %s（定番%d曲中%d曲が無い）" % (kuni, a["artist"],
                                                        len(a["songs"]), len(a["nai"]))
        text = "\n".join([
            "【仕入れ】定番の棚卸し（1081番・%s）で、棚に無かった定番。" % kuni,
            "",
            "■ 誰を仕入れるか",
            "  %s%s" % (a["artist"], ("（%s）" % a["yomi"]) if a["yomi"] else ""),
            "  別表記: %s" % ("、".join(a["aliases"]) or "（なし）"),
            "  ジャンル: %s" % (a["jyanru"] or "（不明）"),
            "  状態: %s" % maru,
            "  この人を挙げたAI: %s" % "・".join(a["dareaga"]),
            "",
            "■ 棚に無い代表曲（★索引に機械で照合済み。推測ではない）",
        ] + ["  ・%s" % s for s in a["nai"]] + ([
            "",
            "■ 棚に既にある代表曲（参考）",
        ] + ["  ・%s" % s for s in a["aru"]] if a["aru"] else []) + [
            "",
            "■ やること",
            "  ① tools/shiire_fetch.py --names \"%s\" で素材（MusicBrainz / Wikipedia）を集める" % a["artist"],
            "  ② 上の曲の公式音源を探す（★素人カバー・AIカバーは棚に載せない）",
            "  ③ ★その周辺も見る（同じ国・同じ時代・同じジャンルの隣の人）。",
            "     たまごさん「その周辺も仕入れる。『これないんですか』って言われたら仕入れる」",
            "",
        ] + SEKISHO + [
            "",
            "※出どころ: %s" % KOUKAI_URL,
        ])
        try:
            st, msg = ci.queue_add(text, priority=2, label=label, origin="factory")
            tsunda.append({"artist": a["artist"], "nai": len(a["nai"]), "status": st})
            _append(os.path.join(OUT, "tsunda.jsonl"),
                    {"at": _now(), "kuni": kuni, "artist": a["artist"],
                     "nai": a["nai"], "status": st})
            sudeni.add(kyaku50._norm(a["artist"]))
        except Exception as ex:
            tsunda.append({"artist": a["artist"], "status": "failed", "msg": str(ex)[:120]})
    return tsunda


# ═════════════════════════ 1枚のページ ═════════════════════════

def e(s):
    return html.escape(str(s if s is not None else ""))


def page_tsukuru():
    kuniz = []
    for p in sorted(glob.glob(os.path.join(OUT, "*.json"))):
        if os.path.basename(p) in ("daicho.json",):
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
            if d.get("hyou") is not None:
                kuniz.append(d)
        except Exception:
            pass
    if not kuniz:
        return None

    kyoku = sum(k["定番の曲数"] for k in kuniz)
    nai = sum(k["棚に無い曲数"] for k in kuniz)
    fumei = sum(k.get("判定できない曲数") or 0 for k in kuniz)
    wakaru = kyoku - fumei
    ritsu = round(100.0 * (wakaru - nai) / wakaru, 1) if wakaru else 0

    honbun = ""
    for k in kuniz:
        gyou = ""
        for a in k["hyou"]:
            mar = "nai" if not a["artistTana"] else ("kake" if a["nai"] else "aru")
            sgs = ""
            for s in a["songs"]:
                c = ("f" if s["tana"] == kyaku50.FUMEI
                     else ("x" if not s["tana"] else "o"))
                sgs += '<span class="s %s">%s</span>' % (c, e(s["song"]))
            gyou += ('<tr class="%s"><td><b>%s</b>%s<br><span class=sub>%s%s</span></td>'
                     '<td>%s</td><td class=n>%d/%d</td></tr>'
                     % (mar, e(a["artist"]),
                        (' <span class=sub>%s</span>' % e(a["yomi"])) if a["yomi"] else "",
                        e(a["jyanru"]),
                        "　挙げたAI: " + e("・".join(a["dareaga"])),
                        sgs, len(a["nai"]), len(a["songs"])))
        kotaenakatta = "".join(
            "<li>%s は答えませんでした：%s</li>" % (e(x["ai"]), e(x.get("error")))
            for x in (k.get("kotaenakatta") or []))
        honbun += """
<h2>%s ― 定番 %d曲のうち、棚に無いのは <b class=akai>%d曲</b></h2>
<div class=sub2>聞いたAI: %s ／ 答えたAI: %s ／ 棚に1曲も無いアーティスト %d組%s</div>
%s
<table><tr><th>アーティスト</th><th>代表曲（<span class="s x">赤</span>＝棚に無い）</th><th class=n>無</th></tr>%s</table>
""" % (e(k["kuni"]), k["定番の曲数"], k["棚に無い曲数"],
            e("・".join(k.get("kiita") or [])), e("・".join(k.get("kotaeta") or [])),
            len(k.get("棚に1曲も無いアーティスト") or []),
            ("／使ったクレジット %s" % e(k.get("使ったクレジット"))) if k.get("使ったクレジット") else "",
            ("<ul class=warn>%s</ul>" % kotaenakatta) if kotaenakatta else "", gyou)

    suii = "".join("<tr><td>%s</td><td>%s</td><td>%s曲</td><td class=akai>%s曲</td></tr>"
                   % (e((h.get("at") or "")[:16]), e(h.get("kuni")),
                      e(h.get("定番の曲数")), e(h.get("棚に無い曲数")))
                   for h in _rows(DAICHO)[-15:])

    return """<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>定番の棚卸し｜「これないんですか」を無くす</title>
<style>
:root{--bg:#12100e;--fg:#f4efe6;--dim:#a79e8f;--line:#2e2a25;--o:#7fd1a6;--x:#e8796a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif;padding:20px 14px 80px}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.date{color:var(--dim);font-size:12px;margin-bottom:20px}
.atama{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:8px}
.card{background:#1b1815;border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.card .k{color:var(--dim);font-size:11px;letter-spacing:.07em}
.card .v{font-size:29px;font-weight:700;line-height:1.2}
.card .v small{font-size:12px;color:var(--dim);font-weight:400}
.akai{color:var(--x)}
.koe{color:var(--dim);font-size:12px;border-left:2px solid var(--line);padding-left:11px;margin:16px 0 26px}
h2{font-size:16px;margin:34px 0 4px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--dim);font-size:11.5px}
.sub2{color:var(--dim);font-size:12px;margin-bottom:10px}
ul.warn{color:var(--x);font-size:12px;margin:6px 0;padding-left:20px}
table{width:100%%;border-collapse:collapse;font-size:13.5px;margin-bottom:10px}
td,th{border-bottom:1px solid var(--line);padding:8px 5px;text-align:left;vertical-align:top}
th{color:var(--dim);font-size:11px;font-weight:400;letter-spacing:.06em}
td.n,th.n{text-align:right;white-space:nowrap;color:var(--dim)}
tr.nai td:first-child{border-left:3px solid var(--x);padding-left:8px}
.s{display:inline-block;margin:2px 5px 2px 0;padding:2px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}
.s.o{color:var(--o);border-color:#2b4a3a}
.s.x{color:var(--x);border-color:#4a2b28;background:#231715}
.s.f{color:var(--dim);border-style:dashed}
</style>
<div class=wrap>
<h1>定番の棚卸し｜「これないんですか」を無くす</h1>
<div class=date>%s ／ 突き合わせた棚＝案内人が引くのと同じ索引（アーティスト2,475組・動画33,947本）</div>

<div class=atama>
<div class=card><div class=k>定番として挙がった曲</div><div class=v>%d<small> 曲</small></div></div>
<div class=card><div class=k>そのうち棚に無い</div><div class=v akai style=color:var(--x)>%d<small> 曲</small></div></div>
<div class=card><div class=k>定番の充足率</div><div class=v>%s<small>%%</small></div></div>
<div class=card><div class=k>判定できない<br><span style=font-size:10px>（題名が1文字など）</span></div><div class=v style=color:var(--dim)>%d<small> 曲</small></div></div>
</div>
<div class=koe>たまごさん「マニアックなのは後回しでいい。でも『これないんですか』はなしだよ。日本人が来て『桑田佳祐ありますか』『ありません』、もうそのレベルはダメ。」／「全曲じゃなくていい。宇多田ヒカルなら First Love / Automatic / Beautiful World / Fly Me to the Moon、それぐらいはあって欲しい。それを各国ぶん。」<br>★棚に無い曲は<b>工場のキューに仕入れとして自動で積んであります</b>。棚に入れるときは入荷の関所（同名別人を止める門）を必ず通ります。<br>★定番を決めたのは外のAIです。<b>AIごとに答えが違います。揃えずにそのまま並べています。</b></div>
%s
<h2>棚卸しの履歴</h2>
<table><tr><th>いつ</th><th>国</th><th>定番</th><th>棚に無い</th></tr>%s</table>
<div class=koe>★「判定できない」＝題名が1文字（「楓」「糸」「M」）などで、索引と機械照合しても意味が取れないもの。<b>「無い」に数えていません。</b>分からないものを分かった顔で数えない、という決まりです。</div>
</div>""" % (_now(), kyoku, nai, ritsu, fumei, honbun, suii)


def page_dasu():
    h = page_tsukuru()
    if not h:
        return "（まだ1か国も棚卸ししていないのでページを作れません）"
    os.makedirs(OUT, exist_ok=True)
    io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(h)
    try:
        import _965_keijiban as kj
        r = kj.run_job({"repo": KOUKAI_REPO, "action": "putfile", "path": KOUKAI_PATH,
                        "branch": "gh-pages", "text": h,
                        "message": "定番の棚卸し（1081番）%s" % time.strftime("%F %T")})
        return KOUKAI_URL if r.get("ok") else "（公開できませんでした：%s）" % r.get("error")
    except Exception as ex:
        return "（公開できませんでした：%s）" % str(ex)[:160]


# ═════════════════════════ 次の1か国を勝手に進める ═════════════════════════

# ★たまごさん「俺が最近『仕入れやって』って言ってないからって、仕入れを止めていい
#   ってことじゃないからね。何も走ってませんって状態だったら、常に仕入れしといてよ。」
#   → 空いたら次の国へ自分で進む。**新しい常駐は増やさない**（既存の5分便から呼ばれる）。
JUNBAN = ["日本", "アメリカ", "イギリス", "韓国", "中華圏", "ブラジル", "南米",
          "東南アジア", "フランス", "イタリア", "アフリカ", "インド"]
STAMP = os.path.join(REPO, "status", ".teiban_last")


def tsugi(n=30, ais=AI_ALL):
    """まだ棚卸ししていない国を1つだけ進める。★1日1か国。
    ★ゲートを使い切るのは『最後まで走り切った時だけ』（931番の穴を繰り返さない）。"""
    try:
        if io.open(STAMP).read().strip() == time.strftime("%Y-%m-%d"):
            return {"ok": True, "skip": "今日はもう1か国やりました"}
    except Exception:
        pass
    try:
        load = os.getloadavg()[0]
    except Exception:
        load = 0
    if load > 40.0:
        return {"ok": True, "skip": "Macが混んでいます（load %.1f）。ゲートは消費しません" % load}

    sumi = set(r.get("kuni") for r in _rows(DAICHO))
    nokori = [k for k in JUNBAN if k not in sumi]
    if not nokori:
        return {"ok": True, "skip": "12か国ぜんぶ棚卸し済みです（次はジャンル別）"}

    r = tanaoroshi(nokori[0], n, ais)
    io.open(STAMP, "w").write(time.strftime("%Y-%m-%d"))   # ★走り切った時だけ書く
    return r


# ═════════════════════════ 入口 ═════════════════════════

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kuni")
    p.add_argument("--tsugi", action="store_true",
                   help="まだ棚卸ししていない国を1つだけ進める（1日1か国・既存の定期便から呼ぶ）")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--ai", default=",".join(AI_ALL))
    p.add_argument("--page", action="store_true")
    p.add_argument("--ichiran", action="store_true")
    p.add_argument("--tana")
    p.add_argument("--no-koukai", action="store_true")
    p.add_argument("--no-tsumu", action="store_true")
    a = p.parse_args()

    if a.tana:
        print("%s → %s" % (a.tana, kyaku50.tana_ni_aruka(a.tana) or "★棚に無い（＝買い物リスト）"))
        return 0
    if a.ichiran:
        for h in _rows(DAICHO):
            print("%s  %s  定番%s曲中 棚に無い%s曲  （答えたAI: %s）"
                  % (h.get("at"), h.get("kuni"), h.get("定番の曲数"),
                     h.get("棚に無い曲数"), "・".join(h.get("kotaeta") or [])))
        return 0
    if a.page:
        print(page_dasu())
        return 0
    if a.tsugi:
        print(json.dumps(tsugi(a.n, tuple(x.strip() for x in a.ai.split(",") if x.strip())),
                         ensure_ascii=False, indent=1, default=str))
        return 0
    if a.kuni:
        r = tanaoroshi(a.kuni, a.n, tuple(x.strip() for x in a.ai.split(",") if x.strip()),
                       koukai=not a.no_koukai, tsumu=not a.no_tsumu)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
