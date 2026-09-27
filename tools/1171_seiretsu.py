#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1171番【整列】予約を「朝09:00＝邦楽／夜21:00＝洋楽」に並べ直す。

たまごさんの言葉（2026-09-27・原文）:
  「朝9:00＝邦楽／夜21:00＝洋楽（21時21分ではなく21時00分）」
  「Neil Young・絢香は外す（三日月は残してよい）」

■ なぜ要るか（2026-09-27 実測）
  いまBufferに入っている10本は、ぜんぶ**逆**で入っていた。
      09:00 JST ＝ 洋楽（Green Day / Nick Drake / S&G / Norah / Neil Young …）
      20:00 JST ＝ 邦楽（秋桜 / 三日月 / EGO-WRAPPIN / キリンジ / 竹内…）
  しかも夜は 21:00 ではなく **20:00** だった。
  1170_hako.py は「これから作る枠」しか見ないので、すでに入っている10本は
  直らない。だからこの係が1回だけ並べ直す。

■ やること（1本ずつ・消さずに時刻だけ書き換える）
  ① いまの予約を取り直す（1叩き）
  ② 1本ずつ「日本の曲か洋楽か」を見て、同じ日付のまま
       邦楽 → その日の 09:00 JST
       洋楽 → その日の 21:00 JST
     へ書き換える（1本につき1叩き。すでに正しいものは0叩き）
  ③ ★外す指定のもの（NOZOKU）は、**本文を控えに保存してから**消す。
     控えは status/1171/nozoita.json に残るので、消えて終わりにはならない。
  ④ 取り直して確かめる（1叩き）。自己申告で「直した」と言わない。

■ 枠について
  Bufferの枠が閉まっている間は1叩きもせず、理由だけ出して終わる。
  枠は 2026-09-28 05:34 JST に戻る。心臓から呼べば戻った直後の周回で走る。

■ 使い方
  python3 tools/1171_seiretsu.py --miru   … 0叩き。控えだけで「何をどう直すか」を出す
  python3 tools/1171_seiretsu.py          … 実際に並べ直す（枠が開いていれば）
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import buffer_kura      # noqa: E402
import buffer_waku      # noqa: E402
import kagi             # noqa: E402
import importlib
irekae = importlib.import_module("1170_irekae")   # 叩き手・書き換え・同定を借りる

JST = datetime.timezone(datetime.timedelta(hours=9))
D = os.path.join(REPO, "status", "1171")
NOZOITA = os.path.join(D, "nozoita.json")
LOG = os.path.join(D, "seiretsu.jsonl")
STAMP = os.path.join(D, ".stamp")

ASA, YORU = "09:00", "21:00"          # ★朝＝邦楽 ／ 夜＝洋楽（21:00。21:21ではない）

# ★たまごさんが名指しで「外す」と言ったもの。
#   絢香は外すが「三日月」だけは残してよい、と言われているので例外に書く。
NOZOKU = ["neil young"]
NOZOKU_NASHI = ["三日月", "mikazuki"]   # この字が本文にあれば外さない


def now():
    return datetime.datetime.now(JST)


def kiroku(rec):
    rec = dict(rec)
    rec.setdefault("at", now().strftime("%F %T"))
    try:
        os.makedirs(D, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def nihongo_ga_aru(s):
    for c in s or "":
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) \
           or (0x3400 <= o <= 0x4DBF) or (0xFF66 <= o <= 0xFF9D):
            return True
    return False


def kotoba(text):
    """その本文が日本の曲(ja)か洋楽(en)か。

    ★「Artist — Song」の行だけを見る。本文のコピーは英語で書いてあるので、
      本文ぜんぶを見ると邦楽まで en に見えてしまう（実測）。
    """
    for ln in (text or "").split("\n"):
        if "—" in ln or "–" in ln:
            return "ja" if nihongo_ga_aru(ln) else "en"
    return "ja" if nihongo_ga_aru(text or "") else "en"


def nozoku_ka(text):
    t = (text or "").lower()
    if any(k.lower() in t for k in NOZOKU_NASHI):
        return False
    return any(k in t for k in NOZOKU)


def aruberi_jikoku(dt, lang):
    """同じ日付のまま、あるべき時刻へ。"""
    hhmm = ASA if lang == "ja" else YORU
    hh, mm = [int(x) for x in hhmm.split(":")]
    return dt.replace(hour=hh, minute=mm, second=0, microsecond=0)


def utc(dt):
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def kangaeru(posts):
    """1本ずつ「どうするか」を決める。叩かない。"""
    plan = []
    for p in posts:
        text = p.get("text") or ""
        t = irekae.jst(p.get("dueAt") or "")
        lang = kotoba(text)
        midashi = irekae.midashi(text)
        if nozoku_ka(text):
            plan.append({"id": p.get("id"), "dou": "外す", "lang": lang,
                         "ima": t.strftime("%F %H:%M") if t else "?",
                         "saki": "", "midashi": midashi, "text": text})
            continue
        if not t:
            plan.append({"id": p.get("id"), "dou": "時刻が読めない", "lang": lang,
                         "ima": "?", "saki": "", "midashi": midashi, "text": text})
            continue
        saki = aruberi_jikoku(t, lang)
        # ★もう過ぎている時刻へは動かさない（過去に置くと即座に出るか消える）。
        #   出る直前のものは触らずにそのまま出してしまう方が安全。
        if saki != t and saki <= now() + datetime.timedelta(minutes=15):
            plan.append({"id": p.get("id"), "dou": "見送り（もう間に合わない）",
                         "lang": lang, "ima": t.strftime("%F %H:%M"),
                         "saki": "", "midashi": midashi, "text": text})
            continue
        plan.append({"id": p.get("id"),
                     "dou": "そのまま" if saki == t else "時刻を直す",
                     "lang": lang, "ima": t.strftime("%F %H:%M"),
                     "saki": saki.strftime("%F %H:%M"), "saki_utc": utc(saki),
                     "midashi": midashi, "text": text})
    return plan


