【便2：画面のずれ（レイアウトシフト）と、読んでいる途中の読み直しをなくす】
1. 画像・動画（YouTube 埋め込み・サムネイル）・カード・広告的な差し込み・フォント読み込みで、後から高さが変わる所を src/ と public/magazine/*.html から全部洗い出す。
2. 直す：img に width/height か aspect-ratio、動画枠は aspect-ratio:16/9 の箱を先に確保、カードの骨組みは本物と同じ高さ、遅れて出る要素は場所を先に取る、font-display と代替フォントの寸法合わせ。
3. 読み直し：勝手な再読み込み（reload・useEffect でのデータ再取得でリストが空になる・key の付け替えで再マウント）、戻るでスクロール位置が飛ぶ（ScrollRestoration・保存と復元）を直す。
4. 関所 scripts/patrol/check-no-layout-shift.mjs：寸法なしの img／比率なしの iframe／reload 呼び出しが新しく入ったら失敗。
