#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""週の作業配分（見たいもの／裏方／予備）を判定するための共通部品。

背景（店主指示）：
  「今週いろんな無駄なタスク（裏方＝仕組み・点検・整理）を走らせて、本当に見たかった
  コンシェルジュ実装ができなかった」。実測で125本の子セッション中、上位7件$147が
  全部「直す・整理する・点検する」の裏方仕事で、たまごさんが見たかったものは
  上位に1件も無かった。これを構造的に防ぐため、週の作業配分を
  「見たいもの60%／裏方30%／予備10%」で管理し、裏方が枠を使い切ったら自動で止める。

「1」＝見たいもの と「4」＝裏方 の定義（取り違え厳禁）：
  1（見たいもの）＝作る（ストップモーション・コンシェルジュ・商品・ページ）／
    たまごさんが「ここ間違ってる」と言ったものを直す／試す（fal・音声等の新規実験）
  4（裏方）＝AIが動きやすい環境・AIが間違えない仕組み・工場が回り続ける仕組み・
    効率化・Lovableが軽くなる・検品・台帳・巻き戻り対策
  たまごさんが実機を見て「これ違う」と言ったものは全部「1」。裏方に分類してはいけない。
"""
import datetime

JST = datetime.timezone(datetime.timedelta(hours=9))

# 緊急＝予備枠（yobi）へ。本番停止・障害等は「見たいもの／裏方」の配分そのものを止めてでも対応する。
_URGENT_KEYWORDS = (
    "緊急", "本番が止まった", "本番停止", "止まっている", "障害", "復旧",
)

# 裏方＝AIが動きやすい環境・仕組み・点検・効率化。店主の定義「4」に沿う語。
_URAKATA_KEYWORDS = (
    "仕組み", "ハーネス", "ループエンジニアリング", "巻き戻り", "台帳", "検品",
    "自動化", "点検", "監視", "ガード", "重複", "メンテ", "効率化", "運用改善",
    "スケジューリング", "自動発車", "自動復旧", "キャッシュ整理", "バックアップ", "仕組み化",
)

# たまごさんが直接「直してほしい」「間違っている」と言った文脈は、裏方キーワードに
# 一致していても見たいもの（1）を優先する（「扉の欄を3つに」事故の再発防止）。
_USER_FIX_KEYWORDS = (
    "直して", "直したい", "直してほしい", "間違って", "間違っている", "間違ってる",
    "ここ違う", "これ違う", "違ってる", "おかしい", "ここ間違ってる",
)


def _text_of(item):
    return "%s\n%s\n%s\n%s" % (
        item.get("title") or "", item.get("label") or "",
        item.get("why") or "", item.get("what") or "")


def classify_item(item):
    """item を "mitai" | "urakata" | "yobi" のいずれかに分類する。
    どちらにも当たらない場合のデフォルトは "mitai"（見たいもの判定を優先する側に倒す。
    店主指示：「直して」は1に入る）。"""
    text = _text_of(item)

    if any(k in text for k in _URGENT_KEYWORDS):
        return "yobi"

    is_urakata = any(k in text for k in _URAKATA_KEYWORDS)
    is_user_fix = item.get("origin") == "user" and any(k in text for k in _USER_FIX_KEYWORDS)
    if is_user_fix:
        return "mitai"
    if is_urakata:
        return "urakata"
    return "mitai"


def week_start(now=None):
    """週は火曜18:00(JST)始まり。nowが属する週の開始時刻(datetime)を返す。"""
    if now is None:
        now = datetime.datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    # 月曜=0 ... 火曜=1 ... 日曜=6
    days_since_tuesday = (now.weekday() - 1) % 7
    candidate = (now - datetime.timedelta(days=days_since_tuesday)).replace(
        hour=18, minute=0, second=0, microsecond=0)
    if candidate > now:
        candidate -= datetime.timedelta(days=7)
    return candidate


def _self_check():
    samples = [
        ({"title": "コンシェルジュが司会をする仕掛けを作る", "why": "", "what": "", "origin": "user"}, "mitai"),
        ({"title": "扉の欄を3つに直して", "why": "", "what": "たまごさんの指示で間違っている表示を修正",
          "origin": "user"}, "mitai"),
        ({"title": "重複発車ガードの仕組み化", "why": "", "what": "自動化で二重発車を防ぐ台帳を作る",
          "origin": "factory"}, "urakata"),
        ({"title": "本番が止まった、復旧してほしい", "why": "", "what": "", "origin": "user"}, "yobi"),
        ({"title": "falで新しい音声を試す", "why": "", "what": "", "origin": "user"}, "mitai"),
        ({"title": "ループエンジニアリングのハーネスを整備", "why": "", "what": "検品・監視の点検自動化",
          "origin": "factory"}, "urakata"),
    ]
    ok = True
    for item, expected in samples:
        got = classify_item(item)
        mark = "OK" if got == expected else "NG"
        if got != expected:
            ok = False
        print("%s: 「%s」→ %s（期待 %s）" % (mark, item["title"], got, expected))
    ws = week_start()
    print("week_start(今): %s" % ws.isoformat())
    print("ALL OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_check())
