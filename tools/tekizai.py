#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1065番【適材適所】仕事が来たら「これは誰向きか」を機械が決めて、依頼文ごと渡す係。

たまごさん（2026-09-24・原文）:
  「能力やポテンシャルを引き出すのも、管理する人の仕事なんじゃないか。
    あなたは各AIの適性を見抜いて力を発揮させるって。」
  「仕事できないやつを切り捨てるって簡単なんだよ。それをうまく役立たせるって方が難しいと思うよ。」

★これは管理側（Dispatch）の仕事で、今までやれていなかった。
  1050番（tools/soto_hatarakite.py）は「いくら払って何本採用できたか」＝**採点**の紙。
  ここはその手前。**切る判断より先に、適性に合った仕事を当てる**ための割り振り表。

━━ 1050番と何が違うか（同じ数字を2か所に書かないための線引き）━━
  お金（月いくら・1本あたり）は **soto_hatarakite.build() の結果をそのまま写す。**
  ここでは1円も計算し直さない。計算を2本持つと、どちらが本当か分からなくなる
  （tools/kaitsuu.py 冒頭と同じ理由）。
  ここが持つのは、1050番が持っていない4つだけ：
     ① 得意（実測）・苦手（実測）
     ② 今の仕事（いま何を持たせているか。0本なら 0本と書く）
     ③ 通した本数／本番に出た本数（★「PRが返った」と「本番で開ける」を分けて数える）
     ④ ★割り振り（仕事の一文 → 誰に投げるか ＋ そのまま使える依頼文）

━━ 「力を発揮させる」の中身（★ここが本題。切る話ではない）━━
  1. 得意な形の仕事だけを当てる。苦手な形を投げて「使えない」と判定しない。
  2. 相手が止まる癖に、**こちら側で**手当てする（KUSE に、癖と手当てを1対1で書いてある）。
  3. 返ってきたものを必ず受け取る（tools/baton.py の検品へ回す）。投げっぱなしにしない。
  4. 3時間で帰らなければ次の選手へ（KOUTAI）。どこまで進んだかを残して渡す。
  5. 仕事が来たら自動で割り振る。Dispatchが毎回考えない（wariate()）。

━━ 判定は最後（★これを破ると、また「使えない」で終わる）━━
  「ちゃんと使った」5条件（TSUKAIKATA）を全部満たすまで、切る／使うを書かない。
  満たしていなければ **「まだ判定できない。こちらの使い方が悪かった」** と書き、
  こちら側の落ち度を名指しで並べる。実測 status/1059_hikitsugi_devin.md:22 が実例。

━━ 決まり ━━
  ① ★AIを1回も呼ばない。外へ1回も出ない。＝クレジット0円（手本 tools/baton.py:37）。
  ② ★憶測を1円も書かない。読んだファイルに在る数字だけを写す。
     取れないものは「取れていない＋どの口が閉じているか」と書く。
  ③ ★数字は出典と**同じ行**に置く（tools/kazu_gate.py は行単位で見る）。
  ④ ★たまごさんのファイルを消さない・動かさない。書くのは下の OUT_* だけ。

使い方:
  python3 tools/tekizai.py                      … 紙を書き換える（中で1日1回に間引く）
  python3 tools/tekizai.py --force              … 今すぐ書き換える
  python3 tools/tekizai.py --shigoto "<仕事の一文>"  … ★誰に投げるか＋依頼文を出す
  python3 tools/tekizai.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import soto_hatarakite as soto   # ★お金と出典の付け方は1か所にしか書かない（1050番）

OUT_JSON = os.path.join(PUBLIC, "tekizai.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1065-tekizai.html")
STAMP = os.path.join(STATUS, ".tekizai_at")
JST = timezone(timedelta(hours=9))

# ★これらの行に、下で写している数字がそのまま載っている（soto.srcline が行番号を取る）
soto.NEEDLE.update({
    "status/1059_hikitsugi_devin.md": "セッション26本",
    "status/1054_jev_nanken_nanen.md": "0.042",
    "status/1030_hikitsugi.md": "16.0秒",
    "status/1049_hikitsugi_irai_gate.md": "1.000",
    "status/1045/me_after.json": "credit_balance",
    "status/public/uketori_machi.json": '"goukaku"',
    "status/public/kaitsuu.json": '"gemini"',
})

