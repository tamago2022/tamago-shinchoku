#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
795番（2026-09-14）：数字のズレをゼロに近づけるための共通部品①「出どころラベル」。

たまごさんの言葉：
  「お金の計算とクレジット計算だとか、ちょっと計算のズレをどんどん少なくしていって。
   間違いが多いよ。計算、見立て、見積もり、なんかズレてるよね」

これまでの事故はどれも「推定を実測と呼んでいた」ことが原因（fal 771番8.2円→実費108円 等）。
今後、金額・％を出す全ての場所は、この関数で作った「ラベル付きの値」だけを使う。

ラベルは3種類だけ：
  実測 = 請求API・課金ダッシュボード・ログに残った実額（取得日時・取得元を必ず書く）
  推定 = 計算した値（計算式をそのまま添える）
  不明 = 取れなかった（空欄にする。埋めない）

使い方:
  from number_labels import measured, estimated, unknown
  x = measured(108, source="fal.ai dashboard 2026-09-13 23:40 手動確認", note="実費")
  y = estimated(6.74, formula="$0.130/秒 × 10秒 × 5.18(倍率) = $6.74", note="旧基準$2.43は更新漏れ")
  z = unknown(note="fal.aiダッシュボードとの自動突き合わせ口が無い")
"""
import time

LABELS = ("実測", "推定", "不明")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S+09:00")


def _make(label, value, source=None, formula=None, as_of=None, note=None):
    if label not in LABELS:
        raise ValueError("label must be one of %r, got %r" % (LABELS, label))
    return {
        "value": value,
        "label": label,
        "source": source,
        "formula": formula,
        "asOf": as_of or (_now() if label != "不明" else None),
        "note": note,
    }


def measured(value, source, as_of=None, note=None):
    """実測：請求API・課金ダッシュボード・ログに残った実額。sourceは必須（取得元）。"""
    if not source:
        raise ValueError("実測ラベルには取得元(source)が必須です")
    return _make("実測", value, source=source, as_of=as_of, note=note)


def estimated(value, formula, note=None):
    """推定：計算した値。formulaは必須（計算式そのまま）。"""
    if not formula:
        raise ValueError("推定ラベルには計算式(formula)が必須です")
    return _make("推定", value, formula=formula, note=note)


def unknown(note=None):
    """不明：取れなかった。valueは常にNone（埋めない）。"""
    return _make("不明", None, note=note)


def is_labeled(obj):
    """既にこのモジュールで作った形（dict + label キー）かどうか。"""
    return isinstance(obj, dict) and obj.get("label") in LABELS


def fmt(obj):
    """報告・進捗表向けの短い表示文字列。"""
    if not is_labeled(obj):
        return str(obj)
    label = obj["label"]
    if label == "不明":
        return "不明" + ("（%s）" % obj["note"] if obj.get("note") else "")
    v = obj.get("value")
    if label == "実測":
        return "実測%s（%s）" % (v, obj.get("source") or "出どころ未記載")
    return "推定%s（%s）" % (v, obj.get("formula") or "式未記載")


if __name__ == "__main__":
    demo = [
        measured(108, source="fal.aiダッシュボード 2026-09-13 23:40 手動確認"),
        estimated(6.74, formula="$0.130/秒 × 10秒 × 1.5(倍率補正) × 3.46 = $6.74（直近7日実測中央値ベース）"),
        unknown(note="請求APIが無くダッシュボードも未確認"),
    ]
    for d in demo:
        print(fmt(d))
