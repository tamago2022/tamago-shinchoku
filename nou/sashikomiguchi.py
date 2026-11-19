#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【脳の差込口】ElevenAgents / GPT-Live / Grok Voice の3つを、同じ魂に繋ぐ薄い層。

━━ たまごさん（2026-09-24・原文）━━

  「脳＝差し替え式。声＝差し替え式。アバター＝差し替え式。将来の物理ロボット＝差し替え式。」
  「それぞれ『差す』だけで動く薄い層にする。★中に魂を書かない。」

━━ ここに書いてよいこと／書いてはいけないこと ━━

  書いてよい  … その脳の住所・繋ぎ方・関数定義をどの方言で渡すか・鍵の**名前**
  書いてはいけない … 曲・アーティスト・棚・推薦の考え方・人格・会話の決まり
                     （それは全部 tamashii/ にある。ここに写した瞬間、写し間違いが始まる）

  ★この決まりは人の気持ちでは守れないので、下の自己試験が機械で見張る。
    魂の言葉（曲名・アーティスト名・「安心4」など）がこのファイルに混ざったら落ちる。

━━ 鍵について（★値は1バイトも読まない・書かない・残さない）━━

  ここが持つのは**鍵の名前だけ**。値は Supabase Secrets にある。
  この係は「その名前の鍵が有る／無い」しか見ない。中身は見ない。

━━ 繋がるかどうかは実測でしか言わない ━━

  この箱（サンドボックス）は外に出られない（2026-09-24 実測：api.x.ai / api.elevenlabs.io /
  api.openai.com いずれも curl で 000＝接続できず）。
  だから**ここでは「繋がった」と一度も言わない。**
  実際に叩くのは Mac 側の `status/mac_jobs/pending/1051_nou_kaitsuu.sh`。
  結果は status/nou_kaitsuu.json に入る。★そこに載るまでは全部「未実測」。

━━ 使い方 ━━

    python3 nou/sashikomiguchi.py --self-test   # 薄さと、魂が混ざっていないかを見る
    python3 nou/sashikomiguchi.py --shitaku eleven   # その脳に差す設定を書き出す
    python3 nou/sashikomiguchi.py --genjo        # いま3つがどこまで来ているか（実測のみ）
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tamashii"))

KAITSUU_JSON = os.path.join(REPO, "status", "nou_kaitsuu.json")
OUT_DIR = os.path.join(HERE, "shitaku")


# ══════════════════════════════════════════════════════════════
# 3つの脳。★1つあたりこれだけ。増えたら魂が漏れている。
# ══════════════════════════════════════════════════════════════
NOU = {
    "eleven": {
        "namae": "ElevenAgents",
        "hougen": "elevenlabs",          # 口をどの方言で渡すか（tamashii/tools.json のキー）
        "kuchi_no_watashikata": "webhook",  # 魂をHTTPで叩きに来る → tamashii/server.py の住所が要る
        "kagi_no_namae": ["ELEVENLABS_API_KEY"],
        "kagi_no_okiba": "Supabase Secrets",
        "tsunagu_saki": "https://api.elevenlabs.io",
        "kizukai": [
            "★新規に金が出る可能性がある。契約・プラン変更・課金を押さない。",
            "無料枠で試せる範囲を実測し、足りないなら『◯円必要』とだけ書いて止める。",
            "Widgetをサイトに埋める場合も、魂は webhook 越し。Widget側に曲名を書かない。",
        ],
    },
    "gptlive": {
        "namae": "GPT-Live",
        "hougen": "realtime",
        "kuchi_no_watashikata": "browser",  # ブラウザの中で kuchi.mjs を直に呼ぶ（住所不要）
        "kagi_no_namae": ["OPENAI_API_KEY"],
        "kagi_no_okiba": "Supabase Secrets",
        "tsunagu_saki": "https://api.openai.com",
        "kizukai": [
            "人が話している最中も聞き続けられる（full-duplex）。割り込みはこちらで止めない。",
            "会話担当と頭脳担当を分けられる。分けても魂の口は1つのまま。",
            "★2026-09-23 実測で残高切れ（429）。金を入れる前に yosan.py の栓を通す。",
        ],
    },
    "grok": {
        "namae": "Grok Voice",
        "hougen": "realtime",
        "kuchi_no_watashikata": "browser",
        "kagi_no_namae": ["XAI_API_KEY2"],
        "kagi_no_okiba": "Supabase Secrets（★Macに置かない）",
        "tsunagu_saki": "https://api.x.ai",
        "kizukai": [
            "★接続は ?model= ではなく ?agent_id=。",
            "★voice と turn_detection を必ず明示する。未指定だと早回し・無反応になる。",
            "窓口の関数 voice-session は既に有る。作り直さない。",
            "★2026-09-20 に本番で鳴った実績あり（声）。文字の口は team_blocked（別物）。",
        ],
    },
}


