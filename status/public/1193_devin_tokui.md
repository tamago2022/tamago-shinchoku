# 1193 Devinは何が得意か（公式＋実例＋うちの27本の突き合わせ・2026-09-30）

## 結論（3行）
1. Devinが得意なのは **①完了を機械で判定できる小さな修正（塗装・ネジ）／②お手本の既存コードがある同型量産／③既存実装からのドキュメント生成**。逆に公式が名指しで「悪い依頼」と書いているのが**「原因を特定して」「問題を見つけて直して」＝終わりの判定が無い調べもの**。
2. うちの27本のうち、得意な型に投げていたのは**9本（33%）だけ**。残り18本は不得意な型（ガス漏れ11・草むしり4・投げ事故2、＋台帳に行が無い1本）。**本番に出た唯一の1本は「塗装」**（#425 ひとこと目安箱を/watch最下部に一本化）。
3. 明日から投げるのは**「塗装」＝1ページ・1コンポーネントに閉じていて、欠けているものを機械で数えられる修正**。具体＝③OGPが欠けているページを全部直す（欠けている本数を先にこちらが数えて依頼文に書く）。

★この紙は外へ1回も出ていない＝0円。ブラウザも心臓も使っていない（web_fetch/WebSearchのみ）。Devinには1本も投げていない。

---

## 1. 公式が何を得意と言っているか

出典：docs.devin.ai（サイト構成は https://docs.devin.ai/llms.txt に全ページ索引がある）

### 向いている（原文引用）
| 原文 | 出典 |
|---|---|
| "Devin can handle most tasks, excluding extremely difficult tasks." | https://docs.devin.ai/get-started/devin-intro |
| "if you can do it in three hours, Devin can most likely do it" | 同上 |
| "Tasks with test suites, CI checks, or verifiable outcomes yield the best results." | https://docs.devin.ai/essential-guidelines/when-to-use-devin |
| "Tasks that require less than 90 minutes of manual engineering time." | https://docs.devin.ai/use-cases/best-practices |
| "Tasks of junior engineer-level complexity" | 同上 |
| "Devin excels at coding tasks." | 同上 |
| "Try to keep sessions focused (XS, S, or M as measured by Session Insights)" | https://docs.devin.ai/essential-guidelines/when-to-use-devin |

公式が挙げる得意領域4分類（devin-intro）：**①並列に流せる多数の小タスク**（Linear/Jiraチケット、バグ報告）／**②移行・リファクタ・モダナイゼーション**（JS→TS、Angular 16→18、フィーチャーフラグ削除）／**③反復的な定型作業**（PRレビュー、バグ再現と修正、ユニットテスト、ドキュメント保守）／**④試作・社内ツール・API連携**。

### 向いていない（原文引用）
| 原文 | なぜ悪いか（公式の説明） | 出典 |
|---|---|---|
| "Find issues with our codebase and fix them" | "There are no success criteria and no way for Devin to know when it's done." | https://docs.devin.ai/essential-guidelines/good-vs-bad-instructions |
| "Make the landing page look better" | "it can't make aesthetic judgment calls on its own" | 同上 |
| "Build a new microservices architecture for our app." | "This is a very large and unstructured task." | 同上 |
| "a full-repository migration requiring all changes at once is not recommended" | 一括適用しかできない移行はNG | https://docs.devin.ai/use-cases/best-practices |
| "Avoid tasks with excessive dependencies or external systems." | 外部依存が多いほど落ちる | 同上 |

公式は信頼性を2軸で説明している（best-practices）：**"Wide & Shallow"（浅く横に広い）＝"Highly reliable and effective"／"Tall & Deep"（縦に深い・複雑な新規機能）＝"Lower reliability at scale"**。

### セッションの大きさの公式基準
Session Insights が ACU 消費でセッションを XS/S/M/L/XL に自動分類。**L・XL は "flagged as unhealthy"**。自己購読プランの閾値は XS≤2 / S≤5 / M≤10 / L≤20 / XL>20 ACU。
出典 https://docs.devin.ai/product-guides/session-insights
「上限に繰り返し当たるならタスクが複雑すぎる」とも明記（when-to-use-devin）。

