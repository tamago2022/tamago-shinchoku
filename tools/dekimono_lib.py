#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「できたもの」棚（status/dekimono.json）への自動登録ロジック（2026-09-07・616番）。

たまごさん「成果物ができたら、自動でここに載る。セッションが手で登録しない」への対応。
仕事が status:done になった瞬間（queue_ok / auto_launcher.py の自動OK、両方）から
この関数を呼ぶ。呼ぶ側は「終わった」ことしか知っていればよく、
「載せるべきかどうか」の判断はここに閉じ込める。

判定はキーワードによる一次分類（v1・完璧ではない）。
「仕組み：」「〜を直す」「点検」等の内部作業・修正は除外し、
動画/音/記事/ページ/資料に当てはまる新規の成果物だけを載せる。
迷ったときは「載せない」を選ぶ（誤って修正を混ぜる方が実害が大きいため）。
"""
import io
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEKI_PATH = os.path.join(REPO, "status", "dekimono.json")

DELIVER_TYPES = [
    ("動画", ["動画", "アニメ", "卵劇場", "EP0", "fal試作", "fal 試作", "カット再生", "ffmpeg", "微動ループ"]),
    ("音", ["音源", "ポッドキャスト", "朗読", "聴き比べ", "効果音を作", "BGMを作"]),
    ("記事", ["特集記事", "マガジン", "記事を作", "コラムを作", "特集を作"]),
    ("ページ", ["パーソナライズ", "入口ページ", "welcome/", "専用ページ", "診断ページ", "試作ページ"]),
    ("資料", ["早見表", "教科書", "教材", "裏取りレポート", "調査レポート", "分析レポート", "犯人特定",
             "やり方まとめ", "実費内訳"]),
]

# これらが含まれる時は「修正・内部作業」とみなし、載せない
# （ただしタイトル自体に強い成果物ワードがある場合は残す＝下の関数内で判定）
FIX_SIGNALS = [
    "仕組み：", "仕組み(", "を直す", "を直した", "を直して", "修正する", "修正した", "修正版",
    "バグ", "不具合", "エラーを", "点検", "崩れ", "戻す", "消す", "軽くする", "治す", "なおす",
    "検品", "揃える", "並べ替え", "差し替え", "切り替える", "見張り", "監視", "統一する",
]

STRONG_TITLE_WORDS = [
    "卵劇場", "早見表", "教科書", "ポッドキャスト", "朗読", "マガジン", "パーソナライズ",
    "犯人特定", "やり方まとめ",
]


def classify(title, result_text=""):
    """成果物として載せるべきタイプ（動画/音/記事/ページ/資料）を返す。該当なしはNone。"""
    title = title or ""
    text = title + " " + (result_text or "")
    matched = None
    for t, kws in DELIVER_TYPES:
        if any(k in text for k in kws):
            matched = t
            break
    if not matched:
        return None
    if any(f in text for f in FIX_SIGNALS) and not any(w in title for w in STRONG_TITLE_WORDS):
        return None
    return matched


def _load():
    if not os.path.exists(DEKI_PATH):
        return {"updatedAt": "", "items": []}
    try:
        return json.load(io.open(DEKI_PATH, encoding="utf-8"))
    except Exception:
        return {"updatedAt": "", "items": []}


def _save(d):
    tmp = DEKI_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DEKI_PATH)


def _first_line(text, limit=80):
    if not text:
        return ""
    line = text.strip().splitlines()[0] if text.strip() else ""
    # 【完了】等の飾りを軽く落とす
    line = line.replace("【完了】", "").strip()
    return line[:limit]


def append_if_deliverable(n, title, result_text="", urls=None):
    """status:done になった仕事を判定し、成果物なら status/dekimono.json へ1件追記する。
    戻り値: 追記したら True、対象外・既存なら False。呼び出し側はエラーで工程を止めないこと。"""
    try:
        t = classify(title, result_text)
        if not t:
            return False
        d = _load()
        items = d.get("items") or []
        if any(it.get("n") == n for it in items):
            return False  # 同じ番号は二重に載せない
        url = ""
        for u in (urls or []):
            if u:
                url = u
                break
        what = _first_line(result_text) or (title or "")
        items.append({
            "n": n,
            "type": t,
            "title": title or "",
            "what": what,
            "url": url,
            "addedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        })
        d["items"] = items
        d["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        _save(d)
        return True
    except Exception:
        return False
