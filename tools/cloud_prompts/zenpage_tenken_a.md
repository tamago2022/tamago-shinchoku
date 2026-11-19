joy-relief-station（main）の改善。調べて終わり禁止。PRまで作ること。終わりの合図はPRのURLだけ。質問せず自分で決めて最後までやる。

【実行の作法（重要・承認待ちで止まらないために）】このリポの .claude/settings.json は許可リスト方式。使えるのは npm ci / bun install --frozen-lockfile / npm run <script> / bun run <script> / npx tsx <file> / git（status・diff・log・add・commit・push・switch -c）/ gh pr create / curl -s https://joy-relief-station.lovable.app/* / curl -s https://www.youtube.com/oembed?… 等。`python3`・`node` 直叩き・`git clone`・`npx playwright` は許可に無いので使わない（.mjs も `npx tsx` で動く）。コマンドは1回1つ、&（バックグラウンド）・$()・サブシェル・sleep・多段パイプは使わない（承認待ちになり、無人なので止まる）。依存は最初に `npm ci`（失敗したら `bun install --frozen-lockfile`）。

【ゴール：全ページ点検＋間違いを作り方から断つ】対象：本番 https://joy-relief-station.lovable.app の全ページ＝曲ページ（/cover-guide?artist=…&song=…・約3.8万。全部は無理なので、棚・マガジン・特集から辿れる曲＋ランダム300を代表に）＋マガジン（public/magazine/*.html・全部）＋特集（/feature/*・全部）。
点検する6つ：①表示崩れ（空の枠・文字化け・はみ出し：SSR出力やHTMLの構造で機械判定できるもの）②動画が再生できない（YouTube oEmbed で生死）③関連の理由なし（「なぜこの曲が隣にあるか」が空・同じ文の使い回し）④制作側メモの残り（「TODO」「仮」「要確認」「oEmbed」「mute=1」「歌詞は引用して」など読者に見せない語）⑤リンク切れ（内部リンク先が無い）⑥言語切替の抜け（5言語のうち訳が無い所）。
やり方：本番は `curl -s https://joy-relief-station.lovable.app/<path>` で取れる（許可済み）。リポ内の静的データ（coverGuide 系・public/magazine）とも突き合わせる。点検スクリプトは scripts/patrol/ に `npx tsx` で動く形で置き、結果を docs/zenpage_tenken.json（点検したページ数・型ごとの件数・直した数）に出す。
直す：直せるもの（④の語の除去・⑤のリンク先修正・③の理由の補充のうちリポ内の記録で言えるもの）は直す。その上で【最重要】その間違いを生んだ所（データ生成スクリプト・取り込み・既存の関所の抜け）を直して、同じ間違いが二度と入らない形にする。新しい検査は package.json の prebuild の並びに加える（軽く・数十秒以内）。
【禁止】本番DB・Supabaseへの書き込み、秘密情報の出力、他人の未commit変更の巻き込み、曲の事実データ（年号など）の書き換え、既存ファイルの大量書き換え。新しい日本語の UI 文言は src/i18n/overlay の4言語に訳を足す。
【PR 本文】点検したページ数・型ごとの件数（前）→直した数（後）→作り方で断った所、を表で。
最後の発言はPRのURLのみ。
