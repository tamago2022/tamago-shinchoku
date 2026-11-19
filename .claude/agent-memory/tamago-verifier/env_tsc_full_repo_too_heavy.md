---
name: env-tsc-full-repo-too-heavy
description: joy-relief-stationで`npx tsc --noEmit`をリポジトリ全体で実行すると、tamago-verifierサブエージェントのサンドボックスでは15分・メモリ増量(--max-old-space-size=4096)でも完了せずkillされる（exit 137/144）。出力ゼロのまま終わる。
metadata:
  type: project
---

`joy-relief-station`は`src/lib/coverGuide.ts`等が数万行規模の巨大ファイルで、`npx tsc --noEmit`をリポジトリ全体に対して実行すると、tamago-verifierサブエージェントの実行環境（`run_in_background`、デフォルト10分・最大900000ms=15分で試行）では、1行も出力されないまま途中でkillされる（1回目:デフォルトタイムアウトでexit 137＝SIGKILL、2回目:`--max-old-space-size=4096`を付けて15分タイムアウトを明示してもexit 144＝SIGTERM）。

**Why:** 対象ファイルが巨大（coverGuide.tsだけで数万行）なため、型チェックの計算量がサブエージェントに割り当てられたリソース・時間内で終わらない。これは新規エラーではなく環境制約（[[env_worktree_needs_npm_install]]と同種のサンドボックス限界）。

**How to apply:** 依頼元から「tsc --noEmitで新規型エラーが無いか確認して」と言われても、全体実行は時間内に終わらないことを前提に動く。代替手段：
1. 変更した2ファイルの追加フィールド（例: `note`/`memo`/`src`）が、同じ配列内の既存の動いているエントリと同じ型パターン（例: 既存の`src: string[]`付きエントリが多数存在する）であることをgrepで確認し、構造的な整合性を示す（型チェックの代替にはならないが参考根拠にはなる）。
2. 実行はしたが結果が出なかったことを正直に報告し、「実行していない検証をOKと書かない」原則に従って、tsc結果は「未確定（環境制約でタイムアウト）」として扱う。PASS/FAILを推測で書かない。
3. 本番ビルド（`npm run build`等、CIで実際に走るもの）での型チェック結果があればそれを優先して参照する。
