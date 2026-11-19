# 【振り分け改善提案】発車待ち番号がjoy-relief-station(ごきげん補給所)側worktreeに誤投入される問題（3回目・896番で確認）

## 症状
「【自動発車】発車待ちの◯◯番です」形式の依頼が、本来 `/Users/mac/Desktop/tamago-shinchoku`（このリポジトリ）宛のはずが、
`/Users/mac/Documents/AI作業/.worktrees/q896-0904`（joy-relief-station＝ごきげん補給所のworktree、tamago-orchestrator）
のセッションへ投入される事故が繰り返し発生している。

- 801番（2026-09-15）
- 896番 1回目・2回目（2026-09-17）
- 896番 3回目（2026-09-17・本件）：queue.json を見ると、既に別セッション（sessionId `da6b9058-3de3-4128-90bb-b9b3e2e397cb`、startedAt 14:06:23、finishedAt 03:57:04）が
  このリポジトリ側で実装・確認ページ公開まで完了済み（`status: "running"`のままだが`result`欄に完了報告あり、
  確認ページ `https://tamago2022.github.io/tamago-shinchoku/share/check/896-renraku-gaibu-renraku-v2.html` はHTTP 200で内容も一致）。
  にもかかわらず、joy-relief-station側のtamago-orchestratorセッションへ**もう一度**同じ896番の指示が届いた。

## 想定原因（未確定・調査推奨）
- auto_launcher（またはCowork/Dispatch側の起動ロジック）が、queue.jsonの`status`フィールドが`"running"`のまま
  更新されていない案件を「まだ終わっていない」と誤認し、別のworktree/セッション種別へ再投入している可能性。
  （`finishedAt`はセットされているのに`status`が`"running"`のまま、という不整合を#896のqueue.jsonで実際に確認した）
- あるいは、案件の宛先リポジトリを判定する仕組みが無く、空いているセッション（joy-relief-station側のtamago-orchestrator）に
  無差別に流し込まれている可能性。

## 提案（機械での恒久対策・要検討）
1. **`status`と`finishedAt`の整合性チェック**：`finishedAt`が入っているのに`status`が`"running"`のままの項目を検出し、
   `status`を`"done"`（または適切な完了値）へ自動修正する軽い監査スクリプトを`tools/`に追加する。
   （直接`queue.json`を書き換えるのは危険なため、既存の`kenpin_gate.py`のような「ops経由の鍵つき書き込み」方式に合わせる）
2. **宛先リポジトリのタグ付け**：`queue.json`の各項目に、依頼文の語彙（`status/failures.md`／`tools/`／`share/check/`／
   `鬼監督`／`oni-kantoku`／`Sonnet固定`等）から判定した宛先リポジトリを`targetRepo`のようなフィールドで明示し、
   起動ロジック側がjoy-relief-station向けセッションへは投入しないようフィルタする。
3. 恒久対策が入るまでの当面の運用：joy-relief-station側のtamago-orchestratorは、依頼文に上記語彙が出てきたら
   まず`ls /Users/mac/Desktop/tamago-shinchoku`と`status/queue.json`の該当`n`を確認し、既に完了していれば
   再実装せず「既に完了・確認URLあり」として報告する（既にこのパターンはtamago-orchestrator側のメモリに
   `project_tamago_shinchoku_misrouted_tasks`として記録済み）。

## 影響
実害は今のところ「同じ作業を無駄に調べ直す時間」のみ（896番3回目は再実装せず確認だけで済ませた）。
ただし繰り返すとトークン消費・セッション枠の無駄になるため、①の整合性チェックだけでも早めの対応を推奨する。

記録者：tamago-orchestrator（joy-relief-stationセッション）2026-09-17

## 追記（896番 4回目・2026-09-17 14:3x台・tamago-orchestrator確認）

同じ896番がさらにjoy-relief-station側へ届いた。今回queue.jsonを確認すると：
- `status: "running"`、`startedAt: "2026-09-17T14:33:25+09:00"`、`sessionId: "f60adb35-..."` で、
  **このリポジトリ側の別セッションが既に着手・走行中**（sekishoFailCount 1件を受けての再修正中と推測）。
- したがって今回はjoy-relief-station側での再実装は行わず、着手せず終える（重複作業防止）。

この4回目の発生で、①②③（894番1〜2回目のGmail/LINE問題）とは別に、**「statusがrunningでも本当に動いているセッションがある場合と、finishedAt済みで放置されている場合の両方があり、joy-relief-station側からは区別がつかない」**という点が新たな課題として確認できた。`targetRepo`タグ付けなど恒久対策の優先度を上げることを推奨する。

## 追記（926番・2026-09-17 15:59台・tamago-orchestrator確認・5回目）

