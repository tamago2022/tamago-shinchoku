joy-relief-station（main）の改善。調べて終わり禁止。PRまで作ること。終わりの合図はPRのURLだけ。質問せず自分で決めて最後までやる。

【実行の作法（重要・承認待ちで止まらないために）】このリポの .claude/settings.json は許可リスト方式。使えるのは npm ci / bun install --frozen-lockfile / npm run <script> / bun run <script> / npx tsx <file> / git / curl -s https://joy-relief-station.lovable.app/* 等。`python3`・`npx playwright` は許可に無いので使わない。スクリプトは `npx tsx` で動かす。コマンドは1回1つ、&（バックグラウンド）・$()・サブシェル・sleep・パイプの多段は使わない（承認待ちになり、無人なので止まる）。依存は最初に `npm ci`（失敗したら `bun install --frozen-lockfile`）。ブラウザは入っていない前提で、計測はコード解析で行う。

【ゴール：白飛びゼロ】店主の言葉：「表示と読み込みは速くなった。でも、触ると白飛びして切り替わるのが多くて残念」。本番 https://joy-relief-station.lovable.app で、トップ→棚→曲ページ→マガジン、戻る、言語の切り替え、のたびに一瞬白い画面が挟まる。これを無くす。
1. 洗い出し（コード解析）：(a) index.html / html / body / #root の初期背景色と、アプリの地の色（ダーク）が揃っているか (b) Suspense の fallback が白い全面になっている箇所（src/routes, src/components を grep） (c) ページ全体の読み直し（location.href= / location.assign / reload / 内部リンクなのに <a href> で全読み込み）になっている遷移（scripts/patrol/check-no-hard-reload.mjs の対象外に残っているもの） (d) 言語切替で再マウント・全消しになる箇所 (e) 静的HTMLのマガジン（public/magazine/*.html）とアプリの行き来で背景色が違う箇所。結果を表（場所／原因の型／直し方）にして PR 本文に書く。
2. 直す（見た目と機能は変えない。気に入られている見た目は変えない）：html/body/#root/index.html の最初の描画から地の色を暗色でそろえる（white が一瞬も出ない）／Suspense の fallback を「前の画面を保つ」（startTransition・useTransition）か、全面白ではなく地の色＋軽い骨組み（skeleton）に／内部遷移は SPA の遷移に（外部へ出る所以外）／マガジン静的HTMLの <html style="background:…"> も同じ地の色に。既存ファイルの大量書き換えはしない。曲の事実データ（coverGuide.ts 等）は触らない。
3. 【永続化・最重要】この状態を守る関所 scripts/patrol/check-no-white-flash.mjs（名称は任意）：index.html・グローバルCSS・マガジンHTMLの初期背景が白系になっていないこと、Suspense fallback が白い全面でないこと、を静的に検査して1件でも出たら失敗で公開が止まる形。package.json の prebuild の並びに加える。既存の check-*.mjs と同じ作法・置き場。数十秒以内。
4. tsc（npx tsc --noEmit）／npm run build／既存の検査（prebuild の並び）が通ること。PR 本文に 前→後の表（箇所ごと）と関所の実行秒数、そして「工場側で測る手順（スマホ相当の headless でフレームの明るさを見る：status/zenkai_1018yu/Y8-shirotobi/jissoku.json）」を1行書く。
【禁止】本番DB・Supabaseへの書き込み、秘密情報の出力、他人の未commit変更の巻き込み。i18n の文言を変えた場合は src/i18n/overlay/{en,zh-Hans,es,ko}.json に同じコミットで訳を足す（check-i18n-parity が落ちると公開が止まる）。
最後の発言はPRのURLのみ。