def kaku(plan):
    print("── いま予約に入っているもの（%d 本）" % len(plan))
    for i, e in enumerate(plan, 1):
        mark = {"そのまま": "  ", "時刻を直す": "→ ", "外す": "✕ ",
                "見送り（もう間に合わない）": "… "}.get(e["dou"], "? ")
        saki = e["saki"] or ("（外す）" if e["dou"] == "外す" else "（%s）" % e["dou"])
        print("  %2d %s%s %s → %s  %s"
              % (i, mark, "邦楽" if e["lang"] == "ja" else "洋楽",
                 e["ima"], saki, e["midashi"]))
    n = sum(1 for e in plan if e["dou"] == "時刻を直す")
    x = sum(1 for e in plan if e["dou"] == "外す")
    m = sum(1 for e in plan if e["dou"].startswith("見送り"))
    print("直すもの %d 本／外すもの %d 本／見送り %d 本／そのまま %d 本"
          % (n, x, m, len(plan) - n - x - m))
    return n + x


def miru():
    y = buffer_kura.yoyaku_yomu()
    ps = y.get("yoyaku") or []
    print("Bufferの枠:", buffer_waku.riyuu())
    print("控えの時点:", y.get("at") or "-")
    if not ps:
        print("控えが空。枠が戻ってから取り直します（1叩き）。")
        return 0
    kaku(kangaeru([{"id": p.get("id"), "text": p.get("text"),
                    "dueAt": p.get("dueAt")} for p in ps]))
    return 0


def main():
    if "--miru" in sys.argv:
        return miru()
    # ★一度並べ直したら二度とやらない（心臓から毎周回呼ばれても0叩きで退く）
    if os.path.exists(STAMP) and "--now" not in sys.argv:
        return 0
    if not buffer_waku.ake():
        print(buffer_waku.riyuu())
        print("★1叩きもしていません。枠が戻ってからもう一度呼んでください。")
        return 10
    tok = kagi.get("BUFFER_ACCESS_TOKEN")
    if not tok:
        print("鍵が無い")
        return 2

    org, chid = irekae.channel(tok)      # ★蔵にあれば0叩き。無い時だけ探して覚える
    def hiku():
        e = ((irekae.gql(tok, irekae.Q_SCHED, {"o": org, "c": [chid]})
              .get("data") or {}).get("posts") or {}).get("edges") or []
        return sorted([x["node"] for x in e], key=lambda x: x.get("dueAt") or "")

    ps = hiku()
    plan = kangaeru(ps)
    naosu = kaku(plan)
    if not naosu:
        print("直すところはありません。")
        kiroku({"result": "直すところ無し", "n": len(ps)})
        return 0

    # ★外すものは、先に本文を控えへ保存してから消す
    nozoku = [e for e in plan if e["dou"] == "外す"]
    if nozoku:
        hikae = []
        try:
            hikae = json.load(io.open(NOZOITA, encoding="utf-8"))
        except Exception:
            hikae = []
        for e in nozoku:
            hikae.append({"at": now().strftime("%F %T"), "id": e["id"],
                          "due": e["ima"], "midashi": e["midashi"],
                          "text": e["text"],
                          "naze": "たまごさんが名指しで外すと言ったもの"})
        os.makedirs(D, exist_ok=True)
        io.open(NOZOITA, "w", encoding="utf-8").write(
            json.dumps(hikae, ensure_ascii=False, indent=1))
        print("外すものの本文を控えた: %s" % NOZOITA)

    kekka = []
    for e in plan:
        if e["dou"] == "時刻を直す":
            ok = irekae.dueAt_wo_kaku(tok, e["id"], e["saki_utc"])
            kekka.append({"id": e["id"], "dou": "時刻", "ok": bool(ok),
                          "ima": e["ima"], "saki": e["saki"],
                          "midashi": e["midashi"]})
            print("  %s %s → %s  %s" % ("○" if ok else "★失敗",
                                        e["ima"], e["saki"], e["midashi"]))
        elif e["dou"] == "外す":
            r = irekae.gql(tok, irekae.M_DEL, {"input": {"id": e["id"]}})
            dp = (r.get("data") or {}).get("deletePost") or {}
            ok = bool((dp.get("post") or {}).get("id"))
            kekka.append({"id": e["id"], "dou": "外す", "ok": ok,
                          "midashi": e["midashi"],
                          "error": dp.get("message") or ""})
            print("  %s 外した %s" % ("○" if ok else "★失敗", e["midashi"]))

    # ★取り直して確かめる（自己申告にしない）
    ato = hiku()
    plan2 = kangaeru(ato)
    print("── 直したあと")
    nokori = kaku(plan2)
    buffer_kura.yoyaku_kaku({"cap": 10,
                             "yoyaku": buffer_kura.naraberu(ato, irekae.jst),
                             "slots": ["09:00=ja", "21:00=en"]})
    kiroku({"result": "並べ直した" if nokori == 0 else "★まだ %d 本ずれている" % nokori,
            "kekka": kekka, "n_mae": len(ps), "n_ato": len(ato)})
    try:
        os.makedirs(D, exist_ok=True)
        io.open(STAMP, "w", encoding="utf-8").write(now().strftime("%F %T"))
    except Exception:
        pass
    return 0 if nokori == 0 else 9


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        kiroku({"result": "落ちた", "error": str(ex)[:300]})
        print("落ちた:", ex)
        sys.exit(1)