def shitaku(nou_id: str) -> dict:
    """その脳に差す設定を作る。★魂はここで作らない。tamashii から借りるだけ。"""
    import kuchi  # 魂の口（借り物）

    n = NOU[nou_id]
    t = kuchi.tools_json()[n["hougen"]]
    return {
        "nou": n["namae"],
        "hougen": n["hougen"],
        "kuchi_no_watashikata": n["kuchi_no_watashikata"],
        "kagi_no_namae": n["kagi_no_namae"],
        "kagi_no_okiba": n["kagi_no_okiba"],
        "tsunagu_saki": n["tsunagu_saki"],
        "kizukai": n["kizukai"],
        # ★脳に渡すのはこの2つだけ。中身は tamashii/ が持っている。
        "tools": t,
        "jinkaku_no_torikata": "会話の最初に jinkaku() を1回呼ぶ。人格をここに文字で書かない。",
        "tamashii_no_basho": {
            "browser": "tamashii/kuchi.mjs（sashikomu() で data/tamashii.json と jinkaku.json を差す）",
            "webhook": "tamashii/server.py（POST /osusume, /shiraberu, /jinkaku）",
        }[n["kuchi_no_watashikata"]],
    }


def genjo() -> dict:
    """いま3つがどこまで来ているか。★実測ファイルが無ければ全部『未実測』と言う。"""
    jissoku = {}
    if os.path.exists(KAITSUU_JSON):
        try:
            jissoku = json.load(open(KAITSUU_JSON, encoding="utf-8")).get("nou", {})
        except Exception:
            jissoku = {}
    # 既にある窓口（Supabase voice-session）の実測。Macに鍵が無くても開くかどうか。
    madoguchi = {}
    p = os.path.join(REPO, "status", "kagi_doko.json")
    if os.path.exists(p):
        try:
            madoguchi = json.load(open(p, encoding="utf-8")).get("sudeni_aru_madoguchi", {})
        except Exception:
            madoguchi = {}

    out = []
    for k, n in NOU.items():
        j = jissoku.get(k) or {}
        if k == "grok" and madoguchi.get("http") in (200, 204, 400, 405, 422):
            # ★400は「窓口が生きていて、叩き方が違う」。401/403（鍵待ち）とは別物。
            j = dict(j)
            j["doko_ga_shimatteru"] = (
                f"鍵はMacに要らない。既存の窓口 voice-session が鍵を持っていて、Macから HTTP "
                f"{madoguchi['http']} で応えている（生きている）。残りは叩き方だけ。"
            )
        out.append(
            {
                "nou": n["namae"],
                "kuchi_wa_sasetaka": "○（設定を書き出せる）",
                "tsunagattaka": j.get("kekka", "未実測"),
                "shimatteru_kuchi": j.get("doko_ga_shimatteru"),
                "itsu": j.get("itsu"),
            }
        )
    return {"jissoku_file": os.path.relpath(KAITSUU_JSON, REPO), "aru": bool(jissoku), "nou": out}


