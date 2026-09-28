#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1481番：「簡潔にして完結」の門。ダラダラした完了報告を機械で止める。

━━ たまごさんの原文（2026-09-19 20:23・スマホ音声入力）━━
  「何が言いたいのかわからない…3行45枚で足りるのにさぁダラダラ…
    治ったかしか興味ないから…簡潔にして完結は価値高いよ」

━━ なぜ作ったか ━━
  「報告は3行以内」「9割削る」は既に複数のツールのプロンプト文言（daicho_tane.py・
  shukudai.py・tomaranai.py・github_watch.py 等）に書かれていた。だが**それは
  「AIへの指示文」であって「機械の関所」ではなかった**。指示文は読み飛ばされる。
  898番の関所思想（「間違いは仕組みで防ぐ」）と同じで、ここも文章のお願いだけでは
  1週間経っても直らず判定日赤に達した（1481番自身がその実例）。

  だから kazu_gate.py（数字の門）・1472_daburu_kanmon.py（確認できないものの門）
  と同じ型で、**通す/止めるをexit codeで決める**関所をここに作る。

━━ 落とす条件は3つだけ（増やさない）━━

  H1  本文の「地の文（自由記述の説明文）」が5行を超える
      ★ラベル行（【完了】【問題】【判断待ち】で始まる行）とURL単独行・
        「ラベル: URL」形式の行は地の文に数えない（報告の骨格として必要だから）。
  H2  経緯・言い訳・謝罪の言葉がある
      （「まず」「次に」「そのため」「原因は」「試行錯誤した結果」「経緯」
        「対応した内容は以下」「申し訳」「させていただきました」「にあたり」）
  H3  実行ログ・コマンド出力・diffをそのまま貼っている
      （`$ ` や `>>> ` で始まる行が2行以上、または3行以上の```コードブロック、
        または `+`/`-` で始まる差分行が3行以上）

━━ AIを1回も呼ばない ━━
  全部ただの文字列判定。課金0。毎回同じ答えが出る。（kazu_gate.pyと同じ型）

使い方：
    python3 tools/1481_houkoku_kanmon.py --file status/houkoku.md
    echo "..." | python3 tools/1481_houkoku_kanmon.py
    python3 tools/1481_houkoku_kanmon.py --text "..."
    python3 tools/1481_houkoku_kanmon.py --self-test

終了コード: 0=通過 / 2=止めた（出してはいけない）
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LOG = os.path.join(STATUS, "1481_houkoku_kanmon.log")

JIRETSU_LIMIT = 5  # H1: 地の文がこの行数を超えたら止める

# ラベル行（報告の骨格として必ず要る。地の文に数えない）
LABEL_LINE = re.compile(r"^【(完了|問題|判断待ち)】")
# 「ラベル: URL」または単独URL行（確認ページ・本番URL等の必須行）
URL_LINE = re.compile(r"^(\S+[:：]\s*)?https?://\S+\s*$")
# 見出し・箇条書き記号だけの短い行（骨格として許す）
BULLET_LINE = re.compile(r"^\s*([#>*・\-]|\d+[.)])\s*")

# H2: 経緯・言い訳・謝罪ワード
KEII_GO = re.compile(
    r"まず(?:調査|確認|コード|読み|試し)?|次に|そのため|原因は|試行錯誤した結果|"
    r"経緯|対応した内容は以下|申し訳|させていただきました|にあたり|"
    r"手順としては|順を追って|説明します|詳しく述べる")

# H3: 実行ログ・コマンド出力・diffの生貼り
SHELL_PROMPT = re.compile(r"^\s*(\$ |>>> )")
DIFF_LINE = re.compile(r"^\s*[+-]\S")
CODE_FENCE = re.compile(r"^```")


def _log(msg):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            import time
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def _jiretsu_lines(text):
    """地の文（骨格行を除いた自由記述の説明文）だけを数える。"""
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if LABEL_LINE.match(s):
            continue
        if URL_LINE.match(s):
            continue
        if BULLET_LINE.match(s) and len(s) <= 40:
            # 短い見出し・箇条書きは骨格として許す（長い箇条書きは地の文として数える）
            continue
        if CODE_FENCE.match(s):
            continue
        out.append(s)
    return out


