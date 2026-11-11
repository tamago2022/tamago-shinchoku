---
name: env-worktree-needs-npm-install
description: joy-relief-stationのgit worktree（例 .worktrees/配下）はnode_modules未インストールのことがあり、scripts/verify-project.shの[1/10] ESLintが「eslint: command not found」で即止まる
metadata:
  type: project
---

joy-relief-station（/Users/mac/Documents/AI作業/.worktrees/配下のworktree）で`bash scripts/verify-project.sh`を実行すると、
そのworktreeで`npm install`/`bun install`が一度も走っていない場合、1番目のESLintステップで`sh: eslint: command not found`になり以降が進まない。
`ls node_modules/.bin/eslint`が無いことで確認できる。

**Why:** worktreeはmainの作業ディレクトリとは別物でnode_modulesを共有しないため、新規worktreeでは依存関係が入っていないことがある。
これはコミット内容（例：markdownファイル1件の追記）が原因の新規エラーではなく、環境未整備によるpre-existingな失敗。

**How to apply:** verify-project.shが即失敗した時は、まず`ls node_modules/.bin/eslint`等で依存関係の有無を確認する。
無ければ「今回の変更が原因の新規エラー」と誤認せず、「このworktreeは依存未インストールのため検証ゲートが実行不能（環境問題、変更内容とは無関係）」と区別して報告する。
変更がコード・ビルドに影響しない範囲（ドキュメントのみ等）なら、このゲート未実行を理由に不合格にしない。関連: [[env-no-network-curl]]