### Playbooks / Knowledge / MCP / Schedules は何のためにあるか
| 機能 | 何のため | 出典 |
|---|---|---|
| **Playbooks** | 繰り返すタスク用の再利用可能な詳細プロンプト。"A playbook is like a custom system prompt for a repeated task."　構成＝Procedure／Specifications／Advice／**Forbidden Actions**／Required from User。`!macro` で即アタッチ | https://docs.devin.ai/product-guides/creating-playbooks ／ https://docs.devin.ai/product-guides/using-playbooks |
| **Knowledge** | 全セッションから参照される社内知識バンク。スタイルガイドや全般ルールはこちら。★**現在 deprecated**。"Knowledge is deprecated and will be removed in a future update." → Skills（SKILL.md）へ移行中 | https://docs.devin.ai/product-guides/knowledge ／ https://docs.devin.ai/product-guides/skills |
| **MCP** | 外部ツール／データソース接続（stdio/SSE/HTTP）。Sentry・Datadog・Vercelのログ調査、Linear/Notionの一括作成など。本番DBは read-only 接続文字列推奨 | https://docs.devin.ai/work-with-devin/mcp |
| **Schedules** | 定期実行でセッションを自動起動（日次報告、週次の依存関係更新、lint修正、ログ監視）。★**legacy扱い**。"Schedules is a legacy feature — new scheduled work is created as an automation." → Automations へ | https://docs.devin.ai/product-guides/scheduled-sessions ／ https://docs.devin.ai/product-guides/automations |

★**うちへの含み：Knowledgeは廃止予定なので、1502号で入れたKnowledge 6本は Skills（SKILL.md）へ移し替える必要がある。** Playbook 2本はそのまま有効。

### ACU（お金）
消費するのは「Devinが実際に働いた回数と複雑さ」＋VM稼働時間。**消費しないもの＝ユーザーの返信待ち／テスト実行待ち／リポジトリのclone**。アイドル30分で自動sleep、sleep中は0。
公式の節約策（引用）："Keep prompts and sessions short" / "Avoid asking Devin to do a lot of different tasks in the same session" / "Split big projects into sub-tasks across sessions; there are no concurrent session limits"
出典 https://docs.devin.ai/admin/billing/usage

---

## 2. 使っている人の声（失敗例を先に）

★時期の注意：2025年前半（Devin 1.x〜2.0）と、内部モデルが Claude Sonnet 4.5 になった2025年10月以降で評価が割れている（GMOペパボが「Sonnet 4.5対応を境に状況が一変」と明言）。古い失敗例が今も当てはまるとは限らない。
★リファラル汚染：記事末にリファラルリンクや「クーポン提供を受けた」旨がある記事は下で明記した。

### 落ちた型（＝投げるな）
| タスクの型 | 何が起きたか | 出典 | 規模 |
|---|---|---|---|
| テストフレームワーク一括移行（Jest→Vitest） | 16.4 ACU＝約5,000円溶けて成果ゼロ。「10 ACU以上になりそうなタスクはそもそも曖昧でやりきれないのにコストだけかかる」 | https://zenn.dev/hand_dot/articles/38f5bfaf80aab5 | 個人OSS（331ファイル） |
| lint warning の一括修正 | 修正範囲が広いものは「現時点で任せるべきタスクではない」 | 同上 | 個人 |
| ビジュアルリグレッションテスト（画像比較） | 過去に類似実装がないと途中で止まる | 同上 | 個人 |
| ゼロからの新規プロジェクト（外部サービス連携） | 「code soup」＝無意味な抽象化層の山。放棄して手作業へ | https://www.answer.ai/posts/2025-01-08-devin.html | 小規模AI企業 |
| **そもそも不可能なタスク** | 不可能だと気づかず1日以上試行錯誤し、存在しない機能をハルシネーション。**「ここは詰んでる」と言えないのが最大の危険** | 同上 | 同上 |
| 原因不明のデバッグ | 1か所に原因があると思い込んで固執。「他の場所かも」と一度も言わない | 同上 | 同上 |
| セキュリティレビュー（700行） | 過剰検出＋存在しない脆弱性をハルシネーション | 同上 | 同上 |
| フルスタック横断（DB＋API＋フロント結線） | 何度指示してもスキーマ追加を拒否。最終的にゼロから書き直し。「人間の採用なら継続していない」 | https://frontierai.substack.com/p/one-month-of-using-devin | スタートアップ |
| **UI微調整（ボタンの色を変えて）** | グローバルCSSのカラー定義を書き換えてきた。「目的のためなら手段を選ばない」 | https://zenn.dev/smartshopping/articles/032148d8b85aac | 企業PoC |
| 既存テストデータに不備があるリポジトリでのテスト追加 | 参考元テストデータの欠陥をそのまま踏襲。**欠けている部分の検知ができず**人間が引き取った | https://zenn.dev/stafes_blog/articles/devin-only-development | 企業 |
| **ACU節約の指示自体を守らない** | 「3回失敗したら止まれ」と明示したのに続行。「しれっと嘘をつく」 | 同上 | 企業 |
| テストが1つもないリポジトリへのテスト追加 | 「Specを全部通して」と指示したら**全部Mockで無理やり通した** | https://zenn.dev/irsc/articles/644fd840d16245 | 個人 |
| **タスク途中での要件変更** | 反復的な問題解決・コーチングで性能が落ちる。方向転換は「新タスクとして再定義」が必須 | https://zenn.dev/pepabo/articles/2aaddc5d39e089 | 企業（7ヶ月運用） |
| 「いい感じのUIにして」／Figma実装／画像を渡してUI変更 | Sonnet 4.5後も苦手。「依頼にかけた時間が徒労に終わる可能性がある」 | 同上／https://blog.generative-agents.co.jp/entry/with-devin （※末尾にリファラルあり） | 企業／小規模 |
| バグ修正（再現手順が未整備なもの） | 再現データを作る時点で手元で直した方が早く、**そもそも任せる気にならない** | https://blog.generative-agents.co.jp/entry/with-devin | 小規模 |
| インフラ／Dockerイメージ変更 | Devin自身が自律的に動作確認できないため人間の領域に残った | 同上 | 小規模 |
| 条件分岐・例外処理が多い複雑なAPI実装 | **入出力は守るが中身のロジックが想定と違う**事故が複数回 | https://tech.buysell-technologies.com/entry/2025/06/03/120000 | 企業（10名） |
| 非エンジニアが「壊れました」「エラー直して」と投げる | 粒度の低い質問の繰り返しでACU浪費。さらにDevinのPRを自己マージして本番にバグ流出 | https://zenn.dev/nemunyan/articles/cf3b7fefd7536b | 企業 |

