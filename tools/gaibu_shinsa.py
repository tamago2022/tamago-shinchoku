#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gaibu_shinsa.py ── 詰める役を外に置く。完了をこちら側が書けなくする。

たまごさん（2026-09-26）:
  「Claudeだけだと裏切られっぱなしで信用できない」
  「★判定する側をClaudeの外に出す。」
  「台帳と実測結果を毎日 公開リポ tamago2022/ai-kaigi に機械でpush（0円）。
    Genspark（Deep Research＝消費0）を監査役にして、台帳と実測を突き合わせて
    『終わってない／嘘がある』を指摘させる。その指摘を台帳に自動で戻す。
    ChatGPT(Codex)にも同じものを読ませる。
    ★こちら側が自分で『完了』と書けない。外の判定が入って初めて完了になる。」

━━ たまごさんのノート「genspark 鬼監督」（tamago_brain）に合わせてある ━━

  ノートの正本：
    「**検品・差し戻し＝◎得意。進捗の常時監視・催促＝✕原理的に無理。**
      俺には常在がない。呼ばれた時だけ起きて、終われば止まる。
      **あなたが成果物やログを持ってきてくれて初めて、俺は検品官として動けます。**」
    「俺の適任ポジションは『常駐の監視役』ではなく
      **『定期的な検品官＋仕様の書き手＋台帳の管理人』**」

  ★だから外のAIに「見張って」とは頼まない。頼んでも構造的にできない。
    こちらが**成果物・差分・ログを束ねて持っていく**。向こうは検品して差し戻し文を返すだけ。
    催促はさせない。催促する係はこちら（tools/hantei.py の判定日）に置いてある。

  ★判定の物差しもノートに合わせる（チャッピー鬼監督レポート）：
    「判定基準は **Alive ではなく Progress**。AIやWorkflowが動いているだけでは進捗ではない。
      企画書を書いた・Issueを作った・コメントした・Aliveだった、は成果に数えない。」
    → だから数えるのは「走らせた本数」ではなく**変わった件数**だけ。

━━ この係がやる4つ ━━
  ① 監査パケットを作る … 台帳（何を何回言われたか）＋実測（URLを叩いた200/中身/差分件数）
  ② 外へ出す          … tools/nageru.py 経由で ai-kaigi（公開）／Genspark／Codex へ
  ③ 指摘を持ち帰る    … 外から返ってきた「終わってない／嘘がある」を台帳へ書き戻す
  ④ 完了の鍵を外に置く … status/gaibu/soto_hantei.json に外のOKが無い限り、
                          どれだけこちらが「完了」と書いても完了にならない

★①と④はこちらだけで完結する（0円・外が黙っていても効く）。
  外が黙っていても「完了」が付かないので、**沈黙はこちらに有利に働かない。**

使い方
    python3 tools/gaibu_shinsa.py            # パケットを作って外へ出す（1日1回）
    python3 tools/gaibu_shinsa.py --packet   # パケットを作るだけ（外へ出さない）
    python3 tools/gaibu_shinsa.py --hirou    # 外から返ってきた指摘を台帳へ戻すだけ
    python3 tools/gaibu_shinsa.py --show
    python3 tools/gaibu_shinsa.py --self-test
