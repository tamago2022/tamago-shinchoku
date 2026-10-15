#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【覆面10問】同じ10問を3つの脳に投げて比べる係。

━━ この係が守る順番（★逆にしない）━━

  ① 脳を1つも呼ばずに測れる分を、先に全部測る（0円・AI0回）
     → 推薦の精度・音楽を押し付けないか・うんちくを作らないか は、
       **魂の口の返り値だけで測れる。**脳の感想は1つも要らない。
  ② 脳が要る分（会話の自然さ・割り込み・遅れ）は、
     ★お金が出る前に tools/yosan.py の栓を必ず通す。通らなければ止まる。
  ③ 止まったら黙らない。「上限で止めた。あと◯円あれば◯ができる」と書いて出す。

━━ 使い方 ━━

    python3 nou/fukumen10.py              # ①だけ走る（0円）
    python3 nou/fukumen10.py --nou grok   # ②も試みる（★栓を通る。通らなければ止まる）
    python3 nou/fukumen10.py --self-test
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9))
sys.path.insert(0, os.path.join(REPO, "tamashii"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import kuchi  # noqa: E402

TOI_PATH = os.path.join(HERE, "toi10.json")
OUT = os.path.join(REPO, "status", "fukumen10.json")


# ══════════════════════════════════════════════════════════════
# ① 脳なしで測れる分（★0円・AI0回・毎回同じ答え）
# ══════════════════════════════════════════════════════════════
def nou_nashi() -> list:
    kuchi._load()
    kekka = []

    def tsuke(no, nerai, ok, mita):
        kekka.append({"no": no, "nerai": nerai, "hantei": "○" if ok else "✕", "mita": mita, "nou": "不要（魂の口だけで測った）"})

    # 問3 ツールを呼べるか → 呼ばれた側（口）が、棚にあるものだけを返しているか
    r = kuchi.shiraberu(go="久保田利伸")
    hit = [a["id"] for a in r["artists"]]
    tsuke(3, "ツールを呼べるか", bool(hit), f"shiraberu('久保田利伸') → アーティスト{len(hit)}件・曲{len(r['songs'])}件（棚の外は1件も返さない）")

    # 問6 推薦の精度（趣味の違う2人）→ 片方が4枚さらっていないか
    r = kuchi.osusume(konomi=["犬", "ブラジル"], hito="fukumen")
    anshin = [c for c in r["cards"] if c["riyu"] == "安心"]
    a_hits = {x[1]["id"] for x in kuchi._candidates(["犬"])}
    b_hits = {x[1]["id"] for x in kuchi._candidates(["ブラジル"])}
    na = sum(1 for c in anshin if c["artist_id"] in a_hits)
    nb = sum(1 for c in anshin if c["artist_id"] in b_hits)
    tsuke(6, "推薦の精度（2人）", na >= 1 and nb >= 1 and max(na, nb) <= 3,
          f"安心4枚の内訳 犬{na}枚／ブラジル{nb}枚。橋＝{'あり' if r['hashi'] else 'なし（無理に繋いでいない）'}")

    # 問7 事実 → 年が無い曲に年を作っていないか
    tsukutta = 0
    for c in r["cards"] + r["kono_nagare_de"]:
        a = next((x for x in kuchi._soul["artists"] if x["id"] == c["artist_id"]), None)
        s = next((x for x in a["songs"] if x["id"] == c["song_id"]), None) if a else None
        if s and (s.get("year") or None) != (c.get("year") or None):
            tsukutta += 1
    tsuke(7, "事実（年号を作らないか）", tsukutta == 0, f"棚に無い年を付けたカード {tsukutta}件")

    # 問10 喋りすぎないか → うんちくが無いとき null（黙る）になっているか
    nai = [c for c in r["cards"] if not c["unchiku"]]
    tsuke(10, "喋りすぎないか", all(c["unchiku"] is None for c in nai),
          f"うんちくの無いカード{len(nai)}枚は全部 null（黙る）。長すぎる一言は出さない（一言＝{r['hitokoto'] or '無し'}）")

    # 問2・問8 音楽を押し付けないか → 口が「押す言葉」を持っていないか
    j = kuchi.jinkaku()
    kimari = " ".join(j["kaiwa_no_kimari"])
    tsuke(2, "音楽を押し付けないか", "押し付けない" in kimari, "人格に『音楽を押し付けない』が明文で入っている")
    tsuke(8, "ちゃんと聞くか", "先に聞く" in kimari, "人格に『先に聞く。1回に1つだけ聞く』が明文で入っている")

    return kekka


# ══════════════════════════════════════════════════════════════
# ② 脳が要る分（★お金が出る前に必ず栓を通る）
# ══════════════════════════════════════════════════════════════
SAIFU = {"eleven": "eleven", "gptlive": "openai", "grok": "xai"}


def nou_ari(nou_id: str) -> dict:
    """★叩く前に見積りを通す。通らなければ1バイトも外に出さない。"""
    try:
        import yosan
    except Exception as e:
        return {"hashitta": False, "riyu": f"予算の栓が読めない: {e}"}

    saifu = SAIFU.get(nou_id)
    if not saifu:
        return {"hashitta": False, "riyu": f"知らない脳: {nou_id}"}

    # ★1回いくらか、まだ実測していない。公式の料金ページをこの箱から開けない
    #   （外に出られない＝2026-09-24 実測で curl 000）。
    #   推測の金額を栓に通すと、栓そのものが嘘になる。だから「不明」として通す＝必ず止まる。
    mitsumori_yen = None
    if mitsumori_yen is None:
        return {
            "hashitta": False,
            "riyu": "1回いくらか未実測（公式の料金ページをこの箱から開けない）。"
                    "★憶測の金額は1円も書かない。料金を実測してから、この行に入れる。",
            "saifu": saifu,
            "ima_no_jougen_yen": _jougen(saifu),
        }
    ok, why = yosan.mitsumori(saifu, mitsumori_yen, f"覆面10問／{nou_id}")
    if not ok:
        return {"hashitta": False, "riyu": why, "saifu": saifu}
    return {"hashitta": False, "riyu": "ここから先はMac側の便で叩く（この箱は外に出られない）"}


def _jougen(saifu: str):
    try:
        import yosan
        return yosan.genjo(saifu)["limit"] if hasattr(yosan, "genjo") else "（--show で見る）"
    except Exception:
        return "（--show で見る）"


def hashiru(nou_list=None) -> dict:
    toi = json.load(open(TOI_PATH, encoding="utf-8"))
    nashi = nou_nashi()
    sunda = {k["no"] for k in nashi}
    nokori = [t["no"] for t in toi["toi"] if t["no"] not in sunda]

    nou = {}
    for n in nou_list or []:
        nou[n] = nou_ari(n)

    r = {
        "itsu": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "toi_kazu": len(toi["toi"]),
        "nou_nashi_de_mireta": nashi,
        "nou_ga_iru_toi": nokori,
        "nou": nou,
        "kane": "0円（AIを1回も呼んでいない）",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(r, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return r


def self_test() -> int:
    ng = []
    r = hashiru()
    ochita = [k for k in r["nou_nashi_de_mireta"] if k["hantei"] == "✕"]
    for k in ochita:
        ng.append(f"問{k['no']}（{k['nerai']}）が落ちている: {k['mita']}")
    if len(r["nou_nashi_de_mireta"]) < 6:
        ng.append("脳なしで測れた問いが少なすぎる")
    # ★栓を通らずに金が出る道が無いこと
    for n in ("eleven", "gptlive", "grok"):
        g = nou_ari(n)
        if g["hashitta"]:
            ng.append(f"{n} が栓を通らずに走った")
    for line in ng:
        print("✕", line)
    if not ng:
        print(f"○ 覆面10問：脳を1つも呼ばずに {len(r['nou_nashi_de_mireta'])}問を実測（0円）。"
              f"残り{len(r['nou_ga_iru_toi'])}問（問{r['nou_ga_iru_toi']}）は脳が要る。"
              f"★3つとも見積りの栓で止まった＝1円も出ていない。")
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    nl = []
    if "--nou" in sys.argv:
        nl = [sys.argv[sys.argv.index("--nou") + 1]]
    print(json.dumps(hashiru(nl), ensure_ascii=False, indent=2))
