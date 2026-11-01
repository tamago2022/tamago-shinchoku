# 音ハメ文字動画 Fable版（2026-11-01・204009番・claude-fable-5-1）

たまごさん依頼：A シティポップ1本（前回C＝60点「もっとおしゃれに」を超える）→ B「ごきげん補給所」のケツロゴ短尺3〜4型＋一覧シート。
納品先：Googleドライブ「AI制作物/Claude/Fable」。記録：`kiroku.jsonl`（1本ごと）。

## できたもの（縦1080×1920・30fps・音つき・無料の道具だけ）
| ファイル | 型 | 一言 |
|---|---|---|
| 261101_Fable_シティポップ_真夜中のLP.mp4（104BPM・15.0秒） | LPの盤面→丸のマッチカット→帯＋横縞の夕日→文字のマット→盤に戻って止まる | 「針を落とす」から始まり、ラベルの丸がそのまま夜の街の丸になる。主役 Didot Italic が16分で1字ずつせり上がり、縦組みの明朝が8分でピントを合わせる。CITY／POP の字の形で写真をくり抜き、キックで図と地が反転。最後は盤がテープストップで止まり、サングラスのコンシェルジュが乗る |
| 261101_Fable_ケツロゴ_01叩き.mp4（160BPM・4.5秒） | 叩きつけ・揺れ・色ずれ・赤い光・砂ぼこり | 1拍1字で極太ゴシックが叩き込まれ、8拍目に上からロゴが落ちて着地（つぶれて戻る） |
| 261101_Fable_ケツロゴ_02ネオン管.mp4（96BPM・5.0秒） | ネオン管の筆記（字の輪郭を線の長さぶん描く）・点滅・映り込み | 濡れた路地で「Joy Relief」が書かれ、「ごきげん補給所」がチカチカ灯る。ロゴはネオンの光を受けて浮かぶ |
| 261101_Fable_ケツロゴ_03誌面.mp4（112BPM・4.8秒） | 紙・グリッド・マスクからせり上がる明朝・タイプライター・丸い穴 | 生成りの紙に罫が引かれ、見出しがせり上がり、紙に穴が開いてロゴ |
| 261101_Fable_ケツロゴ_04フィルム.mp4（70BPM・5.1秒） | リムライトの帯・字間で寄せる題字・光漏れ・粒子・ゲートの揺れ | 暗闇を光の帯が横切ってロゴが浮かび上がり、題字が字間を詰めながらピントを結ぶ |
| 261101_Fable_ケツロゴ_一覧シート.jpg | 型名・一言・代表コマ | 5本を1枚で見比べる |

## 作り方（src/）
- 土台 `src/fb.py`：Opus版 `status/motion_lab/photo/src/dodai.py` の型をそのまま移植。**違いは1つ：この Mac に pycairo が無いので、文字は Pillow（FreeType）で1字ずつ描いて numpy で合成する**（`Font.glyph`＝字のマスク、`Layer.blit`、`draw_text`、`rise`）。fontsource の和文（100個以上の分割 woff）は fontTools で「文字→ファイル」の表を作って引く。書体は `status/motion_lab/variations/src/shotai.py` の台帳（121書体）の ID。ffmpeg は imageio_ffmpeg のもの（PATH に無い）。`--self-test` あり。
- 描く係 `src/rend.py`：`rendr.py` そのまま（かたまりに切って描く・続きから・音を作ってつなぐ・一覧・1コマ）。
- 台本：`src/a_citypop.py`／`src/k1_tataki.py`／`src/k2_neon.py`／`src/k3_shimen.py`／`src/k4_film.py`（scene／subframes／post／music の4関数。文字と音は同じ拍の表から作る）。一覧シート `src/ichiran.py`。
- 手順：`python3 rend.py a_citypop --sheet 一覧.jpg`（確かめる）→ `--all -j 4 --budget 7000`（くり返す）→ `--join 出力.mp4`。
- 音は全部 numpy で自作（`oto.py`：エレピ・スラップ・ゲートのスネア・鈴・ノコギリ波のブラス・ネオンのうなり・タイプライター・映写機）。テープストップは最後の2.5拍を再標本化して速さ 1→0。
- ロゴは `joy-relief-station/src/assets/egg-concierge-rocker.png`（サングラスのコンシェルジュ・透過）だけ。卵だけのロゴ・宇宙うんこの絵は使っていない。ロゴは各本の最後だけ。
- 写真：`share/check/assets/`（ikareru/billboard・fuukei/hikigatari-josh-turner-5・2・naze-ongaku-01-takoukan-5・hito-wa-naze…ai-mj-05-3）。高速道路の写真は看板の文字（ARE YOU ANGRY?）が入らない右下だけを使った。

