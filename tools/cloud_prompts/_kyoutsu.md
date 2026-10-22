joy-relief-station（main）の改善便。調べて終わり禁止。最後まで直して PR を作る。質問せず自分で決める。終わりの合図は最後の発言＝PR の URL だけ。

【作法】
- 作業ブランチは claude/ で始める。main へ直接 push しない。PR を作ったら終わり（マージは工場がやる。gh pr merge は禁止）。
- 依存は最初に `npm ci`（ダメなら `bun install --frozen-lockfile`）。npm install・依存の追加は禁止。
- このリポの .claude/hooks/cloud-no-wait.mjs が、削除・外部への送信・課金・公開・マージを待たずに拒否する。拒否されたら別の道で続ける（止まらない）。
- 本番DB・Supabase への書き込み禁止。秘密情報は出さない。曲の事実データ（src/data/coverGuide*.ts の note 等）は触らない。
- 気に入られている見た目（色・配置・文字）は変えない。直すのは「速さ・安定・ずれ・白飛び」。
- 文言を変えたら src/i18n/overlay/{en,zh-Hans,es,ko}.json に同じコミットで訳を足す（check-i18n-parity が落ちると公開が止まる）。`location.href =` は使わない（check-no-hard-reload）。
- 出す前に `npx tsc --noEmit` と `npm run build`（prebuild の関所すべて）を通す。
- 直した状態を守る関所を scripts/patrol/check-*.mjs として1本足し、package.json の prebuild に並べる（既存の check-*.mjs と同じ作法・数十秒以内・--self-test 付き）。
- PR 本文：前→後の表（場所／原因／直し方）、関所の名前と実行秒数、工場が本番で確かめる手順を1行。
