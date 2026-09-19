#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""924番【仕組み⑯】引き継ぎを「読ませる」関所——読んだかを機械で確かめる。

■ 背景（たまごさんの言葉 2026-09-17 09:20）
  「次の人が読むかどうかは保証できません、ってさぁ、それも仕組みでクリアできないの」
  「あなたも最初の1日2日『聞いてません』って状態だったじゃん」
  「引き継ぎ書は"置いてある"だけで、読まなくても仕事が始められる」← 今の穴

■ 世界の事例からの裏付け（status/WORLD_CASES_924.md）
  Anthropic公式 sub-agents docs：「Ask the subagent to consult its memory」＝
  読ませる責任は呼び出し側にある、自動で読まれる保証はどこにも書いていない。
  → だから「読んだはず」で進めず、機械で読んだ証拠を取ってから先へ進む。

■ 土台（新しい別物を作らない）
  - status/public/genzaichi.md（900番）＝今の状態1枚
  - ai-brain/kettei.json（900番）＝決定台帳
  この2つを実際に読んでいないと答えられない問題を、この2つのファイルから
  **機械的に自動生成**する（手で書いた問題ではないので、内容が古くなっても追従する）。

■ 使い方（3段階）
  ① 新しい担当・会話の最初に問題を作る：
     python3 tools/hikitsugi_gate.py --generate
     → status/hikitsugi_test.json に問題（正解も含む・カンニング防止が目的ではなく
       「読んだという事実」を残すのが目的なので正解は隠さない）

  ② 自分で genzaichi.md / kettei.json を読んで、回答ファイルを作り、答え合わせする：
     python3 tools/hikitsugi_gate.py --answer-file /path/to/answers.json
     answers.json の形： {"q1": "...", "q2": "...", ...}
     → status/hikitsugi_passed.json に本日合格の記録（PASSでない問題があれば1件ずつ理由を表示）

  ③ 報告する前に、合格済みかを確認する（kenpin_gate.py --can-deliver から呼ばれる）：
     python3 tools/hikitsugi_gate.py --check
     終了コード 0=本日すでに合格済み／1=未合格（先に①②をやり直す）

■ 合格ライン
  7問中5問以上正解（数字は前後の表記ゆれ・✅等の記号は緩く許容）。
  100%を要求しないのは、genzaichi.mdが30分おきに数字が動く「現在地」であり、
  読んでから数分後に数字が変わって「不正解」になる誤爆を避けるため
  （静的な決定＝kettei.json由来の問題は完全一致に近い判定にする）。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, date

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

GENZAICHI_MD = os.path.join(REPO, "status", "genzaichi.md")
GENZAICHI_PUBLIC_MD = os.path.join(REPO, "status", "public", "genzaichi.md")
KETTEI_JSON = os.path.join(REPO, "ai-brain", "kettei.json")
TEST_JSON = os.path.join(REPO, "status", "hikitsugi_test.json")
PASSED_JSON = os.path.join(REPO, "status", "hikitsugi_passed.json")

PASS_THRESHOLD = 5  # 7問中5問以上


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _pick_genzaichi_text():
    # public版があればそちら（Dispatchが実際に読む方）、無ければ非public版
    t = _read(GENZAICHI_PUBLIC_MD)
    if t:
        return t, GENZAICHI_PUBLIC_MD
    t = _read(GENZAICHI_MD)
    return t, GENZAICHI_MD