# ══════════════════════════════════════════════════════════════
# 自己試験：★この層が薄いことと、魂が混ざっていないことを機械で見張る
# ══════════════════════════════════════════════════════════════
def self_test() -> int:
    ng = []
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    body = src.split("NOU = {", 1)[-1].split("def self_test", 1)[0]

    # ① 魂の言葉がこの層に混ざっていないか
    tamashii_no_kotoba = ["安心4", "冒険1", "この流れで", "こちらもどうぞ", "うんちく", "スナックのママ", "カードはドア"]
    for w in tamashii_no_kotoba:
        if w in body:
            ng.append(f"脳の層に魂が混ざっている: 「{w}」→ tamashii/ に置くこと")

    # ② 曲名・アーティスト名が混ざっていないか（魂のデータと突き合わせる）
    import kuchi

    kuchi._load()
    # 「Live」のような、どこにでも出る短い英単語は名簿にも載っているので外す。
    # 日本語が入っていれば4文字から、英数字だけなら6文字から見る。
    def _mireru(nm: str) -> bool:
        wa = any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in nm)
        return len(nm) >= (4 if wa else 6)

    namae = {a["name"] for a in kuchi._soul["artists"] if _mireru(a["name"])}
    mazatta = sorted(n for n in namae if n in body)
    if mazatta:
        ng.append(f"脳の層にアーティスト名が混ざっている: {mazatta[:5]}")

    # ③ 鍵の値が書かれていないか（★名前だけのはず）
    for kigo in ("sk-", "xai-", "eleven_", "Bearer "):
        if kigo in body:
            ng.append(f"鍵の値らしきものが書かれている: {kigo}")

    # ④ 3つとも、同じ3つの口を渡しているか
    kuchi_mei = {}
    for k in NOU:
        s = shitaku(k)
        t = s["tools"]
        names = sorted(x["name"] if "name" in x else x["function"]["name"] for x in (t if isinstance(t, list) else t["functionDeclarations"]))
        kuchi_mei[k] = names
    if len({json.dumps(v) for v in kuchi_mei.values()}) != 1:
        ng.append(f"脳ごとに渡している口が違う: {kuchi_mei}")
    elif kuchi_mei["grok"] != ["jinkaku", "osusume", "shiraberu"]:
        ng.append(f"口が3つではない: {kuchi_mei['grok']}")

    # ⑤ 薄いか（1脳あたりの行数）
    gyou = len(body.strip().splitlines())
    if gyou > 160:
        ng.append(f"脳の層が厚くなっている（{gyou}行）。魂が漏れ始めている合図")

    # ⑥ ★繋がったと書いていないか（実測が無いのに）
    if not os.path.exists(KAITSUU_JSON):
        for w in ("繋がった", "つながった", "開通済"):
            if w in body:
                ng.append(f"実測が無いのに「{w}」と書いている")

    for line in ng:
        print("✕", line)
    if not ng:
        print(
            f"○ 脳の差込口：3つ（{' / '.join(n['namae'] for n in NOU.values())}）"
            f"／どれも同じ3つの口を渡す／魂の言葉もアーティスト名も鍵の値も1つも混ざっていない／{gyou}行"
        )
        g = genjo()
        print(f"  実測: {'あり' if g['aru'] else '★まだ無い（この箱は外に出られない。Mac側の 1051_nou_kaitsuu.sh で叩く）'}")
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--genjo" in sys.argv:
        print(json.dumps(genjo(), ensure_ascii=False, indent=2))
        sys.exit(0)
    if "--shitaku" in sys.argv:
        which = sys.argv[sys.argv.index("--shitaku") + 1] if len(sys.argv) > sys.argv.index("--shitaku") + 1 else "all"
        os.makedirs(OUT_DIR, exist_ok=True)
        for k in ([which] if which in NOU else list(NOU)):
            p = os.path.join(OUT_DIR, f"{k}.json")
            with open(p, "w", encoding="utf-8") as fp:
                json.dump(shitaku(k), fp, ensure_ascii=False, indent=2)
            print(f"書いた: {os.path.relpath(p, REPO)}")
        sys.exit(0)
    print(__doc__)
