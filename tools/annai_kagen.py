#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1176番【案内人の上限を1か所にする係】＋★たまごさん本人（管理者）は無制限。

たまごさん（2026-09-24・原文）:
  「たまごさん本人は無制限にする（管理者だけ上限を外す）。これは実装してよい。」

------------------------------------------------------------------
★お金の実測（2026-09-24。ここに書いてあるのは全部、出どころのある数字だけ）
------------------------------------------------------------------
◆ 文字の案内人（覆面10問を含む）＝**0円**
    出どころ: status/fukumen10.json（2026-09-24 03:32 実測）
              "kane": "0円（AIを1回も呼んでいない）"
    理由: 問いを作る側も（tools/annai_toi.py 冒頭「★AIを1回も呼ばない」）、
          判定する側も、棚のデータ（魂の口）だけで答えている。
          ★10問のうち6問は脳なしで判定できた。残り4問（no.1/4/5/9）は
          「脳が要る」と記録されているが、**まだ1回も走らせていない**＝0円。
    ＝**100人でも1000人でも 0円**（人数に比例して増える口が無い）。

◆ 声（案内所の「話す」＝xAI Grok Realtime Voice / Voice Agent Iris）
    1回いくら＝**取れていない。**（★憶測の円を書かない）
    こちらに在る数字は status/grok_voice_cost.json の
      ratePerSecondUsdEstimate = 0.02（1秒あたり）だが、同ファイルに
      "未実測（実機マイク/スピーカーが無い開発環境のため）。xAI公開価格表からの概算値"
      と書いてある。＝**概算なので円にしない。**
    実額の累計: spentUsd = 0（同ファイル）／いま鳴らせる状態でもない
      （status/public/kaitsuu.json の xai_koe = "窓口は生きているが断られた
        （budget_exceeded）"）。★今日の声の実額 = 0円・0回。
    閉じている口（＝これが開くまで1回◯円は出せない）:
      ① xAIコンソールの使用量画面 … 人がログインしないと見えない（こちらからは押せない）
      ② Supabase の voice_usage_log … service_role の鍵しか読めない（鍵がこちらに無い）

◆ 今日（2026-09-24）の実額 = **0円**
    Claude: 本物の発車 0本（status/auto_launch.log の 2026-09-24 に発車の行が1本も無い。
            全部「見送り（ログイン切れ）」と「空回し」）
    fal   : 0件 0円（status/public/fal_cost_ledger.json に 2026-09-24 の行が無い）
    外注  : 0件 0.00USD（status/public/gaibu.json に 2026-09-24 の行が無い）
    声    : 0回（上記 budget_exceeded）

------------------------------------------------------------------
★上限（ここが1か所。数字を増やすときはこのファイルだけを直す）
------------------------------------------------------------------
一般のお客さん:
  - 声は1回 180秒まで（status/grok_voice_cost.json の maxSessionSeconds。既存の実測値）
  - 声は1日 3回まで（＝540秒。★この「3回」はこの係が決めた運用値で、実測ではない。
    お金の数字ではなく回数の数字なので置いている。変えるときはここだけ直す）
  - 文字の問いは上限なし（掛かる金が無いので、絞る理由が無い）
管理者（たまごさん本人）:
  - 声の秒数・回数の上限を**外す**（無制限）
  - ★外せないものが1つある: xAI側の $5 ハード上限。
    これは向こうのコンソールの設定で、こちらからは押せない（たまごさんが2026-09-13に設定）。
    ＝「無制限」は**こちら側の栓を全部開ける**という意味。向こうの栓は開けられない。

管理者の見分け方（★秘密を公開フォルダに置かない形にしてある）:
  この端末の localStorage に `tamago_admin` = "1" が立っているかどうか。
  ＝たまごさんのMacのブラウザで1回立てれば、以後その端末だけ無制限。
  メールアドレスも鍵も status/public/ には書かない（あそこは公開される）。

置き場所:
  紙   status/public/annai_kagen.json  … 案内所のサーバ側（voiceConcierge.functions.ts）が読む