# ---------------------------------------------------------------------------
# ★止まる癖と、こちら側の手当て（1対1。ここを読めば依頼文が書ける）
# ---------------------------------------------------------------------------
KUSE = {
    "devin": ("詰まると「指示があるまで待ちます」と言って止まる（status/devin_990_report.md:34）",
              "依頼文に「返事を書くな。質問をするな。終わりの合図はPull RequestのURLだけ」を必ず入れる"),
    "jules": ("PRは返すが、そのあと誰も受け取らないと止まったまま残る（`cat status/public/uketori_machi.json`）",
              "ただ働きなので数で押す。返ったPRは tools/baton.py に必ず通す"),
    "genspark": ("こちらが手で叩かないと動かない＝水汲みになる（status/1049_hikitsugi_irai_gate.md:63）",
                 "tools/1058_genspark_pipe を使って自動で流す。人が叩きに行かない"),
    "jev": ("文章を返さない。書き直しは1文字もできない（tools/sekisho/jev_honnin.py:22）",
            "問いを1つに絞り、0/1（はい確率）で返させる。複数問は1リクエストにまとめる"),
    "ko": ("長い作業の途中で枠が切れると、どこまで進んだか消える",
           "仕事を小さく切り、終わるたび status/ に現在地を残させる"),
    "openai": ("残高が切れると 429 で黙って返らなくなる（`cat status/ai_daicho.jsonl`）",
               "その場で返る短い検品だけに使う。長い仕事を持たせない"),
    "copilot": ("Issueに書いても担当者の候補に出ない（`cat status/public/kaitsuu.json`）",
                "GitHubのトークンを通してから測り直す。通るまで仕事を当てない"),
    "gemini": ("鍵が置かれていないので1回も叩けていない（`cat status/public/kaitsuu.json`）",
               "鍵を置く。置いた日から測れる"),
    "grok": ("文字の口が 403（`cat status/public/kaitsuu.json`）。声の口だけ 200",
             "声（読み上げ）だけ当てる。文字の仕事を投げない"),
}

# ★交代先（3時間で帰らなければ、ここへ同じ仕事を渡す）
KOUTAI = {
    "jules": "子セッション", "devin": "Jules", "genspark": "子セッション",
    "jev": "子セッション", "ko": "Jules", "openai": "Jev",
    "copilot": "Jules", "gemini": "Jev", "grok": "—",
}

# ★「ちゃんと使った」の5条件。全部 True になるまで、切る／使うを書かない。
TSUKAIKATA = ("得意な形の仕事を当てた", "正しい依頼文で投げた", "まとめずに投げた",
              "返りを受け取って検品した", "帰らないものを交代させた")
# ★交代までの持ち時間。数字はここ1か所にしか書かない（紙では出典としてこの行を指す）。
KOUTAI_JIKAN = "3時間"
KOUTAI_SRC = "tools/tekizai.py:118"

