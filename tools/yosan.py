#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1034番【予算の栓】財布ごとに上限を持つ。51円目は叩けない。

━━ なぜ作ったか（2026-09-23・たまごさん原文）━━

  「雑にやるといきなり何千円だとか請求が来るとびっくりするから、そこをまとめて。
    ガッツリテストができないから、そこ安心しないと。
    例えば50円分、100円分テストして、みたいなやり方ができるのかな。」

  「気をつけます」は仕組みではない。**止まる場所を1つ作る。**
  外部APIを叩く口は全部ここを通す。通らない口が1本でもあれば意味がないので、
  `--kuchi` で全部の口を並べ、通っていない口を名指しで出す（隠さない）。

━━ 決めたこと（増やさない）━━

  ① 財布ごとに上限（円）。既定は **全部 0円＝止まっている**。
     たまごさんが `--set xai 50` と言った分だけ、その財布が開く。
     ★「知らないうちに減っていた」を作らないため、既定を「開いている」にしない。
  ② 叩く**前**に見積もりを通す（`mitsumori`）。超えるなら**叩かせない**。
  ③ 叩いた**後**に実額を記録する（`tsukatta`）。台帳は status/yosan.jsonl。
  ④ 上限で止めたときは**黙らない**。
     「上限で止めました。あと◯円あれば◯ができます」を status/yosan.jsonl と
     status/dispatch_outbox.jsonl の両方に残す。
     ★「動いているのに何も取れていない」が一番悪い壊れ方なので、止めた事実は必ず出す。
  ⑤ AIを1回も呼ばない。ただの足し算とファイル。課金0。毎回同じ答えが出る。

━━ 使い方 ━━

    python3 tools/yosan.py --show                  # いまの上限と使った額
    python3 tools/yosan.py --set xai 50            # 「今日はxAIに50円まで」
    python3 tools/yosan.py --set all 0             # 全部止める
    python3 tools/yosan.py --spent xai 12.5 "声3秒"  # 実額を手で入れる
    python3 tools/yosan.py --kuchi                 # 外部APIを叩く口の一覧（通っているか）
    python3 tools/yosan.py --self-test             # 10円の上限で11円目が止まるか

  コードから：
    import yosan
    ok, why = yosan.mitsumori("xai", 13.0, "声1分")   # 叩く前
    if not ok: return {"ok": False, "error": why}      # ★理由をそのまま上に返す
    ...実際に叩く...
    yosan.tsukatta("xai", 12.4, "声57秒")             # 叩いた後

  終了コード: 0=通した / 1=上限で止めた
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
SETTEI = os.path.join(STATUS, "yosan.json")      # 上限
DAICHO = os.path.join(STATUS, "yosan.jsonl")     # 見積り・実額・止めた記録
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")
JST = timezone(timedelta(hours=9))

# ★財布の名前はここだけ。増やすときはここに足す。
SAIFU = {
    "xai":      "xAI（アイリスの声・画像）",
    "openai":   "OpenAI（チャッピー・検品・GPT Live）",
    "gemini":   "Gemini（Google）",
    "fal":      "fal.ai（画像・動画・音声）",
    "devin":    "Devin（オンデマンド）",
    "genspark": "Genspark（クレジット）",
    "anthropic": "Anthropic API（従量・使うなら）",
    # 1051番で足した。★財布が無いと「栓の外」になってしまう＝知らないうちに出る側に回る。
    # ElevenAgents は新規に金が出る可能性がある口なので、0円で置いておく（＝止まっている）。
    "eleven":   "ElevenLabs / ElevenAgents（声・エージェント）",
    # 1052番で足した。Jev（TypeSafe AI）＝判定だけ返すモデル。仕入れの本人判定に使う。
    # ★入力課金のみ・出力は0円。$0.042/1Mトークン＝約6.6円/1Mトークン（1ドル157.16円）。
    # ★出典: https://docs.typesafe.ai/models（2026-09-24 実読）
    # ★0円で置く＝止まっている。たまごさんが --set typesafe N と言った分だけ開く。
    "typesafe": "TypeSafe AI / Jev（本人判定・検品の門）",
}

# 1ドル何円で数えるか。★実測したレートを1か所に置く（1032番の実測値）。
USD_YEN = 157.16
USD_YEN_SOURCE = "2026-09-22 時点・1032番で実測（console.x.ai の $ 表示を円に直すのに使用）"


def _now():
    return datetime.now(JST)


def _today():
    return _now().strftime("%Y-%m-%d")


def _month():
    return _now().strftime("%Y-%m")