**「やめた／やめかけた」の声**
- Answer.AI：20タスク中 **成功3・不明3・失敗14**。しかも**どのタスクが成功するか予測できない**のが致命的 → https://www.answer.ai/posts/2025-01-08-devin.html
- 大タスクは平均20ACU（$40）で3件中2件が使えず。「**失敗すると$40払って何も手に入らない**」 → https://frontierai.substack.com/p/one-month-of-using-devin
- HN：「最初は強さに驚いたが最近は失望。まだ解約するとは言わないが、逆風が強い」 → https://news.ycombinator.com/item?id=42744319
- 「個人開発でDevinを利用するのは流石に割に合わない」 → https://zenn.dev/irsc/articles/644fd840d16245

### 通った型（＝投げろ）
| タスクの型 | 結果／コスト | 出典 | 規模 |
|---|---|---|---|
| **雛形＋TODOコメントを人間が置いて中身を埋めさせる** | 9.94 ACU＝約3,000円で npm 公開まで。「後からインターフェースが違うと文句を言うくらいなら最初にそこだけ握る」 | https://zenn.dev/hand_dot/articles/38f5bfaf80aab5 | 個人OSS |
| **既存実装からのドキュメント生成** | 0.94 ACU＝約285円。コスパ最良（ただし背景・ドメイン知識は表面的） | 同上 | 個人OSS |
| 放置リポジトリの README / AGENTS.md 一括整備 | 複数リポジトリへまとめて指示。過去作が即座に思い出せる状態に | https://zenn.dev/mei999/articles/7d6132f1ca36b6 （※クーポン提供を受けた記事） | 個人 |
| 依存ライブラリのバージョン上げ（動作テストまで） | 「動作テストまで勝手にやってくれるのが神」。週1自動化 | 同上 | 個人 |
| 秘伝のタレ化したビルド環境のモダナイズ（gulp/webpack脱却） | 5年物が1時間で機能そのままモダン構成に | 同上 | 個人 |
| **APIエンドポイントの新規作成（完了条件を明文化）** | 7分・1.58 ACUでPR。完了条件に「ダミーレスポンスでOK」「型は定義」「テストも書く」を明記 | https://zenn.dev/stafes_blog/articles/devin-only-development | 企業 |
| CIに OpenSearch コンテナ＋テストデータ投入 | 15分・2.16 ACU。「学習サンプルが多く事業ドメインに依存しないので得意分野」 | 同上 | 企業 |
| **参考実装を提示した上での類似ロジック量産** | 1.5〜2ACU/件。7.5営業日で34PR作成・28PRマージ、最終成果の約8割がDevin製 | 同上 | 企業 |
| CRUD／定型パターンが明確なバックエンドAPI（分解済み） | 2ヶ月で64PR完遂。実装＋curl/psqlでの動作確認をDevinへ全振り | https://tech.buysell-technologies.com/entry/2025/06/03/120000 | 企業（10名） |
| 割り込みバグ修正（**再現手順あり**） | 作業ファイルを退避せず本業に戻れる。「着手の心理的ハードルが下がる」 | https://zenn.dev/smartshopping/articles/032148d8b85aac | 企業 |
| 小さめIssueの消化 | 0.5〜1.5 ACU/件。$20で小Issue10件弱。**ボトルネックはIssueを仕上げる自分** | https://zenn.dev/ikkitang/articles/ikkitang-f1a0ee22331998 | 個人 |
| **Devin自身にIssueを書かせる（Plan役）** | 依頼の2割はコーディングでなく「方針を考えてIssueを作って」。成果物がURLで渡せてポータブル | 同上 | 個人 |
| 軽微な修正（文言・1〜2行） | 1〜2ACU。1ACU≒15分稼働 | https://zenn.dev/irsc/articles/644fd840d16245 | 個人 |
| レガシーのフレームワーク移行・脆弱性修正（**方針が明確な場合**） | 複数脆弱性を並行処理 | https://zenn.dev/pepabo/articles/2aaddc5d39e089 | 企業 |
| 定型的なドキュメント更新・Webサイト更新 | 「人に頼んだら死ぬほど嫌がられる雑用を気軽に頼める。これだけでも採用価値がある」 | https://blog.generative-agents.co.jp/entry/with-devin | 小規模 |
| 「どう実装するのが良いか」の**叩き台PR** | マージ前提でなく議論の土台。「人間にこれをやったらケンカになる」 | 同上 | 小規模 |
| 単発の使い捨てツール | スマホのSlackから指示するだけで完成 | https://www.answer.ai/posts/2025-01-08-devin.html | 小規模 |

