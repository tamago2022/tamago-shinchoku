#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1177番【棚の推測】投げたものの中身を読んで、174本の棚のどれに合うかを機械で当てる。

たまごさん（2026-09-25・原文）:
  「どこの棚に入れるかの指定はどうしようか。口頭で言えばいいのか、
    メモやリンクを貼って送信するだけで済むようにするか。」
  → ★決まったこと：**棚の指定は任意。空なら機械が推測して仮の棚を付ける。**後から直せる。

■ なぜこれが要るか（実測の詰まり）
  status/public/nagekomi_shelf.json（2026-09-25 00:00 の便）
    seen 14 / ireta 0 / mitei 11 ← **11件すべて「行き先の棚がまだ決まっていません」で止まっていた。**
  箱は直っていた。台帳にも入っていた。**棚が空なだけで、1件も棚へ行けていなかった。**
  だから穴はここ1点。ここを埋めると、あとは既にある道（nagekomi_shelf.run）がそのまま流れる。

■ 決め（なぜこの形か）
  ・**棚の名簿を手打ちしない。**status/public/tana_ichiran.json（tana.py が正本から吐いたもの）だけを読む。
    棚が増えたら推測の語彙も勝手に増える。ここに棚名を1つも書かない。
  ・**合う棚が無ければ「新しい棚が要る」と言う。勝手に新設しない。**（棚を増やしすぎない）
  ・**推測は「仮」だと分かる形でしか返さない。**confidence と根拠の語を必ず一緒に返す。
    受付一覧には「仮」と出る。後から棚のボタンで直せる。
  ・**AIを呼ばない。0円。ネットに出ない。**だからサンドボックスでも工場でも同じ答えが出る。
  ・★**当たった根拠の語を必ず返す。**「なぜその棚なのか」が読めないものは、直す気にもならない。

■ 当て方（これだけ）
  ① 棚の題名そのものを語彙にする（「麺」「カレーの棚」→「麺」「カレー」）
  ② 日本語↔英語の言い換え表 SYN を通す（soup→スープ、cat→猫、beef→肉）
  ③ 投げたものの題名・チャンネル名・ひとこと・URL を1本の文にして、語が何回出るかを数える
  ④ いちばん点の高い棚を返す。★2位と差が無いときは「迷った」と正直に返す（決めつけない）

使い方:
  python3 tools/tana_suiron.py --selftest          # 台帳の実物14件で当ててみる（0円・ネット不要）
  python3 tools/tana_suiron.py --text "..."        # 文字を1本投げて当てる
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ICHIRAN = os.path.join(REPO, "status", "public", "tana_ichiran.json")
LEDGER = os.path.join(REPO, "status", "nagekomi.jsonl")

# 棚の題名から語を取るときに落とす飾り（「カレーの棚」→「カレー」）
KAZARI = ["の棚", "棚", "横丁", "路地", "広場", "実験室", "食堂", "案内所", "部屋", "コーナー"]
# 語彙にしても当たらない（どこにでも出る）ので数えない語
TOMARI = {"の", "と", "は", "が", "に", "を", "もの", "こと", "世界", "ごきげん", "その他",
          "いろいろ", "おすすめ", "特集", "新着", "まとめ", "映像", "動画", "音", "良い"}

