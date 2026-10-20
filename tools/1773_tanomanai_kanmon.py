#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/1773_tanomanai_kanmon.py ── 「たまごさんにやってもらう」を最初の選択肢にしない関所（1773号）。

たまごさん（★3回言わせている・1773号）:
  枷1「たまごさんに確認を出さない」は session_preamble.md に文章として
  何度も書かれているが、henkan_kanmon.py で調べると機械の関所が無い
  （mi_henkan=文章だけで終わっている12枷のうちの1つ）。
  文章だけのルールは「もう一度言わせる」ことになる（1694号の教え）。

━━ この関所が見るもの ━━
  たまごさんへ送る・報告に書く「確認・お願い・判断待ち」の文を受け取り、
  以下を判定する：

  ① 止めてよいのは4カテゴリだけ
     お金／不可逆の削除／外部公開／パスワード・ログイン・権限承認
     → この4つのどれにも当たらない「確認してください」「どうしますか」は
        それ自体が違反（＝「たまごさんにやってもらう」を最初の選択肢にした）。

  ② 聞き方の型（34987号）
     4カテゴリに当たる場合でも、URL（開く場所）と具体的な操作
     （押す・入力する・承認する・ログインする等）を言い切っていなければ
        曖抽象的な丸投げとして弾く。

  ③ ①②どちらも通らない時点で「試した跡」が無ければ、1464番（打開関所）の
     対象でもある（本関所は①②だけを機械的に見る。試行の裏取りは1464が担当）。

  **文に「確認・お願い・してください・どうしますか・判断待ち」等の
  "たまごさんへ振る"サインが無ければ、そもそも対象外＝無条件PASS。**

━━ 使い方 ━━
    python3 tools/1773_tanomanai_kanmon.py --text "..."
    python3 tools/1773_tanomanai_kanmon.py --text-file report.md
    python3 tools/1773_tanomanai_kanmon.py --show        # 弾いた数・通した数
    python3 tools/1773_tanomanai_kanmon.py --self-test

━━ 守っていること ━━
  - 台帳は追記のみ・消さない
  - ブラウザを使わない・ネットワークに出ない（ローカルのテキスト判定だけ）
  - OSには一切触らない（文字列を読むだけ）
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DAICHO = os.path.join(ST, "1773_tanomanai_daicho.jsonl")

JST = datetime.timezone(datetime.timedelta(hours=9))

# ★「たまごさんへ振る」サイン（これが無ければ対象外＝無条件PASS）
FURU_SIGN = re.compile(
    r"(確認して|お願いします|お願いし|してください|どうしますか|どうします\？|"
    r"判断待ち|承認して|進めていいです|これでいいです|してもらう|やってもらう|"
    r"やってください|開いてください|してほしい)"
)

# ①止めてよい4カテゴリ
CATEGORY = {
    "money": re.compile(r"(お金|課金|購入|送金|円|決済|支払い|有料API)"),
    "delete": re.compile(r"(削除|消す|作り直せない|不可逆|元に戻せない)"),
    "publish": re.compile(r"(外部公開|SNS投稿|送信|投稿する|公開する|メール送信)"),
    "auth": re.compile(
        r"(パスワード|ログイン|二段階認証|権限承認|本人確認|認証画面|初回登録)"
    ),
}

# ②聞き方の型：URL + 具体的な操作動詞
HAS_URL = re.compile(r"https?://\S+")
ACTION_VERB = re.compile(
    r"(開いて|押して|入力して|承認して|ログインして|クリックして|タップして)"
)


def _now():
    return datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def sadamu(text: str) -> dict:
    """1件のテキストを見て ok / riyuu を返す。"""
    riyuu = []
    furu = bool(FURU_SIGN.search(text or ""))

    if not furu:
        return {"ok": True, "furu": False, "riyuu": [], "categories": []}

    cats = [name for name, pat in CATEGORY.items() if pat.search(text)]
    if not cats:
        riyuu.append(
            "4カテゴリ（お金／不可逆の削除／外部公開／パスワード・ログイン・権限承認）"
            "のどれにも当たらないのに確認・お願いを出している"
            "＝「たまごさんにやってもらう」を最初の選択肢にした違反"
        )

    if cats:
        if not HAS_URL.search(text):
            riyuu.append("URL（開く場所）が無い＝曖抽象的な丸投げ")
        if not ACTION_VERB.search(text):
            riyuu.append("具体的な操作（押す・入力する・承認する等）を言い切っていない")

    return {"ok": not riyuu, "furu": True, "riyuu": riyuu, "categories": cats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        cases = [
            ("普通の完了報告です。本番URLはhttps://example.com/です。", True, False),
            ("どうしますか？AとBどちらがいいですか。", False, True),
            ("確認してください。", False, True),
            (
                "パスワードの入力が必要です。https://example.com/login を開いて、"
                "ログインしてください。",
                True,
                True,
            ),
            ("ログインが必要です。確認してください。", False, True),
        ]
        ok_all = True
        for text, want_ok, want_furu in cases:
            r = sadamu(text)
            got = (r["ok"], r["furu"])
            want = (want_ok, want_furu)
            if got != want:
                ok_all = False
                print("FAIL: %r -> got=%s want=%s (%s)" % (text, got, want, r["riyuu"]))
        print("TANOMANAI_KANMON_SELFTEST: %s" % ("PASS" if ok_all else "FAIL"))
        return 0 if ok_all else 1

    if args.show:
        if not os.path.exists(DAICHO):
            print(json.dumps({"total": 0, "ok": 0, "ng": 0}, ensure_ascii=False))
            return 0
        total = ok_n = ng_n = 0
        with io.open(DAICHO, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("ok"):
                    ok_n += 1
                else:
                    ng_n += 1
        print(json.dumps({"total": total, "ok": ok_n, "ng": ng_n}, ensure_ascii=False))
        return 0

    text = args.text
    if args.text_file:
        with io.open(args.text_file, encoding="utf-8") as f:
            text = f.read()
    if text is None:
        print("TANOMANAI_KANMON_RESULT: ERROR --text か --text-file が必要です", file=sys.stderr)
        return 2

    r = sadamu(text)
    rec = dict(r)
    rec["at"] = _now()
    os.makedirs(ST, exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if not r["furu"]:
        print("TANOMANAI_KANMON_RESULT: PASS（たまごさんへ振るサイン無し・対象外）")
        return 0

    if r["ok"]:
        print(
            "TANOMANAI_KANMON_RESULT: PASS（カテゴリ=%s・型も満たす）"
            % ",".join(r["categories"])
        )
        return 0

    print("TANOMANAI_KANMON_RESULT: FAIL")
    for why in r["riyuu"]:
        print("  - %s" % why)
    return 2


if __name__ == "__main__":
    sys.exit(main())