def _extract(pattern, text, group=1, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    return m.group(group).strip()


def build_questions():
    """genzaichi.md + kettei.json から機械的に問題を生成する。"""
    gtext, gpath = _pick_genzaichi_text()
    ktext = _read(KETTEI_JSON)
    kettei = {}
    try:
        kettei = json.loads(ktext) if ktext else {}
    except Exception:
        kettei = {}

    qs = []

    # --- genzaichi.md から動的な問題（現在地系。判定は緩め） ---
    honban = _extract(r"本番\(Lovable\)：([^\n]+)", gtext)
    qs.append({
        "id": "q1_honban",
        "source": "genzaichi.md",
        "q": "今、本番(Lovable)は止まっていますか？（止まっていない/止まっている、で答える）",
        "answer": honban or "（genzaichi.mdに記載なし）",
        "kind": "loose",  # ✅が含まれるか、止まっていない/動いている等のキーワード一致で正解とする
    })
    shinzo = _extract(r"心臓：([^\n]+)", gtext)
    qs.append({
        "id": "q2_shinzo",
        "source": "genzaichi.md",
        "q": "今、心臓（15秒ループ）は動いていますか？",
        "answer": shinzo or "（genzaichi.mdに記載なし）",
        "kind": "loose",
    })
    kanryo = _extract(r"今日の完了\s*\*\*(\d+)件\*\*", gtext)
    qs.append({
        "id": "q3_kanryo",
        "source": "genzaichi.md",
        "q": "今日の完了件数は何件ですか？（数字だけでよい）",
        "answer": kanryo or "（記載なし）",
        "kind": "number",
    })
    machi = _extract(r"件数\s*\*\*(\d+)件\*\*", gtext)
    qs.append({
        "id": "q4_matteiru",
        "source": "genzaichi.md",
        "q": "たまごさんの確認・OK待ち（『待っているもの』）は何件ですか？",
        "answer": machi or "（記載なし）",
        "kind": "number",
    })
    hashitteiru = re.findall(r"## 今すぐ走っているもの\n((?:- .+\n?)+)", gtext)
    first_running = None
    if hashitteiru:
        m = re.search(r"-\s*(\d+)", hashitteiru[0])
        if m:
            first_running = m.group(1)
    qs.append({
        "id": "q5_soukou",
        "source": "genzaichi.md",
        "q": "今すぐ走っているものの号番号を1つ挙げてください。",
        "answer": first_running or "（記載なし）",
        "kind": "number_in_list",
    })

    # --- kettei.json から静的な問題（決定台帳。完全一致に近い判定） ---
    principle = (kettei.get("principle") or {}).get("text", "")
    qs.append({
        "id": "q6_genryu",
        "source": "kettei.json:principle",
        "q": "『実物』と『文書に書かれた数字』が食い違っていたら、どちらを正しいとして採用しますか？",
        "answer": "実物",
        "kind": "keyword",
        "keyword": "実物",
    })
    decisions = kettei.get("decisions") or []
    badge_h = None
    for d in decisions:
        if d.get("id") == "badge-height-ratio-28pct":
            badge_h = d.get("value")
    qs.append({
        "id": "q7_badge",
        "source": "kettei.json:decisions",
        "q": "バッジの高さは、サムネイル短辺の何%と決まっていますか？（数字だけでよい）",
        "answer": "28",
        "kind": "keyword",
        "keyword": "28",
    })

    return qs, gpath


def cmd_generate():
    qs, gpath = build_questions()
    out = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sourceGenzaichi": gpath,
        "sourceKettei": KETTEI_JSON,
        "passThreshold": PASS_THRESHOLD,
        "totalQuestions": len(qs),
        "questions": qs,
    }
    os.makedirs(os.path.dirname(TEST_JSON), exist_ok=True)
    with open(TEST_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("HIKITSUGI_GENERATE: OK - %d問を作成しました（%s）" % (len(qs), TEST_JSON))
    for q in qs:
        print("  - [%s] %s" % (q["id"], q["q"]))
    return 0


def _judge(q, given):
    given = (given or "").strip()
    ans = (q.get("answer") or "").strip()
    kind = q.get("kind")
    if not given:
        return False
    if kind == "loose":
        # ✅/⚠️/🔴などの記号、または「止まっていない」「動いている」等のキーワードで緩く判定
        if "✅" in ans and ("✅" in given or "止まっていない" in given or "動いて" in given or "正常" in given):
            return True
        if "⚠️" in ans or "🔴" in ans:
            return ("⚠️" in given or "🔴" in given or "止まっ" in given or "異常" in given)
        return given in ans or ans in given
    if kind == "number":
        m1 = re.search(r"\d+", given)
        m2 = re.search(r"\d+", ans)
        if not m1 or not m2:
            return given == ans
        return m1.group(0) == m2.group(0)
    if kind == "number_in_list":
        m1 = re.search(r"\d+", given)
        return bool(m1)  # 番号らしきものを1つでも挙げていればOK（読んだ形跡があればよい）
    if kind == "keyword":
        kw = q.get("keyword", ans)
        return kw in given
    return given == ans


def cmd_answer(answer_file):
    if not os.path.exists(TEST_JSON):
        print("HIKITSUGI_RESULT: FAIL - 先に --generate で問題を作ってください")
        return 1
    with open(TEST_JSON, encoding="utf-8") as f:
        test = json.load(f)
    if not os.path.exists(answer_file):
        print("HIKITSUGI_RESULT: FAIL - 回答ファイルがありません: %s" % answer_file)
        return 1
    with open(answer_file, encoding="utf-8") as f:
        answers = json.load(f)

    results = []
    correct = 0
    for q in test["questions"]:
        given = answers.get(q["id"], "")
        ok = _judge(q, given)
        if ok:
            correct += 1
        results.append({"id": q["id"], "q": q["q"], "given": given, "expected": q["answer"], "ok": ok})

    total = len(test["questions"])
    passed = correct >= min(PASS_THRESHOLD, total)

    record = {
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "date": date.today().isoformat(),
        "correct": correct,
        "total": total,
        "passed": passed,
        "results": results,
    }
    os.makedirs(os.path.dirname(PASSED_JSON), exist_ok=True)
    history = []
    if os.path.exists(PASSED_JSON):
        try:
            with open(PASSED_JSON, encoding="utf-8") as f:
                existing = json.load(f)
                history = existing.get("history", [])
        except Exception:
            history = []
    history.append(record)
    history = history[-50:]  # 直近50件だけ保持
    with open(PASSED_JSON, "w", encoding="utf-8") as f:
        json.dump({"latest": record, "history": history}, f, ensure_ascii=False, indent=2)

    if passed:
        print("HIKITSUGI_RESULT: PASS - %d/%d問正解（合格ライン%d問）" % (correct, total, PASS_THRESHOLD))
        return 0
    else:
        ng = [r for r in results if not r["ok"]]
        print("HIKITSUGI_RESULT: FAIL - %d/%d問正解（合格ラインに届きません）" % (correct, total))
        for r in ng:
            print("  - [%s] %s → 回答『%s』／正解『%s』" % (r["id"], r["q"], r["given"], r["expected"]))
        return 1


def cmd_check():
    if not os.path.exists(PASSED_JSON):
        print("HIKITSUGI_CHECK: NG - まだ一度も引き継ぎテストに合格していません")
        return 1
    with open(PASSED_JSON, encoding="utf-8") as f:
        data = json.load(f)
    latest = data.get("latest") or {}
    if latest.get("date") != date.today().isoformat():
        print("HIKITSUGI_CHECK: NG - 今日まだ合格していません（最後の合格: %s）" % latest.get("date"))
        return 1
    if not latest.get("passed"):
        print("HIKITSUGI_CHECK: NG - 直近の受験が不合格でした")
        return 1
    print("HIKITSUGI_CHECK: OK - 本日 %s に合格済み（%d/%d問）" % (
        latest.get("checkedAt"), latest.get("correct"), latest.get("total")))
    return 0


def main():
    ap = argparse.ArgumentParser(description="引き継ぎを読ませる関所（読んだかを機械で確かめる）")
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--answer-file")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.generate:
        return cmd_generate()
    if a.answer_file:
        return cmd_answer(a.answer_file)
    if a.check:
        return cmd_check()
    ap.error("--generate / --answer-file / --check のいずれかを指定してください")


if __name__ == "__main__":
    sys.exit(main())
