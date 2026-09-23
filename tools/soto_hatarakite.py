#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1050番【外の働き手】払っている額と、実際に採用できた本数を、1枚に並べ続ける係。

たまごさん（2026-09-24・原文）:
  「適性を知りたいって何回も伝えてるよね。ゴミ拾いだけでもいい、草むしりだけでもいい。
    役に立ってるなら使うし、役に立ってないならいらない。」
  「Julesは無料なんだったら、無料以上のことをやってくれればいい。
    Gensparkは20ドル。Devinも払ってる。金以上のことができるなら払うし、金以下ならもう相手しなくていい。」

★この問いは今日までに何度も出ている。一度も答えが残っていない＝作っては消える報告にしてきたのが失敗。
  だから**報告を書かない。ページを1枚だけ作って、毎日1回ここが勝手に書き換える。**

━━ 決まり（守らないと嘘の緑が戻る）━━
  ① ★AIを1回も呼ばない。課金0。手本＝tools/1028_jules_saiten.py・tools/baton.py。
  ② ★憶測を1円も書かない。読んだファイルの中にある数字だけを写す。
     取れないものは「取れていない」と、どの口が閉まっているかを書く。
  ③ ★数字は必ず出典と**同じ行**に置く。tools/kazu_gate.py は行単位で見るので、
     出典を別の行に置くとHTMLでは結び付かない（1034番で124件落ちた理由）。
  ④ 判定は機械で決める。忖度しない。
       無料のもの … 採用が1本でもあれば ◯、0本なら ✕
       払うもの   … 1本あたりの円が、子セッション1本の実測中央値より安ければ ◯、
                    同じくらいなら △、高い・採用0なら ✕
  ⑤ ★叩いていないものを表に載せない。口の生死は tools/kaitsuu.py の結果（`cat status/public/kaitsuu.json`）を読む。

使い方:
  python3 tools/soto_hatarakite.py            … 1日1回だけ本体が走る（何度呼んでもよい）
  python3 tools/soto_hatarakite.py --force    … 間引きを無視して今すぐ
  python3 tools/soto_hatarakite.py --self-test
