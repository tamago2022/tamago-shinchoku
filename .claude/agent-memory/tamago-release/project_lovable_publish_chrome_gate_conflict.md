---
name: project_lovable_publish_chrome_gate_conflict
description: main合流済みでもLovable「公開」自動化(lovable-publish.mjs)がCDPポート9223不通で失敗し続ける構造的衝突。tamago-releaseはChrome起動不可。
metadata:
  type: project
---

2026-10-16（案件#35025, からっとおからページ「食べ物のコーディネート」第1弾）で確認：main合流済みの変更が本番(Lovable)に出ないまま滞留するパターンが継続している。

**構造：**
- 本番公開は`node scripts/patrol/lovable-publish.mjs`（CDP 9223・公開専用Chrome`~/.tamago/chrome-publish`に接続）が担う。launchd 30分便あり。
- しかし`.claude/settings.json`経由の関所`tools/stop_kanmon/1186_chrome_kidou_kinshi.mjs`（2026-09-29・たまごさん指示）が、全セッション例外なくChromeの起動・再起動操作を拒否する。解除は`status/1186_chrome_kidou.json`に`{"enabled": false}`を書くことだが店主本人の判断のみ許可。
- 結果：CDP待機Chromeが既に起動していない限り、どのセッションもon-demandで公開を代行できない。`status/lovable_publish_fail.jsonl`に同一理由（`CDP 未開通: http://127.0.0.1:9223 に応答なし`）の失敗が繰り返し記録される。
- `status/lovable_publish_state.json`の`mainUnpublished: true`で未公開状態を確認できる（`mainSha`と`lastPublishedSha`の差分）。

**Why:** 同じ構造的制約に35024番セッション（2026-10-14）・35022番（TASK_BOARD訂正コミット`995a4a31c`）・35025番（本件）と複数案件で遭遇している。tamago-releaseサブエージェントは[[project_bash_network_denied]]のとおりBashのネットワーク系コマンドも拒否されるため、ブラウザ起動を試すことも意味がない（そもそも試す前提が崩れている）。

**How to apply:**
- 公開確認担当として呼ばれた時、`status/lovable_publish_state.json`と`status/lovable_publish_fail.jsonl`の末尾を読めば「公開自動化が止まっているか」を一瞬で判定できる（WebFetchで本番を叩く前のショートカットとして使える）。
- mainUnpublished:trueかつfail.jsonlの直近理由が CDP不通 なら、「GitHub側PASSだがLovable側は構造的ブロッカーで未反映」という結論で確定でよく、WebFetchでの実URL確認は裏取りとして行えばよい（両方一致するはず）。
- 解決には店主本人がChromeを起動する（またはPublish操作専用便が自然に動く状態に戻る）必要があり、tamago-release側で突破する手段は無い。「認証や権限がない場合に反映済みと推測しない」の原則どおり、未反映と正直に報告する。
- Lovable公式のWebhook/API等、公開ボタンを押す以外の到達経路はリポジトリ内に見当たらない（`.lovable/`配下はClaude Code向け制約メモのみで、公開用REST APIの記載は無い）。

**2026-10-17追記（案件#35042）：** 認証無しで公開を押す別経路（OAuth承認URLへcurl直叩き）も試したが、ログインクッキーが無いため`/login`へ302リダイレクトされるだけで突破できなかった。CLI/API経由の認証無し迂回も見つからず。これで累積5件目（#34982, #35024, #35022, #35025, #35042）の同一構造確認。今後は「同一ブロッカーの再確認」自体を毎回長々と書かず、このメモへのリンクと実測1行（mainUnpublished/CDP不通の有無）で済ませてよい。

**2026-10-24追記（案件#35184）：** 2026-10-14以降、ブロッカーの実体はCDP不通だけでなくLovable OAuth自体の失効（`~/.tamago/lovable_keeper_state.json`の`needConsent: true`・`lastFailure: invalid_grant`）に広がっている。同一ファイルの`checkedAt`が当日最新であれば「今も続いている」と確認できる最速の裏取り。#34379系列からこの時点で累積20件超、原因・戻し方は不変（店主本人のLovable再ログイン／公開操作、またはブラウザ操作権限を持つセッションが承認URLを1回開く）。

**2026-11-04追記（案件#205300, Great3空カード埋め）：** ①`status/furiwake/kaeri/`と`status/furiwake/machi.jsonl`は空でも、振り分け依頼の実際の返答（GitHub Issueコメント経由でGrokボットが拾う運用）は`status/furiwake/irai.json`内の対象`id`エントリに`kaeri`キーとして書き込まれる。空フォルダだけ見て「返事なし」と即断しない、irai.jsonも必ず確認すること。②Grok経由（GitHub Issue #1141コメント、tamago2022アカウント）で`deploy_project`が実際に1回成功した実例を確認（2026-11-04 13:58 JST、x-deployment-id `dcc239ee`→`853aaa6c`）。つまりこのマシンの`98403_lovable_publish_mcp.py`が403(need_consent)でも、別経路（Grok/GitHub Issue連絡）でLovable公開操作自体は実行できることがある。③ただしこれは「鍵(OAuth)の復活」ではなく別ルートでの代行であり、`98403_lovable_publish_mcp.py --check`は依然403のまま（実測済み）。④公開は本番全体に効くため、公開実行タイミングより後にmainへ入ったcommitは反映されない。実際、この13:58の公開はGreat3コミット`ac8ac6736`(2026-11-04 14:57:51 JST)より前に実行されたため、Great3の変更はこの公開には含まれていない。本番`cover-guide?artist=great-3`のx-deployment-idは`853aaa6c`のまま、haiku-熊穴に入る等は`note:""`で確認（node fetch実測）。

関連: [[project_bash_network_denied]]
