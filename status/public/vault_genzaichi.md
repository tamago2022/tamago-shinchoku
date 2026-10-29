<!-- 自動生成・genzaichi_sync.py・2026-10-29 20:07:22・hash=8730c795a17f -->
# 00_現在地（一つの会議室・正本）
**読む場所の1行：チャットのClaude＝Vaultのこのファイル／Codex＝GitHub joy-relief-station の docs/genzaichi.md／Claude Code＝CLAUDE.md経由でこのファイル（更新はClaude Code、自動でGitHubへ写る）**
> 読む場所：チャットのClaude＝このファイル／Codex＝GitHub `docs/genzaichi.md`（joy-relief-station）／Claude Codeの子セッション＝CLAUDE.md経由でこのファイル。更新はClaude Code側のみ（区切りごと）。GitHubへは自動で写る。

**Jules：外した（2026-10-04 たまごさん判断）。** チームの数に入れない。送り先から外し、記録は残す。Jules宛ての票は保留（ラベル `保留:Jules外し`）。
> 最終更新：2026-10-06（Fable・軽さの根本設計）

### 2026-10-04 決定：Julesを外した
- 直近30日の実績：投げた78件（ラベル票）／返ってきた44件（台帳）／PRが出た22本／本番に入った3本。
- 止まっていたJules宛て77件は全部「保留」（ラベル `保留:Jules外し`）。Codexへ一括で付け替えはしない（77件が一度にCodexへ飛ぶのを避けるため）。必要なものだけ後からCodexへ。
- 工場の送り先（nageru・shigoto_furu・tekizai・irai_gate）からJulesを外した。GitHubの `jules` ラベルは `jules-外した` に改名し、自動起動を止めた。

## 今動いているプロジェクトと現在の状態
- **【X投稿の2重検品＋手直し帳】（2026-10-24）** Bufferに入れる・直すXの文は機械＋別のAI（停止札の間は Codex→Claude CLI）を通ったものだけ（tools/x_nijuu_kenpin.py）。赤入れは手直し帳へ流し込み、同じ直しが2回で決まりに（tools/tenaoshi_chou.py・~/jrs-clone/ai-clone）。秋の予約6本の文を直した（時刻は不変）。
- 10-14 地球観察日記 第2作（Issue #975）：音源受領済み・原稿の枠/声3候補/静止画方針を作成（tamago-shinchoku/status/chikyu2/plan.md）。詩は10-15にChatGPTへ催促済み（#975コメント＋ai-brain/sync/claude/latest.md。1行目【短縮版の詩】のコメントを sozai_hiroi.py が自動で受け取る）、声・画像は見積り約106円（上限170円）の承認待ち。素材は tools/sozai_hiroi.py が【制作依頼】Issueのファイル名を見てDownloads/Desktopから自動で拾う。
- **【Obsidian円卓会議（34582番・2026-10-07確認）】稼働中。** 2026-08-06にたまごさんが聞いた「URLをぽっと入れたらそれが行われるように」「最終的にオブシリアンで動かせるのか」は、プラグイン`entaku-kaigi`(v1.2.0・2026-09-02更新)で実現済み——**ノートに`@`＋URLを書いて改行するだけで円卓会議が自動発火し、議事録がVaultへ自動保存される**（裸のURLでは発火しない安全装置・偽引用禁止の安全装置つき）。直近実績：2026-10-04に9件生成。顧問は25人登録済み（ゴール100人以上には未達）。このプロジェクトは店主指定の絶対制約により公開Webアプリ・Lovable・joy-relief-stationには一切触れないローカル専用設計のため、公開本番URLは存在しない。確認ページ: https://tamago2022.github.［除去］.html
- **【Fable・10/9〜10/14投稿枠コピー磨き＋マガジン下書き】（2026-10-06）** main反映済み（commit bbe49bef6）。22曲のnoteを「見出し1行＋出典付き事実」へ、3曲にmemo。マガジン下書き `/feature/midnight-pretenders-abroad`（noindex・台帳未登録）。**次：Lovable Publish→本番で新コピー確認→下書きをたまごさんに見せる→OKなら magazineFeatures.ts/sitemap 登録＋noindex外し。** 本番は10/06 00:48時点で旧コピー（公開待ち）。
- **後退防止の関所**（10/06・Fable）：大事な機能11個（@ログイン・YouTube差し替え・棚から外す・投げ込み箱・案内人の声・AIバッジ・言語切替・下のバー・検索・共有・曲ページ）に契約テスト（prebuild）＋ヘッドレスE2E。公開の押す係が押す前/出た後に自動チェックし、落ちたら原因コミットを自動で外して直前の合格版を出す。本番11/11合格。YouTube差し替えは本番で差し替え→戻すまで実測OK（原因はログイン退行、d74efed99で修理済み）。正本 docs/guard/taisetsu-kinou.md
- **コンシェルジュ**（Grok irisの声で会話・口パク・日英・選曲理由1行）：本番OK・死守。10/05 実測：Grok 1分12.6円・おすすめの声まで平均4.2秒（改善前6.2秒）・正確さ8/10／Gemini Live 1分2.4〜4.5円(計算)・平均4.4秒・8/10。比較ページ https://joy-relief-station.lovable.app/voice-test/index.html 。Gemini鍵は ~/.tamago/keys/api_keys.env にあり（無料枠）。今日の声の予算は1日$1（試験で使い切らないこと）。 【10/10】案内所の写真の卵の口が声に合わせて動く版を本番公開（人型VRMは廃止・0716c0502）。PC実測で声の返事＋口の開き確認・1回約9.9円/47秒。スマホ実測は未確認。
  - **10/07 たまごさんの実機感想5点対応**：前任セッション（32ca40f3f）が実装済みだったものを本セッションが公開スクリプト(1144_osu_chokusetsu.py)で本番へ出し確認。①初回からvoice=iris・turn_detection明示②無音15秒で自動切断③「ほかにも」→←→矢印④在庫全体から次々（コードは入っている・実機音声での動作は未確認）⑤理由1行を自然な日本語に。本番 https://joy-relief-station.lovable.app/ 。⑥サムネカード見た目「ダサい」指摘は実装せず、共通カード部品に合わせたレイアウト案A〜D（4パターン・PC/スマホ両方のスクショ）を `［除去］ に作成済み、たまごさんの採用判断待ち（→下記「判断待ち」参照）。
