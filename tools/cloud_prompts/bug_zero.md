joy-relief-station（main）の改善。調べて終わり禁止。PRまで作ること。終わりの合図はPRのURLだけ。質問せず自分で決めて最後までやる。

【実行の作法（重要）】このリポの .claude/settings.json は許可リスト方式。使えるのは npm install / npm run / bun install / bun run / npx tsx / bun x tsx / git / gh pr create 等。`node` と `python3` は許可に無いので、スクリプトは `npx tsx` か `bun run` で動かす（.mjsも npx tsx で動く）。コマンドは1回1つ、&（バックグラウンド）・$()・サブシェル・sleep は使わない（承認待ちになり、無人なので止まる）。依存が無ければ最初に `bun install`（失敗したら `npm install`）。

【ゴール：バグゼロ】全ルートでブラウザのコンソールエラー（特に React hydration #418/#423/#425、未捕捉例外、404の資源）を 0 にする。
1. 現状計測：ルート一覧を src/routes から機械的に作り（動的ルートは代表例を数個）、ビルドして起動し、Playwright等で全ルートを開いて console error / pageerror / requestfailed を収集し、前の件数を表にする。ブラウザが入らない・ネットワークで取れない場合は、SSR出力とクライアント初回描画の差（日付・乱数・localStorage・window参照・Date.now・Math.random・ロケール依存）をコード検索で洗う方法に切り替え、できた範囲と「取れなかった範囲」を正直にPR本文へ書く。
2. 原因ごとに最小の修正（見た目と機能は変えない。既存ファイルの大量書き換えはしない。曲の事実データは触らない）。
3. 【永続化・最重要】この数字を守る関所を作る：scripts/check-console-errors.ts（名称は任意）を作り、公開前の検査（prebuild／verify-project.sh／既存のcheck-*の並び）に必ず組み込む。コンソールエラーが1件でも出たら失敗して公開が止まる形。関所自体は軽く（毎回数十秒以内。全ルートが重ければ主要ルートの固定リスト＋ルート追加時に未登録を検出する仕組み）。既存の他の関所と同じ作法・置き場に揃える。
4. After計測を同じ方法で取り、PR本文に前→後の表（ルートごとのエラー件数）と、関所の実行秒数を書く。tsc／ビルド／既存の検査が通ること。
【禁止】本番DB・Supabaseへの書き込み、秘密情報の出力、他人の未commit変更の巻き込み。
最後の発言はPRのURLのみ。
