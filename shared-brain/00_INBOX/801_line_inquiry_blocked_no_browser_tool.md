# 801番：LINE2窓口への問い合わせ送信＋見張り — 未着手（ツール制約で実行不可）

## 状況
- このタスクは「ごきげん補給所（joy-relief-station）」リポジトリのworktree上で動く`tamago-orchestrator`（卵商店街の総合店長ペルソナ）セッションに投入された。
- 本セッションのツールは `Agent`（`tamago-builder`/`tamago-memory`/`tamago-verifier`/`tamago-release`の4種のみ・いずれもブラウザ操作不可）、`Read`、`Bash`、`Write`、`Edit`のみ。
- **ブラウザ操作ツール（claude-in-chrome系MCP）が無い。** LINE Creators Market・LINEスタンプメーカーの問い合わせフォームは、本文欄がカテゴリ選択完了までreadonlyになるJS駆動UI（791番が実測済み）で、curlでの静的送信は再現不可能（フォーム送信を試すと不完全送信の事故リスクがあるため実行しなかった）。
- Gmail見張り（eggypop2010@gmail.comの受信確認）もメールAPI/IMAPアクセス手段が無く実行不可。
- `kitty-chan-hisho` skillはこのMac環境内を検索したが見当たらなかった（`/Users/mac/Desktop/tamago-shinchoku`配下・`~/Library/Application Support/Claude`配下とも未発見）。

## 確認済みの手持ち材料（次の担当がそのまま使える）
- 送信文面は確定済み・変更不要：`status/791_email_draft.md`
- 確認ページ（文面の一次ソース）：https://tamago2022.github.io/tamago-shinchoku/share/check/791-line-inquiry-draft.html
- 送信先：
  - LINE Creators Market：https://contact.line.me/serviceId/10569
  - LINEスタンプメーカー：https://contact-cc.line.me/detailId/11844
- 送信者情報：お名前=miketamawae／メール=eggypop2010@gmail.com／カテゴリ=規約・利用について

## 次の担当への申し送り
**ブラウザ操作ツール（claude-in-chrome MCP等）を持つセッションで、上記文面をそのまま2窓口へ送信し、送信完了画面のスクショを確認ページへ貼って報告してください。** カテゴリ選択→本文入力の順番厳守、送信前に全欄をスクショ確認（メールアドレス欄の文字混入事故が過去にあり）。

記録：2026-09-15、tamago-orchestrator（joy-relief-stationセッション）が試したが、リポジトリ・ツール構成のミスマッチで着手不能と判断し引き継ぎ。

## 2026-09-17 追記（訂正）：claude-in-chrome MCPが無くても実行できた

上の「ブラウザ操作ツールが無い」という判断は不正確だった。`tools/_791_fill_form*.mjs`が既に
`~/.tamago/node_modules/playwright-core` + ローカルのGoogle Chromeバイナリをheadlessで起動する
自前のブラウザ自動操作手段で、これは`Bash`ツールだけで`node ほにゃらら.mjs`と実行するだけで動く
（claude-in-chrome MCPは不要）。実際に今回、次を実測した：

- カテゴリ・詳細・追加アンケート（1〜5の質問）まで含めた全項目の自動入力に成功（本文・メール欄とも混入なし）。
- 送信ボタンを実際にクリックしたところ、**reCAPTCHAが「不審なアクティビティが検出されました」でブロック。**
- これが唯一の壁。電話番号欄は空欄のままでも先へ進めた（従来の「電話番号必須」認識は誤りだった）。
- reCAPTCHA突破を試みる行為はしない（今回の問い合わせ内容＝AI自動操作の可否確認、と自己矛盾するため）。

**結論・見張りの状態を含めた最新版は確認ページ本体に反映済み：**
https://tamago2022.github.io/tamago-shinchoku/share/check/791-line-inquiry-draft.html

Gmail見張り（`tools/check_line_reply.py`）も実装済み・`tools/heartbeat.sh`に組み込み済みだが、
`~/.tamago/gmail_app_password`（Gmailアプリパスワード）が未設置のため`blocked: no_credential`で停止中。
これは秘密情報のためAI側では書けない。たまごさん本人がそのファイルにパスワードを1行書けば動き出す。
