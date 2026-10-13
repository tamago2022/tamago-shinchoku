# -*- coding: utf-8 -*-
"""お金がかかるタスクの判定（案件#676、795番で文脈判定を追加）。

2026-09-08にfalで15ドル溶けた事故を受けての機械ガード。
「会話の流れのやってみて」がそのまま課金実行に化けるのを防ぐため、
タスクの文面から自動でお金の匂いを判定し、既存の costsMoney 表示（654番）と
同じフィールドに書き込む。False Negative（見逃し）よりFalse Positive（多く拾う）を
優先する——見逃すと課金事故、多く拾っても確認が1回増えるだけ。

【795番・2026-09-14追記】793番の誤検知の再発防止：
793番の本文には「777番の教訓：二重課金で$55捨てた」という**過去の損失額**の言及しか無く、
これから金がかかる予定は無かったのに、costEstimateが「ドル額の言及: $55.0」を拾って
costsMoney=Trueと誤判定された（後でdispatchが手動でクリアした）。
原因は「金額があれば全部これからの費用」と決め打ちしていたこと。
→ 金額の前後の文脈（過去形か将来形か）を見て、
  過去の言及（捨てた・溶けた・だった・実績・教訓・損失 等）は費用として拾わない、
  将来の言及（かかります・予定・投げます・購入します 等）は費用として拾う、
  どちらでもない曖昧なケースは金額を空にして「要確認」と出す（埋めない）。
ただし fal.ai・生成API・サブスク契約 等、サービス利用そのものを指す明示的なキーワードは、
金額の有無に関わらずこれまで通り無条件でTrue扱いを維持する（見逃し優先度=Falseを避ける方針は変えない）。

【795番・追記2】1回目の実装では「課金」というキーワード自体を無条件Trueに残していたため、
793番の「二重課金で$55捨てた」がまさにこの語にヒットしてテストが落ちた（is_cost_risk()は
Trueのまま）。793番は「課金」という単語が過去形の事故報告の中で使われていただけなので、
「課金」「有料」系の語も**金額と同じく前後の文脈で過去/将来を判定する対象**へ格下げした
（_CONTEXTUAL_KEYWORDS）。一方 fal.ai・サブスク契約のようなサービス名・契約行為そのものの
語は、過去形で語られていても「falを使う話をしている」こと自体に変わりはないため、
引き続き無条件Trueのまま（_EXPLICIT_KEYWORDS）。
"""
import re

# 金額の有無に関わらず無条件でTrue扱いにする明示的なキーワード（サービス名・契約行為そのもの）
_EXPLICIT_KEYWORDS = (
    "fal.ai", "fal ai", "falに", "fal課金", "falを使", "falで", "fal(", "fal（",
    "生成api", "有料api",
    "クレジットカード", "サブスク契約", "月額契約",
)
# 795番：金額と同じく前後の文脈（過去/将来）を見てから判定するキーワード。
# 「課金」「有料」は過去の事故報告（例：793番「二重課金で$55捨てた」）でも使われる語なので、
# 無条件Trueにすると793番のような誤検知を再発する。
_CONTEXTUAL_KEYWORDS = ("課金", "有料版", "有料プラン", "有料級", "有料の", "有料で")

_YEN_RE = re.compile(r'(\d[\d,]*)\s*円')
# 「ドル」は「ハンドル」「キャンドル」等の部分文字列として誤検知しやすいので、
# 単語一致ではなく必ず数字を伴う「3ドル」のような形だけを金額の言及として扱う。
_DOLLAR_RE = re.compile(r'\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*ドル')
_COUNT_RE = re.compile(r'(\d+)\s*(?:本|件|回|枚)')

# 795番：金額の前後にある語で「過去の言及」か「これから発生する費用」かを判定する。
_PAST_CONTEXT_WORDS = (
    "捨てた", "溶けた", "だった", "でした", "損失", "教訓", "事故", "失った", "消えた",
    "かかった", "使った", "捨てちゃった", "溶かした", "前回", "既に", "過去に", "実績",
    "この前", "この間", "先日", "去年", "先週", "実費", "だったので",
)
_FUTURE_CONTEXT_WORDS = (
    "これから", "予定", "予算", "かかります", "かかる見込み", "見込み", "いくらになります",
    "投げます", "実行します", "発注します", "購入します", "使います", "かける予定",
    "本投げ", "課金します", "支払います", "生成します", "作ります", "回します",
)
_CONTEXT_WINDOW = 20  # 金額の前後何文字を文脈として見るか


