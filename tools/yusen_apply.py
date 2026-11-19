#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026-10-01 たまごさんが決めた優先順位（正本：status/yusen_2026-10-01.md）を queue.json の票に反映する。

★票は1枚も消さない。変えるのは priority（A=1…E=5）と yusen（ラベル）だけ。
★D・E・不要・保留・デザイン側は「保留」＝ status を hold にして発車させない（元の状態は statusBefore に控える）。
★元の優先度は prioBefore に控える（何度流しても最初の値を上書きしない＝やり直し可能）。
★進行中(running)・済み(done/cancelled)・確認待ち(review等)は状態を触らない。開いている票（waiting/hold/stuck/later）だけ。

使い方：
  command_ingest の受信箱アクション "queue_yusen"（鍵の中で apply(q) を呼ぶ）
  python3 tools/yusen_apply.py --dry   … 件数だけ数える（書き込まない）
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RUN_ID = "2026-10-01"
MD = os.path.join(REPO, "status", "yusen_2026-10-01.md")
RESULT = os.path.join(REPO, "status", "yusen_2026-10-01_result.json")

OPEN = ("waiting", "hold", "stuck", "later")
HOLDABLE = ("waiting", "stuck", "later")

# 上から順に見て、最初に当たったものを採用する（狭いもの・止めるものを先に置く）。
# (ラベル, 優先度, 保留にするか, 当てる正規表現, 外す正規表現)
RULES = [
    ("不要", 5, True, r"自動投稿.*(Twitter|ツイッター|許可)|(Twitter|ツイッター).*自動投稿|SNS自動投稿|準備中|セプテンバー|「名カバー」", None),
    ("デザイン側（触らない）", 5, True, r"コンシェルジュ.*(見た目|デザイン|外観|衣装)|(見た目|デザイン).*コンシェルジュ", None),
    ("保留（Kling等の試作）", 5, True, r"Kling|kling|クリング|Hedra|HeyGen", None),
    ("A①コンシェルジュ", 1, False, r"コンシェルジュ|口パク|リップシンク|口の(形|動き|パラメータ)|つないでいます|勧める理由|声の(1日|上限)|円で表示|1回の費用", None),
    ("A②豆知識を声で", 1, False, r"豆知識", None),
    ("A③補給所を軽く", 1, False, r"補給所.*(軽く|軽量|重い|重く)|多言語|クラウドセッション|Macを重く", None),
    ("A④工場が止まらない", 1, False, r"工場.*(止ま|死な|止め)|半永久", r"【空回し】"),
    ("A⑤やりっぱなしゼロ", 1, False, r"やりっぱなし|やりっ放し", None),
    ("A⑥アバター", 1, False, r"Live2D|live2d|アバター", None),
    ("その他", 3, False, r"相互リンク|(進捗表.*投げ込み|投げ込み.*進捗表).*リンク", None),
    ("A⑦投げ込み箱→棚", 1, False, r"投げ込み", None),
    ("AかB落ちても再開", 2, False, r"落ちても|続きから再開", None),
    ("その他", 3, False, r"アーティストページ.*自動(登録|で)|同名別人|犬|飼い主|進捗表.*整理", None),
    ("D", 4, True, r"Notion|ノーション|(Vault|ボールト|ボルト).*zip|zip.*Genspark|判定役|Jev", None),
    ("DかE独自ドメイン", 5, True, r"ドメイン", None),
    ("E", 5, True, r"相続|公文書|行政の(難しい)?資料", None),
    ("B", 2, False, r"動画が(無|な)い|動画の(無|な)い|^GH\d+|Jules|Devin|外部担当|クレジット配分|クレジット.*(オーバー|使いすぎ)", None),
    ("C", 3, False, r"AI作曲|(Spotify|スポティファイ).*プレイリスト|国別|ペルソナ|Genspark", None),
    ("BかC", 3, False, r"再生バー|シークバー|40曲|国民的歌手|仕入れ|Obsidian.*(遅|重)", None),
    ("CかD Spotify連携", 4, False, r"Spotify|スポティファイ", None),
]
_COMPILED = [(lab, p, h, re.compile(a), re.compile(n) if n else None) for (lab, p, h, a, n) in RULES]
UNSORTED = "未仕分け"


def classify(it):
    text = "%s %s" % (it.get("title") or "", it.get("hyoudai") or "")
    for lab, p, h, a, n in _COMPILED:
        if a.search(text) and not (n and n.search(text)):
            return lab, p, h
    return UNSORTED, None, False


def bucket(label):
    """報告用のまとめ先（A／AかB／B／BかC／C／CかD／その他／未仕分け／保留）。"""
    if label.startswith("A①") or label[:2] in ("A②", "A③", "A④", "A⑤", "A⑥", "A⑦"):
        return "A"
    if label.startswith("AかB"):
        return "AかB"
    if label == "B":
        return "B"
    if label == "BかC":
        return "BかC"
    if label == "C":
        return "C"
    if label.startswith("CかD"):
        return "CかD"
    if label in ("その他", UNSORTED):
        return label
    return "保留"   # D・DかE・E・不要・保留・デザイン側


def apply(q, dry=False):
    now = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    counts = {}
    rows = []
    for it in q.get("items") or []:
        st = it.get("status")
        if st not in OPEN or it.get("test"):
            continue
        lab, p, hold = classify(it)
        b = bucket(lab)
        counts[b] = counts.get(b, 0) + 1
        rows.append({"n": it.get("n"), "title": (it.get("title") or "")[:60], "yusen": lab, "bucket": b})
        if dry:
            continue
        first = it.get("yusenRunId") != RUN_ID
        if first:
            it["prioBefore"] = it.get("priority")
        it["yusen"] = lab
        it["yusenRunId"] = RUN_ID
        it["yusenAt"] = now
        if p is not None:
            it["priority"] = p
        elif lab == UNSORTED:
            # 正本に載っていない票は、A・Bを追い越さないよう C（3）より上には置かない
            cur = it.get("priority")
            if isinstance(cur, int) and cur < 3:
                it["priority"] = 3
        if hold and st in HOLDABLE:
            if first or "statusBefore" not in it:
                it["statusBefore"] = st
            it["status"] = "hold"
            it["holdNote"] = "【2026-10-01 たまごさんの優先順位】%s のため保留（発車させない）" % lab
    order = ["A", "AかB", "B", "BかC", "C", "CかD", "その他", "未仕分け", "保留"]
    line = "・".join("%s%d件" % (k, counts.get(k, 0)) for k in order) + "に振り直した"
    return line, counts, rows


def write_result(line, counts, rows):
    out = {"runId": RUN_ID, "doneAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "line": line,
           "counts": counts, "items": rows}
    tmp = RESULT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RESULT)
    try:
        with io.open(MD, "a", encoding="utf-8") as f:
            f.write("\n\n## 反映結果（機械・%s）\n\n%s\n\n明細：status/yusen_2026-10-01_result.json\n"
                    % (out["doneAt"], line))
    except Exception:
        pass


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    import queue_store
    qq = queue_store.load_queue()
    ln, c, r = apply(qq, dry=True)
    print(ln)
