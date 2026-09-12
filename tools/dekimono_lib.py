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

【2026-09-12追記・759番】たまごさん「昨日ちらっと『できたもの』で中目黒のやつが上がってて、
今もう見つけられなかった。ちゃんと『直した系』のカテゴライズ...これも埋もれちゃうと困る」。
上のロジックは「新しく作ったもの」だけを載せ、修正・内部作業は載せない設計だった＝
直したものの行き場がどこにも無かった（✅完了は1週間で流れて消える）。
ここに kind（"new"=新しく作った／"fixed"=直した）を追加し、record_done() を新しい入口にする。
新しく作った判定に当てはまらない完了は、原則すべて「直した」として同じ棚（消えない）へ積む
（純粋な内部配管作業＝INTERNAL_ONLY_SIGNALSだけは今まで通り除外＝たまごさんが見て
嬉しい・探したいものではないため）。
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
             "やり方まとめ", "実費内訳", "がっつりまとめ", "調べてVault", "調べてまとめ"]),
]

# これらが含まれる時は「修正・内部作業」とみなし、"新しく作った"側には載せない
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

# 759番：純粋な内部配管作業（たまごさんが「できたもの」として探したいものではない）は
# 「直した」棚にも載せない。範囲は狭くしてある（迷ったら載せる側＝中目黒のような
# 実物のページ修正まで消してしまう事故を繰り返さない）。
INTERNAL_ONLY_SIGNALS = [
    "仕組み：", "仕組み(", "点検", "見張り", "監視", "巡回", "重複を", "重複%", "並べ替え",
    "台帳", "ハートビート", "心臓が止まって", "キャッシュ", "ロックを", "ロックが",
]


def _match_type(text):
    for t, kws in DELIVER_TYPES:
        if any(k in text for k in kws):
            return t
    return None


def classify(title, result_text=""):
    """"新しく作った"として載せるべきタイプ（動画/音/記事/ページ/資料）を返す。該当なしはNone。"""
    title = title or ""
    text = title + " " + (result_text or "")
    matched = _match_type(text)
    if not matched:
        return None
    if any(f in text for f in FIX_SIGNALS) and not any(w in title for w in STRONG_TITLE_WORDS):
        return None
    return matched


def _is_internal_only(text):
    return any(s in text for s in INTERNAL_ONLY_SIGNALS)


def classify_fix(title, result_text=""):
    """"直した"として載せるべきタイプを返す。純粋な内部配管作業だけはNone（載せない）。
    タイプが動画/音/記事/ページ/資料のどれにも当てはまらない一般的な修正は「修正」にする。"""
    title = title or ""
    text = title + " " + (result_text or "")
    if _is_internal_only(text):
        return None
    return _match_type(text) or "修正"


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


def _append(d, n, kind, t, title, result_text, urls, added_at=None):
    items = d.get("items") or []
    if any(it.get("n") == n for it in items):
        return False
    url = ""
    for u in (urls or []):
        if u:
            url = u
            break
    what = _first_line(result_text) or (title or "")
    items.append({
        "n": n,
        "kind": kind,  # "new"=新しく作った／"fixed"=直した
        "type": t,
        "title": title or "",
        "what": what,
        "url": url,
        "addedAt": added_at or time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    })
    d["items"] = items
    d["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    return True


def append_if_deliverable(n, title, result_text="", urls=None, added_at=None):
    """status:done になった仕事を判定し、"新しく作った"成果物なら status/dekimono.json へ1件追記する。
    戻り値: 追記したら True、対象外・既存なら False。呼び出し側はエラーで工程を止めないこと。
    【互換のため残す】新規呼び出しは record_done() を使うこと。"""
    try:
        t = classify(title, result_text)
        if not t:
            return False
        d = _load()
        ok = _append(d, n, "new", t, title, result_text, urls, added_at)
        if ok:
            _save(d)
        return ok
    except Exception:
        return False


def append_fix(n, title, result_text="", urls=None, added_at=None):
    """"直した"（不具合の修正・コピーの手直し等）として status/dekimono.json へ1件追記する。
    純粋な内部配管作業は載せない（classify_fixがNoneを返す）。"""
    try:
        t = classify_fix(title, result_text)
        if not t:
            return False
        d = _load()
        ok = _append(d, n, "fixed", t, title, result_text, urls, added_at)
        if ok:
            _save(d)
        return ok
    except Exception:
        return False


def record_done(n, title, result_text="", urls=None, added_at=None):
    """759番で新設：done になった仕事すべての入口。まず"新しく作った"判定を試し、
    当てはまらなければ"直した"として同じ棚（消えない）へ積む。
    戻り値: "new" / "fixed" / None（純粋な内部配管作業で、どちらにも載せなかった）。"""
    try:
        d = _load()
        items = d.get("items") or []
        if any(it.get("n") == n for it in items):
            return None
        t = classify(title, result_text)
        if t:
            if _append(d, n, "new", t, title, result_text, urls, added_at):
                _save(d)
                return "new"
            return None
        t = classify_fix(title, result_text)
        if t:
            if _append(d, n, "fixed", t, title, result_text, urls, added_at):
                _save(d)
                return "fixed"
        return None
    except Exception:
        return None