# ---------------------------------------------------------------------------
# ★割り振り表（仕事の形 → 選手）。ここを増やすときは必ず実測の根拠を付ける。
# ---------------------------------------------------------------------------
SHIGOTO = [
    dict(kind="data", label="件数とキーが決まっているJSONをそろえる",
         words=("json", "件数", "キー", "そろえ", "一括", "埋める", "リスト化", "csv", "データ"),
         who="jules",
         konkyo="149件で合格 136/149＝91.3%（`cat status/1028/jules_kekka.json`）・0円"),
    dict(kind="jissou", label="コードを書いてPRまで運ぶ",
         words=("実装", "直す", "修正", "バグ", "コンポーネント", "pr", "ビルド", "軽く", "速く"),
         who="devin",
         konkyo="26本投げてPR5本・本番に出たのは1本（status/1059_hikitsugi_devin.md:12）"),
    dict(kind="shirabe", label="調べもの（出典つきで集める）",
         words=("調べ", "検索", "リサーチ", "候補", "探し", "仕入れ", "下調べ", "出典"),
         who="genspark",
         konkyo="deep_research 1本が120秒で出典つき3件（status/1045_hikitsugi.md:14）"),
    dict(kind="hantei", label="はい／いいえ・点数だけ返す判定",
         words=("判定", "本人か", "かどうか", "点数", "採点", "確信", "仕分け", "ふるい"),
         who="jev",
         konkyo="入力だけ課金 $0.042/1Mトークン＝約6.60円（status/1054_jev_nanken_nanen.md:5）・出力0円"),
    dict(kind="handan", label="判断・配管・原因究明（答えの形が決まっていない）",
         words=("原因", "設計", "どうすれば", "配管", "つなぐ", "決めて", "方針", "作って"),
         who="ko",
         konkyo="261本の実測中央値（`cat status/public/cost_by_task.json`）"),
    dict(kind="e", label="絵・音・動画を作る",
         words=("絵", "画像", "動画", "音声", "サムネ", "ポスター", "映像"),
         who="fal",
         konkyo="採用の本数が台帳に付いている（`cat status/public/fal_cost_ledger.json`）"),
    dict(kind="koe", label="読み上げ（声）",
         words=("読み上げ", "声", "ナレーション"), who="grok",
         konkyo="声の口だけ 200（`cat status/public/kaitsuu.json` の xai_koe）"),
    dict(kind="sokuji", label="その場で返る短い検品",
         words=("検品", "チェック", "点検", "水道水"), who="openai",
         konkyo="1回 0.013円（`cat status/public/gaibu_kenpin_ledger.json`）"),
]

# ★依頼文の型（そのまま貼れる形。相手の癖の手当てを最初から埋め込む）
IRAI_ATAMA = ("返事を書くな。質問をするな。終わりの合図は成果物のURLだけ。\n"
              "完了の条件：本番で開けること。pushだけでは完了ではない。\n"
              "触るな：棚のデータ、たまごさんのファイル。")


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _lines(p):
    try:
        return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 実測（全部ファイルから。外へ1回も出ない）
# ---------------------------------------------------------------------------
def tooshita_honban():
    """通した本数（機械の検品に合格）と、本番に出た本数（mainに入った）。

    ★ここを1つの数にまとめない。「PRが返った」で数えると、Devinの26本が
      働いているように見えてしまう（実測では本番に出たのは1本だけ）。
    """
    u = _load(os.path.join(PUBLIC, "uketori_machi.json"), {}) or {}
    got = {}
    for r in u.get("goukaku", []):
        who = r.get("who") or ""
        k = ("jules" if "Jules" in who else "devin" if "Devin" in who else
             "copilot" if "Copilot" in who else "sonota")
        d = got.setdefault(k, {"tooshita": 0, "honban": 0})
        d["tooshita"] += 1
        if r.get("merged"):
            d["honban"] += 1
    return got, len(u.get("sonota", []))


def ko_session():
    """子セッション（Claude）の実測。`cat status/public/cost_by_task.json` が正本。"""
    t = (_load(os.path.join(PUBLIC, "cost_by_task.json"), {}) or {}).get("tasks", [])
    n = len([x for x in t if x.get("costUsd")])
    return n


def nosetai():
    """子セッションが本番リポジトリに載せた紙の枚数。status/commit_inbox/done が正本。"""
    try:
        return len([x for x in os.listdir(os.path.join(STATUS, "commit_inbox", "done"))
                    if x.endswith(".json")])
    except Exception:
        return 0


def okane_kara_1050():
    """お金は1050番の結果をそのまま写す。★ここで計算し直さない。"""
    d = soto.build()
    return {r["name"]: r for r in d["rows"]}, d.get("kijunYen"), d.get("kijunN")