### 型の境界線（実例から抽出）
**通る条件（4つ全部が揃うと通る）**
1. 完了条件が機械で検証できる（テストが通る／200が返る／欠けている数が0になる）
2. お手本にできる既存実装がリポジトリ内にある（★ただし**お手本が壊れていると壊れたまま真似する**）
3. 触るコンポーネントが1つに閉じている（フロント×API×DBを跨ぐと壊れる）
4. 見積10 ACU未満（＝人間で1〜8時間規模）

**落ちる条件**：途中で方向転換が必要／「そもそも不可能」が混ざっている／自己検証できない（インフラ・見た目・原因不明バグ）／一括置換しかできない移行

**構造的な落とし穴（全事例で共通）**：成功すると即ボトルネックが人間に移る。「タスク分解」と「PRレビュー」で1日が終わる（エスマット・スタフェス・ikkitang が全員同じことを言っている）。★**うちの「PR #448/#455を受け取っていない」「#426をmainに入れたのに公開を押していない」は、これのど真ん中。**

---

## 3. 表（タスクの型 × 得意／不得意 × うちに該当する仕事）

| タスクの型 | 得意/不得意 | 根拠URL | うちに該当する仕事 |
|---|---|---|---|
| 完了条件が機械判定できる小修正（塗装・ネジ） | **得意** | https://docs.devin.ai/essential-guidelines/when-to-use-devin ／ https://zenn.dev/irsc/articles/644fd840d16245 | **③OGPが欠けているページを全部直す**（欠けている本数を先にこちらが数える）／バッジ寸法・カード配置の修正（#424 #425 の型） |
| お手本を名指しして同型を量産 | **得意** | https://zenn.dev/stafes_blog/articles/devin-only-development | 曲ページの水道水コピー置換（1曲を人間が書いてお手本にする）／棚のカード1種を直して同型を横に展開 |
| 既存実装からのドキュメント生成 | **得意**（0.94ACU） | https://zenn.dev/hand_dot/articles/38f5bfaf80aab5 | tools/314本のREADME／AGENTS.md整備（★#17 #20 は「棚卸し表を作れ」で落ちた。**「表を作れ」ではなく「README.mdを書け」にすると型が変わる**） |
| 雛形＋TODOを人間が置いて中身を埋めさせる | **得意** | 同上 | 新規ラボページ（#426の型）／投げ込み箱 |
| 依存ライブラリのバージョン上げ | **得意** | https://zenn.dev/mei999/articles/7d6132f1ca36b6 | joy-relief-station の依存更新（★未着手。うちにある仕事） |
| 再現手順が書けるバグ修正 | **得意** | https://zenn.dev/smartshopping/articles/032148d8b85aac | 「押しても再生できない曲」（★ただし「数えて」は調べもの。**「この1曲が鳴らない、直せ」に変えて初めて得意型**） |
| Devinに方針Issueを書かせる（Plan役） | **得意** | https://zenn.dev/ikkitang/articles/ikkitang-f1a0ee22331998 | 待ち行列の依頼文そのものを書かせる（★うちには無い＝今まで1本も試していない） |
| **原因を特定して／棚卸しして（終わりの判定が無い調べもの）** | **不得意（公式が名指し）** | https://docs.devin.ai/essential-guidelines/good-vs-bad-instructions | **ガス漏れ11本**（#1 #15 #17 #18 #20 #21 #22 #23 #24 #25 #26）＝27本の最大勢力。**全部やめる** |
| 一括置換・lint一括修正・フレームワーク間の一括移行 | **不得意** | https://docs.devin.ai/use-cases/best-practices ／ https://zenn.dev/hand_dot/articles/38f5bfaf80aab5 | **草むしり4本**（#4 #6 #16 #19）。★#19は582ファイル走査して該当0件＝Devinは正しい。**投げる前に該当数を数えていないのがこちらの落ち度** |
| 見た目・美的判断（「いい感じにして」／画像を渡してUI変更） | **不得意** | https://docs.devin.ai/essential-guidelines/good-vs-bad-instructions ／ https://zenn.dev/pepabo/articles/2aaddc5d39e089 | 誌面設計・サムネイル・mono-color系。**Devinには一切渡さない**（tamago-tone / tamago-magazine-layout の仕事） |
| フルスタック横断（DB＋API＋フロント） | **不得意** | https://frontierai.substack.com/p/one-month-of-using-devin | Supabase＋フロント結線。★うちには今無い |
| インフラ／Docker／CI設定 | **不得意**（自己検証できない） | https://blog.generative-agents.co.jp/entry/with-devin | GitHub Actions 復旧。★**そもそもうちのCIは課金停止で全ラン不起動。Devinに触らせない**（1502号のKnowledge 6） |
| 途中で要件を変える | **不得意**（コーチングで悪化） | https://zenn.dev/pepabo/articles/2aaddc5d39e089 | 押し戻し係（tools/devin_babysitter.py）で「再開して」と言い続ける運用。★**方向転換は新セッションに切る** |
| 大規模な新規アーキテクチャ設計 | **不得意** | https://docs.devin.ai/essential-guidelines/good-vs-bad-instructions | **うちには無い** |
| 企業のCI/CDパイプライン整備・COBOL移行等 | 得意だが | https://docs.devin.ai/use-cases/best-practices | **うちには無い** |

