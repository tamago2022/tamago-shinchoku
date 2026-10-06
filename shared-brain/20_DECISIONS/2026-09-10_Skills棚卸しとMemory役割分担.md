# Skills棚卸しとMemory役割分担（701番・2026-09-10）

## 背景

Anthropicサポート（Fin AI Agent）の回答の趣旨：「セッションごとに文脈がリセットされるのは仕様どおり。挙動を固定する公式の手段は無い。**MemoryとSkillsで指示を明示的にするのが対策。**」

この工場は既に、下の4層で「挙動の固定」を実装済みだった（今回の棚卸しで初めて1枚に整理した）。今後、新しいルールを足す担当は、この表を見てどこに書くかを選ぶ。**同じ内容を2箇所以上に書かない。**

## 4層構造（確実性が高い順）

| 層 | 実体 | 確実性 | コスト | 向いている内容 |
|---|---|---|---|---|
| ①hooks | `tamago_context.py`等（Vault `AI出力/_ルール/hooks/`） | 100%（SessionStart/SubagentStart/UserPromptSubmitで機械的に発火） | 中（毎回注入） | たまご憲法コア・受付台帳・コンロ3口など、Vault内で動く全セッションに必ず効くべき前提 |
| ②prompt_rules（always） | `tools/prompt_rules/always-*.md`＋`INDEX.json` | 100%（`auto_launcher.py`の`build_prompt()`が機械的に全部連結） | 高（全タスクに常時注入。628番の反省で1件1ファイルに分割済み） | 全ての子セッションが必ず守るべき動作（報告フォーマット・証拠必須・確認しない・キャッシュ1時間・お金の見積もり等） |
| ③prompt_rules（topics） | `tools/prompt_rules/topic-*.md`＋`INDEX.json`の`keywords` | 高（タイトル・本文にキーワードが一致した時だけ機械的に注入） | 低（該当作業のときだけ） | 特定分野だけに要る手順（fal・パフォーマンス・queue運用・ブラウザ操作等） |
| ④skills（SKILL.md） | `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/.../skills/*/SKILL.md` | **不確実（Claude自身がdescriptionを見て判断）** | 低（読み込まれた時だけ） | 名指しで呼ぶペルソナ・厚い手順書（鬼監督・AI社員・トーン基準・誌面基準等）。事前に何が要るか決め切れない/分量が多い内容 |

**Memory（事実・決定）はこの4層とは別軸**：`shared-brain/`（このディレクトリ、GitHub経由でAI間共有）と`status/failures.md`（事故台帳）が正本。**「何が起きたか・何を決めたか」はMemory、「次にどうすればいいか」はSkills/prompt_rules/hooks**、と役割を分ける。同じ事故の記録をprompt_rulesにベタ書きしない（failures.mdへのリンク・要約だけ書く）。

## 今回の棚卸しで分かったこと

1. **④skills（自動発火）は確実性が一番低い。** Claudeがdescriptionを読んで「今関連あるか」を判断するため、記述が曖昧だと読まれない。この工場は主要ルール（鬼監督・AI社員・運用OS）を④だけに頼らず、①②③でも同じ内容を確実化する二重化をすでに行っていた（例：`tamago-unyou-os`スキルの内容は`tamago_context.py`フックでも強制注入。`oni-kantoku`の心構えは`always-01`でも触れている）。**これが「挙動を固定できない」への現実的な回答**——公式Skillsの自動発火だけに賭けず、確実性が要る内容は上位の層（hooks/always）へ複製する。
2. **④skills 28個の内訳**（`skill-creator`で一覧化）：Anthropic組み込み13個（docx/pdf/pptx/xlsx/schedule/morning/consolidate-memory/import-memory/explain-usage/setup-claude/setup-cowork/skill-creator/design-critique、触らない）＋たまごさん独自13個（ai-hisho-discord-jochu/ai-shain/bonjovi-ojisan-kobun/digital-eguide/kitty-chan-hisho/mono-color/oni-kantoku/page-kenpin/pro-marketing-director/tamago-magazine-layout/tamago-tone/tamago-unyou-os/unei-houkoku）。
3. **バグ発見・修正**：`always-01-ai-shain-oni-kantoku.md`が「`oni-kantoku`スキルは実在しない」（2026-09-07時点の記述）のまま放置されていた。実際は現在SKILL.mdとして実在し、関門0〜10まで整備済み。誤情報のまま新規セッションへ配られ続けていたので本日修正した（`status/failures.md`への追記は本ファイル末尾を参照）。
4. **欠落の発見・補完**：「queue.jsonへの積み方」「進捗表の見方」は`README.md`にしか書いておらず、どのprompt_rules層にも無かった。`topic-dispatch-queue-ops.md`を新設しキーワード一致時に配布するようにした。

## 今後の運用ルール

- 新しいルールを思いついたら、まず「全セッションに常時必要か（①②）」「特定作業だけか（③）」「厚い手順・ペルソナで名指しで呼ぶものか（④）」を判定してから書く場所を選ぶ。
- ④に書いた内容のうち「これは絶対に外してはいけない」と分かったものは、①か②へも複製する（④だけに任せない）。
- ④のSKILL.mdを新規作成・改訂したら、`status/failures.md`やこのファイルのような「実在しない」前提の記述が他に残っていないか`grep -rl`で確認する。

## 効果測定について

`status/failures.md`は「同じ症状が繰り返し起きたか」を追える唯一の実測ログ。今回時点（2026-09-10・#20まで）を基準点とし、今後1〜2週間で同種の事故（スキル参照ミス・prompt_rules記載漏れ）が#20以降に増えていないかを次の棚卸し担当が比較する。3時間の作業内では「減ったこと」自体はまだ測定できないため、この基準点の記録をもって今回の成果とする。