使い方:
  python3 tools/annai_kagen.py             … 紙を書き直す
  python3 tools/annai_kagen.py --show
  python3 tools/annai_kagen.py --selftest  … 一般客と管理者で本当に違うかを機械で見る
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
KOE_COST = os.path.join(STATUS, "grok_voice_cost.json")
OUT = os.path.join(STATUS, "public", "annai_kagen.json")

JST = timezone(timedelta(hours=9))

# ★一般のお客さんの栓（1か所）
IPPAN_KOE_BYOU_1KAI = None      # ← grok_voice_cost.json から読む（下で入る）
IPPAN_KOE_KAISU_1NICHI = 3
ADMIN_KEY = "tamago_admin"      # localStorage のこの印が "1" なら管理者


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    json.dump(d, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def koe_byou_1kai():
    """声1回の秒数。★勝手に決めない。既に在る実測値を読む。"""
    d = _load(KOE_COST, {}) or {}
    v = d.get("maxSessionSeconds")
    return int(v) if isinstance(v, int) and v > 0 else 180


def kagen(admin=False):
    """★上限を返す1か所。admin=True なら、こちら側の栓を全部開ける。"""
    d = _load(KOE_COST, {}) or {}
    return {
        "admin": bool(admin),
        "koeByou1kai": None if admin else koe_byou_1kai(),
        "koeKaisu1nichi": None if admin else IPPAN_KOE_KAISU_1NICHI,
        "mojiToiJougen": None,                       # 文字は誰でも上限なし（0円だから）
        # ★管理者でも外せない栓（向こう側の設定）
        "xaiHardLimitUsd": d.get("hardLimitUsd"),
        "kochiraGuardUsd": d.get("localGuardUsd"),
        "hazusenai": "xAI側の $%s ハード上限（向こうのコンソールの設定。こちらからは押せない）"
                     % d.get("hardLimitUsd"),
    }


def tsukaete_yoi(admin, koe_byou_kyou, koe_kaisu_kyou, tsukatta_usd):
    """いま声を鳴らして良いか。(良いか, 理由)
    ★管理者はこちら側の栓を通す。★向こう側のハード上限は管理者でも通さない。"""
    k = kagen(admin)
    guard = k.get("kochiraGuardUsd")
    hard = k.get("xaiHardLimitUsd")
    if isinstance(hard, (int, float)) and tsukatta_usd is not None and tsukatta_usd >= hard:
        return False, "xAI側の $%s ハード上限に達している（管理者でも外せない）" % hard
    if (not admin) and isinstance(guard, (int, float)) and tsukatta_usd is not None \
            and tsukatta_usd >= guard:
        return False, "こちら側のガード $%s に達している" % guard
    if k["koeKaisu1nichi"] is not None and koe_kaisu_kyou >= k["koeKaisu1nichi"]:
        return False, "今日の回数の上限（%d回）に達している" % k["koeKaisu1nichi"]
    if k["koeByou1kai"] is not None and koe_byou_kyou >= k["koeByou1kai"]:
        return False, "1回の秒数の上限（%d秒）に達している" % k["koeByou1kai"]
    return True, ("管理者なので、こちら側の栓は外れている" if admin else "上限の内側")


def kaku():
    d = _load(KOE_COST, {}) or {}
    kami = {
        "at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        "adminKey": ADMIN_KEY,
        "adminHow": "localStorage の %s が \"1\" の端末だけ管理者（たまごさん本人）。"
                    "★メールアドレスも鍵もこの紙に書かない（この紙は公開される）" % ADMIN_KEY,
        "ippan": {
            "koeByou1kai": koe_byou_1kai(),
            "koeKaisu1nichi": IPPAN_KOE_KAISU_1NICHI,
            "mojiToiJougen": None,
        },
        "admin": {
            "koeByou1kai": None,
            "koeKaisu1nichi": None,
            "mojiToiJougen": None,
            "imi": "こちら側の栓は全部外れる。★xAI側のハード上限だけは外れない",
        },
        "hazusenai": {
            "xaiHardLimitUsd": d.get("hardLimitUsd"),
            "kochiraGuardUsd": d.get("localGuardUsd"),
            "naze": "向こうのコンソールの設定（2026-09-13 たまごさんが設定）。こちらからは押せない",
        },
        "okane": {
            "mojiAnnai1kai": "0円（AIを1回も呼んでいない）",
            "mojiMoto": "status/fukumen10.json（2026-09-24 03:32 実測）",
            "fukumen10mon": "0円（同上。10問のうち4問は『脳が要る』が未実行）",
            "koe1kai": "取れていない",
            "koeNaze": "1秒0.02ドルという値は status/grok_voice_cost.json に"
                       "『未実測・xAI公開価格表からの概算』と書かれている＝概算なので円にしない",
            "koeTojiteiruKuchi": [
                "xAIコンソールの使用量画面（人がログインしないと見えない）",
                "Supabase の voice_usage_log（service_role の鍵がこちらに無い）",
            ],
            "koeIma": "鳴らない（status/public/kaitsuu.json の xai_koe = budget_exceeded）",
            "kyouNoJitsugaku": "0円（Claude発車0本・fal 0件・外注0件・声0回）",
            "hyakunin": "文字だけなら100人でも1000人でも0円。★声は1回の単価が取れていないので出せない",
        },
        "note": "★案内人の上限はこの1枚。tools/annai_kagen.py が書いている。"
                "サーバ側（voiceConcierge.functions.ts）はここだけを読む。"
                "数字を変えるときも、このファイルを直さずツール側の定数を直す。",
    }
    _save(OUT, kami)
    return kami


def selftest():
    ng = []
    # ① 一般客には栓がある
    k = kagen(False)
    if k["koeByou1kai"] is None or k["koeKaisu1nichi"] is None:
        ng.append("一般客の栓が外れている")
    # ② 管理者は無制限
    a = kagen(True)
    if a["koeByou1kai"] is not None or a["koeKaisu1nichi"] is not None:
        ng.append("管理者の栓が外れていない")
    # ③ 回数を使い切った一般客は止まる／管理者は止まらない
    ok1, w1 = tsukaete_yoi(False, 0, 3, 0.0)
    ok2, w2 = tsukaete_yoi(True, 0, 999, 0.0)
    if ok1:
        ng.append("一般客が回数の上限を越えて鳴らせる")
    if not ok2:
        ng.append("管理者が回数で止められている：%s" % w2)
    # ④ 1回の秒数：一般客は180秒で止まる／管理者は止まらない
    if tsukaete_yoi(False, koe_byou_1kai(), 0, 0.0)[0]:
        ng.append("一般客が1回の秒数を越えて鳴らせる")
    if not tsukaete_yoi(True, 99999, 0, 0.0)[0]:
        ng.append("管理者が秒数で止められている")
    # ⑤ ★向こう側のハード上限は管理者でも外れない
    hard = kagen(True).get("xaiHardLimitUsd")
    if isinstance(hard, (int, float)):
        if tsukaete_yoi(True, 0, 0, hard)[0]:
            ng.append("xAIのハード上限を管理者が踏み越えられる（外せない栓が外れている）")
    else:
        ng.append("xAIのハード上限が読めない（status/grok_voice_cost.json）")
    # ⑥ 紙に憶測の円が載っていない
    kami = kaku()
    if "0.02" in json.dumps(kami, ensure_ascii=False) and "概算" not in json.dumps(kami, ensure_ascii=False):
        ng.append("概算の単価を断りなく紙に載せている")
    if kami["okane"]["koe1kai"] != "取れていない":
        ng.append("取れていない声の単価に円を書いている")
    print("自己試験 %s（%d件）" % ("◯ 通った" if not ng else "✕ 落ちた", len(ng)))
    for x in ng:
        print(" -", x)
    return 1 if ng else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--show" in sys.argv:
        print(json.dumps(_load(OUT, {}), ensure_ascii=False, indent=1))
        sys.exit(0)
    k = kaku()
    print("書いた %s" % OUT)
    print("一般客: 声%d秒×%d回/日 ／ 管理者: 無制限（外せないのは xAI $%s）"
          % (k["ippan"]["koeByou1kai"], k["ippan"]["koeKaisu1nichi"],
             k["hazusenai"]["xaiHardLimitUsd"]))
