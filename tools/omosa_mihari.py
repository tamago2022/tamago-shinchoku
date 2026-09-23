#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1057番【重さの見張り】ごきげん補給所が重くなったことに、たまごさんより先に気づく係。

━━ なぜ要るか（2026-09-24・たまごさんの注文）━━

  「穴を塞ぐのではなく、パイプごと替える。同じ重さが2回目に出たら、直さずに素材を替える。」
  「重さの見張りを心臓に相乗りさせて1日1回走らせる。前回比+5%超で赤。★赤のときだけ知らせる。」

  これまで重さは **人が思い出したときにだけ** 測られていた。だから
  「いつの間にか3MBに戻っていた」が何度でも起きる。1日1回、機械が測って、
  **悪くなった時だけ** 声を出す。良い日は黙っている（黙っていることが正常の合図）。

━━ 係の分け方（kohyou_kanshi / kohyou_osu と同じ思想）━━

  この係は **測って判定して知らせるだけ。直さない。**
  直すのは人（か別の便）。測った本人が直すと、誰も嘘を見つけられなくなる。

━━ 赤の線（1か所にしか書かない）━━

  ・総バイトが **前回比 +5% 超** → 赤
  ・総バイトが **1,048,576 (1MB) 超**  → 赤（たまごさんが決めた上限）
  ・CLS が **0.1 超**                  → 赤（読んでる途中で画面が飛ぶ量）
  ・測定そのものが失敗                 → 黄（重さの話ではないので赤にしない）

━━ 安全 ━━

  ・1日1回だけ実際に測る（それ以外の呼び出しは数ミリ秒で戻る＝心臓は重くならない）
  ・GETだけ。外部AIを1回も呼ばない。課金0。
  ・たまごさんの普段のブラウザには触らない（omosa.mjs が毎回その場限りの一時プロファイルを使う）
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE = os.path.join(REPO, "status", "omosa_mihari.json")
LOG = os.path.join(REPO, "status", "omosa_mihari_log.jsonl")
HUMAN = os.path.join(REPO, "status", "omosa_mihari.log")
LAST = os.path.join(REPO, "status", "omosa_last.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")

ZOU_GENDO = 1.05          # 前回比 +5% 超で赤
BYTE_GENDO = 1048576      # 1MB
CLS_GENDO = 0.1
HAKARU_KANKAKU = 20 * 3600   # 1日1回（20時間あけば次を測る）
OMOSA_TIMEOUT = 300


def _load(path, dflt):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dflt


def _now():
    return time.strftime("%F %T")


def hakaru():
    """omosa.mjs を1回走らせて status/omosa_last.json を最新にする。"""
    try:
        p = subprocess.run(["node", os.path.join(HERE, "omosa.mjs"), "--phase", "bytes"],
                           capture_output=True, text=True, timeout=OMOSA_TIMEOUT, cwd=REPO)
        return p.returncode, (p.stderr or "")[-400:]
    except Exception as e:
        return -1, repr(e)[:300]


def han(ima, mae):
    """赤か青かを決める。★規則はここ1か所にしか書かない。"""
    riyuu = []
    for w in sorted(ima.keys()):
        cur = ima[w]
        total, cls = cur.get("total"), cur.get("cls")
        if total is None:
            continue
        if total > BYTE_GENDO:
            riyuu.append("%spx 総バイト %s が上限 1MB を超えています" % (w, f"{total:,}"))
        old = (mae or {}).get(w, {}).get("total")
        if old:
            zou = total / old - 1
            if zou > ZOU_GENDO - 1:
                riyuu.append("%spx 総バイトが前回比 +%.1f%%（%s → %s）"
                             % (w, zou * 100, f"{old:,}", f"{total:,}"))
        if cls is not None and cls > CLS_GENDO:
            riyuu.append("%spx CLS %.3f が 0.1 を超えています（読んでいる途中で画面が飛ぶ）" % (w, cls))
    return ("赤" if riyuu else "青"), riyuu


def shiraseru(riyuu, ima, mae):
    """★赤のときだけ知らせる。青の日は1行もどこにも出さない（黙っているのが正常の合図）。"""
    honbun = "／".join(riyuu)
    try:
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "n": "1057-omosa-mihari",
                "type": "omosa_akai",
                "title": "ごきげん補給所が重くなりました",
                "message": honbun + "｜直す前に tools/omosa.mjs で実測し直すこと。"
                           "直した後も同じ物差しで測って、数字で比べる。",
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run():
    st = _load(STATE, {})
    if time.time() - float(st.get("last_run", 0)) < HAKARU_KANKAKU:
        return  # 1日1回。それ以外は即座に戻る（心臓を待たせない）

    st["last_run"] = time.time()
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass

    rc, err = hakaru()
    d = _load(LAST, {})
    ima = {}
    for w, v in (d.get("byWidth") or {}).items():
        ima[w] = {"total": (v.get("bytes") or {}).get("total"), "cls": v.get("cls"),
                  "lcpMs": v.get("lcpMs")}

    if not any(v.get("total") for v in ima.values()):
        line = "%s 黄 測れませんでした（rc=%s %s）。重さの話ではないので赤にしません" % (_now(), rc, err[:120])
        _kaku(line, {"iro": "黄", "rc": rc, "err": err[:200]})
        return

    mae = st.get("mae") or {}
    iro, riyuu = han(ima, mae)
    if iro == "赤":
        shiraseru(riyuu, ima, mae)

    st["mae"] = ima
    st["last_iro"] = iro
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass

    matome = " ".join("%spx=%s%s" % (w, f"{v['total']:,}" if v.get("total") else "?",
                                     ("/CLS%.3f" % v["cls"]) if v.get("cls") is not None else "")
                      for w, v in sorted(ima.items()))
    line = "%s %s %s%s" % (_now(), iro, matome, ("｜" + "／".join(riyuu)) if riyuu else "")
    _kaku(line, {"iro": iro, "ima": ima, "mae": mae, "riyuu": riyuu})


def _kaku(line, obj):
    try:
        with open(HUMAN, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        obj["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    if "--force" in sys.argv:
        st = _load(STATE, {})
        st["last_run"] = 0
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    if "--selftest" in sys.argv:
        # ★規則が効いているかを、実物を触らずに確かめる（課金0・ネットに出ない）
        ng = 0
        iro, r = han({"375": {"total": 900000, "cls": 0.05}}, {"375": {"total": 890000}})
        if iro != "青": print("NG 1 増えていないのに赤:", r); ng += 1
        iro, r = han({"375": {"total": 950000, "cls": 0.05}}, {"375": {"total": 890000}})
        if iro != "赤": print("NG 2 +6.7%なのに青"); ng += 1
        iro, r = han({"375": {"total": 1100000, "cls": 0.05}}, {"375": {"total": 1090000}})
        if iro != "赤": print("NG 3 1MB超なのに青"); ng += 1
        iro, r = han({"375": {"total": 900000, "cls": 0.169}}, {"375": {"total": 900000}})
        if iro != "赤": print("NG 4 CLS0.169なのに青"); ng += 1
        iro, r = han({"375": {"total": 900000, "cls": None}}, {})
        if iro != "青": print("NG 5 前回が無いのに赤:", r); ng += 1
        print("selftest", "OK" if ng == 0 else "NG=%d" % ng)
        sys.exit(1 if ng else 0)
    run()