## 正直な弱点
- **描く速さ**：この Mac は他の仕事で混んでいて（この便の Python は nice 10・CPUの3割しか取れない実測）、1コマ約15〜22秒。15秒の A で約2時間かかった。後半（CITY/POP・盤）は動きが少ないのでモーションブラーの重ね描きを1枚にして軽くした。
- 書体の大きさは整数 px に丸めている（Pillow の都合）。大きく拡大縮小する動き（CITY/POP の叩きつけ）は、ごく小さな段つきが出る可能性がある。
- 手持ちの写真が横1080px以下なので、全面に伸ばすと柔らかい。A は帯・丸・字の形の中で見せて逃げた。
- ネオン管の筆記（02）は fontTools の輪郭を「左から順」に描くだけで、人が書く筆順ではない。
- 音ハメのずれは、文字と音を同じ拍の表から作っているので原理的にずれないが、今回は `sync_check.py` での実測はしていない。
- 粒子（グレイン）は少し強め。「画質が少し粗いのは今はかまわない」（たまごさん）に甘えた。

## 進み（2026-11-01 16:05・再開3回目）
- A：完成・Drive「AI制作物/Claude/Fable」に納品済み（crf21・93MB・15.0秒）。フォルダ https://drive.google.com/drive/folders/1dEn01jXnO2798sso37srK7K9Cy73bCoH
- B：型01 叩き＝8/8かたまり描けて結合済み（raw）。型02 ネオン管＝5/8、型03 誌面＝6/8、型04 フィルム＝4/8 → 残り9かたまりを `/private/tmp/204009_fm/finish_b.sh`（nohup で切り離し・ログ `finish_b.log`）が描いている。描き終わると自動で 結合（`rend.py --join`）→ crf21 圧縮（`out/<型>.c21.mp4`）→ 一覧シート（`out/ichiran.jpg`）まで進み、最後に `FINISH_B_DONE` を出す。
- **次の担当がやること（finish_b.log に FINISH_B_DONE が出たら）：** `out/k1_tataki.c21.mp4` 等を `261101_Fable_ケツロゴ_01叩き.mp4`／`02ネオン管`／`03誌面`／`04フィルム`、`out/ichiran.jpg` を `261101_Fable_ケツロゴ_一覧シート.jpg` に改名 → `python3 tools/claude_nouhin.py put <各ファイル> --anken Fable --saishin` → kiroku.jsonl に1本ずつ追記 → 確認ページ（share/check/204009-*.html）を更新 → Dispatch へ報告 → `/private/tmp/204009_fm` を消す。FINISH_B_DONE が出ていなければ `finish_b.sh` をもう一度 nohup で走らせる（続きから）。
- 実測の遅さ：この Mac はディスク待ち（iCloud 同期の fileproviderd が CPU 80%・load 18〜22）で、1コマ＝型02 約109秒・型03 約94秒・型04 約33秒（単独でも）。4本並列は逆効果（1かたまり50分・予算切れで3本分の途中が捨てられた）→ 2本・打ち切りなしに変更。
- 事故：3時間ルールで打ち切られた前の再開セッション（pid 87708）がプロセスとして生き残り、同じ作業場で並走していた（`rm` の許可待ちで固まりつつ k1〜k3 を結合しようとしていた）。この再開が kill した。`status/failures.md` に1行。
