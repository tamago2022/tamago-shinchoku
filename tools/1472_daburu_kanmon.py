#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1472番：「確認できないものをよこすな」の門。

━━ たまごさんの原文（2026-09-19 20:23・スマホ音声入力）━━
  「今ねパソコンの前にいるんだけども、ダブルクリックで開きますって開かれないよ
   …確認できないものをよこすなって言うの、何回も言ってるよ…俺から時間を奪わないでくれ。」

━━ なにが起きていたか（推測ではなく実物の記録）━━
  同じ夜（2026-09-20・975番 tools/auth_keeper.py 冒頭）に、まさにこの事故の実例が
  そのまま残っている：

    「ファイルを渡さない・ダブルクリックさせない・ターミナルを開かせない
      （2026-09-20 たまごさん指定。過去に『ダブルクリックで開きます』が
      開けず実害あり）。」

  975番はこの教訓を「Claudeログインの再貼り付け」1件だけに適用して直した
  （status/LOGIN.md の1行貼り付け方式へ切替）。だが元の苦言はもっと広く、
  「確認してほしいものを出すとき全般」に対する話だった。そのため、
  ログイン以外の確認提出物（kenpin_gate.py 経由でたまごさんへ渡す報告）には
  同じ弱さがまだ残っていた＝1472号として再発・判定日赤に。

━━ この門がすること ━━
  たまごさんへの提出物（kenpin_gate.py --submit の本文）に、
  「確認して／見て／開いて／ダブルクリック」の文脈で
  ★ローカルファイルパス（/Users/…・~/…・file://…・拡張子だけのローカル参照）
  がそのまま書かれていたら止める。

  ローカルパスを渡してよいのは「たまごさん自身がMacで実行する必要がある
  操作」（鍵を貼る・投稿を承認する等の .command ファイル）だけで、
  「見て確認するだけ」の用途は必ず実際にHTTP(S)で200を確認したURLに
  置き換える（tools/make_check_page.py で作る確認ページ・GitHub Pages）。

━━ 出してよい確認は0件にはできない。だから区別する ━━
  ①「確認」「見て」「開いて」「ダブルクリック」の直前・直後にローカルパスが
    ある → 止める（KZ的な文字列判定。AIは呼ばない・課金0）
  ②「ダブルクリック」だけがあり、ローカルパスと同じ文に「実行」「貼る」
    「承認」「入れる」など操作系の言葉がある → 通す（既存の .command 運用は
    正当な用途として残す）
  ③ http(s):// のURLが書かれている → その周辺は対象にしない

使い方：
    python3 tools/1472_daburu_kanmon.py --file status/houkoku.md
    echo "確認: /Users/mac/Desktop/x.html をダブルクリック" | python3 tools/1472_daburu_kanmon.py
    python3 tools/1472_daburu_kanmon.py --text "..."
    python3 tools/1472_daburu_kanmon.py --self-test

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
LOG = os.path.join(STATUS, "1472_daburu_kanmon.log")

# 「確認してほしい」ことを示す言葉
KAKUNIN_GO = re.compile(
    r"確認(?:して|できます|できません|ください|お願い)?|見て(?:ください)?|"
    r"開き(?:ます|ません)|開いて(?:ください)?|ダブルクリック")

# ローカルファイルパスの兆候
LOCAL_PATH = re.compile(
    r"(?:file://\S+|~/[^\s、。）)」\]]+\.\w+|/Users/[^\s、。）)」\]]+\.\w+)")

# たまごさん自身がMacを操作する正当な用途（実行・貼る・承認等）。
# これが同じ文にあれば、ローカルパス＋ダブルクリックでも止めない。
JIKKOU_GO = re.compile(
    r"実行|貼(?:る|って|り付け)|承認|入れる|鍵を|コマンドを打|Enterを押")

# http(s)のURLがあるかどうか
HTTP_RE = re.compile(r"https?://\S+")


def _log(msg):
    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            import time
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def _sentences(text):
    """雑に「行」単位で見る。1文ずつに割るより誤検出が少ない。"""
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def check(text: str):
    """戻り値: (hits, ok_local_paths)。hitsが空なら通過。"""
    hits = []
    for ln in _sentences(text):
        if not LOCAL_PATH.search(ln):
            continue
        if not KAKUNIN_GO.search(ln):
            continue
        if JIKKOU_GO.search(ln):
            # 実行・貼る等の正当な操作系ワードが同じ行にあれば見逃す
            continue
        hits.append(ln.strip())
    return hits


def run(text: str) -> int:
    hits = check(text)
    if not hits:
        print("DABURU_KANMON: PASS — ローカルパスを『確認して』の文脈で渡していません")
        _log("PASS")
        return 0
    print("🛑 1472番の門が止めました。これはたまごさんに上げられません。\n")
    for ln in hits:
        print("  ● %s" % ln)
    print(
        "\n  直し方：そのローカルパスを渡すのをやめて、"
        "python3 tools/make_check_page.py で確認ページを作り、"
        "curlで200が返ることを自分で確かめてから、そのHTTP URLを渡してください。\n"
        "  （たまごさんの言葉：『ダブルクリックで開きますって開かれないよ…"
        "確認できないものをよこすな』2026-09-19）\n"
    )
    _log("BLOCK %d件" % len(hits))
    return 2


# ---------------------------------------------------------------------------
# 自己試験
# ---------------------------------------------------------------------------

def self_test() -> int:
    cases = [
        ("確認ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/1472-x.html",
         True, "HTTP URLだけ→通す"),
        ("確認してください: /Users/mac/tamago/tamago-shinchoku/share/check/x.html をダブルクリックで開きます",
         False, "ローカルパス＋確認→止める"),
        ("このファイルをダブルクリックで開くと見れます: ~/Desktop/report.html",
         False, "ローカルパス＋見て→止める"),
        ("wae_autopost/1_鍵を貼る.command をダブルクリックして、貼ってEnter。",
         True, "実行系（貼る/Enter）は正当な運用なので通す"),
        ("0_この11本にOKを出す.command をダブルクリックして承認してください。",
         True, "承認系も正当な運用なので通す"),
        ("本番URL: https://joy-relief-station.lovable.app/room/card/x を確認してください",
         True, "URLベースの確認依頼は通す"),
    ]
    ok = True
    for text, expect_pass, label in cases:
        hits = check(text)
        passed = not hits
        mark = "OK" if passed == expect_pass else "NG"
        if mark == "NG":
            ok = False
        print("[%s] %s → 期待=%s 実際=%s" % (
            mark, label, "PASS" if expect_pass else "BLOCK",
            "PASS" if passed else "BLOCK"))
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
