---
name: role-playbook-generic
description: 「担当（役割）」ごとの恒久ルール・現在地・落とし穴・完成条件を1コマンドで復元し、終わりに書き戻す汎用パターン。どのリポジトリでも使える（特定プロダクトに依存しない）。複数セッション・複数AIが同じプロジェクトを長期間引き継ぎながら進める時、依頼者が毎回同じ説明を繰り返さなくて済むようにする。
---

# 担当別プレイブック（汎用版）

## これは何か

`joy-relief-station`（ごきげん補給所）で2026-08に作られ、2026-08-09から本番で動き続けている
「担当別プレイブック」（`.claude/skills/tamago-role-playbook/SKILL.md`）の**型だけを、
そのプロダクトの中身（仕入れ・棚編集・Lovable等の固有名詞）を抜いて切り出したもの**。

元の実装はjoy-relief-station専用の担当（仕入れ担当・つなげる担当…）と固有の運用語（店主・Lovable）が
roles.json・各スクリプトのコメント・完了条件の文言に混ざっていたため、**別のリポジトリへそのまま
持っていくことはできなかった**。本スキルは、ロジック部分（`scripts/*.mjs`）をプロダクト固有の文言から
分離し、固有の部分は全部 `roles.json` 側のデータとして注入できる形に直してある。

## 解く問題

複数セッション・複数AI（Claude Code・Codex・他エージェント）が同じプロジェクトを長期間、
引き継ぎながら進めると、次の事故が繰り返し起きる。

- 新しいセッションが、前のセッションの文脈・過去の事故・今どこまで進んだかを知らずに着手し、
  依頼者が同じ説明を何度もすることになる。
- 「どこまでやったか」が会話ログの中にしか残らず、会話が終わると消える。
- 同じ落とし穴に何度も落ちる（前回気づいた教訓が、次のセッションに伝わらない）。
- 自分の仕事を自分で「完了」と判定してしまい、検証が甘くなる。

## 使う場面

- 1つのプロジェクトに、継続して繰り返し発生する「担当（役割）」の種類がいくつかある
  （例：執筆・検品・実装・調査・公開・SNS運用…プロダクトの種類は問わない）。
- セッションがその都度変わる、または複数のAIが交代で同じ担当を引き継ぐ。
- 「前回どこまでやったか」「このプロジェクトでこの作業をする時に気をつけることは何か」を
  依頼者に聞き直したくない。

**使わない方がいい場面：** 1回限りの単発タスク、担当という概念に分けるほど継続しない作業。

## 中身（このスキルに入っているもの）

```
role-playbook-generic/
├── SKILL.md                         ← 本体（このファイル）
├── scripts/                         ← ロジック（プロダクト名・固有名詞に依存しない）
│   ├── role-brief.mjs               ← 入口。担当名→ブリーフ1枚を出す
│   ├── role-check.mjs               ← roles.json・playbookの整合性チェック
│   ├── role-handoff.mjs             ← 終わる前の書き戻し（現在地メモ・ACTIVE_WORK更新）
│   ├── role-sweep.mjs               ← 無人巡回。全担当の残件・繰り返し話題を検出
│   ├── role-log.mjs                 ← 巡回ログへの記録（完了／問題／判断待ち）
│   ├── role-claim.mjs               ← Builder側：証拠付きの主張を記録
│   ├── role-judge.mjs               ← Judge側：証拠だけを実行してPASS/FAILを出す
│   ├── role-help.mjs                ← 担当間の横相談（詰まった時に隣の担当へ振る）
│   └── role-stress-test.mjs         ← 仕組みが本当に効いているかをわざと壊して確認する
└── templates/
    ├── roles.json.example           ← 担当台帳（恒久情報）のひな型。2つのダミー担当つき
    └── role-playbook.md.example     ← 担当1件分の「現在地メモ」のひな型
```

**プロダクト固有の情報は一切入っていない。** 仕入れ・棚・Lovable・店主といった語は、
元の実装からの引用コメント（由来の説明）としてのみ残っている箇所があるが、
ロジックはすべて `roles.json` が持つデータ（`completionStages`・`sweepTopics`・`roles[]`）で動く。

## 導入手順（どのリポジトリでも）

