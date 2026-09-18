#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""944番 検品ゲートのやりとりを、たまごさんが読める形にする。

たまごさんの言葉（2026-09-18・原文）:
  「例のOpenAIに検品させるやつ、実際に動いてるの？ やりとり見れるの？」

■ 答え：動いている。ただし今まで**読める形で出ていなかった。**
  記録は status/kenpin/<号>/NNN-result.json に全部ある（提出本文・AIの生の指摘・判定・費用）。
  ただしJSONなので、たまごさんが開いても読めない。それをこのツールが日本語の1枚に開く。

■ 出るもの
  status/kenpin/<号>/やりとり.txt … ★たまごさんが読む用（FIX→修正→FIX→…→PASS が順に並ぶ）
  status/kenpin/<号>/やりとり.md  … 進捗表のトグルに入れる用
  status/public/kenpin_mieru.json … 進捗表が1行で出すための要約（全号ぶん）

■ 使い方
  python3 tools/kenpin_mieru.py --n 915     # 1号ぶん
  python3 tools/kenpin_mieru.py --all       # 記録がある号を全部＋要約を作り直す
"""
import argparse
import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
KENPIN = os.path.join(REPO, "status", "kenpin")
PUBLIC = os.path.join(REPO, "status", "public", "kenpin_mieru.json")

VERDICT_JA = {"PASS": "✅ 通した", "FIX": "🔴 直させた", "SKIP": "⚪️ 判定できず"}


def _load(path):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def _title_of(n):
    try:
        q = json.load(io.open(os.path.join(REPO, "status", "queue.json"), encoding="utf-8"))
        for it in (q.get("items") or []):
            if str(it.get("n")) == str(n):
                return (it.get("title") or "").strip(), it.get("state")
    except Exception:
        pass
    return "", None


def _submitted_part(prompt):
    """検品に出した本文（＝Claudeが『これでどうですか』と見せたもの）をプロンプトから抜く。"""
    if not prompt:
        return ""
    m = re.search(r"■実行しようとしているもの(.*?)(?:\n■|$)", prompt, re.S)
    if m:
        return m.group(1).strip()
    m = re.search(r"■Claudeの解釈(.*?)(?:\n■|$)", prompt, re.S)
    return m.group(1).strip() if m else ""


def rounds(n):
    d = os.path.join(KENPIN, str(n))
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*-result.json"))):
        j = _load(p)
        if not j:
            continue
        seq = j.get("seq") or 0
        sub = os.path.join(d, "%03d-submission.md" % seq)
        j["_submission"] = io.open(sub, encoding="utf-8").read() if os.path.exists(sub) else _submitted_part(j.get("prompt"))
        out.append(j)
    out.sort(key=lambda x: x.get("seq") or 0)
    return out


def build_text(n, rs):
    title, state = _title_of(n)
    L = []
    A = L.append
    A("=" * 70)
    A("%s号の検品ゲート — 外部AIとのやりとり全記録" % n)
    if title:
        A("題名：%s" % title)
    A("=" * 70)
    A("")
    A("■ これは何か")
    A("　Claudeが作ったものを、たまごさんに見せる**前に**外部のAI（ChatGPT等）に見せて、")
    A("　「ダメ、ここ違う」と言わせる仕組みです。PASSが出るまでたまごさんには上げません。")
    A("")
    if not rs:
        A("　この号にはまだ記録がありません。")
        return "\n".join(L)

    fixes = sum(1 for r in rs if (r.get("verdict") or "").upper() == "FIX")
    passed = any((r.get("verdict") or "").upper() == "PASS" for r in rs)
    total = round(sum(float(r.get("costYen") or 0) for r in rs), 3)
    A("■ 結果のまとめ")
    A("　往復した回数：%d回（うち『直させた』が%d回）" % (len(rs), fixes))
    A("　最後の判定　：%s" % ("✅ PASS（通った）" if passed else "まだ通っていない"))
    A("　かかったお金：%.3f円（外部AIの利用料。合計）" % total)
    A("　使った相手　：%s" % "・".join(sorted({r.get("provider") or "?" for r in rs})))
    A("")
    A("=" * 70)
    A("■ やりとりの流れ（上から順に起きたこと）")
    A("=" * 70)

    for r in rs:
        seq = r.get("seq")
        v = (r.get("verdict") or "").upper()
        A("")
        A("─" * 70)
        A("【第%s回】%s　%s" % (seq, VERDICT_JA.get(v, v), r.get("ts") or ""))
        A("　相手：%s / %s　　費用：%.3f円　　種類：%s"
          % (r.get("provider") or "?", r.get("model") or "?", float(r.get("costYen") or 0),
             "お金を使う前のゲート" if r.get("kind") == "pre" else "出す前のゲート"))
        A("─" * 70)
        sub = (r.get("_submission") or "").strip()
        if sub:
            A("")
            A("▼ Claudeが出したもの（これでどうですか、と見せた中身）")
            for line in sub.splitlines()[:40]:
                A("　　" + line)
            if len(sub.splitlines()) > 40:
                A("　　…（以下略。全文は %03d-submission.md）" % (seq or 0))
        gaps = r.get("gaps") or []
        if gaps:
            A("")
            A("▼ 外部AIの指摘（ここがズレている）")
            for i, g in enumerate(gaps, 1):
                A("　　%d. %s" % (i, g))
        if r.get("blindspot"):
            A("")
            A("▼ たまごさんが見落としていそうな点")
            A("　　%s" % r["blindspot"])
        if r.get("one_line"):
            A("")
            A("▼ 一言")
            A("　　%s" % r["one_line"])
        if v == "FIX":
            A("")
            A("→ 直させた。たまごさんには通知していない。同じ号番号で直して再提出。")
        elif v == "PASS":
            A("")
            A("→ ✅ 通った。ここで初めてたまごさんに上げてよい状態になった。")
    A("")
    A("=" * 70)
    A("（このファイルは tools/kenpin_mieru.py が自動生成。元データは同じフォルダのJSON）")
    return "\n".join(L)


def build_md(n, rs, txt_rel):
    title, _ = _title_of(n)
    fixes = sum(1 for r in rs if (r.get("verdict") or "").upper() == "FIX")
    passed = any((r.get("verdict") or "").upper() == "PASS" for r in rs)
    total = round(sum(float(r.get("costYen") or 0) for r in rs), 3)
    L = []
    A = L.append
    A("<details>")
    A("<summary>%s号の検品：%d往復・直させたのが%d回・%s・%.3f円（開くと全部見えます）</summary>"
      % (n, len(rs), fixes, "最後はPASS" if passed else "まだ通っていない", total))
    A("")
    if title:
        A("**%s**" % title)
        A("")
    A("| 回 | 判定 | 相手 | 指摘の要点 | 円 |")
    A("|---|---|---|---|---|")
    for r in rs:
        v = (r.get("verdict") or "").upper()
        g = (r.get("gaps") or [""])[0]
        g = re.sub(r"\s+", " ", str(g))[:60]
        A("| %s | %s | %s | %s | %.3f |"
          % (r.get("seq"), VERDICT_JA.get(v, v), r.get("provider") or "?", g,
             float(r.get("costYen") or 0)))
    A("")
    A("全文（たまごさんが読む用）： `%s`" % txt_rel)
    A("")
    A("</details>")
    return "\n".join(L)


def do_one(n, quiet=False):
    rs = rounds(n)
    if not rs:
        if not quiet:
            print("%s号：記録がありません" % n)
        return None
    d = os.path.join(KENPIN, str(n))
    txt = os.path.join(d, "yaritori.txt")
    md = os.path.join(d, "yaritori.md")
    body = build_text(n, rs)
    with io.open(txt, "w", encoding="utf-8") as f:
        f.write(body + "\n")
    # 進捗表（GitHub Pages）から押せるように status/public/ へも同じものを置く。
    # ファイル名は日本語だとURLが読みにくくなるので半角にする。
    pub = os.path.join(REPO, "status", "public", "kenpin", "%s.txt" % n)
    os.makedirs(os.path.dirname(pub), exist_ok=True)
    with io.open(pub, "w", encoding="utf-8") as f:
        f.write(body + "\n")
    rel = os.path.relpath(txt, REPO)
    with io.open(md, "w", encoding="utf-8") as f:
        f.write(build_md(n, rs, rel) + "\n")
    if not quiet:
        print("%s号：%d往復 → %s" % (n, len(rs), txt))
    return {
        "n": int(n), "rounds": len(rs),
        "fixes": sum(1 for r in rs if (r.get("verdict") or "").upper() == "FIX"),
        "passed": any((r.get("verdict") or "").upper() == "PASS" for r in rs),
        "costYen": round(sum(float(r.get("costYen") or 0) for r in rs), 3),
        "lastAt": rs[-1].get("ts"), "providers": sorted({r.get("provider") or "?" for r in rs}),
        "txt": rel, "md": os.path.relpath(md, REPO),
        "publicTxt": "status/public/kenpin/%s.txt" % n,
        "title": _title_of(n)[0],
        "rows": [{"seq": r.get("seq"), "verdict": (r.get("verdict") or "").upper(),
                  "provider": r.get("provider"), "yen": round(float(r.get("costYen") or 0), 3),
                  "gap": re.sub(r"\s+", " ", str((r.get("gaps") or [""])[0]))[:90]}
                 for r in rs],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if a.n and not a.all:
        r = do_one(a.n, a.quiet)
        return 0 if r else 1

    rows = []
    for d in sorted(os.listdir(KENPIN)) if os.path.isdir(KENPIN) else []:
        if not d.isdigit():
            continue
        r = do_one(d, quiet=True)
        if r:
            rows.append(r)
    rows.sort(key=lambda x: x["n"], reverse=True)
    os.makedirs(os.path.dirname(PUBLIC), exist_ok=True)
    with io.open(PUBLIC, "w", encoding="utf-8") as f:
        json.dump({"updatedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": rows},
                  f, ensure_ascii=False, indent=1)
    if not a.quiet:
        print("%d号ぶん書き出しました。要約：%s" % (len(rows), PUBLIC))
        for r in rows[:12]:
            print("  %s号 %d往復（直させた%d回）%s %.3f円"
                  % (r["n"], r["rounds"], r["fixes"], "PASS✅" if r["passed"] else "未PASS", r["costYen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