def check(text: str):
    """戻り値: hitsのリスト（空なら通過）。各要素は (code, why)。"""
    hits = []

    jiretsu = _jiretsu_lines(text)
    if len(jiretsu) > JIRETSU_LIMIT:
        hits.append(("H1", "地の文が%d行（上限%d行）。3行で足りる報告に長い説明が付いています。"
                     % (len(jiretsu), JIRETSU_LIMIT)))

    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        m = KEII_GO.search(s)
        if m:
            hits.append(("H2", "経緯・言い訳の言葉「%s」を含む行：%s" % (m.group(0), s[:60])))
            break  # 1件見つければ十分。行ごとに何度も出さない。

    shell_hits = sum(1 for ln in text.splitlines() if SHELL_PROMPT.match(ln))
    diff_hits = sum(1 for ln in text.splitlines() if DIFF_LINE.match(ln))
    fence_hits = sum(1 for ln in text.splitlines() if CODE_FENCE.match(ln.strip()))
    if shell_hits >= 2:
        hits.append(("H3", "コマンド実行ログが%d行そのまま貼られています。" % shell_hits))
    elif fence_hits >= 2 and (len(text.splitlines()) - fence_hits) >= 3:
        hits.append(("H3", "コードブロックの生貼りがあります。"))
    elif diff_hits >= 3:
        hits.append(("H3", "diff/差分が%d行そのまま貼られています。" % diff_hits))

    return hits


def run(text: str) -> int:
    hits = check(text)
    if not hits:
        print("HOUKOKU_KANMON: PASS — 地の文%d行・経緯語なし・ログ生貼りなし"
              % len(_jiretsu_lines(text)))
        _log("PASS jiretsu=%d" % len(_jiretsu_lines(text)))
        return 0
    print("🛑 1481番の門が止めました。この報告はダラダラしています。\n")
    for code, why in hits:
        print("  ● [%s] %s" % (code, why))
    print(
        "\n  直し方：【完了/問題/判断待ち】1行＋確認ページURL＋本番URLの3行に削る。\n"
        "  経緯・言い訳・実行ログは全部消す。治ったかどうかだけを書く。\n"
        "  （たまごさんの言葉：『簡潔にして完結は価値高いよ』2026-09-19）\n"
    )
    _log("BLOCK %d件 %s" % (len(hits), ",".join(c for c, _ in hits)))
    return 2


# ---------------------------------------------------------------------------
# 自己試験（逆テスト：わざと悪い報告文を混ぜて、落ちるか確認する）
# ---------------------------------------------------------------------------

def self_test() -> int:
    cases = [
        (
            "【完了】1481番の報告簡潔化の門を実装\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/1481-x.html\n"
            "本番: https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/1481_houkoku_kanmon.py",
            True, "正しい3行の完了報告→通す",
        ),
        (
            "まず調査をしました。次にコードを読みました。そのため原因はここにあると分かりました。\n"
            "試行錯誤した結果、直すことができました。原因は設定ファイルの読み込み順序でした。\n"
            "対応した内容は以下の通りです。詳しく述べると、まず環境を確認し、次にログを見て、\n"
            "そのうえで修正パッチを当てました。申し訳ありませんが少し時間がかかりました。\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html",
            False, "経緯だらけの長文報告→止める",
        ),
        (
            "【完了】ビルドを直しました\n"
            "実行結果:\n"
            "$ npm run build\n"
            "> building...\n"
            "> done in 3.2s\n"
            "$ npm test\n"
            "> 12 passed, 0 failed\n"
            "本番: https://example.com/x",
            False, "実行ログの生貼り→止める",
        ),
        (
            "【判断待ち】A：今すぐ直す B：明日まとめて直す どちら？\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html",
            True, "短い判断待ち報告→通す",
        ),
        (
            "【問題】外部APIが403を返しています\n"
            "確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/x.html\n"
            "参考: https://example.com/status",
            True, "短い問題報告（3行）→通す",
        ),
    ]
    ok = True
    for text, expect_pass, label in cases:
        hits = check(text)
        passed = not hits
        mark = "OK" if passed == expect_pass else "NG"
        if mark == "NG":
            ok = False
        print("[%s] %s → 期待=%s 実際=%s%s" % (
            mark, label, "PASS" if expect_pass else "BLOCK",
            "PASS" if passed else "BLOCK",
            "" if passed else "  (%s)" % "; ".join("%s:%s" % (c, w[:30]) for c, w in hits)))
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