# ★日本語↔英語・言い換え。**棚名は書かない。**「この語が出たらこの語と同じ」だけを書く。
#   （棚名を書くと名簿が2か所になる。増えた棚に追従しなくなる）
SYN = {
    "スープ": ["soup", "スープ", "汁", "みそ汁", "味噌汁", "ポタージュ", "broth", "だし", "出汁",
             "鍋", "nabe", "hotpot", "hot pot", "シチュー", "stew", "chowder", "ramen broth"],
    "麺": ["麺", "noodle", "noodles", "ラーメン", "ramen", "うどん", "udon", "そば", "soba",
          "パスタ", "pasta", "焼きそば", "yakisoba", "pho", "フォー"],
    "パスタ": ["パスタ", "pasta", "spaghetti", "スパゲ", "ペンネ", "carbonara", "カルボナーラ"],
    "肉": ["肉", "meat", "beef", "牛", "pork", "豚", "chicken", "鶏", "lamb", "羊", "steak",
          "ステーキ", "焼肉", "bbq", "barbecue", "ribs", "bacon", "ベーコン"],
    "卵": ["卵", "たまご", "egg", "eggs", "omelet", "オムレツ", "目玉焼き"],
    "野菜": ["野菜", "vegetable", "veggie", "salad", "サラダ", "白菜", "cabbage", "トマト",
           "tomato", "きのこ", "mushroom", "茄子", "なす"],
    "芋": ["芋", "いも", "potato", "fries", "ポテト", "さつまいも", "sweet potato"],
    "魚介": ["魚", "fish", "seafood", "海鮮", "寿司", "sushi", "蟹", "crab", "海老", "shrimp",
           "prawn", "牡蠣", "oyster", "貝", "タコ", "octopus", "イカ", "squid"],
    "海の幸": ["魚", "fish", "seafood", "海鮮", "寿司", "sushi", "蟹", "crab", "海老", "shrimp"],
    "パン": ["パン", "bread", "sandwich", "サンド", "toast", "トースト", "ピザ", "pizza",
           "バーガー", "burger", "croissant", "クロワッサン", "bagel"],
    "チーズ": ["チーズ", "cheese", "raclette", "ラクレット", "モッツァレラ", "mozzarella"],
    "カレー": ["カレー", "curry", "スパイス", "spice", "masala", "マサラ"],
    "中華": ["中華", "chinese", "餃子", "gyoza", "dumpling", "点心", "麻婆", "mapo", "炒飯",
           "チャーハン", "fried rice"],
    "ご飯": ["ご飯", "ごはん", "rice", "丼", "どんぶり", "おにぎり", "onigiri", "米"],
    "甘": ["スイーツ", "sweet", "dessert", "デザート", "ケーキ", "cake", "チョコ", "chocolate",
          "アイス", "ice cream", "プリン", "pudding", "パフェ", "菓子", "candy", "donut", "ドーナツ"],
    "酒": ["酒", "sake", "beer", "ビール", "wine", "ワイン", "cocktail", "カクテル", "whisky",
          "ウイスキー", "bar", "居酒屋", "izakaya", "highball", "ハイボール"],
    "ソース": ["ソース", "sauce", "タレ", "dressing", "ドレッシング", "マヨ", "mayo", "dip", "ディップ"],
    "朝ごはん": ["朝ごはん", "朝食", "breakfast", "モーニング", "brunch", "ブランチ"],
    "屋台": ["屋台", "street food", "stall", "market", "市場", "食堂", "diner"],
    "キャンプ": ["キャンプ", "camp", "camping", "焚き火", "bonfire", "outdoor", "アウトドア", "bbq"],
    "猫": ["猫", "ねこ", "ネコ", "cat", "cats", "kitten", "子猫", "にゃ", "meow"],
    "犬": ["犬", "いぬ", "イヌ", "dog", "dogs", "puppy", "子犬", "わんこ", "柴", "shiba",
          "bulldog", "frenchie", "corgi", "コーギー", "retriever"],
    "動物": ["動物", "animal", "アライグマ", "raccoon", "パンダ", "panda", "リス", "squirrel",
           "カピバラ", "capybara", "鳥", "bird", "うさぎ", "rabbit", "bunny", "ハムスター",
           "hamster", "キツネ", "fox", "アルパカ", "alpaca", "ペンギン", "penguin"],
    "赤ちゃん": ["赤ちゃん", "baby", "babies", "幼児", "toddler", "子ども", "kids", "child"],
    "音楽": ["音楽", "music", "song", "曲", "バンド", "band", "ライブ", "live", "concert",
           "コンサート", "cover", "歌", "sing", "singer", "official music video", "mv"],
    "ダンス": ["ダンス", "dance", "dancing", "踊", "choreography", "振付", "ballet", "バレエ"],
    "ピアノ": ["ピアノ", "piano", "keyboard", "鍵盤"],
    "ギター": ["ギター", "guitar", "riff", "リフ"],
    "笑": ["笑", "funny", "笑える", "コメディ", "comedy", "ネタ", "漫才", "コント", "prank",
          "fail", "爆笑", "ツッコミ", "ボケ"],
    "モノマネ": ["モノマネ", "ものまね", "impression", "impersonat", "パロディ", "parody"],
    "旅": ["旅", "travel", "trip", "旅行", "観光", "tour", "散歩", "walk", "walking tour"],
    "東京": ["東京", "tokyo", "渋谷", "shibuya", "新宿", "shinjuku", "浅草", "asakusa"],
    "AI": ["ai", "人工知能", "chatgpt", "claude", "gemini", "robot", "ロボット", "生成ai"],
    "宇宙": ["宇宙", "space", "rocket", "ロケット", "starship", "nasa", "spacex", "月", "moon",
           "火星", "mars", "衛星", "satellite"],
    "生活": ["生活", "暮らし", "掃除", "cleaning", "収納", "整理", "life hack", "ライフハック",
           "便利", "diy", "修理", "repair"],
    "手仕事": ["手仕事", "職人", "craft", "handmade", "工芸", "製造", "how it's made", "作り方",
            "recipe", "レシピ", "料理"],
}


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower())


