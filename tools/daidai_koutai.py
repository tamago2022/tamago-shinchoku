#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""924番【仕組み⑯】歴代ディスパッチ台帳を仕組みにする。

■ 背景（たまごさんの言葉 2026-09-17）
  「歴代ディスパッチも比べられるようにしといて。クロマティ何月何日、クロ丸 何月何日…
  役者だとか、役所だとか、都知事とか県知事とかだって、それぐらいやってるでしょう。
  全部議事録みたいに残ってるはずじゃん。」
  「交代時に自動で『その期間の完了数・使った額・怒られた件数・出せた成果物』を集計して埋める」

■ 正本（このツールは正本を変えない。新しい台帳を作らない）
  ~/Documents/AI作業/会話ログ/歴代ディスパッチ台帳.md
  既存フォーマット：冒頭の「一覧（比べるための表）」＋代ごとの詳細セクション（# 第N代｜名前）。
  **議事録なので、既存行は書き換えない・消さない。新しい代の行・セクションを足すだけ。**

■ 集計に使うデータソース（tamago-shinchokuリポジトリ内・すべて既存）
  - 完了数     : status/queue.json の finishedAt が期間内 かつ status in (done, merged, delivered)
  - 出せた成果物: status/dispatch_outbox.jsonl の期間内で ok:true かつ urls を持つ行
  - 怒られた件数: status/failures.jsonl の期間内エントリ数（date列でフィルタ）
  - 使った額   : status/fal_cost_ledger.json（fal）＋ status/gaibu.json（外部AI、costUsd）を合算。
                 Claude本体のセッション課金は「当日スナップショットのみ」で期間累計の仕組みが
                 無いため、**正直に「不明（当日分のみ既知）」と明記する**（無い数字を嘘で埋めない）。

■ 使い方
  # まず中身を確認する（ファイルには何も書かない）
  python3 tools/daidai_koutai.py --from 2026-09-17 --to 2026-09-17 --name "（次の担当）" --dry-run

  # 実際に歴代台帳.mdへ追記する（一覧表の1行＋詳細セクションを両方追記）
  python3 tools/daidai_koutai.py --from 2026-09-17 --to 2026-09-17 --name "（次の担当）" --append
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime, date

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

DAICHOU = os.path.expanduser("~/Documents/AI作業/会話ログ/歴代ディスパッチ台帳.md")


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _in_range(dt_str, d_from, d_to):
    if not dt_str:
        return False
    try:
        d = dt_str[:10]
        return d_from <= d <= d_to
    except Exception:
        return False


def count_completed(d_from, d_to):
    q = _load_json(os.path.join(ST, "queue.json"), {})
    items = q if isinstance(q, list) else (q.get("items") or q.get("queue") or [])
    per_day = {}
    ns = []
    for it in items:
        if (it.get("status") or "") not in ("done", "merged", "delivered"):
            continue
        fin = it.get("finishedAt") or ""
        if not _in_range(fin, d_from, d_to):
            continue
        day = fin[:10]
        per_day[day] = per_day.get(day, 0) + 1
        ns.append(it.get("n"))
    return len(ns), per_day, ns


def collect_deliverables(d_from, d_to, limit=8):
    rows = _load_jsonl(os.path.join(ST, "dispatch_outbox.jsonl"))
    out = []
    for r in rows:
        if not r.get("ok"):
            continue
        if not r.get("urls"):
            continue
        if not _in_range(r.get("ts") or "", d_from, d_to):
            continue
        out.append(r)
    out.sort(key=lambda r: r.get("ts") or "")
    return out, out[-limit:]


def count_scolded(d_from, d_to):
    rows = _load_jsonl(os.path.join(ST, "failures.jsonl"))
    out = [r for r in rows if _in_range(r.get("date") or "", d_from, d_to)]
    return len(out), out


def sum_cost(d_from, d_to):
    total_yen = 0.0
    fal = _load_json(os.path.join(ST, "fal_cost_ledger.json"), {}) or {}
    for r in (fal.get("records") or []):
        if _in_range(r.get("date") or "", d_from, d_to):
            v = r.get("totalCostYen")
            if isinstance(v, (int, float)):
                total_yen += v
    gaibu = _load_json(os.path.join(ST, "gaibu.json"), {}) or {}
    usd_to_yen = gaibu.get("usdToYenFallback") or 150
    gaibu_usd = 0.0
    for it in (gaibu.get("items") or []):
        ts = it.get("createdAt") or it.get("updatedAt") or ""
        if _in_range(ts, d_from, d_to):
            v = it.get("costUsd")
            if isinstance(v, (int, float)):
                gaibu_usd += v
    total_yen += gaibu_usd * usd_to_yen
    return total_yen, gaibu_usd