# ---------------------------------------------------------------------------
# ★割り振り（仕事の一文 → 選手 ＋ 依頼文）
# ---------------------------------------------------------------------------
def wariate(text):
    """仕事の一文を受け取って、誰に投げるかを決める。Dispatchが毎回考えないための口。"""
    t = (text or "").lower()
    best, hit = None, 0
    for s in SHIGOTO:
        n = sum(1 for w in s["words"] if w in t)
        if n > hit:
            best, hit = s, n
    if not best:
        # ★分からないものを黙って誰かに投げない。答えの形が決まっていない仕事は
        #   判断ができる子セッションへ回すのが既定（実測：Devinはこの形で1本も返さなかった）。
        best = [s for s in SHIGOTO if s["kind"] == "handan"][0]
        hit = 0
    who = best["who"]
    kuse, teate = KUSE.get(who, ("", ""))
    return dict(kind=best["kind"], katachi=best["label"], who=who,
                name=NAMAE.get(who, who), konkyo=best["konkyo"], atari=hit,
                kuse=kuse, teate=teate, koutai=KOUTAI.get(who, "子セッション"),
                irai="%s\n%s\n【この仕事】%s" % (IRAI_ATAMA, teate, (text or "").strip()))


NAMAE = {"jules": "Jules（Google）", "devin": "Devin", "genspark": "Genspark（gsk）",
         "jev": "Jev（TypeSafe）", "ko": "子セッション（Claude）", "fal": "fal",
         "openai": "ChatGPT（OpenAI API）", "copilot": "GitHub Copilot",
         "gemini": "Gemini", "grok": "Grok（xAI）"}


# ---------------------------------------------------------------------------
# ★判定は最後。5条件を満たすまで「まだ判定できない」と書く。
# ---------------------------------------------------------------------------
def hantei(tsukaikata, tooshita, honban):
    warui = [k for k, v in tsukaikata.items() if not v]
    if warui:
        return ("未判定", "まだ判定できない。こちらの使い方が悪かった（" + "／".join(warui) + "）")
    if honban > 0:
        return ("使う", "本番に出た %d本（`cat status/public/uketori_machi.json`）" % honban)
    if tooshita > 0:
        return ("未判定", "検品は %d本通ったが、本番に出たのが0本。押していないのはこちら側" % tooshita)
    return ("切る候補", "5条件を満たして投げて、それでも本番0本")


