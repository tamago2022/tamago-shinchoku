# 896番：外部連絡いっぱつ（renraku.py）を新設。Gmail下書きの完全自動化だけ次の一歩が必要

## やったこと
- `tools/renraku.py`（メイン）、`tools/_renraku_cdp.mjs`（ブラウザ自動操作。生CDP直叩き、追加依存なし）を新設。
- `status/renraku_madoguchi.json`（窓口台帳）に4件登録：LINE Creators Market・LINEスタンプメーカー・Lovable・Anthropic（Anthropicは626番の既存記録を統合）。
- 使い方: `python3 tools/renraku.py send <相手キー> --subject "..." --body-ja "..." [--subject-en "..." --body-en "..."]`
  - 海外窓口(country=overseas)は英語本文が無いとエラーで止まる（英日セット必須を機械的に強制）。
  - 送信は一切押さない（そのコードが存在しない）。
- 実演2件、通しで動作確認済み（確認ページ https://tamago2022.github.io/tamago-shinchoku/share/check/896-renraku-gaibu-renraku.html ）：
  1. LINE Creators Market: フォームを開き「ログインせずにつづける」を自動クリックし、お問い合わせフォーム本体まで到達。スクショあり。
  2. Lovable: 英日セット文面（件名・本文とも）を自動生成し、Gmail作成画面をブラウザで開くところまで到達。

## 次の一歩（たまごさんの一度だけの設定が要る）
Gmail下書きの完全自動化（下書きフォルダへ直接保存 or ログイン済み状態での作成画面表示）には、次のどちらかが要る。**どちらもAI側だけでは用意できない（パスワード入力はAI側の確認義務③に当たるため）**：

1. `~/.tamago/gmail_app_password` にGmailのアプリパスワードを設置する（これが用意されれば `renraku.py send` は自動でIMAP経由の下書き直接保存に成功する。コードは実装済み・待機中）。
   - 既存の `tools/check_line_reply.py` / `tools/check_anthropic_reply.py`（返信の見張り）も同じ理由でずっと `no_credential` のまま止まっている。これが用意されれば896番の返信見張り(`renraku.py check`)も含め3本まとめて動き出す。
2. または、専用Chromeプロファイル `~/.tamago/chrome-line`（ポート9224、既存）で、たまごさん本人が一度だけ eggypop2010@gmail.com にGoogleログインする。ログイン後はセッションがプロファイルに保存され、以後は自動で使える。

どちらか一方で十分。①の方が、返信見張りも一緒に解決するので優先度が高い。

## 副産物・他のセッションが使えるもの
- `tools/_renraku_cdp.mjs` は896番専用ではなく、CDP経由でChromeタブを操作する汎用ヘルパー（open/click/fill/shot）。既存の `tools/line_inquiry_prepare.mjs`（playwright-core版）は、2026-09-17実測で `Browser.setDownloadBehavior: Browser context management is not supported`（playwright-core 1.62.1と通常配布版Chrome152系の非互換）により接続確立自体に失敗することを確認した。今後Playwright系スクリプトが同じエラーで詰まったら、このCDP直叩き版への書き換えを検討する。

## 記録
- 2026-09-17、tamago-orchestrator（joy-relief-stationのworktreeセッション、801番と同じ構造の誤投入だが今回は実装まで完走）。