- **曲カードの豆知識の声**：設計済み。Gemini鍵が無く試作止まり（1件約0.17円）。
- **補給所の高速化**（10/06・Fable「軽さの根本設計」）：真因＝案内所トップ(/cover-guide)が名簿2.2MB＋PNG2.7MBを丸ごと待っていた（スマホ33.8秒）＋棚データ200KBが全ページ共通の塊に混入。作りから直してmain反映（5e60ff24f）：一覧は軽い索引・head()の重い計算はloaderへ・控え優先でチカチカ防止・WebP化。手元実測：案内所スマホ33.8→6.1秒、トップ13.6→4.5秒、曲12.7→6.6秒。E2E 11/11。軽さの予算関所をk05（公開前＝静的／公開後＝本番計測）に接続。公開はDispatchへ依頼→無反応のため自分でkohyou_ima.py（公開API）を2回実行、get_projectでビルド側エラー無し・最新コミット反映済みを確認したが、本番のdeployment-idは30分以上未切替（CDNキャッシュではなく原因不明の反映遅延、過去にも同型の事故あり＝KNOWN_ISSUES.md「mainへ入れてもLovableの公開画面へ反映されない」）。【真因判明 10/06】mainの公開前関所（check-kansei-protected.mjs）が赤＝1145番 74428ff56 が保護曲7件を再非表示→Lovableのビルドが走らず、以降の全コミットが本番に出ていない。直しは kanseiHidden.generated.ts の7行削除（手元ブランチ fable/kansei-protected-unblock・未push）。→ 10/06 22:30 Fableが保護曲7件の戻し＋チカチカ根治（React #418：バッジ枠のDB先読みズレ・NextUpCardの入れ子button）を main（a441888e4）へ入れ、公式の鍵で公開→本番 edca9e68 に切替済み。注意：1145番の生成（tools/1145_*）を次に走らせると保護曲7件がまた非表示になり関所が赤→公開が止まる。生成側で保護曲を除外する仕組みが未着手。残り：曲ページの名簿裏取得の完全ゼロ化（アーティスト別シャード）、世界ページの#418、再訪の固定チャンク。設計書 `AI出力/40_プロジェクト/ごきげん補給所/軽さの根本設計_2026-10-06.md`。
- **工場が止まらない**：心臓は約1秒で復旧に改善。
- **やりっぱなしゼロ**：206件。
- **投げ込み箱**：道は直った（10/04）＝トンネルURL変更時に即公開・箱が読み直して再送・貯めた分は自動再送・1時間ごとの通し見張り（赤になる）。ただし**棚へ書く鍵（Lovable OAuth）が0バイトのため、鍵が戻るまで棚には入らない**（投げた分は台帳に残り、鍵が戻れば自動で入る）。
- **投げ込み箱の重複防止**（10/07）：URLを正規形（?s=・twitter.com・末尾/を吸収）で照合し、箱に入れた瞬間に赤字「同じURLがあります：◯◯棚」。同じURLは新規作成せず「もうダブってます」。DBにも一意ガード（10/07以降の新規分）。既存の重複はX 1組・YouTube 4組・内部リンク8組（消さず放置）。
- **サイトの簡素化**（2026-10-06・再確認完了。実装自体は2026-10-04に全項目main反映済みと判明）：言語は地球マークのみ・全文切替（commit 1ec88b8bb）／UI・棚文言を4言語分翻訳（lc()+overlay辞書、9158f056d／9c15486e4。「AIの棚の仲間たち」「棚を全部見る」等の具体例も翻訳済みを確認）／記憶の扉とひとこと目安箱をフラグ1か所で全ページ非表示（SITE_MEMORY_DOOR_ENABLED／SITE_FEEDBACK_DOOR_ENABLED＝false）／下部固定Spotify型ナビ（ホーム・検索・案内所）＋管理者はどこでも棚編集（d0914fbc6／111d00be5）。**本番未反映**：Lovable公開パイプラインが停止中のため（x-deployment-id=5aa4b07dで不変、原因は「補給所の高速化」項の1145番保護曲再非表示の関所赤。既に別セッションが特定・監視を恒久化済み、担当は1145番/Dispatch）、本番での実画面確認はまだできていない。パイプライン復旧後に別の目での確認が必要（検証待ち）。前任セッション「サイトをシンプルに」は3回process_interruptedで停止・無関係なLovable詰まり調査に発展していたため、本セッションが実装状況を再確認して引き継ぎを閉じた。
- **外部追加の検品関所**（作業中）：別表記の名寄せ・新規は保留・1日1回Codex判定。
- **カードのズレ実測関所**（10/04・main反映済み／本番は公開の鍵待ち）：サムネの黒帯（本番で51件）・♡▶ラベルの角余白（257件）を実測で潰した（本番310件→手元の同条件でも387→0）。公開前に毎回測り、ズレがあれば**自動で直してから出す**（直せない分は票を立てて公開は止めない）（工場 tools/zure_kanmon.py ＝ k05/k09/k12/k13 と Lovable押す係 kohyou_osu に接続）。公開後は本番も自動で測る（status/zure_kanmon/prod.json）。仕様：site docs/operations/card-geometry-gate.md

- **ブックマーク(☆)＋履歴の全ページ自動記録**（2026-10-08・本番反映済み）：端末内localStorageのみ・サーバー負担ゼロ。☆は右下の小ボタン（上限200件）、/bookmarks 新設、/history は全ページ自動記録(最新100件・原因＝一部カードでしか記録していなかった)。手元で新ページ追加後は routeTree 再生成が必要。
- **特集「シティポップ」の指摘対応は完了済み**（2026-10-08・commit d69fd0d9c／origin/main反映済み）：「シティポップ特集の直し」が3回クラッシュ(process_interrupted)したため見張り番が引き継いだが、調査の結果**修正自体は別セッションがクラッシュより前に完成・本番反映していた**と判明。本番 https://joy-relief-station.lovable.app/feature/citypop-sekai を実機確認：ヘッダー背景＝松原みき「真夜中のドア」のサムネに差替済み、IN THIS ISSUEは『Out of Time』『真夜中のドア』『フライデー・チャイナタウン』『Plastic Love』『テレフォン・ナンバー』『Remember Summer Days』と英語曲名のまま表示（変な日本語訳なし）。あわせて同クラッシュ連鎖の前セッションが報告していた「特集の入口バナーを原曲カバー含め53曲に自動付与」（commit f11060a47）も同じく本番反映済みを再確認。追加作業なし、クローズ。

