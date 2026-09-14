# NOW（全AI共通・会話の最初にこれだけ読む・案件828）

更新: 2026-09-14 Claude（828番）

## 今週の大目標
Claude・ChatGPT・Grokが「話しかけたらもう知ってる」状態を作る。店主の手橋渡し回数をゼロに。

## 今動いているもの
- Claude: 828番新設／仕入れ継続（700番台）／762番Obsidian整理
- ChatGPT: company-os執筆（8/31〜9/7）。直近1週間停滞、再開待ち
- Grok: 未接続。xAI鍵なし、設計上もadapter未実装

## 直近の決定（5件）
1. `TAMAGO_COMMON_BRAIN.md`を記憶／判断／実行の共通入口に採用
2. Executorはモデル名直書き禁止、`EXECUTOR_REGISTRY.json`のcapabilityで選ぶ
3. Lovable公開はAI側がデフォルト自動完走、店主に押させない
4. queue.jsonは差分マージ書込み・件数減少拒否へ一本化
5. fal費用は実測／推定／不明ラベル必須、単価は直近7日実測中央値

## 直近の事故と対策（5件）
1. queue.json全消し（271→0）→ 件数急減の書込みを拒否
2. queue.json28件消失→ 差分マージ書込みへ変更
3. 走行中タスクを5回列へ戻し二重課金$55→ 差戻し禁止ガード未実装、対応中
4. 検品がボタン無反応でもPASS判定→ 実クリック検品を導入
5. 渡した確認URLが404化→ リンクを消さない運用徹底、原因調査中

## 各チーム最終更新
Claude 2026-09-14／ChatGPT 2026-09-07／Grok 未接続

## 追記ルール
上書き禁止・末尾へ追記のみ。「日付 AI名: やったこと」

## 変更ログ
- 2026-09-14 Claude（828番）: 新設（joy-relief-station側と同一内容、こちらがpublic URL）

詳細: `TAMAGO_COMMON_BRAIN.md`（非公開）／貼付短文: `AI_ENTRY_PROMPTS.md`
