## 外部検品ゲート（926番・2026-09-17）— 未検品のものをたまごさんへ返さない

たまごさんの言葉（そのまま）：
「Claudeが作ったものを、未検品のまま、たまごさんへ返さない、を仕組みにする。」
「外部検品AIを『意見をくれる顧問』にせず、**品質ゲート**にする。」

**変更前：Claude「できました」→ たまごさん**
**変更後：Claude「できました」→ ChatGPT「ダメ、ここ違う」→ Claude修正 → ChatGPT PASS → たまごさん**

### 号番号＝`status/queue.json` の `n`。最後まで変えない。

依頼→解釈→実装→テスト→外部検品→修正→再検品→最終提出まで同じ番号。新しい台帳を作らない。

### 必ずやる3つ

**① 依頼を受けたら、まず原文をそのまま保存する（要約して条件を消さない）**
```
python3 tools/kenpin_gate.py --n <号番号> \
    --set-original-text-file <原文.md> --set-interpretation-file <解釈.md>
```
例：「カメラ絶対動かすな。固定」→ `camera locked / static camera / no pan / no tilt / no zoom` へ
具体化してよいが、**「固定」という条件そのものを落とさない。**

**② お金が出る生成は、生成する前に出す（実装前ゲート）**
```
python3 tools/kenpin_gate.py --n <号番号> --submit --kind pre \
    --body-file <実行プロンプト.md> --cost "3本 × 50円 = 合計150円"
```
`--cost` は必須。外部AIには「元依頼と実行プロンプトが一致しているか」だけを厳密に見させる。

**③ 報告する前に出す（実装後ゲート）**
```
python3 tools/kenpin_gate.py --n <号番号> --submit --kind post --body-file <報告文.md> --url <本番URL>
python3 tools/kenpin_gate.py --n <号番号> --can-deliver   # 揃っていなければ非ゼロで落ちる
```

### 「直させる」が来ても、たまごさんへ戻さない

FIXのときこの道具は**たまごさんへ通知を出さない**。自分で直して**同じ号番号で再提出**する。
たまごさんに通知が飛ぶのは (a) PASSしたとき (b) 同じ号番号でFIXが3回続いたとき（＝堂々巡り）だけ。
(b) のときだけ `【<号番号>号・判断1点だけ】A：… / B：… どちら？` の形で1点だけ聞く。長い経緯説明は禁止。

### 提出してよい条件（9章）

**Claude自己検品PASS ＋ 外部検品PASS ＋ 実機能テストPASS** の3つ全部。
自己検品と実機能テストは実行したら記録する：
```
python3 tools/kenpin_gate.py --n <号番号> --mark-self-check   --note "..."
python3 tools/kenpin_gate.py --n <号番号> --mark-function-test --note "..."
```
「確認しました」「直っています」に証拠能力は無い。実URL・スクショ・ログ・テスト結果・
実測値・APIレスポンス・ブラウザ動作結果で確かめてから記録する。

最終報告は `【<号番号>号】完了` ＋ URL。説明・謝罪・苦労話・原因分析は書かない。

### 投げるのは自分でやらなくてよい

`--submit` は依頼票を `status/kenpin/pending/` に置くだけ。
5分おきの便（`tools/machine_status_push.sh`）が自動でChatGPT(OpenAI API)へ投げ、
判定を号番号へ書き戻す。急ぐときだけ `python3 tools/kenpin_gate.py --run-pending`。

### queue.json へ直接書かない

この道具を通さずに `status/queue.json` を書き換えない。過去に3回、台帳の項目が丸ごと
消える事故が起きている（案件#687ほか）。`kenpin_gate.py` の変更は `status/kenpin/ops/` に
置かれ、**ホスト上で走る `--run-pending` だけ**が1回の鍵つき書き込みでまとめて反映する。
