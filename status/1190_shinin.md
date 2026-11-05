# 実測で分かった真因（次の担当が調べ直さなくていいように）

**これは推測ではない。全部こちらで実際に測って分かったこと。**
新しく真因が分かったら、ここに1行足す。引き継ぎの1枚（`status/hikitsugi_ima.md`）に自動で入る。

- **作業サーバー（Anthropic側のLinux）はディスク満杯で死んでいる。**回避路は「心臓経由」＝
  `status/oneshot/pending/*.sh` に置くとMac側が実行し、`status/oneshot/done/*.out` に結果が出る。
  作業サーバー側で粘らない。（2026-09-28・1180番／2026-09-29 再実測・1190番）
- **Bufferが止まっていたのは、自前スクリプトが1日576回叩いていたから。**
  残り本数は自前カウンタではなくBufferの実データを見る。ズレた側が嘘をつく。（2026-09-28・1180番）
- **Chromeでプロファイル選択画面が出る真因は `tools/1401_cdp_arm.py`。**
  Chrome自体の設定ではない。（2026-09-28・1180番）
- **タブが残る真因は `NEVER_CLOSE` の優先順位。**「閉じる処理が動いていない」ではなく、
  閉じない設定が先に効いている。（2026-09-28・1180番）
- **残量%が止まる真因は `pace.py` を重い処理に相乗りさせていたこと。**軽い周回に分ける。（2026-09-28・1180番）
- **26,000件をJSに直書きしていた。**V8公式が禁じている形（巨大な配列リテラル）。
  大量データは Pagefind を**そのまま移植**すると決定。自作しない。（2026-09-28・1180番）
- **YouTube埋め込みのバックグラウンド再生は規約で不可。**
  出典：YouTube API Services Terms of Service（映像を隠して音だけ流すことを禁止）。
  回避策を探すのではなく、この前提で設計する。（2026-09-28・1180番）
- **トーキングアバターは pixiv の three-vrm ＋ ChatVRM を「そのまま移植」と決定。**自作しない。（2026-09-28・1180番）
- **`.git/index.lock` が残って工場のgitが丸ごと止まるのは、サンドボックスが直接gitを叩いたとき。**
  正しい口は `status/commit_inbox/` に紙を置くだけ。（2026-09-24・台帳 gitlock）
- **「pushした」と「本番に出た」は今この瞬間もズレている。**
  トップは200で開くのに、同じコミットに入っている `share/daicho.html` は404（実測）。
  Lovableの「公開」は別操作。main合流だけでは成果ゼロ。（2026-09-29・台帳 honban）
- **claude CLI は Mac に存在しない**（PATH・/usr/local/bin・/opt/homebrew/bin・~/.claude/local すべてに無い）。
  「認証切れ」ではなく「居ない」。工場は codex（ChatGPTログイン・0円）へ繋ぎ替え済み。（2026-09-29・台帳 claudeauth）
- **外部AIの口：Grok／Genspark／GitHub Copilot はどれも返らない。**
  Grok＝x.ai が team_blocked かつクレジット0で403。Genspark＝APIドメインが名前解決しない・掲示板も無反応。
  Copilot＝担当者に入れると403、有料プランがいる。**全部たまごさんの課金判断待ち。**
  生きているのは ChatGPT(Codex)／チャッピー(ChatGPT直)／Gemini(Jules)。（2026-09-29 実測・ai_daicho）
- **GitHub Pages公開(tools/pages_publish.sh)がgh-pagesへのforce pushで10時間以上HTTP 408連続失敗。**
  ~/.tamago-pagesのローカルgitが65,872個のloose object(1GB・未gc)まで肥大しており、
  回線が細い時間帯に押し切れず落ち続けていた。`git gc`で50,929個をpack化(200MB)し多少緩和したが、
  回線自体が遅い(github.comへの単純GETが2.9秒)ため根治はできず。**緊急時の代替経路**：
  `gh api --method PUT repos/.../contents/<path>`でgh-pagesへ単一ファイルを直接コミット
  （6.5KBのHTMLなら数秒で成功・git push全体をバイパスできる）。次回もPages公開が長時間止まっていたら
  まずこれを使う。gh CLIは`/Users/mac/.local/bin/gh`（PATHに無い場合あり）、tamago2022アカウントで認証済み。
  （2026-09-30・1516番）
