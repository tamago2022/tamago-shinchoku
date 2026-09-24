#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1075番【Xの投稿をGrokに拾わせる】残り分を、xAI公式の道で取る。

たまごさん（2026-09-24・原文）:
  「Grok / xAI。Xの投稿はxAI自身のもの。」

★なぜこの道か（推測ではなく公式の作り）
  xAI の chat/completions には **Live Search** があり、
  `search_parameters.sources` に `{"type":"x","x_handles":[...]}` を渡すと
  **その人のXの投稿だけ**を探しにいく。スクレイピングではない。
  ＝x.com のHTMLに5件しか載っていなくても、残りを拾える見込みがある。

★お金（憶測で書かない）
  xAI の Live Search は **探した情報源1件につき課金**される方式。
  だから叩く前に必ず tools/yosan.py の栓を通す。上限を超えるなら**叩かない**。
  1回の呼び出しで拾う情報源の上限を `max_search_results` で**こちらから縛る**。

━━ 決まり ━━
  ★工場（Mac）側でだけ走る（サンドボックスからは api.x.ai に出られない）。
  ★鍵の値を返り値にもログにも1文字も書かない。
  ★1件も投稿しない。読むだけ。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT_DIR = os.path.join(REPO, "status", "1075_x")
URL = "https://api.x.ai/v1/chat/completions"
SAIFU = "xai"

# ★1情報源あたりの実費の見積もり（公式の $25 / 1000 sources を 1ドル155円で換算）
YEN_PER_SOURCE = 25.0 / 1000 * 155


def _key():
    import zandaka
    return zandaka.find_key("XAI_API_KEY", "GROK_API_KEY")


def run_job(payload):
    payload = payload or {}
    op = payload.get("op") or "shirabe"
    user = (payload.get("user") or "oasisjoyrelief").lstrip("@")
    max_src = int(payload.get("maxSources") or 20)

    k = _key()
    if op == "shirabe":
        # ★鍵が「有るか無いか」だけ。値は返さない。1円も出ない。
        return {"ok": bool(k), "op": op,
                "kagiAri": bool(k),
                "mitsumoriYen": round(YEN_PER_SOURCE * max_src, 1),
                "memo": "叩くときは yosan の栓を通します" if k else "xAIの鍵がありません",
                "totalYen": 0.0}

    if op != "toru":
        return {"ok": False, "error": "知らない op です", "totalYen": 0.0}
    if not k:
        return {"ok": False, "error": "xAIの鍵がありません（値は探しません）",
                "totalYen": 0.0}

    mitsu = round(YEN_PER_SOURCE * max_src, 1)
    try:
        import yosan
        ok, why = yosan.mitsumori(SAIFU, mitsu, "Xの投稿を拾う（情報源%d件まで）" % max_src)
    except Exception as e:
        return {"ok": False, "error": "予算の栓を通せませんでした: %s" % str(e)[:120],
                "totalYen": 0.0}
    if not ok:
        return {"ok": False, "tomatta": True, "error": why,
                "mitsumoriYen": mitsu, "totalYen": 0.0}

    toi = ("Xのアカウント @%s の投稿を、**できるだけ古いものまで**そのまま集めてください。\n"
           "各投稿について、次のJSONの配列だけを返してください（説明文は書かないでください）:\n"
           '[{"url":"投稿のURL","itsu":"YYYY-MM-DD","honbun":"本文をそのまま・省略しない"}]\n'
           "本文は要約せず、改行もそのまま入れてください。" % user)

    body = json.dumps({
        "model": payload.get("model") or "grok-4-fast",
        "messages": [{"role": "user", "content": toi}],
        "search_parameters": {
            "mode": "on",
            "return_citations": True,
            "max_search_results": max_src,
            "sources": [{"type": "x", "x_handles": [user]}],
        },
    }).encode("utf-8")

    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + k, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        code = getattr(e, "code", 0)
        return {"ok": False, "error": "xAIが %s を返しました（%s）"
                % (code or "?", type(e).__name__), "totalYen": 0.0}

    txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    used = ((d.get("usage") or {}).get("num_sources_used")
            or (d.get("usage") or {}).get("num_search_queries") or 0)
    yen = round(YEN_PER_SOURCE * (used or 0), 1)
    try:
        import yosan
        yosan.tsukatta(SAIFU, yen, "Xの投稿を拾う（情報源%s件）" % used)
    except Exception:
        pass

    toukou = []
    try:
        s = txt[txt.index("["):txt.rindex("]") + 1]
        toukou = json.loads(s)
    except Exception:
        pass

    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "grok_%s.json" % user)
    json.dump({"at": time.strftime("%F %T"), "user": user, "kensu": len(toukou),
               "toukou": toukou, "namaHenji": txt[:20000],
               "citations": d.get("citations") or []},
              io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    return {"ok": bool(toukou), "op": op, "user": user, "kensu": len(toukou),
            "jouhougen": used, "byou": round(time.time() - t0, 1),
            "file": os.path.relpath(p, REPO), "totalYen": yen}


if __name__ == "__main__":
    print(json.dumps(run_job({"op": sys.argv[1] if len(sys.argv) > 1 else "shirabe"}),
                     ensure_ascii=False, indent=1))
