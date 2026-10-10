#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""34853番・確認ページ作成。
前回提出(34850番)は、たまごさんのAI検品で「憲法条文矛盾確認で元の依頼と無関係、的外れ」と
差し戻された。今回は34853番の実際の依頼文（Managerの一つ手前に『詰まる→自己解決→横相談
→判断待ち』を位置付けてほしい）そのものに対応する確認ページを作り直す。

既存ツール tools/make_check_page.py をそのまま呼ぶだけ（新しい仕組みは作らない）。
"""
import subprocess
import sys

RAW_SWEEP_EVIDENCE = (
    "<pre style=\"white-space:pre-wrap;background:#efe9db;padding:10px;border-radius:8px;"
    "font-size:0.78rem;overflow-x:auto;\">"
    "$ node scripts/roles/role-sweep.mjs --json  （2026-10-10 18:36 JST 実行・joy-relief-station repo）\n"
    "manager.pending[0] = {\n"
    "  role: \"棚編集UI担当・認証担当\",\n"
    "  deliverable: \"本番DBの列欠けを直したので管理画面は復旧した\",\n"
    "  attempts: 0,  // 上限3回未満→まだ差し戻し中（エスカレーションには上げていない）\n"
    "  issues: [\"終了コード 1 で失敗 → check-db-schema.mjs / 合計: 欠け 4\"]\n"
    "}\n"
    "manager.escalate = []  // 今日時点で人へ上げた件数はゼロ\n"
    "peerHelp.open = 2  // 横相談カード2件が実稼働\n"
    "  例: task:\"petit-story-ssr-019\" need:\"つなげる担当\"\n"
    "      tried:[\"本番HTMLをcurlで直接取得して4語で検索\",\"トップと曲ページを比較\"]\n"
    "      → 自己解決を試した跡(tried)が無いと横相談カード自体が成立しない設計\n"
    "</pre>"
)

WHAT = (
    "34853番の依頼文（2026-08-08 07:09）：「今のManager(全担当チェックの差し戻しロジック)の"
    "一つ手前の選択肢として位置付けてください：詰まる→自己解決を試す→ダメなら横の担当に"
    "振れないか確認→それでもダメなら判断待ちとして記録、の順番です。」<br><br>"
    "前回提出(34850番)は無関係な「憲法条文矛盾確認」ページを貼ってしまい、たまごさんのAI検品で"
    "的外れとして差し戻された。今回はこの依頼そのものを調べ直した。<br><br>"
    "結果：この依頼は<b>同日2026-08-08 07:14（5分後）に実装済み</b>だった。"
    "正本は<code>.claude/skills/loop-engineering/SKILL.md</code>の"
    "「もう1層：横相談（Peer Help）を Manager の手前に置く」節で、文面はほぼ依頼のまま"
    "<code>詰まる → ①自己解決を2〜3手 → ②横相談（隣の担当へ） → ③人へエスカレーション</code>"
    "という順番が明記されている。実コードは<code>scripts/roles/role-sweep.mjs</code>の"
    "<code>runPeerHelp()</code>（横相談＝依頼の「横の担当に振れないか確認」）と"
    "<code>runManager()</code>（差し戻し／エスカレーション＝依頼の「それでもダメなら判断待ち」）"
    "の2関数で、横相談はManagerより前に評価され、助けを求められている担当は"
    "自分の残件より先にスコアで前へ出る実装になっている（＝「一つ手前」の位置付けが構造的に"
    "コードへ反映されている）。<br><br>"
    "なお同じ2026-08-08 07:09の発言は、判定日システム側で34851番としても別枠に積まれており、"
    "そちらは本日2026-10-10 17:28に台帳側で「実装済み」へ訂正済み。34853番は34851番と同じ事実の"
    "別チケットであり、今回あらためて本日時点のライブ実行で裏取りした。<br><br>" + RAW_SWEEP_EVIDENCE
)

ARGS = [
    sys.executable, "tools/make_check_page.py",
    "--n", "34853",
    "--slug", "manager-mae-jiko-kaiketsu",
    "--title",
        "判定日赤34853番：Managerの一つ手前「詰まる→自己解決→横相談→判断待ち」は実装済み・"
        "本日ライブ実行で再確認（前回34850の的外れページを差し替え）",
    "--what", WHAT,
    "--num", "5分|依頼(2026-08-08 07:09)から実装(07:14)までの時間",
    "--num", "2件|本日2026-10-10に実行して実測した横相談(Peer Help)カードの件数",
    "--num", "0件|本日時点でManagerが人へエスカレーションした件数(上限3回未満のため差し戻し中が1件)",
    "--link",
        "本番の案内所ページ（担当別の次の一手・たまごさんが直接開ける）"
        "|https://joy-relief-station.lovable.app/admin/role-status",
    "--link",
        "同じ事実を別チケット(34851番)として確認した本物の確認ページ"
        "|https://tamago2022.github.io/tamago-shinchoku/share/check/34851-peer-help-layer.html",
    "--link",
        "確認ページを作る仕組み自体（公開リポジトリ・たまごさんも開ける）"
        "|https://github.com/tamago2022/tamago-shinchoku/blob/main/tools/make_check_page.py",
    "--table",
        "依頼文の順番「詰まる→自己解決→横相談→判断待ち」がSKILL.mdの設計文言に明記されているか"
        "|.claude/skills/loop-engineering/SKILL.md 内「詰まる → ①自己解決を2〜3手 → ②横相談"
        "（隣の担当へ） → ③人へエスカレーション」の1行を本日確認"
        "|yes",
    "--table",
        "横相談(runPeerHelp)が実コードとして存在し、Managerより手前の扱いで本日実行できたか"
        "|role-sweep.mjs本日実行→peerHelp.open=2件、助けを求められた担当はスコア+35以上で"
        "自分の残件より前に出る実装を確認"
        "|yes",
    "--table",
        "Managerの差し戻し/エスカレーションが依頼の「それでもダメなら判断待ち」に対応しているか"
        "|runManager()本日実行→pending(差し戻し)1件・escalate(人へ上げる＝判断待ち化)0件を実測"
        "|yes",
    "--table",
        "前回提出(34850番)のページが今回の依頼と無関係だった件への対応"
        "|34850番の「憲法条文矛盾確認」ページはそのまま残し、本件は新規ページ(34853番)として"
        "作り直した（既存資産は消さない）"
        "|yes",
    "--allow-no-screenshot",
        "見た目の変更ではなく裏側の無人巡回ロジック(Builder/Judge/Manager+横相談)の実装確認"
        "のため、スクショの代わりに本日の実行結果(生データ)を貼った",
    "--print-url",
]

if __name__ == "__main__":
    res = subprocess.run(ARGS, cwd="/Users/mac/tamago/tamago-shinchoku")
    sys.exit(res.returncode)
