#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1772番：完了報告に残る「実行ログ・コマンド出力・エラーメッセージの抜粋」を消す道具。

━━ たまごさんの原文（抜粋・何回も言わせている）━━
  「実行ログの抜粋とかもまるで要らない。」（2026-09-06・報告は9割削る）

━━ なぜ今さら作るのか（1481番が既にあるのに）━━
  `tools/1481_houkoku_kanmon.py` が同じ H3（実行ログ・コマンド出力・diffの生貼り）を
  **止める**関所として既に存在する（2026-09-19）。だが1481番が効くのは
  `kenpin_gate.py --submit --kind post` を**自分で呼んだ**提出物だけ。

  現実の大半の案件（この1772番自身も含む）は `tools/auto_launcher.py` の
  `harvest()` が、死んだセッションのログから最後の "result" 文字列を正規表現で
  抜き出し、**どの関所も通さずそのまま** `queue.json` の `it["result"]` へ書き込む
  （旧実装：1行で代入して[:1200]で切るだけ）。ここにログ生貼りが残る。

  harvest()はセッションが**もう死んでいる**地点で動くので、1481番のように
  「止めて書き直させる」ことができない（書き直す相手がいない）。
  だから1481番は「止める関所」、この1772番は**「消して通す」サニタイザ**として
  役割を分ける（二重管理ではなく、提出口と収穫口で役目が違う）。

━━ 消す条件（1481番のH3と同じ3種類＋エラーメッセージの生貼り）━━
  - ``` で囲まれたコードブロック（中身ごと）
  - `$ ` / `>>> ` で始まるシェル実行行
  - `+`/`-` で始まる差分(diff)行
  - Python/Node/npm のトレースバック・スタックトレース行
    （`Traceback (most recent call last):` / `  File "..."` / `    at ` / `npm ERR!`）

  消した場所には1行だけ「（実行ログ・コマンド出力を除去）」を残す（連続分は1回にまとめる）。
  それ以外の地の文・URL・結論は一切変えない。

使い方：
    python3 tools/1772_rogu_sakujo.py --file status/x.txt
    echo "..." | python3 tools/1772_rogu_sakujo.py
    python3 tools/1772_rogu_sakujo.py --text "..."
    python3 tools/1772_rogu_sakujo.py --self-test
"""
from __future__ import annotations

import argparse
import io
import re
import sys

MARK = "（実行ログ・コマンド出力を除去）"

_CODE_FENCE = re.compile(r"^\s*```")
_SHELL_PROMPT = re.compile(r"^\s*(\$ |>>> )")
_DIFF_LINE = re.compile(r"^\s*[+-]\S")
_TRACE_START = re.compile(
    r"^\s*(Traceback \(most recent call last\):|npm ERR!|  File \"|    at |"
    r"[A-Za-z_][\w.]*Error:\s|[A-Za-z_][\w.]*Exception:\s)"
)
_CJK = re.compile(r"[぀-ヿ㐀-鿿]")
_LABEL_LINE = re.compile(r"^\s*【")


def _is_log_continuation(line: str) -> bool:
    """$ やトレースバックの直後に続く、素の出力行っぽいものだけを拾う。
    日本語（CJK）を含む行・URL行・【ラベル】行は地の文として必ず止める
    （本文の日本語をログと誤って一緒に消さないための安全弁）。
    """
    s = line.strip()
    if not s:
        return False
    if _LABEL_LINE.match(line):
        return False
    if _CJK.search(s):
        return False
    if re.match(r"^https?://", s):
        return False
    return True


def strip_log_excerpts(text: str):
    """戻り値: (消した後の文, 消した行数)。地の文・URL・結論はそのまま残す。"""
    lines = (text or "").splitlines()
    out = []
    removed = 0
    i, n = 0, len(lines)

    def mark_once():
        if not out or out[-1] != MARK:
            out.append(MARK)

    while i < n:
        line = lines[i]
        if _CODE_FENCE.match(line):
            removed += 1
            i += 1
            while i < n and not _CODE_FENCE.match(lines[i]):
                removed += 1
                i += 1
            if i < n:
                removed += 1
                i += 1  # 閉じ```も消す
            mark_once()
            continue
        if _SHELL_PROMPT.match(line) or _DIFF_LINE.match(line) or _TRACE_START.match(line):
            removed += 1
            i += 1
            # 続く素の出力行（> building... 等）も、日本語に出会うまで一緒に消す
            while i < n and _is_log_continuation(lines[i]):
                removed += 1
                i += 1
            mark_once()
            continue
        out.append(line)
        i += 1
    return "\n".join(out), removed


def run(text: str) -> int:
    cleaned, removed = strip_log_excerpts(text)
    if removed:
        print("1772_ROGU_SAKUJO: %d行を除去" % removed)
    else:
        print("1772_ROGU_SAKUJO: 除去対象なし")
    print(cleaned)
    return 0


# ---------------------------------------------------------------------------
# 自己試験（逆テスト：ログ混入を実際に混ぜて、消えるか・地の文が残るかを見る）
# ---------------------------------------------------------------------------

def self_test() -> int:
    cases = [
        (
            "【完了】ビルドを直しました\n"
            "実行結果:\n"
            "$ npm run build\n"
            "> building...\n"
            "> done in 3.2s\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html",
            True, False,
            "シェル実行ログが地の文から消え、URL行は残る",
        ),
        (
            "【完了】関数を直しました\n"
            "```\n"
            "def f():\n"
            "    return 1\n"
            "```\n"
            "本番: https://example.com/x",
            True, False,
            "コードブロックが消え、他の行は残る",
        ),
        (
            "【問題】起動時に落ちます\n"
            "Traceback (most recent call last):\n"
            "  File \"tools/x.py\", line 10, in <module>\n"
            "    raise ValueError(\"bad\")\n"
            "ValueError: bad\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html",
            True, False,
            "Pythonのトレースバックが消え、見出し行は残る",
        ),
        (
            "【完了】差分を当てました\n"
            "+line1\n"
            "+line2\n"
            "-line3\n"
            "本番: https://example.com/x",
            True, False,
            "diff行が消える",
        ),
        (
            "【完了】短い正常な報告です\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html",
            False, True,
            "ログが無い報告はそのまま変化しない",
        ),
    ]
    ok = True
    for text, expect_removed, expect_unchanged, label in cases:
        cleaned, removed = strip_log_excerpts(text)
        got_removed = removed > 0
        unchanged = cleaned == text
        mark = "OK"
        if got_removed != expect_removed:
            mark = "NG"
        if expect_unchanged and not unchanged:
            mark = "NG"
        if mark == "NG":
            ok = False
        print("[%s] %s → removed=%d" % (mark, label, removed))
        if mark == "NG":
            print("  --- cleaned ---")
            print(cleaned)
    print()
    print("SELF_TEST: %s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="このファイルの中身を見る")
    ap.add_argument("--text", help="この文字列を見る")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.file:
        text = io.open(args.file, encoding="utf-8", errors="replace").read()
    elif args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()

    return run(text)


if __name__ == "__main__":
    raise SystemExit(main())
