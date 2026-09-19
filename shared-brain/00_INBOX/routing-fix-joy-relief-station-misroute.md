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