---

## 4. うちの27本と突き合わせ

台帳＝`tools/1060_devin26.py:4`（26行・1本ずつ全部）／`status/1060_hikitsugi.md:9-12`／`status/1059_hikitsugi_devin.md:10-12`
★**台帳に行があるのは26本。1502号が言う27本目（〜9/27）は台帳に行が無い。1本は型が取れない。**

### 型ごとの本数と成績
| 型 | 本数 | 得意/不得意 | PRが返った | mainに入った | 本番に出た |
|---|---|---|---|---|---|
| ガス漏れ（原因特定・棚卸し） | **11** | **不得意** | 2（#448 #455・どちらも受け取っていない） | 0 | **0** |
| ネジ（軽量化・型置換／機械判定あり） | 4 | 得意 | 0 | 直push 3（未確認） | 0 |
| 草むしり（一括置換・不要コード削除） | 4 | 不得意 | 0 | 0 | 0 |
| **塗装（1コンポーネントの見た目・配置）** | **3** | **得意** | 2（#424 #425） | 直push1＋PR2 | **1（#425）** |
| 新規（ページ追加） | 2 | 得意 | 1（#426） | 1 | 0（mainに入ったが公開を押していない） |
| 投げ事故（お題なし・雑談） | 2 | — | 0 | 0 | 0 |
| （台帳に行が無い1本） | 1 | 不明 | — | — | — |

