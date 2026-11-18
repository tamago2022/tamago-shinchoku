#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""何がクレジットを使っているか（出どころ別×週）。2026-11-19 店主「内訳がざっくりすぎて分からない。無駄な作業でどれぐらい消費していたか」。

入力：status/teiki/z1119.json（tools/teiki_uchiwake_atsume.py が全会話ログから集めたもの・公開しない）
      status/teiki/plan-usage-history.copy.json（Claudeアプリが自分で書く週枠の％の写し）・status/pace_history.jsonl
出力：status/public/teiki_uchiwake.json（数字だけ・会話の中身は出さない）→ tools/teiki_ichiran.py が表の一番上に出す。
AIは呼ばない。使い方：python3 tools/teiki_uchiwake.py ／ --self-test

数え方：
  ・会話ログ（~/.claude/projects と Cowork の会話）の assistant 行の usage（input／output／キャッシュ書き込み／キャッシュ読み）を
    同じ返事が2回書かれた分（message.id＋requestId）を除いて足す。子エージェントの分は親の会話の出どころに入れる。
  ・出どころは、アプリの札（定期タスク名・sessionType=dispatch_child 等）と、会話の最初の依頼文の頭で見分ける。
  ・週は週枠のリセット（火曜18時）で区切る。
  ・「重み」＝ input×1＋キャッシュ書き込み×1.25＋キャッシュ読み×0.1＋output×5（公開されているAPI料金の比。モデルの違いは入れていない）。
    週枠の数え方は公開されていないので、週枠の％＝その週の重みの割合×その週の記録された％、は【推測】。