- **★交代の引き継ぎ（担当期間・言われたこと全1,203件・叱られたこと・オリジナル禁止の実例）は
  この1枚にまとまっている：https://tamago2022.github.io/tamago-shinchoku/share/1712-hikitsugi-0930.html**
  正本は `status/1712_hikitsugi_2026-09-30.md`（Macの `~/Documents/AI作業/引き継ぎ_2026-09-30.md` にも同じもの）。
  **調べ直すな。まずこれを読む。**（2026-09-30・1712番）
- **担当期間：クロマティ2（この担当）＝2026-09-17〜2026-09-30／前々任クロ丸＝2026-09-09〜2026-09-17**
  （たまごさん本人のメモ）。**交代を記録する紙が工場に無いので、次の担当は交代した日をその日にここへ1行書く。**
  ★**やってはいけない逆算：`status/failures.md` の日付行の最古（09-05）を担当開始日にする。**
  あの台帳は担当が替わっても行が積まれ続ける**工場全体**の失敗ログで、前任・前々任の分が混ざっている。
  1712番は実際にこれで「09-05から」と誤って書き、たまごさんに訂正された。（2026-09-30・1712番）
- **件数の数え方：1件＝票1枚。たまごさんの発言1つではない。**`origin:"user"` を「たまごさんが言ったこと」と
  等号で扱うと水増しになる（その印の中に外部AI/GitHubの返信・機械の自動記入・同一発言の分裂が混ざる）。
  **実測（票番号#920以降＝09-17以降）：票1,101枚（済17／やりかけ99／止まっている39／未着手946）。
  そのうち「たまごさんの発言がそのまま票になったもの（判定日赤）」は114枚、
  外部AI/GitHubの返信187枚、機械の自動記入29枚、自動分割13枚。**
  1712番は最初これを1,203件と報告して訂正された。（2026-09-30・1712番）
- **票の数＝言われた回数ではない。**同じ発言が複数の票に分裂している（実測：Live2Dの調査が14票
  #1966〜#1979、「整理を止めて行き先を証明する」が4票 #735〜#738、「確認できないものをよこすな」が
  4票 1397/1464/1466/1472）。**回数は `status/daicho.json` の `kaisu` を見る。票数で判断すると間違える。**
  （2026-09-30・1712番）
- **コンシェルジュは「喋る」までは本番で通っている（たまごさん評65点）が、残りはこの2つ。**
  ①「つないでいます…」のまま戻らない回がある（#2187）②**声の使いすぎを止める1日の上限額が、本番だけ
  旧値の $4.5 のまま4日以上届いていない**（コード側は 単価$0.08/分・1日上限$1.00 で09-24にmain合流済み。
  実測＝本番の `action:"create"` 応答が `budgetLimitUsd:4.5`。$1.00なら12.5分で止まるはずが56分喋れる＝栓が4.5倍緩い。
  いま何ドル使ったかを聞く `action:"status"` は本番に存在せず `unknown_action` を返す。#1386／#1487で再確認）。
  声の速さは実測 468ms／903ms で問題ない。**「遅い」ではなく「戻らない」と「本番だけ古い」が真因。**
  （2026-09-30・1712番）
- **「画像と動画は無罪」はもう違う。**曲ページ（スマホ・1.6Mbps実測）4,984KBのうち coverguide-data 2,180KB、
  PNG 3枚（egg-concierge-guide 672KB／badges/concierge-pick 323KB／badges/good-cover 235KB）で1,230KB。
  トップの youtube-id-map は15KBまで下がっていて、PR #448/#455/#512 の標的は既に消えている。数字は `status/2192_pagefind/before.json`。（2026-10-01・2192番）
