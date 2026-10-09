#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34835番・確認ページの作り直し（1回目の機械検品で非公開リポジトリのリンクを指摘され差し戻された分）。
既存ツール tools/make_check_page.py をそのまま呼ぶだけ（新しい仕組みは作らない）。
shell経由だと引用符・改行の扱いが事故るため、subprocessへargvのリストで渡す。
"""
import subprocess
import sys

ARGS = [
    sys.executable, "tools/make_check_page.py",
    "--n", "34835",
    "--slug", "zenkantou-check-logic",
    "--title", "判定日赤34835番：全担当チェックのロジックは実在・本日も再実行して確認（店主が開けるリンクに差し替え）",
    "--what",
        "判定日赤34835番の元ネタ「全担当チェックのロジックを作ってください」は、"
        "たまごさんが言った同日2026-08-08にjoy-relief-stationへ実装済みだった"
        "（<code>scripts/roles/role-sweep.mjs</code>＝ファイル冒頭のコメントに"
        "「全担当チェック（無人巡回の目）」と明記、本番の案内所ページ"
        "<code>/admin/role-status</code>で結果を見られる）。"
        "前回の確認ページは、たまごさんが開くと404になる非公開リポジトリ"
        "(joy-relief-station)のコミットリンクを貼っていたため機械検品で差し戻された。"
        "今回は本日2026-10-10に同じロジックをもう一度実際に実行し直し、"
        "たまごさんが直接開ける本番URLだけに差し替えた。"
        "なお自動30分おき巡回は2026-09-28にたまごさんの指示"
        "（<code>scripts/roles/sweep-cron.sh:34</code>「読むだけの見回りは止めた」）で"
        "手動実行へ切り替え済み。読むだけで何も直さない仕組みだったため、"
        "台帳反映・push等の「手を動かす」便へ統合した判断であり、壊れているわけではない。",
    "--num", "15件|本日実行した全担当チェックが対象にした担当の数",
    "--num", "10件|残件ありと判定された担当の数（全15件中）",
    "--num", "67件|15担当ぶんの残件の合計",
    "--link", "本番の案内所ページ（担当別の次の一手・ログイン不要で今も開ける）|https://joy-relief-station.lovable.app/admin/role-status",
    "--link", "確認ページを作る仕組み自体（公開リポジトリ・たまごさんも開ける）|https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/make_check_page.py",
    "--table",
        "全担当チェックのロジックが実在し、本日も動くか"
        "|$ node scripts/roles/role-sweep.mjs --json --no-checks を本日実行"
        "→15担当・残件67件を検出（ranAt 2026-10-09T21:56:47Z UTC＝2026-10-10 06:56 JST）"
        "|yes",
    "--table",
        "本番の案内所ページが、たまごさんの手元で実際に開けるか（非公開リポジトリのリンクではない）"
        "|https://joy-relief-station.lovable.app/admin/role-status を本日取得"
        "→HTTP 200・本文16,396バイト（ログイン不要）"
        "|yes",
    "--table",
        "自動30分おき巡回が今も動いているか"
        "|2026-09-28にたまごさん指示で停止済み（scripts/roles/sweep-cron.sh:34"
        "「読むだけの見回りは止めた」）。読むだけで直さない仕組みだったため、"
        "台帳反映・push等の手を動かす便へ統合した。今は npm run role:status:page で手動更新"
        "|no",
    "--allow-no-screenshot",
        "画面の見た目を変える作業ではなく、裏側の無人巡回ロジックの実在・本日の動作確認のため、"
        "スクショではなく実行結果の件数とHTTPコードで裏取りした",
    "--print-url",
]

if __name__ == "__main__":
    res = subprocess.run(ARGS, cwd="/Users/mac/tamago/tamago-shinchoku")
    sys.exit(res.returncode)