def build_section(name, d_from, d_to, dai_label):
    n_done, per_day, ns = count_completed(d_from, d_to)
    all_deliv, sample_deliv = collect_deliverables(d_from, d_to)
    n_scolded, scolded_rows = count_scolded(d_from, d_to)
    total_yen, gaibu_usd = sum_cost(d_from, d_to)

    days = max(1, len(set([d_from, d_to])) if d_from == d_to else
               (date.fromisoformat(d_to) - date.fromisoformat(d_from)).days + 1)
    avg = n_done / days if days else 0

    table_row = "| 次 | **%s** | **%s〜%s** | **%d日** | **%d件** | **%.1f件** | **%d件** | （機械集計・一言は追記してください） |" % (
        name, d_from, d_to, days, n_done, avg, len(all_deliv))

    lines = []
    lines.append("")
    lines.append("# %s｜%s（%s〜%s・%d日・**daidai_koutai.py 自動集計 %s**）" % (
        dai_label, name, d_from, d_to, days, datetime.now().strftime("%Y-%m-%d %H:%M")))
    lines.append("")
    lines.append("## 成績（機械集計・status/queue.json 等より）")
    lines.append("")
    lines.append("- **完了数：%d件**（%d日間・1日平均%.1f件）" % (n_done, days, avg))
    if per_day:
        lines.append("  - 内訳：" + " / ".join("%s:%d" % (k, v) for k, v in sorted(per_day.items())))
    lines.append("- **出せた成果物（ok:true かつURL付き）：%d件**" % len(all_deliv))
    for r in sample_deliv:
        title = (r.get("title") or r.get("message") or "")[:50]
        url = (r.get("urls") or [""])[0]
        lines.append("  - %s %s" % (title, url))
    lines.append("- **怒られた・失敗として記録された件数：%d件**（status/failures.jsonl）" % n_scolded)
    for r in scolded_rows[:5]:
        lines.append("  - %s %s" % (r.get("date"), (r.get("what") or "")[:60]))
    if total_yen > 0:
        lines.append("- **使った額（fal＋外部AI合算・機械集計分のみ）：約%d円**（うち外部AI %.2f USD）" % (total_yen, gaibu_usd))
    else:
        lines.append("- **使った額：機械集計分は0円 or 記録なし**（Claude本体セッション課金の期間累計は"
                      "当日スナップショットのみのため不明。cost_by_task.jsonは履歴を持たない）")
    lines.append("")
    lines.append("## ★次の担当へ（このセクションはdaidai_koutai.pyの雛形。手で書き足してよい）")
    lines.append("- たまごさんの評価（原文）・怒られたこと（削らない）・直したこと・申し送りは、"
                  "自動集計できないので、交代する担当が自分で追記すること。")
    lines.append("")
    return "\n".join(lines), table_row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d_from", required=True, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="d_to", required=True, help="YYYY-MM-DD")
    ap.add_argument("--name", default="（次の担当）")
    ap.add_argument("--dai-label", default="第4代", help="見出しに使う代の呼び方")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--append", action="store_true")
    a = ap.parse_args()

    section, table_row = build_section(a.name, a.d_from, a.d_to, a.dai_label)

    if a.dry_run or not a.append:
        print("=== 一覧表への1行（手で『次』行と置き換える） ===")
        print(table_row)
        print()
        print("=== 追記されるセクション ===")
        print(section)
        print()
        print("DAIDAI_KOUTAI_RESULT: DRY_RUN - 何もファイルに書いていません（--appendで実際に追記）")
        return 0

    if not os.path.exists(DAICHOU):
        print("DAIDAI_KOUTAI_RESULT: FAIL - 歴代台帳が見つかりません: %s" % DAICHOU)
        return 1
    with io.open(DAICHOU, "a", encoding="utf-8") as f:
        f.write(section)
        f.write("\n<!-- daidai_koutai.py 自動集計ここまで（%s） -->\n" % datetime.now().isoformat(timespec="seconds"))
    print("DAIDAI_KOUTAI_RESULT: OK - 歴代台帳へ追記しました: %s" % DAICHOU)
    print("  一覧表の『次』行は手でこの1行に置き換えてください：")
    print("  " + table_row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