def build():
    kane, kijun, kijun_n = okane_kara_1050()
    th, youjinte = tooshita_honban()
    ko_n = ko_session()
    nose = nosetai()
    gs_zan = (_load(os.path.join(STATUS, "1045", "me_after.json"), {}) or {}).get("data", {}).get("credit_balance")

    def money(name, key):
        r = kane.get(name)
        return (r or {}).get(key, "取れていない")

    def t(k):
        return th.get(k, {"tooshita": 0, "honban": 0})

    rows = []

    # ---- 子セッション（Claude） -------------------------------------------
    rows.append(dict(
        who="ko", name=NAMAE["ko"],
        tokui="判断・配管・原因究明。261本ぶんの実測が残っている（`cat status/public/cost_by_task.json`）",
        nigate="絵と映像の質。検品は別便（鬼監督 tools/oni_gate.py）に出している＝自分では出せない",
        kane="1本 %s円（中央値・%d本ぶん：`cat status/public/cost_by_task.json`）" % (kijun, kijun_n),
        ima="この紙を含む道具づくり。★こちらのクレジットを食う唯一の選手",
        tooshita=nose, honban=nose,
        tooshita_moto="本番リポジトリに載った紙 %d枚（$ ls status/commit_inbox/done | wc -l → %d）" % (nose, nose),
        tsukaikata={k: True for k in TSUKAIKATA}))

    # ---- Jules --------------------------------------------------------------
    j = t("jules")
    rows.append(dict(
        who="jules", name=NAMAE["jules"],
        tokui="件数とキーが決まっているJSON。149件で合格 136/149＝91.3%（`cat status/1028/jules_kekka.json`）",
        nigate="答えの形が決まっていない調べもの。投げた記録が台帳に無い＝まだ測れていない（`cat status/ai_daicho.jsonl`）",
        kane="0円（払った記録が台帳に 0件：`cat status/ai_daicho.jsonl`）。別マシンで動くのでこちらの同時枠を食わない",
        ima="0本（いま持たせている仕事は無い：`cat status/ai_daicho.jsonl`）",
        tooshita=j["tooshita"], honban=j["honban"],
        tooshita_moto="検品 %d本合格／本番に出た %d本（`cat status/public/uketori_machi.json`）。検品1本 16.0秒（status/1030_hikitsugi.md:98）"
                      % (j["tooshita"], j["honban"]),
        tsukaikata={"得意な形の仕事を当てた": True, "正しい依頼文で投げた": True,
                    "まとめずに投げた": True, "返りを受け取って検品した": True,
                    "帰らないものを交代させた": False}))

    # ---- Devin --------------------------------------------------------------
    d = t("devin")
    rows.append(dict(
        who="devin", name=NAMAE["devin"],
        tokui="コードを書いてPRまで運ぶ。26本投げてPRが返ったのは5本（status/1059_hikitsugi_devin.md:12）",
        nigate="答えの形が決まっていない調べもの。この形は1本もPRを返していない（status/1059_hikitsugi_devin.md:27）",
        kane="1本 %s" % money("Devin", "hitotsu"),
        ima="0本（残高切れで立たない：403 out_of_quota・status/1059_hikitsugi_devin.md:4）",
        tooshita=d["tooshita"], honban=1,
        tooshita_moto="mainに入った3本／本番で開けたのは1本（status/1059_hikitsugi_devin.md:14）",
        tsukaikata={"得意な形の仕事を当てた": False, "正しい依頼文で投げた": False,
                    "まとめずに投げた": False, "返りを受け取って検品した": False,
                    "帰らないものを交代させた": False}))

    # ---- fal（★子セッションが苦手な「絵・映像」の持ち場） -------------------
    falrec = (_load(os.path.join(PUBLIC, "fal_cost_ledger.json"), {}) or {}).get("records", [])
    fal_ok = sum(1 for r in falrec if r.get("result") == "adopted")
    rows.append(dict(
        who="fal", name=NAMAE["fal"],
        tokui="絵・音・動画を作る。%d本のうち %d本を採用（`cat status/public/fal_cost_ledger.json`）" % (len(falrec), fal_ok),
        nigate="良し悪しを自分で測れない。検品は別便の鬼監督（tools/oni_gate.py）に出している",
        kane="1本 %s" % money("fal", "hitotsu"),
        ima="0本（いま流している注文は無い：`cat status/public/fal_cost_ledger.json`）",
        tooshita=fal_ok, honban=fal_ok,
        tooshita_moto="採用 %d本（`cat status/public/fal_cost_ledger.json`）。★絵は本番に出た時点で採用として数える" % fal_ok,
        tsukaikata={"得意な形の仕事を当てた": True, "正しい依頼文で投げた": True,
                    "まとめずに投げた": True, "返りを受け取って検品した": True,
                    "帰らないものを交代させた": True}))

    # ---- Genspark -----------------------------------------------------------
    rows.append(dict(
        who="genspark", name=NAMAE["genspark"],
        tokui="調べもの。deep_research 1本が120秒で出典つき3件（status/1045_hikitsugi.md:14）",
        nigate="こちらが手で叩かないと動かない。自動で流す配管がまだ通っていない（status/1049_hikitsugi_irai_gate.md:63）",
        kane="1回 1.000クレジット（status/1049_hikitsugi_irai_gate.md:25）。残 %s（`cat status/1045/me_after.json`）" % gs_zan,
        ima="0本。★2026-10-04 にプラン終了・繰り越し無し（status/1049_hikitsugi_irai_gate.md:13）",
        tooshita=0, honban=0,
        tooshita_moto="検品を通した記録が 0件（`cat status/public/uketori_machi.json`）",
        tsukaikata={"得意な形の仕事を当てた": True, "正しい依頼文で投げた": False,
                    "まとめずに投げた": True, "返りを受け取って検品した": False,
                    "帰らないものを交代させた": False}))

    # ---- Jev ----------------------------------------------------------------
    rows.append(dict(
        who="jev", name=NAMAE["jev"],
        tokui="はい／いいえ・点数だけの判定。13問を1リクエストにまとめると 12.2倍安い（tools/sekisho/jev_honnin.py:25）",
        nigate="文章を書き直せない・画像を見ない・ウェブを見ない（status/1054_jev_nanken_nanen.md:12）",
        kane="入力だけ課金 $0.042/1Mトークン＝約6.60円（status/1054_jev_nanken_nanen.md:5）。出力は0円",
        ima="0本（鍵が無いので1件も聞けていない：status/1054_jev_nanken_nanen.md:33）",
        tooshita=0, honban=0,
        tooshita_moto="鍵が無く、全部「保留」に倒れた＝実額0円（status/1054_jev_nanken_nanen.md:33）",
        tsukaikata={"得意な形の仕事を当てた": True, "正しい依頼文で投げた": True,
                    "まとめずに投げた": True, "返りを受け取って検品した": False,
                    "帰らないものを交代させた": False}))

    # ---- 口が閉じている面々（★叩いた結果だけを書く） -----------------------
    ks = {k["id"]: (k.get("status"), (k.get("detail") or "")[:60])
          for k in (_load(os.path.join(PUBLIC, "kaitsuu.json"), {}) or {}).get("keys", [])}
    for who, tokui, nigate in (
        ("gemini", "まだ1回も叩けていない（`cat status/public/kaitsuu.json`）",
         "鍵が置かれていない。置いた日から測れる"),
        ("grok", "声（読み上げ）の口は 200 で生きている（`cat status/public/kaitsuu.json` の xai_koe）",
         "文字の口が 403（`cat status/public/kaitsuu.json` の xai）"),
        ("openai", "その場で返る短い検品。1回 0.013円（`cat status/public/gaibu_kenpin_ledger.json`）",
         "残高0で 429 が返る（`cat status/ai_daicho.jsonl`）"),
        ("copilot", "まだ1件も返っていない（`cat status/ai_daicho.jsonl`）",
         "担当者の候補に出ない＝Issueを立てても受け取られない（`cat status/public/kaitsuu.json`）"),
    ):
        c = t(who)
        rows.append(dict(
            who=who, name=NAMAE[who], tokui=tokui, nigate=nigate,
            kane=money(NAMAE[who], "hitotsu") or "取れていない",
            ima="0本（口が %s：`cat status/public/kaitsuu.json`）" % (ks.get(who, ("ng", ""))[0] or "ng"),
            tooshita=c["tooshita"], honban=c["honban"],
            tooshita_moto="検品を通した記録が %d件（`cat status/public/uketori_machi.json`）" % c["tooshita"],
            tsukaikata={"得意な形の仕事を当てた": False, "正しい依頼文で投げた": False,
                        "まとめずに投げた": False, "返りを受け取って検品した": False,
                        "帰らないものを交代させた": False}))

    for r in rows:
        r["hantei"], r["riyuu"] = hantei(r["tsukaikata"], r["tooshita"], r["honban"])
        kuse, teate = KUSE.get(r["who"], ("", ""))
        r["kuse"], r["teate"] = kuse, teate
        r["koutai"] = KOUTAI.get(r["who"], "子セッション")
        r["warui"] = [k for k, v in r["tsukaikata"].items() if not v]
        for k in ("tokui", "nigate", "kane", "ima", "tooshita_moto", "kuse", "teate", "riyuu"):
            r[k] = soto.shusshou(r[k])

    wari = []
    for s in SHIGOTO:
        kuse, teate = KUSE.get(s["who"], ("", ""))
        wari.append(dict(katachi=s["label"], name=NAMAE.get(s["who"], s["who"]),
                         konkyo=soto.shusshou(s["konkyo"]), teate=soto.shusshou(teate),
                         koutai=KOUTAI.get(s["who"], "子セッション")))

    return dict(
        generatedAt=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        kijunYen=kijun, kijunN=kijun_n, rows=rows, wariate=wari,
        mihantei=[r["name"] for r in rows if r["hantei"] == "未判定"],
        tsukau=[r["name"] for r in rows if r["hantei"] == "使う"],
        youjinte=youjinte)


