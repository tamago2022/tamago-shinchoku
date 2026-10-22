【便1：白飛びをなくす】
店主の言葉：「表示と読み込みは速くなった。でも、触ると白飛びして切り替わるのが多くて残念」。原因の一つはわかっている：**ページを開くたびに見出しが透明（opacity:0）から浮かび上がる演出**（フェードイン／framer-motion の initial={{opacity:0}}／CSS animation の from{opacity:0}・IntersectionObserver で後から表示 等）。
1. 洗い出し（src/ 全体を grep）：opacity:0 から始まる入場演出、Suspense fallback の白い全面、index.html／html／body／#root の初期背景、言語切替での再マウント（key の付け替え・全消し）、静的マガジン public/magazine/*.html とアプリの行き来で背景色が違う所、内部リンクなのに全読み込みになる遷移。
2. 直す：最初の描画で見出し・本文が見えている状態にする（入場演出は transform だけ・または初回表示では無効。prefers-reduced-motion も尊重）。地の色を最初の1フレームから暗色でそろえる。Suspense は前の画面を保つ（startTransition）か地の色の骨組み。言語切替はツリーを作り直さずに文字だけ替える。マガジンHTMLの <html> の背景も同じ色。
3. 関所 scripts/patrol/check-no-white-flash.mjs：opacity:0 始まりの入場演出が新しく入る・初期背景が白系・fallback が白い全面、のどれかで失敗。
