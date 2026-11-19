【便3：初回表示を速く（JS の分割・画像の軽量化）】
1. `npm run build` の出力でチャンクごとの大きさを表にする（前）。大きい順に、最初の画面に要らないもの（ルートごとのページ・重い部品・曲データの大きな表・three 等）を React.lazy / dynamic import に分ける。曲データの検索が全件を最初に読んでいるなら、検索を開いた時に読む形にする（Pagefind 等の導入は依存の追加になるので、今回は既存の依存の範囲で分割と遅延だけ）。
2. 画像：public/ の重い PNG/JPG のうち表示に使っているものを洗い出し、既存の依存（sharp 等が package.json にあれば）で WebP を作って差し替える。無ければ一覧と大きさの表だけ PR 本文に書く。img に loading="lazy" decoding="async"（最初の画面の主役画像は除く）。
3. 後（同じ表）を PR 本文に。初回に読む JS の合計が何 KB → 何 KB になったか。
4. 関所 scripts/patrol/check-bundle-size.mjs：最初に読む JS の合計が今回の値＋5% を超えたら失敗。