- **Pagefind は曲単位で索引すると fragment が3.7万ファイルになる。**Cloudflare Workers の静的アセット上限（無料2万）を超える危険があるので、
  アーティスト単位（約2,461件）で索引する。（2026-10-01・2192番）
- 2026-10-16（101885）Lighthouseの Slow 4G（1.6Mbps/150ms）で本番を測ると LCP 7〜14秒・90秒timeoutが出て、+10%の物差しとして荒すぎる。関所の既定は DevTools の Fast 4G（4Mbps/20ms・CPU2倍遅）＋2回の良い方＋落ちたページだけ測り直し。送る量はYouTube等の外部を除いた自サイト分で比べる（外部は毎回ゆれる）。
- 2026-10-16（101885）Claude Code の Bash から ( … ) & で起動した vite build（8GB）は途中で黙って消えた（EXIT行が残らない）。nohup bash -c '…' & で起動すると最後まで走る。Playwright の headless shell は ~/Library/Caches/ms-playwright に無かった（MISSING）。node ~/.tamago/node_modules/playwright-core/cli.js install chromium-headless-shell で入る（1.3MiB+本体、お金0）。
- 2026-10-16（35029）「Claude CLI経路の--max-turns上限が8で止まる」は現状発生していない。現行CLI(claude 2.1.278)に--max-turnsオプション自体が無く(--help未掲載)、auto_launcher.pyの着火コマンドにも過去git履歴にも一度も指定が無い。実測:~/.claude/projects配下のトランスクリプトで2751ターンまで進んだ実例あり。ターン数の長時間化はsession_watchdog.pyのHANDOFF_TURNS(80)で検知・引き継ぎする仕組みに置き換わっている。追加の--max-turns明示指定は入れない(存在しないオプションを渡すとCLI起動自体が壊れるリスクがあるため)。
- 2026-10-17（118370）動画制作：Playwright同梱のffmpeg（~/Library/Caches/ms-playwright/ffmpeg-*/ffmpeg-mac）はwebm/vp8専用でH.264もAACも作れない。本物は imageio_ffmpeg の同梱バイナリ（python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'＝ffmpeg 7.1・libx264・aac）。描画はplaywright-core（~/.tamago/node_modules）＋chromium_headless_shell-1234で1080×1920を450コマ、メモリ不足で途中死ぬので再開可能にして100コマごとにブラウザを立て直す。確認ページは main に push しても出ない＝tools/pages_publish.sh（gh-pages）を回す。
- 2026-10-17（118370）design-critique（5観点×10点）で「85点以上」を合格線にすると、スキル自身が『平均8を超えたら自分を疑え』と書いているため、第三者（別エージェント）採点では66点止まりになる。自己採点91→第三者66の差は『見本の実写素材の一撃』『小さい副文の可読性』『数字の見せ場』『CTAの大きさ』。制作者本人の採点を合格根拠にしない。第三者採点は tamago-verifier に画像パスと観点を渡せば90秒で返る。
- 2026-10-19（124962）クラウドセッション（claude.ai/code）は Mac の子セッションからは起動できない：RemoteTrigger は 401 oauth_scope_insufficient（子のトークンに /v1/code/triggers の scope が無い）、CLI `claude --cloud` は対話専用（-p 併用不可）で Mac の CLI login も期限切れ。起動は Dispatch（デスクトップ版 Claude Code）だけ。子は依頼文と body（tools/cloud_launch.py）を用意して outbox に1行、が正しい分担。
- 2026-11-05 宇宙うんこv3滝（206316）：後半が「のっぺり」だった真因＝①上からの補助光(fillB 160)が雲海の起伏の陰影を消していた ②オーロラが山より低く(ct+10〜80)置かれ山の陰で壁紙状に見えた。コードだけ読んでも分からず、実コマ(800・1150)を目で見比べて判明。描き直す前に4コマの試し描き(GitHub Actions・3分)で確かめてから本番に回すのが正解