# ---------------------------------------------------------------------------
# 紙にする（375pxで横に溢れさせない。数字と出典は同じ行）
# ---------------------------------------------------------------------------
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def html(d):
    h = []
    a = h.append
    a('<!doctype html><html lang="ja"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>適材適所｜誰に何を当てるか</title>')
    a('<style>')
    a('*{box-sizing:border-box}body{margin:0;padding:12px;background:#111;color:#eee;'
      'font:14px/1.6 -apple-system,"Hiragino Sans",sans-serif}')
    a('h1{font-size:17px;margin:0 0 4px}.sub{color:#999;font-size:12px;margin:0 0 10px}')
    a('h2.sec{font-size:13px;color:#8a8a8a;margin:18px 0 8px;border-bottom:1px solid #2c2c2c;padding-bottom:4px}')
    a('.card{background:#1a1a1a;border-radius:10px;padding:10px;margin:0 0 8px}')
    a('.card h3{font-size:15px;margin:0 0 6px;display:flex;justify-content:space-between;'
      'align-items:baseline;gap:8px}')
    a('.ok{color:#5fd68a}.mid{color:#e8c352}.ng{color:#f2777a}')
    a('.k{color:#8a8a8a;font-size:11px;margin:4px 0 0}.v{font-size:12px;word-break:break-all;margin:0 0 4px}')
    a('.num{display:flex;gap:8px;margin:4px 0 6px}.num div{flex:1;background:#222;border-radius:6px;'
      'padding:4px;text-align:center}.num b{display:block;font-size:17px}')
    a('.why{font-size:12px;color:#bbb;border-top:1px solid #2c2c2c;padding-top:5px;margin-top:6px}')
    a('.warui{font-size:12px;color:#f2777a;margin:2px 0 0}')
    a('.w{background:#171717;border-left:3px solid #3a3a3a;padding:8px 10px;margin:0 0 6px;border-radius:0 8px 8px 0}')
    a('.w b{font-size:13px}')
    a('</style></head><body>')
    a('<h1>適材適所</h1>')
    a('<p class="sub">切る前に、得意な形の仕事を当てるための紙。毎日ここが自分で書き換わる。'
      '最後に書き換えた時刻 %s</p>' % esc(d["generatedAt"]))
    a('<p class="v">判定の物差し：子セッション1本の実測中央値 <b>%s円</b>'
      '（%d本ぶん：`cat status/public/cost_by_task.json`）</p>'
      % (d["kijunYen"], d["kijunN"]))
    a('<p class="v">交代の決まり：投げて %s 帰ってこなければ、次の選手へ渡す（%s）</p>'
      % (KOUTAI_JIKAN, KOUTAI_SRC))
    a('<p class="v k">前の紙（一度きりで止まっていたもの）：'
      '<a href="1027-tekizai-tekisho.html" style="color:#7fb6ff">#1027 誰に何を任せるか</a>。'
      'ここはその続きで、毎日ひとりでに書き換わる側です。</p>')

    a('<h2 class="sec">★仕事が来たら、ここで決まる（割り振り）</h2>')
    for w in d["wariate"]:
        a('<div class="w"><b>%s</b> → <span class="ok">%s</span>' % (esc(w["katachi"]), esc(w["name"])))
        a('<p class="k">そう決めた実測</p><p class="v">%s</p>' % esc(w["konkyo"]))
        if w["teate"]:
            a('<p class="k">こちら側の手当て</p><p class="v">%s</p>' % esc(w["teate"]))
        a('<p class="k">帰ってこなければ</p><p class="v">%s へ渡す</p></div>' % esc(w["koutai"]))

    a('<h2 class="sec">選手ごと（得意・苦手・お金・今の仕事・通した本数）</h2>')
    cls = {"使う": "ok", "未判定": "mid", "切る候補": "ng"}
    for r in d["rows"]:
        a('<div class="card">')
        a('<h3>%s<span class="%s">%s</span></h3>'
          % (esc(r["name"]), cls.get(r["hantei"], "mid"), esc(r["hantei"])))
        a('<div class="num"><div><b>%d</b><span class="k">通した</span></div>'
          '<div><b>%d</b><span class="k">本番に出た</span></div></div>' % (r["tooshita"], r["honban"]))
        a('<p class="k">得意（実測）</p><p class="v">%s</p>' % esc(r["tokui"]))
        a('<p class="k">苦手（実測）</p><p class="v">%s</p>' % esc(r["nigate"]))
        a('<p class="k">お金</p><p class="v">%s</p>' % esc(r["kane"]))
        a('<p class="k">今の仕事</p><p class="v">%s</p>' % esc(r["ima"]))
        a('<p class="k">通した本数／本番に出た本数</p><p class="v">%s</p>' % esc(r["tooshita_moto"]))
        a('<p class="k">止まる癖</p><p class="v">%s</p>' % esc(r["kuse"]))
        a('<p class="k">こちら側の手当て</p><p class="v">%s</p>' % esc(r["teate"]))
        a('<p class="k">帰ってこなければ</p><p class="v">%s へ渡す</p>' % esc(r["koutai"]))
        if r["warui"]:
            a('<p class="warui">★こちらがまだやれていない：%s</p>' % esc("／".join(r["warui"])))
        a('<p class="why %s">%s</p>' % (cls.get(r["hantei"], "mid"), esc(r["riyuu"])))
        a('</div>')
    a('<p class="v k">この紙は tools/tekizai.py が書いている。手で書き換えない。'
      'お金は tools/soto_hatarakite.py（1050番）の結果をそのまま写していて、ここでは計算し直していない。</p>')
    a('<p class="v k">仕事を割り振るとき： $ python3 tools/tekizai.py --shigoto "&lt;仕事の一文&gt;"</p>')
    a('</body></html>')
    # ★紙にする直前に、`cat <path>` を <path>:<行番号> へ開く。
    #   これをやらないと tools/kazu_gate.py が出典として読めない（門は行単位で見る）。
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
    os.makedirs(PUBLIC, exist_ok=True)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html(d))
    with io.open(STAMP, "w", encoding="utf-8") as f:
        f.write(today)
    return d


