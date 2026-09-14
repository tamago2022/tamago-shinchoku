# ChatGPT／Grokに1回だけ貼る短文（案件828）

たまごさんが1回だけコピペして設定すれば、以後は毎回自動で効く想定の短文です。

## ChatGPTへ（Project instructions／Custom instructionsに貼る）

```
あなたは「たまごさん」の卵商店街プロジェクトの担当AIです。
会話を始める前に、必ずブラウジング機能で次のURLの中身を取得し、その内容を踏まえて答えてください。
https://tamago2022.github.io/tamago-shinchoku/status/NOW.md

このページには今週の目標・今動いているもの・直近の決定・直近の事故と対策が書かれています。
これを読まずに「前の会話は分かりません」「知りません」と答えないでください。
作業ルールの詳細は https://tamago2022.github.io/tamago-shinchoku/status/ai-company-loop.md も参照してください。
```

## Grokへ（Custom instructionsに貼る）

```
あなたは「たまごさん」の卵商店街プロジェクトの担当AIです。
会話の最初に、必ずWeb閲覧/検索機能で次のURLの中身を取得してから答えてください。
https://tamago2022.github.io/tamago-shinchoku/status/NOW.md

ここに今週の目標・今動いているもの・直近の決定・直近の事故が書かれています。
読まずに「分かりません」「知りません」と答えないでください。
```

## 技術メモ（自分で決めた設計理由）

- MCP／A2Aは、開発者がエージェント基盤を組む時の規格で、ChatGPT/Grokの一般ユーザー向けチャット画面からは直接つなげない（企業向けConnectors等が別途必要）。今回の「たまごさんが個人のChatGPT/Grok画面で使う」用途には向かないため見送った。
- 一番壊れにくいのは「1つのURLを毎回読ませる」方式。実装済みのgit管理Markdown（NOW.md）は差分監査ができ、人間にも読める。
- URLはtamago-shinchoku（public・GitHub Pages）側に統一。joy-relief-station側は非公開のため、ChatGPT/Grokの一般アカウントからは直接読めない可能性が高い。
- ChatGPTはブラウジングツールが有効なら明示指示で毎回fetchできる。Grokは標準でLive Search機能を持つため、Custom instructionsの指示だけで実際にURLを開きにいく可能性が高い（未実機検証）。

## Grokへの接続実験（案件828・追加分）

案件826時点の記録（`status/renkei.json`の`grokExperiment`）を踏襲し、828番で追加確認した内容：

- 試した経路1: xAI API経由でGrokに読ませてこちらが代筆する → 両リポジトリの`.env`にXAI_API_KEYが無いことを確認済み（値は見ず、存在確認のみ）。不可。
- 試した経路2: 本セッションから外部ドキュメント（platform.openai.com等）をcurlで直接確認する → 権限ブロックで実行不可（自動モードのclassifierに拒否された）。よってMCP/A2Aの採用状況は既知の学習データに基づく記述であり、本セッションでのライブ検証はできていない。
- 試した経路3: Grok本人のブラウザ操作でCustom instructionsへ短文を設定する → たまごさん個人のXアカウントへのログインが必要な操作のため、AI側で代行できない（本人操作が必須の人間ゲート）。
- 結論: 「偽装で代筆する」「勝手にログインする」はしない。今回の到達点は、たまごさんが1回貼るだけで済む短文をここに用意するところまで。貼った後、実際にGrokが読めているかは次回たまごさんが「今週の合言葉は？」と聞くテスト（`ai-brain/company-os/aikotoba.md`）で判定できる。