"""
import collections
import datetime as D
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "status", "teiki", "z1119.json")
OUT = os.path.join(REPO, "status", "public", "teiki_uchiwake.json")

HEART = [("題名係", "進捗表の見出し係"), ("1+1は？", "ログイン確認"), ('Translation job for "Joy', "自動翻訳(1191)"),
         ("You romanize", "曲名ローマ字"), ("コピーを書く編集者", "コピー直し"), ("棚に並べるカードの題名", "題名直し"),
         ("OKとだけ答えて", "生存確認")]
CATS = ["留守番の見回り", "ほかの定期タスク", "心臓のAI係", "工場の子セッション", "工場の検品", "Dispatch本体", "Dispatchの子",
        "店主との会話", "不明"]
# 週（火曜18時リセット）。％は Claudeアプリの記録（plan-usage-history）と工場の写し（pace_history）から、その週の最後に分かっている値。
WEEKS = [
    ("10/20〜10/27", D.datetime(2026, 10, 20, 18), D.datetime(2026, 10, 27, 18), 56, "10/23 12:10 のアプリの記録56%が最後（それ以降は記録なし＝実際はそれ以上）"),
    ("10/27〜11/03", D.datetime(2026, 10, 27, 18), D.datetime(2026, 11, 3, 18), 63, "11/02 03:01 のアプリの記録63%が最後（それ以降は記録なし＝実際はそれ以上）"),
    ("11/03〜11/10", D.datetime(2026, 11, 3, 18), D.datetime(2026, 11, 10, 18), 100, "11/10 04:46 アプリの記録100%（上限に当たった）"),
    ("11/10〜11/17", D.datetime(2026, 11, 10, 18), D.datetime(2026, 11, 17, 18), 87.4, "11/17 リセット前の工場の写し（pace_history）87.4%"),
    ("11/17〜いま", D.datetime(2026, 11, 17, 18), D.datetime(2026, 11, 24, 18), 25, "11/19 04:22 の工場の写し25%（週の途中）"),
]
RUSUBAN_TOMETA = D.datetime(2026, 10, 11, 23)   # 中身を「停止済みと返すだけ」にした時刻（SKILL.md の更新時刻 10/11 23:10）


def omomi(b):
    return b[0] * 1 + b[2] * 1.25 + b[3] * 0.1 + b[1] * 5


def bunrui(rows):
    def cat0(r):
        m = r.get("meta") or {}
        st = r.get("task") or m.get("scheduledTaskId")
        if st == "rusuban-mimawari-30min":
            return "留守番の見回り"
        if st or m.get("sessionType") == "scheduled":
            return "ほかの定期タスク"
        h = r.get("head") or ""
        for k, _ in HEART:
            if k in h:
                return "心臓のAI係"
        if "鬼監督（Verifier" in h or "実装後ゲート" in h or "independent, strict" in h:
            return "工場の検品"
        if "ditto_" in r["f"]:
            return "Dispatch本体"
        if m.get("sessionType") == "dispatch_child":
            return "Dispatchの子"
        if r.get("src") == "cowork":
            return "店主との会話" if m else None
        if r.get("ent") == "sdk-cli":
            return "工場の子セッション"
        if r.get("ent") == "claude-desktop" and m:
            return "店主との会話"
        return "不明"
    bysid = {r["sid"]: cat0(r) for r in rows if not r.get("side")}
    out = []
    for r in rows:
        if r.get("side"):
            m = re.search(r"/([0-9a-f-]{36})/subagents/", r["f"])
            c = bysid.get(m.group(1)) if m else None
            c = c or ("Dispatch本体" if "ditto_" in r["f"] else "不明")
        else:
            c = cat0(r) or ("Dispatch本体" if "ditto_" in r["f"] else "不明")
        sub = next((v for k, v in HEART if k in (r.get("head") or "")), None) if c == "心臓のAI係" else None
        out.append((c, sub, r))
    return out


def shuukei(rows):
    B = bunrui(rows)
    wk = [{"label": w[0], "pct": w[3], "pct_src": w[4], "cats": {}, "heart": {}} for w in WEEKS]
    tot = [[0, 0, 0, 0] for _ in WEEKS]
    ru_all, ru_n, ru_w, ru_wn = [0, 0, 0, 0], set(), [0, 0, 0, 0], set()
    ru_first = None
    for c, sub, r in B:
        for k, b in (r.get("hb") or {}).items():
            t = D.datetime.strptime(k.split("|")[0], "%Y-%m-%d %H")
            if c == "留守番の見回り":
                for j in range(4):
                    ru_all[j] += b[j]
                ru_n.add(r["sid"])
                ru_first = min(ru_first or k[:13], k[:13])
                if t >= RUSUBAN_TOMETA:
                    for j in range(4):
                        ru_w[j] += b[j]
                    ru_wn.add(r["sid"])
            for i, w in enumerate(WEEKS):
                if w[1] <= t < w[2]:
                    for j in range(4):
                        tot[i][j] += b[j]
                    x = wk[i]["cats"].setdefault(c, {"kaiwa": set(), "tok": [0, 0, 0, 0]})
                    x["kaiwa"].add(r["sid"])
                    for j in range(4):
                        x["tok"][j] += b[j]
                    if sub:
                        y = wk[i]["heart"].setdefault(sub, {"kaiwa": set(), "tok": [0, 0, 0, 0]})
                        y["kaiwa"].add(r["sid"])
                        for j in range(4):
                            y["tok"][j] += b[j]
    ruiseki_pct = 0.0
    for i, w in enumerate(wk):
        tw = omomi(tot[i]) or 1
        w["goukei"] = sum(tot[i])
        for d in (w["cats"], w["heart"]):
            for k, x in d.items():
                x["kaiwa"] = len(x["kaiwa"])
                x["goukei"] = sum(x["tok"])
                x["wari"] = round(100 * omomi(x["tok"]) / tw, 2)
                x["waku_suisoku"] = round(x["wari"] * w["pct"] / 100, 2)
        r = w["cats"].get("留守番の見回り")
        if r:
            ruiseki_pct += r["waku_suisoku"]
    return {
        "weeks": wk,
        "rusuban": {"saisho": ru_first, "kaiwa": len(ru_n), "tok": ru_all, "goukei": sum(ru_all),
                    "tometa_ato": {"kara": RUSUBAN_TOMETA.strftime("%Y-%m-%d %H:%M"), "kaiwa": len(ru_wn), "tok": ru_w,
                                   "goukei": sum(ru_w)},
                    "4shuu_waku_suisoku": round(ruiseki_pct, 1)},
    }


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    res = shuukei(d["rows"])
    res["at"] = d.get("at")
    res["kazoekata"] = __doc__.split("数え方：")[1].strip()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(OUT + ".tmp", OUT)
    print("ok", res["rusuban"]["kaiwa"], res["rusuban"]["4shuu_waku_suisoku"])


def self_test():
    rows = [
        {"sid": "a" * 36, "f": "/p/x/" + "a" * 36 + ".jsonl", "task": "rusuban-mimawari-30min", "head": "", "hb": {"2026-11-12 10|opus": [0, 0, 100, 1000]}},
        {"sid": "b" * 36, "f": "/p/x/" + "b" * 36 + ".jsonl", "ent": "sdk-cli", "head": "1+1は？数字だけ", "hb": {"2026-11-12 10|sonnet": [1, 1, 0, 0]}},
        {"sid": "c", "side": True, "f": "/p/x/" + "a" * 36 + "/subagents/c.jsonl", "head": "", "hb": {"2026-11-12 11|opus": [0, 0, 10, 0]}},
        {"sid": "d" * 36, "f": "/p/x/" + "d" * 36 + ".jsonl", "ent": "sdk-cli", "head": "作業", "hb": {"2026-11-12 10|sonnet": [0, 0, 0, 0]}},
    ]
    r = shuukei(rows)
    w = r["weeks"][3]
    assert w["cats"]["留守番の見回り"]["goukei"] == 1110 and w["cats"]["留守番の見回り"]["kaiwa"] == 2, w
    assert w["heart"]["ログイン確認"]["kaiwa"] == 1 and "工場の子セッション" in w["cats"]
    assert r["rusuban"]["tometa_ato"]["goukei"] == 1110
    print("teiki_uchiwake self-test OK")


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