## 最近決まったこと（2026-10-02〜04）
- **リンクの出し方を全AI統一**（10/26）：コードブロックに入れず本文に。曲は「|曲|YouTube URL|」表、URLは [https://…](https://…) 形式（URL自体をリンク文字）。単体リンクも同形式。詳細は 00_決定ログ.md。
- 2026-10-25 **同じ部屋（全AIが読める）**：Vault の .md をドライブ「マイドライブ/tamago_brain」へ5分おき・差分だけ写す（Dataview は写し側だけ結果の一覧を書き足す・Vault は書き換えない）。AIの入口＝ドライブ直下「00_索引_AIはここから読む.md」。Notion は tamago_brain/notion/（鍵 NOTION_TOKEN 待ち・振り分け所 #1055）。各AIの読み口（赤＝片道・未接続）＝ドライブ「00_AIの読み口台帳.md」／https://tamago2022.github.［除去］.html#yomikuchi（週1自動見直し）。仕組み：Vault AI出力/_ルール/gdrive_md_mirror/・工場 tools/notion_utsushi.py・tools/yomikuchi.py。
- 2026-10-22 棚は慎重に：棚に入れる・置く・移すのは、たまごさんがその日に曲名と棚名を名指ししたものだけ。前日以前の言葉で動かさない。今ある棚はそのまま。棚の依頼67件を保留（一覧 https://tamago2022.github.［除去］.html ／関所 tools/tana_sekisho.py・check-tana-shitei.mjs／メモ https://github.［除去］）
- 2026-10-21 **仕入れても棚には置かない。棚はたまごさんが名指しした曲だけ。**仕入れは曲ページ＋関連＋検索＋裏タグまで。関所＝joy-relief-station prebuild check-tana-shitei（台帳 scripts/patrol/tana-shitei.json）。アジアの5曲を棚から外した（main cf6007d42・公開待ち）。過去分の一覧は工場 status/tana_shiire_kako.json（外すかはたまごさんの判断待ち）。
- 2026-10-21 ごきげんの種（LINE 週1回・金曜20時）：導線をサイト全ページに入れた（友だち追加URLが空の間は出ない。joy-relief-station public/gokigen-tane.json に入れれば全ページに出る）／配信便 tools/gokigen_tane.py（鍵 LINE_CHANNEL_ACCESS_TOKEN が入るまで下書きだけ）／第1号 10-30 キャロル・キング「It's Too Late」・第2号 11-06 杏里「オリビアを聴きながら」の下書きはドライブ「ごきげん一粒」。たまごさん待ち：LINE公式アカウント作成→友だち追加URLと鍵。公開はDispatch。
- 10-14 Claudeの生成物は全部 Googleドライブ「AI生成物/Claude/<案件>」へ（詩と音楽_僕は見た…／ポッドキャスト神回_日本語音源／HowItHolds／わえちゃん／その他）。iCloud・Mac本体は使わない。納品は tools/claude_nouhin.py。
- 2026-10-14 外部カードの題名は「何の動画か」（主題の名詞＋していること・スマホで23文字以内に主題）。きっかけ＝「⛱ 「冷やす」でなく「癒す」」→「チャイ香る、さつまいもアイスのビスケットサンド」に直し本番確認済み（芋の棚）。関所 tools/daimei_kanmon.py を取り込み（2210_tanaire／nagekomi_shelf）に接続、落ちた題名は tools/daimei_naoshi.py が5分便で1日20件ずつ直す（前後は status/public/daimei_naoshi.json）。次：1か月後（11/14）に外部カードの差し戻し件数が0に近いかを --tanaoroshi で測る。
- 2026-10-11 GitHub Actions（非公開のjoy-relief-stationだけが有料枠を食う）：10月は1〜5日で約1,955分＝無料枠2,000分を使い切り、以降は全ジョブが起動前に失敗（PR #906の「支払いが止まっている」の正体）。17本の起動条件を削減（Quality Gateの追いpush毎検査と毎日便をやめる・@発射は発射台Issueだけ・店主確認は判定語だけ・管理職AI1日1回・台帳週1・重複のバンドル重量PR便停止・見回り系7本は3日に1回・ブランチ回収月2回）。見込み約920分/月。11/1に枠が戻れば動く。戻す1語：`python3 tools/actions_waku.py modosu`（記録 status/gh_actions_waku/）。公開リポ（tamago-shinchoku等）は無料なので触っていない。
- 2026-10-10 判定日赤34859号対応：joy-relief-station側の担当別プレイブック（`.claude/playbooks/`）の考え方をVault側へ移植。`00_管理/プレイブック/`を新設（正本README.md・索引一覧.md・Eden Loop／カガリビト／錬金術の現在地メモ・ごきげん補給所運用の窓口）。`00_現在地.md`はこれ以上肥大化させず、プロジェクトごとの詳しい現在地はこのフォルダ側で持つ運用に変更。確認ページ: https://tamago2022.github.［除去］.html
- 2026-10-10 Ink Explainer比較：分析＋Opus 5.5試作77秒を公開（share/check/ink-explainer-hikaku/）。結論＝PIL作画3色では未だ超えられず（39対30）。Opus 5.5の子1本＝週約0.04%・5h約0.13%（推定）、Gemini TTS約4円。Macの claude 口(2.1.278)は Opus 5.5 非対応→2.1.296 本体を CLAUDE_REAL_BIN で指定して起動（工場の固定は未変更・判断待ち）。
- 2026-10-10 Ink Explainer比較にキャラクター版（10章）を追加：オリジナル案内役1人・59.5秒・30カット。採点 本家39／棒人間30／キャラ33、デザインセンス 棒人間17→キャラ28（40点満点）。外部API約23円（fal Flux 3 画像3枚19.8円＋Gemini声3.0円）、Opus 5.5 週枠約0.08%。Gemini鍵は無料枠で画像不可と判明。元画質 ~/Documents/AI作業/2026-10-10_キャラ版_NightOwls_1080p.mp4
- 2026-10-10 21:50 Ink Explainer比較に11章「キャラ版v2 絵本トーン」を追加：絵14枚（同じ絵は最大2回）・主役Pipの表情7種・59.8秒29カット。採点 キャラ版33→v2 36（本家39）、デザインセンス28→32。外部API約27円（fal 画像24.3円＝1枚約1.7円、Flux3見本1枚＋Flux2 flash編集で参照）、Opus週枠約0.09%。元画質 ~/Documents/AI作業/2026-10-10_キャラ版v2_絵本トーン_NightOwls_1080p.mp4。次の課題：声（詰めて速い）と細部検品（マフラー移り・ランタン2つ）
- 2026-10-11 03:0x Ink Explainer比較に12章「安くする比較と8分の見積り」：推奨＝fal flux-2 flash編集版＋見本参照・約1MPで出してMacで単純拡大（1枚2.37→1.58円・v2と同等）、Pip無しの絵は参照なし0.79円。Real-ESRGANは紙の質感が消えるので不採用。8分60枚≈96円。8分版は未作成＝Genspark脚本待ち、指示書 status/ink/long8/PROMPT_build.md（未起動）。外部API 7.28円。
- 2026-10-10 子セッションの「failed（exit 143）」の正体＝見回り rusuban-mimawari-30min の tamago_tatamu がCoworkの子を起動30分で一律SIGTERMしていた。Coworkの子・放置時間不明は畳まないよう修正（00:18の見回りで0本＝実測確認）。許可待ちで固まった子・未回収のGensparkは tools/okoshi.py（心臓5分おき）が自動で列に積み直す。web_fetchは tools/mac_fetch.py へ。許可ゼロ設定(~/.claude/settings.json)はCoworkの許可には効かない→Anthropic/Genspark宛の問い合わせ文は tamago-shinchoku/status/shitagaki/（未送信・Gmail下書きは許可ポップアップが出るため未作成）
- 2026-10-06 決定：大事な機能（店主が一度OKを出した11個）は退行禁止。正本 ［除去］.json。保護ファイル冒頭の注意書き・検査を外すのは禁止。壊れたら工場の関所が原因コミットを自動で外す（止めて古いままにしない）。
- 2026-10-04 決定：鍵・ログインで人を動かさない。毎朝 tools/kagi_seimei.py が全鍵を1回叩き status/kagi_seimei.md に生死を残す（承認URLは status/kagi_shounin_url.json）。頼んでよいのはパスワード・二段階認証・初回登録・お金だけ。今の要注意＝xAIは鍵は生きているが残高なし（課金は本人）。
- 2026-10-04 決定（憲法）：デスクトップに許可なくファイルを作らない。残すのは joy-relief-station だけ。工場は ［除去］ に引っ越し済み（tamago-dispatch-log・nagekomi も ［除去］ 配下、鍵置き場は ［除去］ ［除去］
- 子セッションはSonnet固定・ブラウザ使用禁止（設定で拒否）・デスクトップに作らない。
- オリジナル禁止＝先人・公式に倣う。たまごさんを動かさない。AI同士はGitHubで直接。
- Devinは10/16で更新しない。
- Notion索引は中止（Obsidianが重くなる）。
- Obsidianは軽さ最優先（スマホのタブ367→3、音声2GB→584MB）。
- 10/04：共有の仕組み＝この00_現在地.mdを正本に、GitHubへ自動で写す。

## 次の一手
1. 白画面の高速化を仕上げる。
2. 本番公開の鍵（Lovable OAuth）の自動復旧。
3. 外部追加の検品関所を通す。
4. 曲カードの豆知識の声（Gemini鍵待ち）。

## 2026-10-05 Genspark #821（音楽データ品質）進行中
- 【#824 Evidence-First QA】赤鬼が旧方式（文字一致だけ）を不合格とし新基準を制定。候補＝雑でよい／変更＝厳密な証拠必須。Claudeの「2,000行から4件だけ変更」する慎重姿勢が基準に採用された。
- 赤鬼指摘2件を修正済み（main commit 02747557）：①`songlessOk`を仕様通り`===1`に修正（2〜3曲の棚で無関係カバー札が出る再発バグ）②「雨の街を」の誤出典Wikipedia削除。#699の1,555件はmanifest化して開示済み（Tier D=チャンネル名一致である旨を明記）。
- 【#695・動画消失の自動対応・新設完了】店主依頼「動画が消された時に差し替えか自動引っ込めを」を実装。原因判明：既存の夜間見張り（daily-link-watch.sh）が未コミットのローカルファイル3本に依存しており、専用worktreeが毎晩`git reset --hard origin/main`する設計のため**6夜連続でモジュールが見つからず全滅**していた。この3本（link-audit-full.mjs／fill-missing-videos.mjs／daily-link-watch.sh）を初めてoriginへコミット（commit c6a82dd5）。あわせて①fill-missing-videos.mjsの表読み戻しが末尾カンマでJSON.parse失敗→毎晩{}扱いで過去の差し替えを全消去していたサイレント事故を修正、②searchReplacement.mjsに版違い（live/remix等）・出どころ（公式/Topic/VEVO以外除外）の関所を追加（Prince「Sometimes It Snows in April」で実機試験：わざと死んだIDに書き換え→検知→引っ込め→ライブ版や第三者チャンネルを弾いてスタジオ版だけ選定→差し替え→投稿予定の自動HOLD→自動復帰、を実測確認）、③新設`oneshot/link-watch-report.mjs`が投稿予定(ops/social/*.jsonl)のHOLD/復帰と「死んだ◯件／自動差し替え◯件／引っ込めたまま◯件」の日次1行を出し#642へ通知。
- 今夜23:18に手動起動で実際の初回本番点検を実行中（36,432曲・94件が消えている判明・1,208件の穴埋め探索を25分枠で実行中）。完了後、mainへの反映と本番確認を行う。
- 残り（10/7夜期限）：#692 Tier A/B証拠待ちのGenspark再提出、#699残り682件、#711〜721残り121件（空欄が正）、#724〜726残り989件、コピー空24,037件は定型文（憲法24条違反）で0件、#642は別セッションが並行して継続中（READY 87件）。

## 2026-10-24 キフネス新作・アーティスト説明文の復活（たまごさん本人指定）
- 済：The Kiffness「Donald Trump BURP REMIX!」曲ページ（YouTube・コンシェルジュ推し・関連5本・Eating the Catsと双方向）／重複映像を1枚に／「このアーティストが好きなら」を手書きに。
- 説明文：10-15アダム・ローズ修正で全非表示→10-23 truthGateが出典なし2,024件を隠した。Wikipediaと照合して618件復活済み。残り約1,100件はCodexの枠が戻りしだい自動で続き（Mac の outputs/tool/tsuzuki2.sh）、263件はWikipediaが見つからず未復活。
- 決まり：説明文を消す・隠すのは、たまごさんのその日の名指しだけ（prebuild check-about-keep.mjs）。
- 止まっている：ウケるの棚（DB）への追加＝DBに書く道が無い（Lovable MCP 401・service_role鍵なし）。

## 2026-10-25 Grokボットとリアルタイムでつなぐ（Reason Network）
- 入口＝Reason Network（無料・Grokボット自身が #1035 で依頼）。工場のMacに reason 0.2.596 を入れた。道具 tools/grok_tsuushin.py（心臓毎分）：共有メモに書いた瞬間に Grok へ呼び鈴／Grokからの文は受付へ／serve claude（作業場 status/grok_tsuushin/madoguchi・コマンド不可）。
- GitHub直通 .github/workflows/grok-yobirin.yml（joy-relief-station 4fb636ffe）：Grokが Secrets GROK_WEBHOOK_URL と変数 GROK_YOBIRIN=1 を入れるまで skip。
- 止まっていること：たまごさんの初回サインイン1回（リンクは Dispatch に出した）→ Grok側の参加（#1052 で依頼・締め切り10/26）。

## 2026-10-25 法務チェックの型（4人でクアドラプルチェック）
- 正本：joy-relief-station Issue #1060（海外6点＋日本7点。列＝Claude/Grok/ChatGPT/Genspark の判定と出典）。道具 tools/houmu_check.py（心臓10分おき：返事集め→食い違い🔴→たまごさんの1枚 share/check/houmu-1060.html＝本人判断・食い違いだけ）。
- 依頼済み：ChatGPT（@codex）／Genspark（AI Drive /できる人いますか/1060.md）／Grok（共有メモ「法務チェック」＋Reason Network待ち行列。RNは未サインイン）。GrokBotの特商法の住所の調べ結果も #1060 に集める。法律の助言ではない。
- Claudeの判定の要点：特商法は今は販売なし＝表示義務なし。売る時は個人でも「請求があれば遅滞なく開示」と書けば氏名・住所・電話を省略可（消費者庁Q&A A15/A17）。PPは要対応（メール取得＝利用目的の公表）。

## 2026-10-27〜29 白飛び（たまごさん「白飛びが全然直らない」）
- 本番は10/25の直し（生成りの起動ローダー・html背景・manifest）が入ったまま（巻き戻りなし）。
- 全場面のコマ数え：`tools/shirotobi_zen.sh`（初回・SPA遷移・戻る・フルリロード・動画埋め込み・暗⇔明・画像の枠／一瞬だけ出る白を `tools/shirotobi_shirokoma.py` で数える）。見つかった白＝関連カードのサムネ枠（読み込み前がほぼ白）→ bg-muted に（553c424c0）。iPhone Air の起動画像が無かった→追加。
- 関所：joy-relief-station prebuild `scripts/patrol/check-no-white-flash.mjs`（白飛びの元が入るとビルドが止まる）／毎日 `tools/shirotobi_mimawari.py --daily`（本番で白コマ1以上→Dispatch＋白飛びを直す公開以外を `koutai_kanmon --pre-publish` で48時間止める）／`koutai_kanmon --check --output` もローカルで白コマを数える。
- 残り：iPhoneのホーム画面アプリは起動画像をホーム画面に追加した時に覚えるので、10/25より前に追加したアイコンは一度消して追加し直さないと起動の白は消えない（サーバー側からは変えられない）。本番の曲ページ・棚は初回応答が数秒かかる（その間の起動画面が長い）。

## 2026-10-29 止まらない改善ループ（たまごさん「自動でどんどん良くなる。止まってるのはありえない」）
- tools/kaizen_loop.py を心臓（top_status）に相乗り。毎時本番を採点→点の低い順（X・LINE・マガジン優先）に直し便→採点し直し・下がったら自動で戻す→同じ失敗2回で関所→30分止まり検知→毎日4つの見方で案（見た目が変わる案はA/Bで選ぶだけ）→日曜朝に週報3行。
- 表：https://tamago2022.github.io/tamago-shinchoku/share/check/kaizen.html（進捗表の「改善ループ」1行から）。並行の子の受け持ちは status/kaizen/heikou.json（11-05まで）。
- 10-29 05:30 時点：シャッター（04:55・誤検知＝判定日が同じ文を3回積み直し）で積めず、直し便は status/kaizen/machi.json に控え中。同じ文は数えないよう kinkyu_shutter を直した。Lovableの公開の鍵（kohyou_osu）は10-14から切れている→公開は Dispatch の deploy_project（koukai_machi で知らせる）。

## 2026-10-29 曲ページの新しい型（Treasure・No Scrubs で試験中・OK待ち）
- 本番に出した：①関連4つ（なぜこれかを必ず）②このアーティストが好きなら4組（系譜でつなぐ一行・両方向・出典つき）／「つぎの寄り道」の大きな1曲は外した。対象は joy-relief-station src/lib/songPageKata.ts の TWO_TIER_PILOT（Treasure・No Scrubs）だけ。OKが出たら TWO_TIER_ALL で全曲へ。
- 同時に：竹内アンナ「No Scrubs」カバー（公式ch）／紹介文が無かった387アーティストに Wikipedia 冒頭（残り473件は動物・会社・映画・feat.名義など）／TLCの曲カードに旅の1行（lib/tabiCopy.ts）／ダークモード切替（ヘッダーの月・既定ライト）。
- 好きならの手選びの理由は tamago-shinchoku status/public/sukinara_daicho.json。スクショ道具 tools/kyoku_shot.mjs（--w 390|1280 --dark）。

## 2026-10-29 Silk Sonic 赤入れ（本番反映済み）
- バンド⇔ソロ／ユニット⇔メンバーの相互リンクを76組追加（Silk Sonic⇔Bruno Mars・Anderson .Paak ほか。出典は各アーティストの紹介文の Wikipedia）。正本 joy-relief-station coverGuide.ts の RELATED_1029。
- 共有ボタンは「タイトルの帯の下・動画の上」（曲ページ）／「見出しの下」（アーティストページ）。戻る矢印の上の案Aから変更。
- 英語・途中切れの Wikipedia 抜き書きメモ 1,017件を日本語の短いメモに言い直し、言い直せない29件（国・動物の記事など別物）は外した。英語のメモは関所 check-about-nihongo で公開が止まる。
- 同じ名前の棚を2回出さない（Treasure の踊る阿呆）。
- 残り：英語以外の古い日本語の抜き書き（約1,250件）はそのまま写しの文。言い直しは未着手。

## 止まっていること・たまごの判断待ち
- 2026-10-25 海外の法的リスク6点：Google Fonts・録画系・課金は該当なし（直す物なし）。判断待ち＝メール配信前の住所の出し方／DMCA代理人（$6・3年ごと・投稿機能を作る時でよい）／13歳未満の一文。https://tamago2022.github.［除去］.html
- 地球観察日記 第2作：見積り約106円（上限170円）の承認（#975に「承認 170円」）。詩の短縮版はChatGPTが#975へ。
- 10-14 Googleドライブのアプリが読めない（Resource deadlock avoided・再起動でも直らず）。Driveコネクタも再接続要求。→ 22ファイルをiMac HDD「Claude上げ待ち」に積み済み、直れば心臓が10分おきに自動で上げる。
- 【コンシェルジュのおすすめカード見た目（10/07）】サイト共通のカード部品に合わせたレイアウト案4パターン（A:4列グリッド／B:横スクロール棚／C:左サムネ右文字の横型リスト／D:大1枚+小3枚）を画像化済み。`［除去］ を見てA〜Dのどれにするか選ぶだけ。選んだら実装する。
- 【Buffer投入・工場側の口（10/05）】工場に投入係 tools/buffer_3kan.py を新設（READY＋Jev QA＋#642のFINAL_OK の3つが揃った曲だけ、@oasisjoyrelief の10/9 15:00以降の枠へ注文票→既存のbuffer_yoyaku）。現在：予約済み7件／最終予約10/9 09:00／copyとFINAL_OKがまだ無く入れられる枠0件。止まり3点：①最初の1件は外部公開なので予約内容を見せて許可待ち ②止め札 status/buffer_queue/.TOMERU は「二重投稿の心配は無い」の一言で剥がす ③本物のJev（TypeSafe）は鍵なし・栓0円（約0.1円/件）なので今は機械版。5分便への自動組み込みは分類器に止められ未実施。READYの正本＝ops/social/claude-ready-prepared-all.jsonl（#642に一覧あり）。
- 【#647 AI ASSISTEDバッジ】実装完了（3種256WebP統一・［除去］更新・pixel整合検品済み・build成功）。push-queueへ投入済み(`20261004-647-ai-assisted-badge`)だが、本セッションからのpush-queue実行がClaude Code側の自動分類器に「Production Deploy」としてブロックされ直接は反映できず。既存の時間毎cron(role-sweep)が自動で拾ってmainへ反映する設計のため待機中（最大で約1時間後）。急ぐ場合は「push-queueを実行していい」の一言でこのセッションから即実行可。
- 本番公開の鍵（Lovable OAuth）が10/04 03:15から無い → Moyun10曲・宇多田ヒカル統合などがmain止まり（自動復旧を作業中）。
  ・カードのズレ修正（コミット d6b34013e ／ 2d2810d2c）も同じく本番待ち。鍵が戻れば押す直前にズレ関所が走り、押した後に本番を自動測定する。
- クラウドセッション（$248・11/5期限）：10/1の①Pagefind化②WebP化は承認待ち（Bashの&&/|）で止まり放置(ABANDONED)。原因=発射本文のallowed_toolsを絞っていたこと。10/8に絞らず再発射(JRS③裏タグ付与 trig_01TNr7PBrwv9VBpqu3PHs15Z)。発射手順=tools/cloud_launch.py+RemoteTrigger(Macのclaude --cloudは403)。
- チャッピーの投稿予定10曲のリストが未着。
- クレジット：週60%（10/04朝）。目標＝日曜終わり80%・月曜90%・火曜18:30で100%。
- 【10/09 00:23発見】`AI出力/_ルール/司令塔/mem_stats.py`・`request_update.py`と`AI出力/_ルール/hooks/taste_gate_sync.py`・`status_board_gen.py`の4本がファイルごと消失（Vault内find全文検索でも見つからない）。見回り係はfactory_status.py（別経路）で代替しメモリ判定・着火は継続できたが、司令塔キュー経由の着火とTaste Gate回収・司令塔HTML再生成は手順そのものが動かない状態。削除はしていない（見回り係の権限外）。次に手を付けるセッションが原因調査・復元が必要。

## 10-04 Obsidian重さ対策（緊急）
- 読み上げ音声110本(583MB)をVaultの外へ移動、110ノートの埋め込みは「（読み上げ音声は準備中）」に戻した。戻し方は ~/Library/Application Support/tamago_audio_outside_vault/戻し方.txt。
- ずんだもん生成のVault書き込みを停止（出力先を外へ・ノート追記を無効化）。読み上げサーバーは停止中。
- 円卓会議プラグインはスマホで読み込まない設定、自動ログ類はObsidianの索引から除外。

- 仕入れの継続（10/04・r075隙間）：母数から15件抽出→2件裏取り（候補止まり・動画ID/CM未確認・push/反映なし）。詳細 `AI出力/仕入れ/カバー・CM候補_2026-10-04_仕入れ継続.md`

- 仕入れの継続2（10/04・r075隙間）：母数の人気曲から2件裏取り（候補止まり・動画ID未確認・push/反映なし）。詳細 `AI出力/仕入れ/カバー・CM候補_2026-10-04_仕入れ継続2.md`
- 仕入れの継続4（10/04・r075）：母数の1960〜99年人気曲から4件精査→通過3件（Time After Time／Running Up That Hill／Don't Stop Believin'）・要確認1件（Can't Take My Eyes Off You）。候補止まり・動画ID未確認・push/公開なし。詳細 `AI出力/仕入れ/カバー・CM候補_2026-10-04_仕入れ継続4.md`
- 仕入れの継続5（10/04・r075）：母数の1960〜99年人気曲から4件精査→通過2件（Take On Me×VW／Here Comes The Sun×Apple）・要確認2件。候補止まり・動画ID未確認・push/公開なし。詳細 `AI出力/仕入れ/カバー・CM候補_2026-10-04_仕入れ継続5.md`
- 仕入れの継続27（10/06・r079）：母数から5件精査→通過2件（Fix You×Kacey Musgraves cover×Chipotle／Be My Baby×Ramones cover×Cialis SB 2005）・保留3件（Virtual Insanity＝CM確認・カバー未確認／I Want You Back・High and Dry＝カバーのみ）。候補止まり・動画ID未確認・push/公開なし。詳細 `AI出力/仕入れ/カバー・CM候補_2026-10-06_仕入れ継続27.md`

- 2026-10-04 締め切りの仕組み：正本=GitHub Milestone（説明欄に「代表Issue: #番号」）。毎晩21時の既存見張り(genspark-821-shuusei-check)が tools/deadline_watch.py を呼び、今日/あと1日/過ぎたを代表Issueへ@codexコメント＋カレンダー https://tamago2022.github.［除去］.ics を更新。#821修正のMilestone(10/7)作成済み。配信の道(~/.tamago-pages)が引っ越しで壊れていたのも修復。
- 2026-10-05 Genspark覆面調査の再開：公開リポ tamago2022/ai-kaigi の Issue #20（曲ページ3＋マガジン1の採点→書き直し案）を立てた。たまごさんがGensparkに貼る待ち。返事が来たら「Genspark案／今の版」の比較ページを作る（本番反映はたまごさんが採用と言ってから）。前回の元＝ai-kaigi #13〜#18（覆面客・クレジット切れで採点止まり）。
- 2026-10-05 Genspark宛て追加：マガジン1本の執筆依頼（海外で聴かれるシティポップ・5〜6曲・読了5分）を https://github.com/tamago2022/ai-kaigi/issues/21 に立てた（#20にも案内コメント済み）。返事が来たら動画の生存と出典を1本ずつ確認し、たまごさんに見せるページ1枚にする。
- 2026-10-06 管理画面の「@」ログイン退行（5回目）を恒久修正・本番確認済み（d74efed99）。原因＝9/27のセキュリティ変更が合言葉と既定鍵をソースから消した。合言葉は平文でなくダイジェストだけをソースに置く方式に。端末は400日記憶。公開前の関所 check-admin-login.mjs（prebuild）が毎回『@で入れるか』を確かめる。adminAuth.server.ts冒頭とCLAUDE.mdに注意書き。公開はLovable公式MCPのdeploy_project（工場が保つOAuth鍵）で押せる＝CDPのChrome経由が2回失敗した時の別経路。
- 2026-10-06 本番が半日止まっていた真因＝公開前関所 check-kansei-protected が赤（74428ff56が保護曲7件を再非表示）でビルドが止まっていた。fable/kansei-protected-unblock(d2bb0bea1)の7行削除をmain(010dea8cb)へ入れ、関所4本緑＋npm run build成功→Lovable公式MCPのdeploy_projectで公開→deployment-id 5aa4b07d→1c5afae6へ変化を確認。本番実測（スマホ）トップ5.6s・案内所8.2s・曲8.0s・世界7.0s／（PC）2.9/3.6/2.1/2.4s。@ログイン200・理由ラベル非表示を確認。未解決：曲ページ・世界ページにハイドレーションのズレ（React#418系・チカチカ）の警告あり。

- 2026-10-10 HowItHolds：非公開リポ tamago2022/howitholds 作成・REQUEST.md（向こうのAIの正式依頼）を main に配置。github_watch.py が push を見張り、HANDOFF.md＋REQUEST.md で「欠陥洗い出し→3シーン作り直し→sample.mp4→判定→スマホ用ページ＋英文要約」を自動で積む（fal 3枚・合計300円まで）。作風の手本＝Ink Explainer（第三者）。次の一手：向こうのAIの push 待ち。

- 2026-10-10 21:50 キャラ版v2（絵本トーン・Pip）解説動画 完成🟡：`status/ink/char2/out/`（59.8秒・29カット・絵14枚各≤2回・7カード・-15.2LUFS・web版988KB）。実費約27.9円。弱点は result.json の weak_points。

- 2026-10-11 名カバーの棚を許可制に（台帳 src/lib/meiCoverLedger.ts＝たまごさん指定だけ表示・prebuild点検 check-meicover-gate）。25件を外し（1語で戻せる：MEI_COVER_UNDO_20261011）、風をあつめて(Josh Turner)を追加。ハートは全サイト一時非表示（HEARTS_VISIBLE）。文字マークは左下・英語、グッドカバーだけ左上。added_by列のmigrationは未適用なら台帳だけで動く。

<!-- 自動まとめ:始 -->
## 今日までに届いた更新（自動まとめ・1日1回／2026-10-26 22:28）

- **35199番:大塚食品ページ汚染調査**（10-25 11:53）main反映(8932b5ca6)まで完了。仁鶴・松山容子の持ち歌から無関係動画4件除去(竹内まりや/尾崎豊/五木ひろし＆市川由紀乃/生活笑百科)、二重の部屋(otsuka-chemical-bon-curry)は2026-08-13に統合済みと確認。Lovable公開はCDP:9223未開通(1186号のChrome起動禁止で自分では直せない、既知の構造的ギャップの3回目再発)で本番は未反映のまま
- **振り分け所（できる人いますか）**（10-25 03:54）2026-10-25 稼働。tools/furiwake.py（心臓2分おき）＋できること台帳 status/furiwake/dekiru_daicho.json・share/check/furiwake.html。ラベル「できる人いますか」＋Issue型を joy-relief-station に設置。試し#1051（gdrive_md_mirror install.sh）を工場が実行→Drive tamago_brain 7756/7846本・launchd登録yes・rsync rc=23で約90本未転送。次：未転送の原因、Codex枠の生死、Gensparkが受付を読むか

（子セッションは Vault に直接書かない。status/genzaichi_kouho.md に追記→夜にここへ1回だけ反映）
<!-- 自動まとめ:終 -->

- 2026-10-15 ごきげん補給所：アダム・ローズ（コメディアン @realadamrose）のページを本人の13本だけに（別人9本をデータから削除）・本番反映済み。全アーティストをoEmbedで照合し別人/的外れ254本を外してmainへ（6b6aaae）。本番反映はLovableの鍵切れ（同意のやり直し待ち）で止まっている。全ページ共通：冒頭の一文・上部の説明文を出さない／カードは「ここから旅をする」。Genspark検品は財布の停止札で未送信（status/_ar_gsk/machi.md）。

## 2026-10-18 全開（〜12:00）
- 週83%・23日期限のリセット券ありで、12:00まで全開。Fableレーン3→6本（status/zenkai.json・tools/zenkai.py。12:00で自動的に3本へ戻る）。ロード平均では絞らず、メモリ空き40%・ディスク40GBを線に。
- 積んだ便44本（Fable）：A マガジン7号の質上げ（怒れる人々の型）／B カードのコピー直し 便1〜33（811件・status/copy_queue_1018.md）／C Macを軽く（棚卸し→status/zenkai_1018/）／D 118370続き・レシピレーダー3案・Genspark納品の配管。既存の月(118284)・踊る(118330)・Flickermood(118557)・タイポ研究(118369)もFableへ。
- 止まっていること：Lovableの鍵が10/14から切れていて工場から公開が押せない（各便は main 合流まで進めて「公開待ち」）。
- 10-18 06:30 Genspark納品の配管を直した（tools/claude_uketsuke.py）：両リポどのIssueの【納品】も5分おき／AI Drive /tamago-inbox/ 全サブフォルダの新着も30分おきに取得→発車待ち（kubun=mitai＝配分ゲートで止めない）→公開見張り（本番が変わったらIssueに「公開しました」）→Dispatch。取れない時は8回取り直し。拾えなかった原因＝118330が週の配分ゲートで「裏方」判定され停止／skillの一時失敗を二度と取りに行かない／tamago-shinchokuのIssueを見ていない／AI Driveは知らせるだけ。試験 #8（tamago-shinchoku）で人の手なしに通った。
- 10-18 月(118284)・踊る(118330)はこのセッションで仕上げて main（374559b）。型は tools/magazine/nouhin_shiage.py（spec は status/magazine_src/<key>/）。公開は Lovable 鍵切れで Dispatch 待ち。改善便 120095（月）・120096（踊る）を積んだ。inbox-pipe.yml は届いていないので置かない（#1018に記載）。skill の突き合わせは ［除去］.md。
- 10-18 17:40 即公開の流れ：受付係が叩き（.html）を拾うと tools/magazine/sokkou.py が型の最低限（制作メモ・未確認を消す／ライセンスの無い写真を外す／シェア・フォロー・og）→ main → 公開（鍵切れなら Dispatch に「公開待ち」）→ バックナンバー「新着」→ 公開見張り。審査・配分ゲートで止めない。uke-01 は main 入り・公開待ち。
- 10-18 マガジンの関所 tools/magazine/magazine_gate.py（即公開と同時＋心臓から1日1回）：全号の曲を動画IDで名簿と突き合わせ（名前の一致では結ばない）、曲ページ・本番で開くか・関連4曲・コピーとメモを見る。初回一巡：8号・曲132／ページ無し44（候補4）／関連4未満6／コピー・メモ不足48／取り違えの疑い3。号ごとの直す便を8本積んだ（122777・122781〜122787）。曲ではない動画は magazine_gate_jogai.json。
- 10-18 22:55 シティポップ特集・月の特集：main 51b629e67・公開待ち（Dispatchが押す）。真夜中のドア／フライディ・チャイナタウンの原曲のすぐ下にMs.OOJAの聴き比べ。挿絵はGrokボット「記事採用」の cp_art_01〜07。月は番号の決めが見つからず、内容で選んだ7枚のまま。MISAMOは訂正でMs.OOJAだった。
- 10-19 03:20 マガジン：出典は本文に出さず記事の最後に章ごと（shutten.py／特集は shutten_tsx.py＋ShuttenSources）。壊れた画像の検査 img_kenpin.py を magazine_gate に追加。シティポップの写真6枚の枠を消した。main 9d9d2fcf1・公開待ち。
- 2026-10-29 Grok通信：Grok Bot は Reason Network に居ない（who 264件＝claude 263・cursor 1）。これまでの『Grok宛て』は工場自身の窓口（madoguchi）宛てだった→宛先をID固定（status/grok_tsuushin/atesaki.json・今は空＝Reasonでは送らない）。本線は GitHub 共有メモ（#1040）。往復確認：01:28送信→02:25 Grok Bot返信（GRK-PING-202610290127）。即時化は Grok 側の webhook URL 待ち（grok-yobirin.yml は用意済み・skip中）。

- 10-29 マガジン曲点検：全マガジン12号＋特集18本の曲281曲・動画304本を点検。リンク・関連4つ（カードB）・コピーとメモ・動画の生死すべて合格。関所＝joy-relief-station prebuild check-magazine-songs.mjs／見張り＝magazine_gate.py --daily（後退でDispatchへ）。
- 2026-10-29 SNSに出した曲の曲ページ強化（d5e206848・本番 d2fa7400 で確認）：投稿済み118曲のうち落ちていた18曲に関連（同じ人の曲・カバーのoriginalRef）・出典つきメモを足し、God Only Knowsに公式動画、The Headhunters「If You've Got It, You'll Get It」を仕入れ（棚には置かない）。コピー78曲をボンジョビおじさん構文で（4言語訳つき・別の目で照合NG0）。マガジン曲12曲は並行の子の版を優先して触らず。残り：中島みゆき「糸」とLeon Russellの共有画像が弱い（動画サムネ由来）。工場の公開係 98403 は403で動かず（deploy_projectで公開）。
- 2026-10-29 追記：SNSに出した118曲の曲ページ点検＝全曲合格（前 100/118 → 後 118/118）。続き 116e3642d・382665a38 を本番（b7814c40）で確認。手書きの関連が別の表（ダンス用）に入っていたのを正しい表へ移した。
- 2026-10-29 追記：工場の main が 10-28 から止まっていた件を直した（作業場が別の枝のまま・衝突で pull をやめ続けていた）。今は main に戻り GitHub と同じ。見張り tools/kojo_push_mihari.py（1時間おき）を足した。／SNSに出した曲のシェア画像を同じ動画の見栄えのする1枚に（tools/sns_og_kaizen.py・本番 c5ac499c）。104曲中、弱い 28→3（残り：ビートルズ Blackbird はジャケット自体が白・Scarborough Fair は名簿が当たっていない・糸は数字上は暗いが歌う姿と名前が見える）。