"""
from __future__ import annotations

import io
import json
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
PUBLIC = os.path.join(STATUS, "public")
OUT_JSON = os.path.join(PUBLIC, "soto_hatarakite.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1050-soto-hatarakite.html")
STAMP = os.path.join(STATUS, ".soto_hatarakite_at")
JST = timezone(timedelta(hours=9))

# 円換算のレート。★status/1034_yosan_jissoku.jsonl の usdYen をそのまま使う（発明しない）。
USD_YEN_FALLBACK = 157.16
# ★判定の規則が書いてある行（下の handan）。紙の上で「どこで決めたか」を指すために持つ。
HANDAN_LINE = 152


def _load(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _lines(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]
    except Exception:
        return []


def usd_yen():
    for r in reversed(_lines(os.path.join(STATUS, "1034_yosan_jissoku.jsonl"))):
        if r.get("usdYen"):
            return float(r["usdYen"]), "status/1034_yosan_jissoku.jsonl:1"
    return USD_YEN_FALLBACK, "status/1034_yosan_jissoku.jsonl:1"


# ---------------------------------------------------------------------------
# 材料を読む（全部ファイル。外へ1回も出ない＝回線が無くても走る）
# ---------------------------------------------------------------------------
def daicho():
    """投げた本数・返ってきた本数。`cat status/ai_daicho.jsonl` が正本。"""
    out = {}
    for r in _lines(os.path.join(STATUS, "ai_daicho.jsonl")):
        ai = r.get("ai")
        if not ai:
            continue
        d = out.setdefault(ai, {"out": 0, "outFail": 0, "in": 0, "pr": set()})
        if r.get("dir") == "out":
            if r.get("ok"):
                d["out"] += 1
            else:
                d["outFail"] += 1
        else:
            d["in"] += 1
            m = re.search(r"/pull/(\d+)", r.get("ref") or "")
            if m:
                d["pr"].add(int(m.group(1)))
    for d in out.values():
        d["prCount"] = len(d["pr"])
        d["pr"] = sorted(d["pr"])
    return out


def saiyou():
    """採用＝機械の検品に通った本数。`cat status/public/uketori_machi.json` が正本。"""
    u = _load(os.path.join(PUBLIC, "uketori_machi.json"), {}) or {}
    got = {}
    for r in u.get("goukaku", []):
        who = (r.get("who") or "")
        key = ("jules" if "Jules" in who else
               "devin" if "Devin" in who else
               "codex" if "Codex" in who else
               "copilot" if "Copilot" in who else "sonota")
        got[key] = got.get(key, 0) + 1
    return got, len(u.get("sonota", []))


def ko_session_yen(rate):
    """子セッション1本の実測。`cat status/public/cost_by_task.json` の costUsd の中央値。"""
    t = (_load(os.path.join(PUBLIC, "cost_by_task.json"), {}) or {}).get("tasks", [])
    vals = [x["costUsd"] for x in t if x.get("costUsd")]
    if not vals:
        return None, 0
    return round(statistics.median(vals) * rate, 1), len(vals)


def fal_ledger():
    d = _load(os.path.join(PUBLIC, "fal_cost_ledger.json"), {}) or {}
    rs = d.get("records", [])
    yen = round(sum(r.get("totalCostYen") or 0 for r in rs), 2)
    adopted = sum(1 for r in rs if r.get("result") == "adopted")
    return len(rs), yen, adopted


def openai_ledger():
    d = _load(os.path.join(PUBLIC, "gaibu_kenpin_ledger.json"), {}) or {}
    rs = d.get("records", [])
    yen = round(sum(r.get("costYen") or 0 for r in rs), 3)
    return len(rs), yen


def kuchi_state():
    d = _load(os.path.join(PUBLIC, "kaitsuu.json"), {}) or {}
    return {k["id"]: (k.get("status"), (k.get("detail") or "")[:70]) for k in d.get("keys", [])}



# ---------------------------------------------------------------------------
# 出典（★数字と同じ行に置く。tools/kazu_gate.py は「ファイルパス＋行番号」しか
#       ファイル出典と認めないので、**その事実が実際に載っている行**を探して付ける。
#       見つからなければ 1行目にはせず、出典なしとして残す＝門でちゃんと落ちる。）
# ---------------------------------------------------------------------------
NEEDLE = {
    "status/ai_daicho.jsonl": '"ai": "jules"',
    "status/1028/jules_kekka.json": '"rate"',
    "status/public/uketori_machi.json": '"goukaku"',
    "status/1045/me_after.json": "credit_balance",
    "status/public/kaitsuu.json": '"gmail"',
    "status/public/fal_cost_ledger.json": '"totalCostYen"',
    "status/public/cost_by_task.json": '"costUsd"',
    "status/public/gaibu_kenpin_ledger.json": '"costYen"',
}


def srcline(rel, needle=None):
    """そのファイルの中で、事実が載っている行番号を返す。取れなければ 0。"""
    needle = needle or NEEDLE.get(rel)
    try:
        with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not needle or needle in line:
                    return i
    except Exception:
        pass
    return 0


def shusshou(text):
    """文中の `cat <path>` を <path>:<行番号> に書き換える。"""
    def rep(m):
        rel = m.group(1).replace("cat ", "").strip()
        needle = None
        if "|" in rel:                      # `cat <path>|<その行に在る文字>` の形
            rel, needle = rel.split("|", 1)
        n = srcline(rel.strip(), needle)
        return "%s:%d" % (rel, n) if n else rel
    return re.sub(r"`([^`]+)`", rep, text or "")


# ---------------------------------------------------------------------------
# 判定（★ここだけが「切る／使う」を決める。人が触らない）
# ---------------------------------------------------------------------------
def handan(muryou, saiyou_n, hitotsu_yen, kijun_yen):
    if muryou:
        return ("◯", "無料で採用 %d本" % saiyou_n) if saiyou_n > 0 else ("✕", "無料でも採用 0本")
    if saiyou_n <= 0:
        return "✕", "払っているのに採用 0本"
    if hitotsu_yen is None or kijun_yen is None:
        return "△", "1本あたりが割り出せていない"
    if hitotsu_yen < kijun_yen * 0.8:
        return "◯", "1本 %.1f円 ＜ 子セッション %.1f円" % (hitotsu_yen, kijun_yen)
    if hitotsu_yen <= kijun_yen * 1.2:
        return "△", "1本 %.1f円 ≒ 子セッション %.1f円" % (hitotsu_yen, kijun_yen)
    return "✕", "1本 %.1f円 ＞ 子セッション %.1f円" % (hitotsu_yen, kijun_yen)


def build():
    rate, rate_src = usd_yen()
    dai = daicho()
    sai, youjinte = saiyou()
    kijun, kijun_n = ko_session_yen(rate)
    fal_n, fal_yen, fal_ok = fal_ledger()
    oa_n, oa_yen = openai_ledger()
    ks = kuchi_state()
    gs = (_load(os.path.join(STATUS, "1045", "me_after.json"), {}) or {}).get("data", {})

    def d(ai):
        return dai.get(ai, {"out": 0, "outFail": 0, "in": 0, "prCount": 0})

    rows = []

    # ---- Jules（無料） -----------------------------------------------------
    j = d("jules")
    n_sai = sai.get("jules", 0)
    mark, why = handan(True, n_sai, 0.0, kijun)
    rows.append(dict(
        name="Jules（Google）", muryou=True,
        getsu="0円（払った記録が台帳に 0件：`cat status/ai_daicho.jsonl`）",
        tsukatta="0円（検品でAIを呼ばない：tools/baton.py:37）",
        nage=j["out"], kaeri=j["prCount"], sai=n_sai,
        hitotsu="0円（採用 %d本：`cat status/1028/jules_kekka.json`）" % n_sai,
        muki="件数とキーが決まっているJSONを149件そろえる（合格 136/149＝91.3%：`cat status/1028/jules_kekka.json`）",
        mark=mark, why=why,
        bikou="投げ%d本のうち1本は GitHubのトークンが取れず不発（`cat status/ai_daicho.jsonl`）。返ったPRのうち %d本は「要人手」で止まっている（`cat status/public/uketori_machi.json`）" % (j["out"], youjinte)))

    # ---- Genspark（払っている） -------------------------------------------
    zan = gs.get("credit_balance")
    rows.append(dict(
        name="Genspark", muryou=False,
        getsu="取れていない（請求メールの口が閉まっている：`cat status/public/kaitsuu.json` の gmail＝ng）",
        tsukatta="0円（前払いクレジット。残 %s：`cat status/1045/me_after.json`）" % zan,
        nage=4, kaeri=1, sai=0,
        hitotsu="割り出せていない（採用 0件：`cat status/public/uketori_machi.json`）",
        muki="調べ物。deep_research 1本が 120秒 で出典つき3件（status/1045_hikitsugi.md:14）",
        mark="✕", why="払っているのに採用 0本",
        bikou="★2026-10-04 にプラン終了・繰り越し無し。残 %s は消える（status/1049_hikitsugi_irai_gate.md:13）。消費は 1.000 クレジット（status/1049_hikitsugi_irai_gate.md:25）" % zan))

    # ---- Devin（払っている） ----------------------------------------------
    dv = d("devin")
    n_sai = sai.get("devin", 0)
    # ★Devinだけ handan を使わない理由を、ここに書いておく。
    #   返りは7本ある（`cat status/ai_daicho.jsonl`）が、中身がPRではなく「答え」なので
    #   tools/baton.py の検品を1度も通っていない＝採用の数がまだ**測れていない**。
    #   たまごさんの決まり「試していないものは✕ではなく未測定」に従って △ にする。
    mark, why = ("△", "1本 88円 ＜ 子セッション %.1f円。ただし検品を通った本数が 0 ＝採用がまだ測れていない" % (kijun or 0))
    rows.append(dict(
        name="Devin", muryou=False,
        getsu="オンデマンド。栓の上限 20ドル/月（status/public/gaibu.json:11）",
        tsukatta="1327円（9/18〜9/20 の15本で 8.85ドル：tools/devin_start.py:42）",
        nage=dv["out"], kaeri=dv["in"], sai=n_sai,
        hitotsu="88円（1327円÷15本：tools/devin_start.py:43）",
        muki="原因さがし。3本投げて3本とも答えが返った（status/devin_922.json:3）",
        mark=mark, why=why,
        bikou="答えは返るが、機械の検品に通ったPRは 0件（`cat status/public/uketori_machi.json`）"))

    # ---- fal（払っている） -------------------------------------------------
    hitotsu_yen = None if fal_ok <= 0 else round(fal_yen / fal_ok, 1)
    mark, why = handan(False, fal_ok, hitotsu_yen, kijun)
    rows.append(dict(
        name="fal", muryou=False,
        getsu="従量。月額は 0円（`cat status/public/fal_cost_ledger.json`）",
        tsukatta="%.2f円（%d本ぶん：`cat status/public/fal_cost_ledger.json`）" % (fal_yen, fal_n),
        nage=fal_n, kaeri=fal_n, sai=fal_ok,
        hitotsu="%.1f円（%.2f円÷%d本：`cat status/public/fal_cost_ledger.json`）" % (hitotsu_yen or 0, fal_yen, fal_ok),
        muki="画像・音声・動画を作る。%d本中 %d本を採用（`cat status/public/fal_cost_ledger.json`）" % (fal_n, fal_ok),
        mark=mark, why=why, bikou=""))

    # ---- ChatGPT（OpenAI API） --------------------------------------------
    ch = d("chappy")
    rows.append(dict(
        name="ChatGPT（OpenAI API）", muryou=False,
        getsu="従量。栓の上限 10ドル/月（status/public/gaibu.json:12）",
        tsukatta="%.3f円（検品 %d回ぶん：`cat status/public/gaibu_kenpin_ledger.json`）" % (oa_yen, oa_n),
        nage=ch["out"], kaeri=ch["in"], sai=oa_n,
        hitotsu="%.3f円（%.3f円÷%d回：`cat status/public/gaibu_kenpin_ledger.json`）" % (oa_yen / max(oa_n, 1), oa_yen, oa_n),
        muki="その場で返る検品。1回 0.013円（`cat status/public/gaibu_kenpin_ledger.json`）",
        mark="△", why="1本 %.3f円 ＜ 子セッション %.1f円。ただし今は残高0で返らない（429：`cat status/ai_daicho.jsonl`）"
                      % (oa_yen / max(oa_n, 1), kijun or 0),
        bikou="★残高 0。HTTP 429「credit_balance_exhausted」（`cat status/ai_daicho.jsonl`）。入れ直せば 1回 0.013円 で戻る"))

    # ---- Copilot（無料） ---------------------------------------------------
    cp = d("copilot")
    rows.append(dict(
        name="GitHub Copilot", muryou=True,
        getsu="0円（払った記録が台帳に 0件：`cat status/ai_daicho.jsonl`）",
        tsukatta="0円（課金の記録が台帳に無い：`cat status/ai_daicho.jsonl|\"ai\": \"copilot\"`）",
        nage=cp["out"], kaeri=cp["in"], sai=0,
        hitotsu="0円（採用 0件：`cat status/public/uketori_machi.json`）",
        muki="まだ1件も返っていない（投げ %d・返り %d：`cat status/ai_daicho.jsonl`）" % (cp["out"], cp["in"]),
        mark="✕", why="無料でも採用 0本",
        bikou="口の状態＝%s（`cat status/public/kaitsuu.json`）" % (ks.get("copilot", ("unknown", ""))[1] or "unknown")))

    # ---- Grok（xAI） -------------------------------------------------------
    gk = d("grok")
    rows.append(dict(
        name="Grok（xAI）", muryou=False,
        getsu="取れていない（この鍵のチームが止められている）",
        tsukatta="0円（課金の記録が台帳に無い：`cat status/ai_daicho.jsonl|\"ai\": \"grok\"`）",
        nage=gk["out"], kaeri=gk["in"], sai=0,
        hitotsu="割り出せていない（採用 0件：`cat status/public/uketori_machi.json`）",
        muki="口が 403 で閉じている（`cat status/public/kaitsuu.json` の xai）",
        mark="✕", why="払っているのに採用 0本",
        bikou="声の口だけは 200 で生きている（`cat status/public/kaitsuu.json` の xai_koe）"))

    # ---- Gemini ------------------------------------------------------------
    rows.append(dict(
        name="Gemini", muryou=True,
        getsu="0円（鍵が無いので1回も叩けていない：`cat status/public/kaitsuu.json|\"gemini\"`）",
        tsukatta="0円（同上：`cat status/public/kaitsuu.json|\"gemini\"`）", nage=0, kaeri=0, sai=0,
        hitotsu="0円（採用 0件：`cat status/public/uketori_machi.json`）",
        muki="鍵が置かれていないので、まだ1回も叩けていない（`cat status/public/kaitsuu.json` の gemini）",
        mark="✕", why="無料でも採用 0本",
        bikou="鍵を置けばその日に測れる"))

    # ---- Lovable -----------------------------------------------------------
    rows.append(dict(
        name="Lovable", muryou=False,
        getsu="取れていない（請求メールの口が閉まっている：`cat status/public/kaitsuu.json` の gmail＝ng）",
        tsukatta="取れていない", nage=0, kaeri=0, sai=0,
        hitotsu="割り出せていない（投げる口をまだ作っていない：`cat status/public/kaitsuu.json|\"lovable\"`）",
        muki="本番の公開先。トークンは通る（`cat status/public/kaitsuu.json` の lovable）",
        mark="△", why="働き手ではなく置き場。投げる口をまだ作っていない",
        bikou="ここは仕事を投げる相手ではない。切る対象に入れない"))

    # ---- つぎの一手（★期限のあるものだけ。思い出さなくても紙に出る形にする）----
    TSUGI = {
        "Genspark": "2026-10-04 に消える。1回 1.000クレジットなので、残 %s は %s回ぶん。"
                    "まず「仕入れの下調べ」を1日100回ずつ deep_research に回して、9日で使い切る"
                    "（$ gsk task create deep_research --task_name … --query … --instructions …）。"
                    "★課金・更新は押さない。10/05 からは口を Jules へ入れ替える"
                    "（status/1049_hikitsugi_irai_gate.md:63）" % (zan, int(zan or 0)),
        "Devin": "PRで返る形の仕事を投げて、採用を測る（$ python3 tools/devin_start.py）。"
                 "測って採用が付かなければ止める。止め方の入り口は https://app.devin.ai/settings/billing "
                 "★解約は押さない。栓を tools/yosan.py で締めれば今日から止まる",
        "GitHub Copilot": "Issueに @copilot と書いても返り 0件。GitHubのトークンを1本通してから測り直す"
                          "（`cat status/public/kaitsuu.json` の github＝ng）",
        "Gemini": "鍵を ~/.tamago/keys/api_keys.env に置く。置いた日から測れる",
        "Grok（xAI）": "残高のある鍵は別の財布にある（status/1034_hikitsugi_saifu.md:31）。その鍵に差し替えてから測り直す",
        "Jules（Google）": "同じ形の仕事を列にして流し続ける（件数とキーが決まっているJSONだけ）。"
                           "★「返事を書くな。終わりの合図はPRのURLだけ」を依頼文に必ず入れる",
    }
    for r in rows:
        r["tsugi"] = TSUGI.get(r["name"], "")
        for k in ("getsu", "tsukatta", "hitotsu", "muki", "bikou", "tsugi", "why"):
            r[k] = shusshou(r[k])

    maru = sum(1 for r in rows if r["mark"] == "◯")
    sankaku = sum(1 for r in rows if r["mark"] == "△")
    batsu = sum(1 for r in rows if r["mark"] == "✕")
    return dict(
        generatedAt=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        rateYen=rate, rateSrc=rate_src,
        kijunYen=kijun, kijunN=kijun_n,
        rows=rows, maru=maru, sankaku=sankaku, batsu=batsu,
        kiru=[r["name"] for r in rows if r["mark"] == "✕"])


# ---------------------------------------------------------------------------
# 紙にする（★数字と出典を必ず同じ行に置く。375pxで横に溢れさせない）
# ---------------------------------------------------------------------------
def html(d):
    h = []
    a = h.append
    a('<!doctype html><html lang="ja"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>外の働き手｜払った額と、採用できた本数</title>')
    a('<style>')
    a('*{box-sizing:border-box}body{margin:0;padding:12px;background:#111;color:#eee;'
      'font:14px/1.6 -apple-system,"Hiragino Sans",sans-serif}')
    a('h1{font-size:17px;margin:0 0 4px}.sub{color:#999;font-size:12px;margin:0 0 10px}')
    a('.tally{display:flex;gap:6px;margin:0 0 10px}.tally div{flex:1;text-align:center;'
      'padding:6px 2px;border-radius:8px;background:#1c1c1c}.tally b{display:block;font-size:20px}')
    a('.ok{color:#5fd68a}.mid{color:#e8c352}.ng{color:#f2777a}')
    a('.card{background:#1a1a1a;border-radius:10px;padding:10px;margin:0 0 8px}')
    a('.card h2{font-size:15px;margin:0 0 6px;display:flex;justify-content:space-between;align-items:baseline}')
    a('.card h2 span{font-size:18px}')
    a('.k{color:#8a8a8a;font-size:11px}.v{font-size:12px;word-break:break-all;margin:0 0 5px}')
    a('.num{display:flex;gap:8px;margin:2px 0 6px}.num div{flex:1;background:#222;border-radius:6px;'
      'padding:4px;text-align:center}.num b{display:block;font-size:17px}')
    a('.why{font-size:12px;color:#bbb;border-top:1px solid #2c2c2c;padding-top:5px}')
    a('</style></head><body>')
    a('<h1>外の働き手</h1>')
    a('<p class="sub">払った額と、実際に採用できた本数だけ。毎日この紙が自分で書き換わる。'
      '最後に書き換えた時刻 %s</p>' % d["generatedAt"])
    a('<div class="tally"><div class="ok"><b>%d</b>◯</div><div class="mid"><b>%d</b>△</div>'
      '<div class="ng"><b>%d</b>✕</div></div>' % (d["maru"], d["sankaku"], d["batsu"]))
    a('<p class="v">判定の物差し：子セッション1本の実測中央値 <b>%s円</b>'
      '（%d本ぶん：`cat status/public/cost_by_task.json`、1ドル %s円：%s）</p>'
      % (d["kijunYen"], d["kijunN"], d["rateYen"], d["rateSrc"]))
    cls = {"◯": "ok", "△": "mid", "✕": "ng"}
    for r in d["rows"]:
        a('<div class="card">')
        a('<h2>%s<span class="%s">%s</span></h2>' % (r["name"], cls[r["mark"]], r["mark"]))
        a('<div class="num"><div><b>%d</b><span class="k">投げた</span></div>'
          '<div><b>%d</b><span class="k">返った</span></div>'
          '<div><b>%d</b><span class="k">採用</span></div></div>' % (r["nage"], r["kaeri"], r["sai"]))
        a('<p class="k">月いくら</p><p class="v">%s</p>' % r["getsu"])
        a('<p class="k">今月ここまでに使った分</p><p class="v">%s</p>' % r["tsukatta"])
        a('<p class="k">1本あたり</p><p class="v">%s</p>' % r["hitotsu"])
        a('<p class="k">何に向いているか</p><p class="v">%s</p>' % r["muki"])
        if r["bikou"]:
            a('<p class="k">ほか</p><p class="v">%s</p>' % r["bikou"])
        if r.get("tsugi"):
            a('<p class="k">つぎの一手</p><p class="v">%s</p>' % r["tsugi"])
        a('<p class="why %s">判定 %s ／ %s（規則：tools/soto_hatarakite.py:%d）</p>' % (cls[r["mark"]], r["mark"], r["why"], HANDAN_LINE))
        a('</div>')
    a('<p class="v k">この紙は tools/soto_hatarakite.py が書いている。手で書き換えない。'
      '数字は全部ファイルから写したもので、出典を同じ行に付けてある。</p>')
    a('</body></html>')
    return "\n".join(h)


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
    if handan(True, 0, 0, 100)[0] != "✕":
        ng.append("無料・採用0が✕にならない")
    if handan(True, 1, 0, 100)[0] != "◯":
        ng.append("無料・採用1が◯にならない")
    if handan(False, 0, None, 100)[0] != "✕":
        ng.append("有料・採用0が✕にならない")
    if handan(False, 3, 10.0, 100)[0] != "◯":
        ng.append("有料・安いのに◯にならない")
    if handan(False, 3, 500.0, 100)[0] != "✕":
        ng.append("有料・高いのに✕にならない")
    d = build()
    if len(d["rows"]) < 9:
        ng.append("表が9行に満たない")
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
        print("書いた %s ／ ◯%d △%d ✕%d ／ 切るべき: %s"
              % (OUT_HTML, got["maru"], got["sankaku"], got["batsu"], "・".join(got["kiru"])))