1. `scripts/` フォルダを、自分のリポジトリの `scripts/roles/` へそのままコピーする
   （スクリプトは自分の場所から2階層上をリポジトリルートとして解決するので、
   `scripts/roles/*.mjs` という深さを変えないこと）。
2. `templates/roles.json.example` を自分のリポジトリの `.claude/playbooks/roles.json` へコピーし、
   `roles[]` を自分のプロジェクトの担当に書き換える（`templates/roles.json.example` のスキーマに
   それぞれのフィールドの意味を書いてある）。
3. 担当ごとに `.claude/playbooks/<担当名>.md` を `templates/role-playbook.md.example` から作る
   （無くても動く。無い場合は「現在地は未確認」と正直に出る設計）。
4. `package.json` に次を追加する。

   ```json
   "scripts": {
     "role": "node scripts/roles/role-brief.mjs",
     "role:check": "node scripts/roles/role-check.mjs",
     "role:handoff": "node scripts/roles/role-handoff.mjs",
     "role:sweep": "node scripts/roles/role-sweep.mjs",
     "role:log": "node scripts/roles/role-log.mjs",
     "role:claim": "node scripts/roles/role-claim.mjs",
     "role:judge": "node scripts/roles/role-judge.mjs",
     "role:stress": "node scripts/roles/role-stress-test.mjs",
     "role:help": "node scripts/roles/role-help.mjs"
   }
   ```

5. 動作確認：`node scripts/roles/role-brief.mjs -- <自分が書いた担当名>` を実行し、
   ブリーフが1枚出ることを確認する。

## 使い方（導入後）

```bash
npm run role -- <担当名>          # そのブリーフを1枚出す（読むだけ・何も書き換えない）
npm run role -- --list            # 担当一覧
npm run role:check                # roles.json / playbookの整合性チェック
npm run role:handoff -- <担当名>  # 終わる前に現在地メモへ書き戻す
npm run role -- 全担当チェック     # 無人巡回。残件・繰り返し話題を検出（読むだけ）
```

終わる前に必ず `role:handoff` を実行する。ここを飛ばすと、次のセッションが前回の現在地を
復元できず、この仕組みが機能しなくなる（＝依頼者が再び同じ説明をする状態に戻る）。

## カスタマイズ点（プロダクトごとに変える場所）

`roles.json` の以下のフィールドだけでプロダクト固有の挙動を注入できる。スクリプト本体は変更不要。

| フィールド | 役割 |
|---|---|
| `roles[]` | 担当の一覧（恒久情報：別名・使命・読むもの・触る場所・落とし穴・検品・完成条件） |
| `completionStages` | 「完了」の段階（例：実装→レビュー→合流→本番反映）。プロダクトごとに段数も文言も違ってよい |
| `sweepTopics` | 無人巡回が「同じ話題が繰り返されている」と検知するためのキーワード正規表現。
  未指定なら繰り返し検知そのものが無効化される（安全側のデフォルト） |
| `alwaysRead` / `crossCuttingLaws` / `reportFormat` | 全担当共通で読むファイル・守るべき横断ルール・報告の型 |

## 元の実装との関係

- 元（プロダクト固有・本番稼働中）：`joy-relief-station` リポジトリの
  `.claude/skills/tamago-role-playbook/SKILL.md` ＋ `scripts/roles/*.mjs` ＋
  `.claude/playbooks/roles.json`（15担当・2026-08-09本番反映・以後launchdで1時間おきに無人巡回）。
- 本スキル（汎用・プロダクト非依存）：上記からロジックだけを分離した移植可能な型。
  joy-relief-station側の実装を書き換えるものではない（既存資産はそのまま）。

## やってはいけないこと

- `roles.json` の `roles[]` を空のまま「導入した」と報告しない。最低1件、実在する担当を書いて、
  実際に `role-brief.mjs` を走らせて出力を確認してから導入完了とする。
- スクリプトのロジック側にプロダクト固有の文言・固有の判定条件を書き戻さない
  （`sweepTopics` のように、固有情報は必ず `roles.json` 側のデータとして注入する）。
- 現在地メモの空欄を、確かめずに想像で埋めない（元の実装と同じ原則）。