def _text_of(item):
    return "%s\n%s\n%s" % (
        item.get("title") or "", item.get("why") or "", item.get("what") or "")


def is_fal_task(item):
    """fal.ai への言及があるか（大小文字を無視）。falは当面使わない方針の対象判定に使う。"""
    return "fal" in _text_of(item).lower()


def _amount_matches(text):
    """円・ドルの金額言及を全部拾い、各候補に前後文脈から past/future/unknown のラベルを付ける。"""
    results = []
    for m in _YEN_RE.finditer(text):
        results.append(_classify_span(text, m.start(), m.end(), "円" + m.group(1)))
    for m in _DOLLAR_RE.finditer(text):
        v = m.group(1) or m.group(2)
        results.append(_classify_span(text, m.start(), m.end(), "$" + (v or "")))
    return results


def _keyword_matches(text):
    """課金・有料系キーワードを全部拾い、金額と同じ基準で past/future/unknown のラベルを付ける。"""
    results = []
    for kw in _CONTEXTUAL_KEYWORDS:
        start = 0
        while True:
            pos = text.find(kw, start)
            if pos < 0:
                break
            results.append(_classify_span(text, pos, pos + len(kw), kw))
            start = pos + len(kw)
    return results


def _classify_span(text, start, end, label):
    before = text[max(0, start - _CONTEXT_WINDOW):start]
    after = text[end:end + _CONTEXT_WINDOW]
    ctx = before + after
    is_past = any(w in ctx for w in _PAST_CONTEXT_WORDS)
    is_future = any(w in ctx for w in _FUTURE_CONTEXT_WORDS)
    if is_future and not is_past:
        context = "future"
    elif is_past and not is_future:
        context = "past"
    else:
        context = "unknown"  # 両方／どちらも無い＝判定不能。金額として計上しない（拾えないときは空欄）
    return {"label": label, "context": context}


def is_cost_risk(item):
    """お金がかかる可能性がある指示文か。
    サービス名・契約行為そのものを指す明示的なキーワード（fal.ai・生成API等）は
    金額の有無に関わらず無条件True。
    金額（円・ドル）や「課金」「有料」系の言及は、前後の文脈が「これから」の場合だけTrueにする。
    過去の言及（捨てた・溶けた等）や文脈不明のものだけでは費用ありと判定しない。"""
    text = _text_of(item)
    t = text.lower()
    if any(k in t for k in _EXPLICIT_KEYWORDS):
        return True
    matches = _amount_matches(text) + _keyword_matches(text)
    return any(mt["context"] == "future" for mt in matches)


def estimate_note(item):
    """指示文から本数・金額の言及を拾って一言メモにする（自動抽出・雑でよい。
    厳密な計算はしない——最終判断は人が画面を見て行う）。
    795番：過去の言及と判定した金額・キーワードは出さない。将来の言及だけを実額候補として出し、
    文脈が不明なものは「要確認」として金額を空欄のまま伝える（埋めない）。"""
    text = _text_of(item)
    matches = _amount_matches(text) + _keyword_matches(text)
    future_amounts = [mt["label"] for mt in matches if mt["context"] == "future"]
    unknown_amounts = [mt["label"] for mt in matches if mt["context"] == "unknown"]
    past_amounts = [mt["label"] for mt in matches if mt["context"] == "past"]
    counts = [int(x) for x in _COUNT_RE.findall(text)]
    parts = []
    if counts:
        parts.append("本数の言及: " + "・".join(str(c) for c in counts))
    if future_amounts:
        parts.append("これから掛かる金額の言及: " + "・".join(future_amounts))
    if unknown_amounts:
        parts.append("要確認（未来か過去か文脈から判定できない金額。金額欄は空にしてあります）: "
                      + "・".join(unknown_amounts))
    if past_amounts:
        parts.append("過去の言及として除外: " + "・".join(past_amounts))
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
