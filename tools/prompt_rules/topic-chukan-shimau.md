## 動画・音声の仕事は、終わる前に中間ファイルを消す（2026-10-16・使ったらしまう）
- 書き出しのコマ（_frames 等）・分割した音（_chunks 等）・ffmpeg の2パスログ・yt-dlp の .part・Whisper 用に切り出した wav など、**作り直せる途中の物は、完成品を納品（`tools/claude_nouhin.py put`）したら自分で消してから報告する。**
- 置き場は `~/howitholds/<作品>/_tmp` か `/private/tmp/<番号>_*` に決め打ちする（ほかに散らかさない）。名前を `_frames`／`_chunks`／`_tmp` にしておけば、消し忘れても `tools/chukan_shimau.py` が2時間後に拾う。
- Mac本体の空きが30GBを切っていたら、重い書き出しを始めない（`status/public/youryou_mihari.json` の free_gb）。
