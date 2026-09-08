# -*- coding: utf-8 -*-
"""お金がかかるタスクの判定（案件#676）。

2026-09-08にfalで15ドル溶けた事故を受けての機械ガード。
「会話の流れのやってみて」がそのまま課金実行に化けるのを防ぐため、
タスクの文面から自動でお金の匂いを判定し、既存の costsMoney 表示（654番）と
同じフィールドに書き込む。False Negative（見逃し）よりFalse Positive（多く拾う）を
優先する——見逃すと課金事故、多く拾っても確認が1回増えるだけ。
"""
import re

_KEYWORDS = (
    "fal.ai", "fal ai", "falに", "fal課金", "falを使", "falで", "fal(", "fal（",
    "生成api", "課金", "有料api", "有料版", "有料プラン", "有料級", "有料の", "有料で",
    "usd", "$",
    "円かか", "円かかり", "円ほど", "円で生成", "円分",
    "クレジットカード", "サブスク契約", "月額契約",
)

_YEN_RE = re.compile(r'(\d[\d,]*)\s*円')
# 「ドル」は「ハンドル」「キャンドル」等の部分文字列として誤検知しやすいので、
# 単語一致ではなく必ず数字を伴う「3ドル」のような形だけを金額の言及として扱う。
_DOLLAR_RE = re.compile(r'\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*ドル')
_COUNT_RE = re.compile(r'(\d+)\s*(?:本|件|回|枚)')


def _text_of(item):
    return "%s\n%s\n%s" % (
        item.get("title") or "", item.get("why") or "", item.get("what") or "")


def is_fal_task(item):
    """fal.ai への言及があるか（大小文字を無視）。falは当面使わない方針の対象判定に使う。"""
    return "fal" in _text_of(item).lower()


def is_cost_risk(item):
    """お金がかかる可能性がある指示文か。判定材料はたまごさん指定の
    fal.ai / 生成API / 課金 / 有料 / ドル / 円 など。"""
    text = _text_of(item)
    t = text.lower()
    if any(k in t for k in _KEYWORDS):
        return True
    return bool(_DOLLAR_RE.search(text))


def estimate_note(item):
    """指示文から本数・金額の言及を拾って一言メモにする（自動抽出・雑でよい。
    厳密な計算はしない——最終判断は人が画面を見て行う）。"""
    text = _text_of(item)
    yens = [int(x.replace(",", "")) for x in _YEN_RE.findall(text)]
    dollars = []
    for a, b in _DOLLAR_RE.findall(text):
        v = a or b
        if v:
            try:
                dollars.append(float(v))
            except ValueError:
                pass
    counts = [int(x) for x in _COUNT_RE.findall(text)]
    parts = []
    if counts:
        parts.append("本数の言及: " + "・".join(str(c) for c in counts))
    if yens:
        parts.append("円額の言及: " + "・".join(str(y) for y in yens) + "円")
    if dollars:
        parts.append("ドル額の言及: $" + "・".join(str(d) for d in dollars))
    if not parts:
        return "金額はタスク文面から自動抽出できません。発車前に金額を確認してください。"
    return " / ".join(parts) + "（自動抽出・目視確認のうえ発車してください）"


def confirm_message(item):
    """発車を止めて出す確認メッセージ本文。"""
    n = item.get("n")
    title = item.get("title") or ""
    note = estimate_note(item)
    return (
        "💰お金の確認：%s番「%s」はお金がかかる可能性があります。%s "
        "進捗表の💴マークからOKを押すと発車します。押さない限り自動発車はしません。"
        % (n, title, note)
    )