"""
from __future__ import annotations

import datetime
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

DIR = os.path.join(ST, "gaibu")
PACKET_JSON = os.path.join(ST, "public", "kansa.json")     # 公開（ai-kaigi から読める）
PACKET_MD = os.path.join(DIR, "kansa.md")                  # 外のAIに読ませる文面
SHITEKI = os.path.join(DIR, "kansa_shiteki.jsonl")         # 外から来た指摘
SOTO = os.path.join(DIR, "soto_hantei.json")               # ★完了の鍵。外だけが開けられる
STATE = os.path.join(DIR, "shinsa_state.json")
LOG = os.path.join(DIR, "shinsa.jsonl")

HATSUGEN = os.path.join(ST, "kioku", "hatsugen.jsonl")
KENPIN = os.path.join(ST, "oni_modoshi", "kenpin.jsonl")
COUNT = os.path.join(ST, "shukudai", "count.jsonl")
AI_DAICHO = os.path.join(ST, "ai_daicho.jsonl")

JST = datetime.timezone(datetime.timedelta(hours=9))
URL_PAGE = "https://tamago2022.github.io/tamago-shinchoku/1152-nankai.html"
URL_JSON = "https://tamago2022.github.io/tamago-shinchoku/status/public/kansa.json"


def now():
    return datetime.datetime.now(JST)


def today():
    return now().strftime("%Y-%m-%d")


def stamp():
    return now().strftime("%Y-%m-%d %H:%M")


def load_json(p, d=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsonl(p, tail=None):
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out[-tail:] if tail else out


def write_text(p, t):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(t)
    os.replace(tmp, p)


def append(p, o):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")


def norm(s):
    return re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "").lower()


# ────────────────────────────────────────── ① 監査パケット


def konshu_no_kazu():
    """★測る数字は「走らせた本数」ではなく『変わった件数』だけ。

      今週言われた件数 … この7日間に初めて言われたもの
      実際に変わった件数 … そのうち、機械の検品を通って完了になったもの
      達成率 … 変わった ÷ 言われた。**たまごさん基準は最低5割。**
    """
    kara = (now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    rows = jsonl(HATSUGEN)
    konshu = [r for r in rows if str(r.get("firstSaid") or "")[:10] >= kara]
    kawatta = [r for r in konshu if (r.get("state") == "完了")]
    n, k = len(konshu), len(kawatta)
    pct = round(100.0 * k / n, 1) if n else 0.0
    return {"iwareta": n, "kawatta": k, "tasseiritsu": pct,
            "kijun": 50.0, "todoiteru": bool(n and pct >= 50.0),
            "kara": kara}


def jissoku():
    """実測。★「やりました」ではなく、機械が叩いた結果だけを載せる。"""
    k = jsonl(KENPIN, tail=200)
    c = jsonl(COUNT, tail=8)
    return {
        "kenpinKensu": len(k),
        "nihyakuOK": len([r for r in k if r.get("ok") and r.get("code") == 200]),
        "hajiita": len([r for r in k if r.get("ok") is False]),
        "hajiitaRiyuu": [{"title": (r.get("title") or "")[:70], "naze": r.get("naze"),
                          "url": r.get("url")} for r in k if r.get("ok") is False][-20:],
        "shukudaiSuii": c,
    }


def packet():
    w = konshu_no_kazu()
    rows = sorted(jsonl(HATSUGEN), key=lambda r: (-int(r.get("count") or 1),
                                                  str(r.get("firstSaid") or "")))
    p = {
        "at": stamp(),
        "nani": "たまごさんに言われたことの台帳と、機械の実測。外のAIに監査してもらうための材料。",
        "page": URL_PAGE,
        "konshu": w,
        "jissoku": jissoku(),
        "daicho": [{
            "iwaretaNichiji": r.get("firstSaidJa") or r.get("firstSaid"),
            "naiyou": r.get("title"),
            "kaisu": r.get("count"),
            "jotai": r.get("state") or "未着手",
            "hantei1w": r.get("hantei1w"), "hantei1m": r.get("hantei1m"),
            "sonogo": r.get("sonogo"),
        } for r in rows[:300]],
        "anatanoyakuwari": (
            "あなたは検品官です。見張りではありません（常在が要る仕事は頼みません）。"
            "この紙に載っている成果物・実測・台帳だけを見て、検品して、差し戻し文を返してください。"),
        "monosashi": (
            "★Alive ではなく Progress で見てください。"
            "『動いている』『Issueを作った』『コメントした』『企画書を書いた』は成果に数えません。"
            "数えるのは：公開物が増えた／売上が増えた／流入が増えた／"
            "手作業が減った／店主の自由時間が増えた／停止時間が減った、のどれか。"),
        "onegai": [
            "この台帳と実測を突き合わせて、『終わっていないのに終わったことになっている』ものを挙げてください。",
            "『動いてはいるが何も変わっていない』ものを、完了扱いから外してください（Alive は成果ではありません）。",
            "『状態＝完了』なのに証拠URLが無いもの、URLが200でないもの、中身が空のものは全部指摘してください。",
            "判定日（hantei1w / hantei1m）を過ぎているのに状態が変わっていないものを挙げてください。",
            "返す形：1行1件で `NG|<内容の先頭30字>|<なぜ>` 。問題が無ければ `OK|<内容>|確認した`。",
        ],
    }
    return p


def packet_md(p):
    L = ["# 監査のお願い（%s）" % p["at"], "",
         "たまごさん（人間）の依頼を機械で集めた台帳と、機械が実際にURLを叩いた実測です。",
         "**作った側（Claude）が自分で「完了」と書けないようにするため、判定を外に出しています。**", "",
         "## 今週の数字（★見るのはここだけ）", "",
         "| 今週言われた件数 | 実際に変わった件数 | 達成率 | 基準 |",
         "|---|---|---|---|",
         "| %d | %d | %s%% | 最低50%%（%s） |" % (
             p["konshu"]["iwareta"], p["konshu"]["kawatta"], p["konshu"]["tasseiritsu"],
             "届いている" if p["konshu"]["todoiteru"] else "★届いていない"),
         "", "## あなたの役割", "",
         "あなたは**検品官**です。見張り役は頼みません（常在が要る仕事はこちらの機械がやります）。",
         "この紙に載っている実測と台帳だけを見て、**差し戻し文**を返してください。",
         "",
         "**物差しは Alive ではなく Progress。**「動いている」「Issueを作った」「コメントした」",
         "「企画書を書いた」は成果に数えません。数えるのは、公開物が増えた／売上が増えた／",
         "流入が増えた／手作業が減った／店主の自由時間が増えた／停止時間が減った、のどれかです。",
         "", "## 実測", "",
         "- 検品した件数：%d／URLが200で中身も入っていた：%d／★弾いた：%d"
         % (p["jissoku"]["kenpinKensu"], p["jissoku"]["nihyakuOK"], p["jissoku"]["hajiita"]),
         "", "## お願いすること", ""]
    L += ["%d. %s" % (i + 1, x) for i, x in enumerate(p["onegai"])]
    L += ["", "## 台帳（言われた日時／内容／回数／状態／1週間後／1ヶ月後／その後）", "",
          "| 言われた日時 | 内容 | 回数 | 状態 | 1週間後 | 1ヶ月後 | 実際どうなったか |",
          "|---|---|---|---|---|---|---|"]
    for d in p["daicho"][:120]:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            d["iwaretaNichiji"], (d["naiyou"] or "").replace("|", "／")[:70],
            d["kaisu"], d["jotai"], d["hantei1w"] or "-", d["hantei1m"] or "-",
            (d["sonogo"] or "―").replace("|", "／")[:60]))
    L += ["", "全文（機械が読む用）: %s" % URL_JSON, "進捗表: %s" % URL_PAGE, ""]
    return "\n".join(L)


# ────────────────────────────────────────── ② 外へ出す


def nageru(saki, odai, honbun):
    """tools/nageru.py に任せる。★口は1本だけ。ここで新しい口を作らない。"""
    p = os.path.join(HERE, "nageru.py")
    if not os.path.exists(p):
        return {"saki": saki, "st": "nageru.py が無い"}
    f = os.path.join(DIR, "kansa_%s.md" % saki)
    write_text(f, honbun)
    try:
        r = subprocess.run(["python3", p, saki, odai, "--body-file", f],
                           capture_output=True, text=True, timeout=180, cwd=REPO)
        return {"saki": saki, "rc": r.returncode,
                "de": ((r.stdout or "") + (r.stderr or ""))[-300:]}
    except Exception as e:
        return {"saki": saki, "rc": None, "de": "%s: %s" % (type(e).__name__, e)}


# ────────────────────────────────────────── ③ 指摘を持ち帰る

# 外のAIに返させる形は `NG|<内容>|<なぜ>` の1行1件だけ。
# 内容が短い件名（「別の件」＝3文字）も来るので、下限を欲張らない。
# 下限を4文字にしていて短い指摘を丸ごと落としていた（2026-09-26 自己試験で発覚）。
_SHITEKI = re.compile(r"^[ \t]*(NG|OK)[ \t]*\|[ \t]*([^|\n]{2,80}?)[ \t]*\|[ \t]*([^\n]{3,200}?)[ \t]*$", re.M)


def hirou():
    """外から返ってきた指摘を拾って台帳に戻す。

    出どころは tools/ai_daicho.py の in の行（tools/github_watch.py が書く）。
    ★ここでは新しい通信をしない。既にある帰りの口をそのまま使う。
    """
    st = load_json(STATE, {}) or {}
    mita = set(st.get("mitaId") or [])
    soto = load_json(SOTO, {}) or {}
    n_ng, n_ok = 0, 0
    for r in jsonl(AI_DAICHO):
        if (r.get("dir") or r.get("direction")) not in ("in", "back", None):
            continue
        rid = str(r.get("id") or r.get("ts") or "")
        if not rid or rid in mita:
            continue
        body = " ".join(str(r.get(k) or "") for k in ("body", "text", "message", "comment"))
        hits = _SHITEKI.findall(body)
        if not hits:
            continue
        mita.add(rid)
        for kekka, naiyou, naze in hits:
            key = norm(naiyou)[:24]
            rec = {"at": stamp(), "kara": r.get("saki") or r.get("from") or "外",
                   "kekka": kekka, "naiyou": naiyou.strip(), "naze": naze.strip()}
            append(SHITEKI, rec)
            if kekka == "OK":
                # ★完了の鍵。外がOKを出したときだけ開く。こちらからは書かない
                soto[key] = {"ok": True, "at": stamp(), "kara": rec["kara"],
                             "naze": naze.strip()[:120]}
                n_ok += 1
            else:
                soto[key] = {"ok": False, "at": stamp(), "kara": rec["kara"],
                             "naze": naze.strip()[:120]}
                n_ng += 1
    st["mitaId"] = list(mita)[-3000:]
    st["lastHirouAt"] = stamp()
    write_text(STATE, json.dumps(st, ensure_ascii=False, indent=1))
    write_text(SOTO, json.dumps(soto, ensure_ascii=False, indent=1))
    return {"ng": n_ng, "ok": n_ok, "kagi": len(soto)}


# ────────────────────────────────────────── ④ 完了の鍵


def soto_ga_mitometa(title):
    """★外が「OK」を出しているか。出ていなければ、何があっても完了にしない。

    他の係（tools/oni_modoshi.py・tools/hantei.py）はこの関数を通してしか
    完了を付けられない。**こちら側に完了を書く口を一切作らない。**
    """
    soto = load_json(SOTO, {}) or {}
    r = soto.get(norm(title)[:24])
    return bool(r and r.get("ok")), (r or {}).get("naze")


def hashiru(dasu=True, dry=False):
    p = packet()
    md = packet_md(p)
    if not dry:
        write_text(PACKET_JSON, json.dumps(p, ensure_ascii=False, indent=1))
        write_text(PACKET_MD, md)
    dashita = []
    if dasu and not dry:
        st = load_json(STATE, {}) or {}
        if st.get("lastDashiHi") != today():        # 1日1回でよい（0円だが騒がしくしない）
            odai = "【監査のお願い】台帳と実測の突き合わせ（%s）" % today()
            for saki in ("genspark", "grok", "codex"):
                dashita.append(nageru(saki, odai, md))
            st["lastDashiHi"] = today()
            write_text(STATE, json.dumps(st, ensure_ascii=False, indent=1))
    h = hirou() if not dry else {"ng": 0, "ok": 0, "kagi": 0}
    rec = {"at": stamp(), "konshu": p["konshu"], "jissoku": {
        k: p["jissoku"][k] for k in ("kenpinKensu", "nihyakuOK", "hajiita")},
        "dashita": dashita, "hirotta": h}
    if not dry:
        append(LOG, rec)
    return rec


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        p = packet()
        for k in ("iwareta", "kawatta", "tasseiritsu", "kijun"):
            if k not in p["konshu"]:
                ng.append("今週の数字に %s が無い" % k)
        if p["konshu"]["kijun"] != 50.0:
            ng.append("基準が5割になっていない")
        if "| 今週言われた件数 |" not in packet_md(p):
            ng.append("外へ出す文面に今週の数字が入っていない")
        ok, _ = soto_ga_mitometa("外がまだ何も言っていない案件")
        if ok:
            ng.append("★外の判定が無いのに完了になっている（鍵が壊れている）")
        m = _SHITEKI.findall("NG|台帳の日時|分が入っていない\nOK|別の件|確認した")
        if len(m) != 2:
            ng.append("外の指摘を読み取れない")
        print("自己試験：%s／今週 言われた%d・変わった%d・達成率%s%%（基準50%%）／台帳%d件"
              % ("OK" if not ng else "NG", p["konshu"]["iwareta"], p["konshu"]["kawatta"],
                 p["konshu"]["tasseiritsu"], len(p["daicho"])))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        p = packet()
        w = p["konshu"]
        print("【外の審査】今週言われた %d件／実際に変わった %d件／達成率 %s%%（基準50%%・%s）"
              % (w["iwareta"], w["kawatta"], w["tasseiritsu"],
                 "届いている" if w["todoiteru"] else "★届いていない"))
        soto = load_json(SOTO, {}) or {}
        print("  外が出した判定：%d件（OK %d／NG %d）"
              % (len(soto), len([1 for v in soto.values() if v.get("ok")]),
                 len([1 for v in soto.values() if not v.get("ok")])))
        print("  指摘の記録：%d行（%s）" % (len(jsonl(SHITEKI)), os.path.relpath(SHITEKI, REPO)))
        return 0
    if "--packet" in a:
        r = hashiru(dasu=False)
    elif "--hirou" in a:
        r = {"hirotta": hirou()}
    else:
        r = hashiru()
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