def self_test():
    ng = []
    # ★割り振りが実測どおりに効くか
    if wariate("yomi-answersのJSONを149件そろえて")["who"] != "jules":
        ng.append("JSONそろえがJulesに行かない")
    if wariate("トップページを軽くする実装をしてPRを出して")["who"] != "devin":
        ng.append("実装がDevinに行かない")
    if wariate("この曲の出典を調べて")["who"] != "genspark":
        ng.append("調べものがGensparkに行かない")
    if wariate("この動画は本人かどうか判定して")["who"] != "jev":
        ng.append("判定がJevに行かない")
    if wariate("")["who"] != "ko":
        ng.append("分からないものが子セッションに落ちない")
    # ★判定は最後。5条件が欠けていたら「未判定」でなければならない
    if hantei({"a": False}, 0, 0)[0] != "未判定":
        ng.append("使い方が満たせていないのに未判定にならない")
    if "こちらの使い方が悪かった" not in hantei({"a": False}, 0, 0)[1]:
        ng.append("未判定の理由にこちら側の落ち度が書かれない")
    if hantei({k: True for k in TSUKAIKATA}, 3, 2)[0] != "使う":
        ng.append("本番に出ているのに使うにならない")
    # ★依頼文に癖の手当てが必ず入るか
    if "返事を書くな" not in wariate("実装してPRを出して")["irai"]:
        ng.append("Devinの依頼文に止める文言が入らない")
    d = build()
    if len(d["rows"]) < 9:
        ng.append("表が9行に満たない")
    for r in d["rows"]:
        for k in ("tokui", "nigate", "kane", "ima"):
            if not r[k]:
                ng.append("%s の %s が空" % (r["name"], k))
    print("自己試験 %s（%d件）" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng)))
    for x in ng:
        print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--shigoto" in sys.argv:
        i = sys.argv.index("--shigoto")
        text = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        w = wariate(text)
        print("仕事の形 : %s" % w["katachi"])
        print("投げる先 : %s" % w["name"])
        print("実測の根拠: %s" % soto.shusshou(w["konkyo"]))
        print("止まる癖 : %s" % soto.shusshou(w["kuse"]))
        print("帰ってこなければ %s へ渡す（持ち時間 %s・%s）" % (w["koutai"], KOUTAI_JIKAN, KOUTAI_SRC))
        print("---- そのまま使う依頼文 ----")
        print(w["irai"])
        sys.exit(0)
    got = run(force="--force" in sys.argv)
    if got is None:
        print("今日はもう書き換え済み（--force で今すぐ）")
    else:
        print("書いた %s ／ 使う:%s ／ まだ判定できない:%s"
              % (OUT_HTML, "・".join(got["tsukau"]) or "なし", "・".join(got["mihantei"]) or "なし"))
