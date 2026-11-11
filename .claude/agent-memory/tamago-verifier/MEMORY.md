# tamago-verifier メモリ索引

- [サンドボックス内でcurl等の外部ネットワーク確認が使えない](env_no_network_curl.md) — 本番URL実測はこのサブエージェント実行環境では不可、報告は限界を明記する
- [worktree未インストール環境でのverify-project.sh](env_worktree_needs_npm_install.md) — node_modules無しだとeslint等が即落ちる。新規失敗ではなく環境未整備と区別する
- [tsc --noEmitのフル実行が重すぎて完了しない](env_tsc_full_repo_too_heavy.md) — coverGuide.ts等が巨大なため15分でもkillされる。PASS/FAILを推測で書かず「未確定」と報告する