def _tokens_of_title(title):
    """棚の題名から数える語を取る。飾りを落として、区切り（空白・全角空白・読点）で割る。"""
    t = title or ""
    for k in KAZARI:
        t = t.replace(k, " ")
    parts = re.split(r"[\s　、,／/・]+", t)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and p not in TOMARI:
            out.append(p)
        elif len(p) == 1 and p in ("麺", "肉", "卵", "芋", "酒", "旅", "米"):
            out.append(p)           # 1文字でも中身のある語
    return out


def load_shelves(path=None):
    try:
        d = json.load(io.open(path or ICHIRAN, encoding="utf-8"))
    except Exception:
        return []
    return [s for s in (d.get("shelves") or []) if s.get("id") and s.get("title")]


def vocab_of(shelf):
    """その棚を当てるための語の一覧。（棚の題名 ＋ SYN で言い換えた分）"""
    words = set()
    for tok in _tokens_of_title(shelf.get("title") or ""):
        words.add(tok.lower())
        for key, syns in SYN.items():
            if key in tok or tok in key:
                for s in syns:
                    words.add(s.lower())
    return words


def material_of(row):
    """投げた1件から、当てるのに使う文を1本作る。"""
    return " ".join(str(row.get(k) or "") for k in
                    ("title", "channel", "memo", "url", "copyDirection"))


def guess(text, shelves=None, min_score=2.0):
    """(棚, 点, 当たった語, 候補一覧) を返す。決まらなければ棚は None。

    ★点は「当たった語の長さの合計」。長い語（ラクレット）が当たる方が、
      短い語（肉）が当たるより確か、という素直な数え方にしている。
    """
    shelves = shelves if shelves is not None else load_shelves()
    t = _norm(text)
    scored = []
    for s in shelves:
        hit = []
        pt = 0.0
        for w in vocab_of(s):
            if not w:
                continue
            if w in t:
                hit.append(w)
                pt += min(len(w), 6) / 2.0        # 2文字=1.0点、6文字以上=3.0点で頭打ち
        if pt > 0:
            # ★同じ意味の語が何個も当たっても水増ししない（上位3語まで）
            hit.sort(key=len, reverse=True)
            pt = sum(min(len(w), 6) / 2.0 for w in hit[:3])
            scored.append({"id": s["id"], "title": s["title"], "world": s.get("world") or "",
                           "score": round(pt, 1), "hit": hit[:6]})
    scored.sort(key=lambda x: (-x["score"], x["title"]))
    if not scored or scored[0]["score"] < min_score:
        return None, 0.0, [], scored[:3]
    top = scored[0]
    # 1位と2位が同点なら決めつけない（「迷った」として返す）
    if len(scored) > 1 and scored[1]["score"] >= top["score"]:
        return None, top["score"], top["hit"], scored[:3]
    return top, top["score"], top["hit"], scored[:3]


def guess_row(row, shelves=None):
    """台帳の1行に対する答え。受付一覧にそのまま出せる形で返す。"""
    top, pt, hit, cand = guess(material_of(row), shelves)
    if top:
        return {"ok": True, "shelfId": top["id"], "shelf": top["title"],
                "world": top["world"], "score": pt, "hit": hit, "kari": True,
                "why": "仮の棚（当たった語：%s）" % "・".join(hit[:3])}
    if cand:
        return {"ok": False, "kari": False, "score": pt, "candidates": cand,
                "why": "★新しい棚が要ります（近い棚：%s。どれも決め手に足りません）"
                       % "／".join("%s(%.1f)" % (c["title"], c["score"]) for c in cand)}
    return {"ok": False, "kari": False, "score": 0.0, "candidates": [],
            "why": "★新しい棚が要ります（合う棚が1つもありません）"}


def selftest():
    shelves = load_shelves()
    print("棚の名簿 %d本" % len(shelves))
    rows = []
    try:
        for line in io.open(LEDGER, encoding="utf-8"):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    except Exception as e:
        print("台帳が読めません: %s" % e)
    ok = 0
    for r in rows:
        g = guess_row(r, shelves)
        mark = "◯" if g["ok"] else "×"
        if g["ok"]:
            ok += 1
        print("%s %-12s %-58s → %s" % (
            mark, r.get("id"), (r.get("title") or "")[:56].replace("\n", " "),
            (g.get("shelf") or "") + " " + g["why"][:70]))
    print("---- 当たった %d / %d" % (ok, len(rows)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--text")
    a = ap.parse_args()
    if a.text:
        top, pt, hit, cand = guess(a.text)
        print(json.dumps({"shelf": top, "score": pt, "hit": hit, "candidates": cand},
                         ensure_ascii=False, indent=1))
        return 0
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
