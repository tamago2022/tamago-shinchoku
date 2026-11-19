#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
既存の status/failures.md（プロース形式・症状/原因/直し方/仕掛け/日付/根拠）を、
status/failures.jsonl の構造化レコードへ変換する一回きりの移行スクリプト（案件#813）。

方針：
- failures.md の本文・書式は一切変更しない（読むだけ）。
- 手書きの番号付き見出し「## N. タイトル」だけを対象にする
  （「## 797番自動記録：発車が…」の自動追記ブロックは運用ログであり、
   個別の恒久対策ノートではないため対象外）。
- 見出しの番号がファイル内で重複・巻き戻りしているため（例：29番が2回、20番が2回）、
  jsonlのidは通し番号を使わず `F-HIST-<連番3桁>` を割り当てる（正本のidは日付ベースではなく
  出現順の連番。日付が本文から取れた場合はdateフィールドへ入れる）。
- 「潰した」の3条件（rootCause実測／機械のガード／わざと壊す逆テスト）は、
  本文に**明示的な逆テストの記述がある場合だけ** preventedBy と reverseTest を埋める。
  「仕掛けを作った」というだけの記述（逆テストの言及が無いもの）は、厳格化の方針に従い
  あえて空のまま（＝赤）にする。過去の仕掛けを甘く「潰した」にしないための意図的な判断。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import failures_ledger as fl  # noqa: E402

MD_PATH = os.path.join(REPO, "status", "failures.md")

REVERSE_TEST_PATTERNS = [
    "逆テスト", "わざと壊", "わざとズラ", "修正前のコードは", "修正前のコードで",
    "壊れることを確認", "検出することを確認", "実行しPASS", "実際に実行して確認",
    "テストを作り、実際に実行して確認",
]


def split_sections(text):
    """'## N. タイトル' で始まる手書きセクションだけを、次の '## ' か文末までで切り出す。"""
    pattern = re.compile(r"^## (\d+)\. (.+)$", re.M)
    matches = list(pattern.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append({"num": m.group(1), "title": m.group(2).strip(), "body": body})
    return sections


def extract_field(body, label):
    # 例: "- **原因**：....（次の - **や見出しまで）"
    pattern = re.compile(
        r"-\s*\*\*" + re.escape(label) + r"\*\*[：:]\s*(.+?)(?=\n-\s*\*\*|\n---|\n## |\Z)",
        re.S,
    )
    m = pattern.search(body)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def extract_date(body):
    d = extract_field(body, "日付")
    m = re.search(r"20\d{2}-\d{2}-\d{2}", d)
    return m.group(0) if m else ""


def has_reverse_test(body):
    return any(p in body for p in REVERSE_TEST_PATTERNS)


def build_entries():
    text = io.open(MD_PATH, encoding="utf-8").read()
    sections = split_sections(text)
    entries = []
    for i, sec in enumerate(sections, start=1):
        body = sec["body"]
        symptom = extract_field(body, "症状")
        cause = extract_field(body, "原因") or extract_field(body, "原因（推定）") or extract_field(body, "原因（未確定）")
        fix = extract_field(body, "直し方") or extract_field(body, "直し方（今回）") or extract_field(body, "今回の対応")
        guard = extract_field(body, "二度と起こさないための仕掛け") or extract_field(body, "教訓")
        evidence = extract_field(body, "根拠")
        date = extract_date(body)
        reverse = has_reverse_test(body)

        entry = {
            "id": "F-HIST-%03d" % i,
            "date": date or "不明",
            "what": (symptom or sec["title"])[:300],
            "howFound": "失敗台帳（旧・元番号#%s）の記載からは不明（当時未記録）" % sec["num"],
            "cost": "当時未計測（円・時間の記録なし）",
            "rootCause": (cause or "未抽出（自動移行の正規表現が本文の書式に一致しなかった。sourceSectionの本文を参照）")[:400],
            "rootCauseEvidence": evidence[:300] if evidence else "",
            "fixedBy": (fix or "")[:400],
            "preventedBy": guard[:300] if (guard and reverse) else "",
            "reverseTest": "本文に逆テストの実施記録あり（自動判定）" if reverse else "",
            "recurrence": 0,
            "lesson": "",
            "sourceSection": "status/failures.md #%s 「%s」" % (sec["num"], sec["title"]),
        }
        entries.append(entry)
    return entries


def main():
    entries = build_entries()
    existing = {e["id"] for e in fl.load_all()}
    added = 0
    skipped = 0
    for e in entries:
        if e["id"] in existing:
            skipped += 1
            continue
        # 逆テスト記載が無いものは preventedBy を意図的に空にしているため、
        # 再発ヒットのボーナス無しでそのまま追記する（重複rootCauseの検出だけは行う）。
        fl.append_entry(e, bump_recurrence_on_match=True)
        added += 1
    print("移行完了: 追加 %d件・既存につきスキップ %d件（対象セクション総数 %d）" % (added, skipped, len(entries)))
    prevented = sum(1 for e in entries if e["preventedBy"])
    print("うち『逆テスト記載あり→潰した扱い』: %d件／それ以外は赤(open)のまま: %d件" % (prevented, len(entries) - prevented))


if __name__ == "__main__":
    main()