def _read_json(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _append(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def settei():
    """上限。★既定は全部0円＝止まっている。"""
    s = _read_json(SETTEI, {})
    out = {"limits": {}, "period": s.get("period", "day"), "updatedAt": s.get("updatedAt")}
    for k in SAIFU:
        out["limits"][k] = float((s.get("limits") or {}).get(k, 0.0))
    return out


def set_limit(saifu, yen):
    if saifu != "all" and saifu not in SAIFU:
        raise SystemExit("知らない財布です: %s（使えるのは %s / all）" % (saifu, "・".join(SAIFU)))
    s = _read_json(SETTEI, {})
    s.setdefault("limits", {})
    if saifu == "all":
        for k in SAIFU:
            s["limits"][k] = float(yen)
    else:
        s["limits"][saifu] = float(yen)
    s["period"] = s.get("period", "day")
    s["updatedAt"] = _now().isoformat()
    _write_json(SETTEI, s)
    _append(DAICHO, {"at": _now().isoformat(), "kind": "上限を変えた",
                     "saifu": saifu, "yen": float(yen)})
    return settei()


def tsukatta_gokei(saifu, period=None):
    """その財布で今日（または今月）使った実額の合計。台帳を読むだけ。"""
    period = period or settei()["period"]
    key = _today() if period == "day" else _month()
    total = 0.0
    n = 0
    if not os.path.exists(DAICHO):
        return 0.0, 0
    for line in io.open(DAICHO, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") != "使った" or r.get("saifu") != saifu:
            continue
        at = str(r.get("at") or "")
        if not at.startswith(key):
            continue
        total += float(r.get("yen") or 0)
        n += 1
    return round(total, 4), n


def mitsumori(saifu, yen, what="", record=True):
    """★叩く前に通す関所。戻り値 (ok, 理由)。

    ok=False のときは**叩いてはいけない**。理由は必ず呼び出し元から上へ返すこと
    （黙って0件で帰ると「動いているのに何も取れていない」になる）。
    """
    if saifu not in SAIFU:
        return False, "知らない財布です: %s" % saifu
    yen = float(yen or 0)
    s = settei()
    limit = s["limits"][saifu]
    used, _ = tsukatta_gokei(saifu, s["period"])
    nokori = round(limit - used, 4)
    tani = "今日" if s["period"] == "day" else "今月"

    if yen <= nokori:
        if record:
            _append(DAICHO, {"at": _now().isoformat(), "kind": "見積り", "saifu": saifu,
                             "yen": yen, "what": what, "limitYen": limit,
                             "usedYen": used, "nokoriYen": nokori, "ok": True})
        return True, "通しました（%s の残り %.2f円 のうち %.2f円 を使う見込み）" % (tani, nokori, yen)

    # ★止める。黙らない。
    why = ("上限で止めました。%s／%s の上限 %.0f円・すでに使った %.2f円・残り %.2f円 に対して、"
           "この1回の見積りが %.2f円 です。\n"
           "→ あと %.2f円 あれば「%s」ができます。\n"
           "→ 開けるなら: python3 tools/yosan.py --set %s %.0f"
           % (SAIFU[saifu], tani, limit, used, nokori, yen,
              max(0.0, round(yen - nokori, 2)), what or "この1回",
              saifu, max(limit, round(used + yen + 0.5))))
    if record:
        _append(DAICHO, {"at": _now().isoformat(), "kind": "止めた", "saifu": saifu,
                         "yen": yen, "what": what, "limitYen": limit,
                         "usedYen": used, "nokoriYen": nokori, "ok": False, "why": why})
        try:
            _append(OUTBOX, {"at": _now().isoformat(), "from": "yosan",
                             "text": "【予算の栓】" + why})
        except Exception:
            pass
    return False, why


def tsukatta(saifu, yen, what="", usd=None, src=""):
    """★叩いた後に実額を記録する。ここを書かないと上限が効かない。"""
    if saifu not in SAIFU:
        return False
    if yen is None and usd is not None:
        yen = float(usd) * USD_YEN
    _append(DAICHO, {"at": _now().isoformat(), "kind": "使った", "saifu": saifu,
                     "yen": round(float(yen or 0), 4), "usd": usd, "what": what,
                     "src": src, "usdYen": USD_YEN})
    return True


def show():
    s = settei()
    tani = "今日" if s["period"] == "day" else "今月"
    rows = []
    for k, label in SAIFU.items():
        used, n = tsukatta_gokei(k, s["period"])
        rows.append({"saifu": k, "label": label, "limitYen": s["limits"][k],
                     "usedYen": used, "count": n,
                     "nokoriYen": round(s["limits"][k] - used, 4)})
    return {"period": tani, "rows": rows, "usdYen": USD_YEN, "usdYenSource": USD_YEN_SOURCE,
            "settei": os.path.relpath(SETTEI, REPO), "daicho": os.path.relpath(DAICHO, REPO)}


# ---------------------------------------------------------------------------
# 外部APIを叩く口の一覧。★通っていない口を隠さない
# ---------------------------------------------------------------------------
KUCHI = [
    # (ファイル, 何の財布, 栓を通しているか, 備考)
    ("tools/gaibu_kuchi.py", "openai/xai/gemini", True,
     "ask() の頭で mitsumori、返ったあと tsukatta。kiku・nageru chappy・gaibu_kenpin の元"),
    ("tools/tanomu.py", "xai(画像)/fal", True, "run_job の頭で mitsumori"),
    ("tools/devin_start.py", "devin", True, "セッションを立てる前に mitsumori"),
    ("tools/fal_cost_ledger.py", "fal", False, "台帳だけ。叩かない（栓は不要）"),
    ("tools/_919_step1_widen.py", "fal", True, "走り出す前に mitsumori（1034番で足した）"),
    ("tools/_919_step2_video.py", "fal", True, "走り出す前に mitsumori（1034番で足した）"),
    ("tools/_636_gen_images.py", "fal", True, "走り出す前に mitsumori（1034番で足した・実演で止まった）"),
    ("tools/_636_gen_videos.py", "fal", True, "走り出す前に mitsumori（1034番で足した）"),
    ("tools/_771_gen_video.py", "fal", True, "走り出す前に mitsumori（1034番で足した）"),
    ("tools/_783_gen_voices.py", "fal", True, "走り出す前に mitsumori（1034番で足した）"),
    ("gsk（Genspark公式CLI）", "genspark", False,
     "★このリポの外（Macに入れたCLI）。ここからは栓をかけられない"),
    ("Supabase voice-session（Lovable側）", "xai(声)", False,
     "★このリポの外。声はブラウザ→Supabase→xAI と流れるので、ここの栓は通らない。"
     "止めるのは xAI コンソール側の上限（$5）と自動チャージOFF"),
]


def self_test():
    """★上限10円で11円目が本当に止まるかを、その場で確かめる。"""
    import shutil
    import tempfile
    global SETTEI, DAICHO, OUTBOX
    keep = (SETTEI, DAICHO, OUTBOX)
    d = tempfile.mkdtemp(prefix="yosan-test-")
    SETTEI = os.path.join(d, "yosan.json")
    DAICHO = os.path.join(d, "yosan.jsonl")
    OUTBOX = os.path.join(d, "outbox.jsonl")
    out = []
    try:
        set_limit("xai", 10)
        ok1, w1 = mitsumori("xai", 4.0, "テストA")
        out.append(("① 上限10円・見積り4円", ok1, True))
        tsukatta("xai", 4.0, "テストA（実額）")
        ok2, w2 = mitsumori("xai", 5.0, "テストB")
        out.append(("② 累計4円のあと5円（合計9円）", ok2, True))
        tsukatta("xai", 5.0, "テストB（実額）")
        ok3, w3 = mitsumori("xai", 2.0, "テストC")
        out.append(("③ 累計9円のあと2円（合計11円）★11円目", ok3, False))
        out.append(("④ 止めた理由に「あと何円」が入っているか",
                    ("あと" in (w3 or "") and "円" in (w3 or "")), True))
        out.append(("⑤ 止めたことが台帳に残っているか",
                    ("止めた" in io.open(DAICHO, encoding="utf-8").read()), True))
        out.append(("⑥ 止めたことが知らせ（outbox）に残っているか",
                    os.path.exists(OUTBOX) and "予算の栓" in io.open(OUTBOX, encoding="utf-8").read(),
                    True))
        set_limit("xai", 0)
        ok7, _ = mitsumori("xai", 0.01, "テストD")
        out.append(("⑦ 上限0円にしたら1銭も通らないか", ok7, False))
        ok8, _ = mitsumori("shiranai", 1.0, "テストE")
        out.append(("⑧ 知らない財布は通らないか", ok8, False))
        ng = [r for r in out if r[1] != r[2]]
        print("予算の栓 見本試験: %d件中 %d件 想定どおり" % (len(out), len(out) - len(ng)))
        for name, got, want in out:
            print("  %s %s（got=%s want=%s）" % ("◯" if got == want else "✕", name, got, want))
        if w3:
            print("\n--- 止めたときに残る文（そのまま） ---\n%s" % w3)
        return 1 if ng else 0
    finally:
        SETTEI, DAICHO, OUTBOX = keep
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--set", nargs=2, metavar=("財布", "円"))
    ap.add_argument("--check", nargs=2, metavar=("財布", "円"))
    ap.add_argument("--spent", nargs=3, metavar=("財布", "円", "何に"))
    ap.add_argument("--kuchi", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if a.set:
        set_limit(a.set[0], float(a.set[1]))
    if a.spent:
        tsukatta(a.spent[0], float(a.spent[1]), a.spent[2])
    if a.check:
        ok, why = mitsumori(a.check[0], float(a.check[1]), "手で確かめた")
        print(("◯ " if ok else "✕ ") + why)
        return 0 if ok else 1
    if a.kuchi:
        print("外部APIを叩く口（栓を通しているか）")
        for f, saifu, gated, note in KUCHI:
            print("  %s %-38s %-18s %s" % ("◯" if gated else "✕", f, saifu, note))
        nashi = [k for k in KUCHI if not k[2]]
        print("\n★通っていない口 %d本。上のとおり名指しで出しています（隠していません）。" % len(nashi))
        return 0
    s = show()
    print("予算の栓（%s・1ドル%.2f円）" % (s["period"], s["usdYen"]))
    print("  %-10s %-34s %8s %8s %8s" % ("財布", "何に使うか", "上限", "使った", "残り"))
    for r in s["rows"]:
        print("  %-10s %-34s %8.2f %8.2f %8.2f"
              % (r["saifu"], r["label"], r["limitYen"], r["usedYen"], r["nokoriYen"]))
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