同じ誤投入が926番でも発生。`joy-relief-station`側worktree（`q926-0904`）へ「【自動発車】発車待ちの926番です」形式の依頼が届いた。

queue.jsonを確認すると、926番は：
- `status: "running"`、`state: "draft"`、`inspections: []`
- `sessionId: "248207f9-7b8b-4916-a542-f67b62c81ce7"`、`startedAt: "2026-09-17T15:55:58+09:00"`、`finishedAt: null`
- 確認した現在時刻は `15:59:11`（=着手からわずか3分後）。**tamago-shinchoku側で別セッションが今まさに着手・走行中**と判断できる。

したがって今回もjoy-relief-station側での再実装・重複作業は行わず、着手せず終える。tamago-orchestrator（joy-relief-stationセッション）が使えるsubagent（tamago-builder/verifier/release/memory）は「ごきげん補給所のコードとデータ」専用であり、そもそもtamago-shinchoku（別リポジトリ・別運用体系）の実装には使えない構造的なミスマッチも今回確認した。

**5回連続（801番, 896番×4回, 926番）の再発**により、①`status`と`finishedAt`の整合性チェック、②`targetRepo`タグ付けによる起動時フィルタ、のいずれかを本気で優先実装すべき段階に来ている。この提案自体は896番の時点で既に出ているが、まだ実装されていない。

記録者：tamago-orchestrator（joy-relief-stationセッション）2026-09-17 15:59

## 追記（874番・2026-09-17 17:00台・tamago-orchestrator確認・6回目・新しい症状パターン）

874番でも同じ誤投入が発生したが、今回は過去5回と少し違うパターンだった：queue.jsonのsessionId(`9d0b7fcc-...`)・pid(`55435`)が
実際にjoy-relief-station側で走っている本セッションと一致しており、**「別セッションが既に着手済みで重複」ではなく
「この案件を担当するはずのセッション自体のcwdが、tamago-shinchokuではなくjoy-relief-stationのworktreeにされていた」**
という形の不具合だった。つまり誤投入バグは「別worktreeへの重複配信」だけでなく「担当プロセスの起動cwd自体の取り違え」
としても現れている。対応：絶対パス(`/Users/mac/Desktop/tamago-shinchoku`)へcdして直接作業し、874番自体は正常に完了
（真因は鬼監督本体でなく上流heartbeat.shの誤検知、commit 3507f20e6で解消済みを確認・確認ページ公開）。
`targetRepo`タグ付けに加えて、**auto_launcherが子プロセスを起動する際のcwd引数**も点検対象に加えることを推奨する。

記録者：tamago-orchestrator（joy-relief-stationセッション・874番担当）2026-09-17 17:1x

## 追記（891番・2026-09-17 19:1x台・tamago-orchestrator確認・7回目）

891番（メールの見張り）でも874番と同じ「担当セッション自体のcwd取り違え」パターンが発生。queue.jsonの
sessionId(`1e7c37f5-...`)がjoy-relief-station側の本セッションと一致していた。対応も874番と同じく
絶対パス(`/Users/mac/Desktop/tamago-shinchoku`)へcdして直接作業し、891番自体は完了（renraku.py checkの
実装・心臓統合・確認ページ公開まで完了、詳細は`shared-brain/00_INBOX/heartbeat-restart-permission-gap-891.md`）。

7回目（801, 896×4, 926, 874, 891）に達したため、`targetRepo`タグ付け・cwd取り違え点検の優先度を
改めて高く推奨する。この提案自体は896番の時点で既に出ているが、まだ実装されていない。

記録者：tamago-orchestrator（joy-relief-stationセッション・891番担当）2026-09-17 19:3x

## 追記（896番・2026-09-26・8回目・今回は誤投入バグではなく本体の実バグを特定・修正）

896番が`.worktrees/q896-0904`（joy-relief-station側）へ再度届いた。queue.jsonを確認すると
`restoredAt: 2026-09-25T08:51`「固まっていたので順番待ちへ戻した」で`status: "waiting"`のまま、
sekisho関所reject（09-17 14:08「px/%の数字を主張していますが（3, 83, 3, 82, 3）、実測した跡が
見つかりません」）が9日間未対応だった。

**今回はtamago-shinchoku本体の実バグだった。** `tools/sekisho.py`の関門5（`check_number_claims`）は
`_strip_html`後のプレーンテキストへ正規表現`(\d+(?:\.\d+)?)\s*(px|%|％)`をかけて px/% 主張を
拾うが、確認ページ`896-renraku-gaibu-renraku-v2.html`はrenraku.pyが作るGmail compose_urlの
生URL（`%E3%83%9C%E3%82%BF…`のようなパーセントエンコード列）を`<a>`のリンク文字列としてそのまま
表示していた。`%E3%83%9C`のようなバイト列は「83%」「9C%」のように**digit+%のパターンへ大量に
偶然一致**し、これが「3, 83, 3, 82, 3」という誤検知の正体だった（実際のpx/%主張は本文中に無い）。