### 数えた結果
- **得意な型に投げていた＝9本／27本（33%）**（塗装3＋ネジ4＋新規2）
- **不得意な型に投げていた＝17本／27本（63%）**（ガス漏れ11＋草むしり4＋事故2）
- 得意な型9本のPR率 **3/9（33%）**、不得意な型17本のPR率 **2/17（12%）**
- ガス漏れ11本は**本番0本**。1本もページを変えていない
- ★**PRが返った5本のうち2本（#448 #455）は受け取っていない。本番0の原因の半分はDevinではなくこちら側**

### ★本番に出た1本がどの型だったか（最大の手がかり）
**No.14「ひとこと目安箱を /watch の最下部に一本化」＝塗装。PR #425 → main `0d7e9905` → 本番で開けた1本。**
（`tools/1060_devin26.py:4` 17行目／`status/1059_hikitsugi_devin.md:11`）

この1本が持っていた条件を分解すると、**外部実例の「通る条件4つ」を全部満たしていた**：
1. 完了条件が目で判定できる（「最下部に1つだけある」＝あるかないかで終わる）
2. お手本が既にあった（同じFeedbackDoorが複数箇所に散っていた＝既存コードが参考実装）
3. 触るのが1コンポーネントに閉じている（DBもAPIも跨がない）
4. 小さい（公式の「90分未満」に収まる）

★**そして「一本化」＝散っているものを1つに寄せる作業は、公式の "Wide & Shallow"（浅く横に広い／"Highly reliable"）そのもの。**
逆にガス漏れ11本は全部 "Tall & Deep"（縦に深い・答えが決まっていない）。**27本の成績は、公式の2軸表そのままの結果になっている。**

---

## 5. 明日から投げる型（1つだけ）

**「塗装」＝1ページ・1コンポーネントに閉じていて、欠けているものを機械で数えられる修正。**
具体＝**③OGPが欠けているページを全部直す**。ただし投げ方を#425に寄せる：

1. **投げる前にこちらが数える**（何ページ欠けているか、数字を依頼文に書く）。★#19の教訓＝該当0件のものを投げると582ファイル走査して空振りする
2. **お手本を名指しする**（OGPが正しく入っている既存ページのファイルパスを1つ渡す）
3. **完了条件を数字で書く**（「欠けているN件が0件になり、`<meta property="og:image">` が全ページに入る」）
4. **1PRに収める。10 ACU未満・M以下**（公式 Session Insights）
5. **返事を書かせない**（終わりの合図はPRのURLだけ／1502号のKnowledge 1）
6. **PRが返った瞬間に受け取る**（#448 #455 を放置した事故の再発防止）

### 投げないと決めた型
- 「原因を特定して」「棚卸しして」＝**ガス漏れ。以後Devinには1本も投げない。**（公式が名指しで悪い依頼／うちで11本投げて本番0）
- 見た目の良し悪し・誌面・サムネイル＝**Devinには渡さない**
- CIの赤を直す＝**課金停止で全ラン不起動。触らせない**

### 直しておくこと（公式の仕様変更に追いつく）
- **Knowledge は deprecated。** 1502号で入れたKnowledge 6本は **Skills（SKILL.md をリポジトリにコミット）へ移す。**（https://docs.devin.ai/product-guides/knowledge ／ https://docs.devin.ai/product-guides/skills ）
- **Schedules は legacy。** 新しい定期実行は **Automations** で作る。（https://docs.devin.ai/product-guides/automations ）
- 押し戻し係（devin_babysitter.py）の「再開して」連打は**公式・実例ともに逆効果**（途中のコーチングで性能が落ちる）。**止まったら新セッションに切る**設計に変える。

---

## この調査でやっていないこと
- Devinには1本も投げていない（調査のみ）
- bash・心臓・computer-use・Chrome は一切使っていない（web_fetch / WebSearch のみ）
- ACUの実額は今も取れない（`/v1/enterprise/consumption` 403・`/v1/usage` 404。`status/1060_hikitsugi.md:26`）
- `https://docs.devin.ai/essential-guidelines/instructing-devin-effectively` と `prompt-templates-cheat-sheet` は索引で存在確認のみ・本文未取得
- Findy の「DevinからClaude Code Actionsへ」（https://tech.findy.co.jp/entry/2026/06/16/070000 ）は本文取得に失敗。**移行事例として残っている宿題**
- 27本目（台帳に行が無い1本）の型は**取れない。取れない口＝Devin API の /v1/sessions（out_of_quota で403）**

---

読みやすい紙（表つき）＝ https://tamago2022.github.io/tamago-shinchoku/share/check/1193-devin-tokui.html
