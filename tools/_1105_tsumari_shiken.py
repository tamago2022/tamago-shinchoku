#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-11-05 わざと1便を詰まらせて、それでも次の便が流れるかを確かめる試験（1回きり・Haiku・数分）。
制作便に並び順（order 1〜4＝いつもの仕事より先）も付ける。結果は status/itsumo/tsumari_shiken.json。"""
import io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import command_ingest
from command_ingest import queue_lock, _load_queue, _save_queue
LABEL = "試験｜わざと詰まらせる便（2026-11-05・4分で切られて次へ進むかを見る）"
st, msg = command_ingest.queue_add(
    "【試験・何も作らない】Bash で `sleep 1500` を1回だけ実行して待つ。終わったら「試験おわり」とだけ書いて終わる。"
    "ファイルを作らない・直さない・push しない・たまごさんに質問しない。", priority=1, label=LABEL, origin="factory",
    model="claude-haiku-4-5", urgent=True)
with queue_lock():
    q = _load_queue(); n = None
    for it in q["items"]:
        if it.get("title") == LABEL and it.get("status") == "waiting":
            it.update({"limitMin": 4, "order": 0, "fixedModel": "claude-haiku-4-5", "model": "claude-haiku-4-5",
                       "tsumariShiken": True}); n = it["n"]
        k = it.get("chuuKey")
        if k:
            it["order"] = {"uchu_unko_taki_v3": 1, "haikyo_mall_204017": 2, "hongkong_crane_204018": 3, "god_funky_bansen": 4}.get(k, 5)
    _save_queue(q)
json.dump({"at": time.strftime("%F %T"), "n": n, "st": st, "msg": str(msg)[:200]},
          io.open(os.path.join(REPO, "status", "itsumo", "tsumari_shiken.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(n, st, msg)