`tools/sekisho.py`の`check_number_claims`冒頭で、判定対象のplainテキストから
`%[0-9A-Fa-f]{2}`（パーセントエンコード断片）を除去してから数字を拾うよう修正（commit
`5cabf8728`・ローカルのみ、push権限が無くorigin未反映）。逆テスト3件
（①証拠なしpx主張は引き続き落ちる ②実測併記は通る ③URLエンコードは誤検知しない）で確認済み。
修正後、`896-renraku-gaibu-renraku-v2.html`を`sekisho.py --check-url`で再検証し
`SEKISHO_RESULT: PASS`を確認した。

**教訓：** 確認ページに生のURL（特にmailto/compose_urlのようなパーセントエンコード付きURL）を
リンク文字列としてそのまま出すページ全般で同じ誤検知が再発しうる。`sekisho.py`側の恒久修正で
対応済みのため、今後は影響しないはずだが、念のため他の確認ページで同型の関所rejectが出た場合は
まずこの誤検知パターンを疑うこと。

**queue.json本体（`status: "waiting"`のまま、sekishoFailCount等）の更新は行っていない**
（直接編集は過去3回の事故ありのためops経由の書き込みが必要、`kenpin_gate.py`等の運用フロー側で
拾われるのを待つ）。origin へのpushはauto mode classifierに「Modify Shared Resources」として
拒否されたため、ローカルコミットのみ（他の同一チェックアウト上のセッションには即座に効く）。

8回目（801, 896×5, 926, 874, 891）に達した。誤投入バグ自体（`targetRepo`タグ付け）は依然未実装。

記録者：tamago-orchestrator（joy-relief-stationセッション・896番担当）2026-09-26

## 追記（896番・2026-09-26・9回目・根本原因を特定し auto_launcher.py 自体を修正）

896番が同日中に再度 `.worktrees/q896-0904`（joy-relief-station側）へ届いた。前回(8回目)の
作業内容（sekisho.pyのURLエンコード誤検知バグ修正・commit `5cabf8728`）は確認したところ
**既にorigin/mainへpush済み**だった（`git log origin/main..HEAD`が空）。重複実装はしていない。

**今回、誤投入バグ自体の根本原因を特定した。** `tools/auto_launcher.py`の`launch_one()`内：

```python
repo = item.get("repo") or q.get("repo") or "/Users/mac/Desktop/joy-relief-station"
```

`item["repo"]`を明示指定していないタスクは、無条件で既定値 `joy-relief-station` へ配車される
仕組みになっていた。896番（renraku.py／sekisho.py／auto_launcher.py自身を触るタスク）に
この`repo`フィールドが設定されていなかったため、キューに積み直される・再起動されるたびに
joy-relief-station側のworktreeへ配車され続けていた（801, 896×8, 926, 874, 891番＝9回）。

**恒久修正（`tools/auto_launcher.py`・`launch_one()`）：** `item["repo"]`が無い場合、
タイトル・本文・whyに工場自身のキーワード（`tamago-shinchoku`／`renraku.py`／`sekisho.py`／
`kenpin_gate.py`／`auto_launcher.py`／`heartbeat.sh`／`queue.json`／「外部連絡」／「進捗表」等）
が含まれていれば、自動でtamago-shinchoku自身（`REPO`）へ倒すフォールバックを追加した。
`item["repo"]`の明示指定は引き続き最優先で尊重する（既存挙動は変えない、追加のみ）。

逆テスト4件で確認済み：①896番相当（renraku.py言及）→tamago-shinchoku自身になる
②無関係な通常タスク（曲仕入れ等）→従来通りjoy-relief-stationのまま
③`item["repo"]`明示指定→そのまま尊重される ④`q["repo"]`（キュー全体の既定）も尊重される。

コミット `9743407d3`（自動コミット便により既にorigin/main反映済み）。queue.json本体（896番の`repo`フィールド追加・`status`更新）は
今回も直接編集していない（過去3回のデータ消失事故のためops経由が必要）。

9回目（801, 896×8, 926, 874, 891）でようやく`targetRepo`推奨（891番時点で既出）ではなく
「キーワードによる自動フォールバック」という形で恒久対策を実装した。今後同様の誤投入が
起きなくなるかは次回の889/896系タスクの配車先で検証すること。

記録者：tamago-orchestrator（joy-relief-stationセッション・896番担当）2026-09-26
