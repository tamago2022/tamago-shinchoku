# ごきげん補給所 仕入れプレイブック（他AI共有版）

このドキュメントは Codex / Claude Code / Fable / Jules / その他の開発AIが、
Lovable と同じ品質で **仕入れ・棚振り分け・アーティストページ整備** を行うための共通手順書です。
`AGENTS.md` と `.lovable/memory/**` の内容を、仕入れ現場で必要な形に統合しています。
このプレイブックと最新 `main` の両方を毎回参照してください。競合したら「より安全・既存資産を保護・店主確認まで追跡できる方」を優先。

---

## 0. 大前提（10行憲法）

1. **事実は捏造しない**。指定URL・公式・本人チャンネル・Wikipedia CC-BY-SA だけを使う。年号・再生数・出身地を盛らない。
2. **既存資産を消さない**。ページ・カード・棚・機能・データを無断削除しない。
3. **ユーザーが貼ったURLは最優先命令**。同じターン内で反映。翌ターン以降に持ち越さない。
4. **リンク切れ・灰色サムネ・再生不可・年齢/地域制限 の動画は棚に出さない**。件数を盛るために弱いカードを残さない。
5. **1アーティスト=1ページ**。別名義・別プロジェクトは統合または `relatedProjects` で相互リンク。
6. **同じ棚に同じ曲・同じYouTube動画・表記ゆれの重複を出さない**。
7. **音楽/笑い/CM系カードのURLは `/cover-guide?artist=<id>&song=<songId>` に統一**。`/room/...` 残置は原則NG（食べ物/かわいい系のみ例外）。
8. **共有URLは曲直リンク**。戻るは直前ページ。動画再生中に URL や artist/song state を変更しない。
9. **PR作成だけを完了と呼ばない**。完了は「実装→PR→main反映→Lovable公開画面で確認」の4段階。
10. **質問で止まらない**。技術判断が2択なら、より安全で後戻りしやすい方をAI側で選び連続完走する。

---

## 1. 仕入れの3レーン

### レーン1：ユーザーが名前/URLを出したら即追加
- 最優先。同じターンで完了。
- URL だけでも仮カードを作り、後続で `about` / `similarArtists` を埋める。

### レーン2：同ポジ横展開
- 追加したアーティストの「他の国・他の時代の同ポジション」を候補化して `.lovable/wantlist.md` に追記。
  - 例：TWICE → BLACKPINK / NewJeans / 4EVE / BABYMONSTER / VCHA
  - 例：ネイト・ジェームス → マックスウェル / レニー・クラヴィッツ / 24Karats / 藤井風
  - 例：ガリアーノ → Brand New Heavies / Incognito / Jamiroquai
- 店主 ✓ で採用、🚫 で二度と出さない。

### レーン3：ジャンル空白レーダー
- 「ジャンル × 国（日本/US/UK/韓国/欧州/東南アジア）」マトリクスの空白マスを毎週リストアップし埋める。

---

## 2. YouTube ID 取得ワークフロー（**混雑回避版・ここが一番重要**）

他AIが「1回叩いて 429 が返ってきたら諦めて帰る」現象が発生している。以下のフローを厳守。

### 2.1 使うスクリプト

```bash
MAX_SONGS=200 CONCURRENCY=10 BATCH_SAVE=25 \
  nohup bun scripts/bulk-ingest.ts > /tmp/bulk.log 2>&1 &
```

必ず **バックグラウンド起動**。フォアグラウンド実行で待つのは禁止（他作業がブロックされる）。

### 2.2 環境変数と推奨値

| 変数 | 意味 | 通常 | 混雑時 |
|---|---|---|---|
| `MAX_SONGS` | 1回で取りに行く曲上限 | 200 | 50〜100 |
| `MAX_ARTISTS` | 1回で回るアーティスト上限 | 1500 | 300 |
| `CONCURRENCY` | 並列検索本数 | 8〜10 | **4以下に半減** |
| `BATCH_SAVE` | 何曲ごとにファイル保存するか | 10〜25 | 5〜10（成果を失いにくくする） |
| `SAVE_INTERVAL_MS` | 定期保存の間隔ms | 30000 | 15000 |
| `SEARCH_DELAY_MS` | 検索と検索の間の待ち時間ms | 120 | **500〜1500に引き上げ** |
| `PER_ARTIST_LIMIT` | 1アーティストあたり最大取得曲数 | 8 | 5 |

### 2.3 混雑時のリトライ戦略（**「早々に諦めない」の実体**）

YouTube HTML / oEmbed が `429`・`503`・空配列・タイムアウトを返してきた時に、他AIがよくやる「1回叩いて諦める」は **禁止**。以下を実装/継承する:

1. **指数バックオフで最低3回** 再試行（例：1s → 3s → 8s）。3回失敗して初めてその1曲をスキップする。
2. **User-Agent を差し替える**。既定UAで弾かれたら、別のChrome/Safariバージョン文字列に切り替えて再試行。
3. **`SEARCH_DELAY_MS` を動的に引き上げる**。連続で 429 が出たら 2倍→4倍とスロットリング。
4. **`CONCURRENCY` を半減させる**。5組連続で結果が空 → 並列数を半分に落として再挑戦。
5. **5組連続で0件が続いたら自動停止**（`bulk-ingest.ts` に実装済み）。ここで人間/上位AIに `/tmp/bulk.log` と `/tmp/bulk.status.json` を報告。
6. **停止しても失うのは直近バッチだけ**。`BATCH_SAVE` ごとにファイルへ書き出しているので、次回起動時は途中から再開できる。
7. **混雑中は別作業に切り替える**。渋滞している時に叩き続けても API 側の Rate Limit を悪化させるだけ。30分〜数時間空けて再挑戦する（時間帯・地域によって明確に空く）。
8. **oEmbed 二次検証** は必須。HTML 検索でヒットした ID を `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<id>&format=json` で叩いて 200 が返るものだけ採用。
9. **サムネ 404 チェック**：`https://img.youtube.com/vi/<id>/hqdefault.jpg` が 404 or 灰色プレースホルダ相当（120x90サイズ）なら不採用。

### 2.4 バックグラウンド運用の型

```bash
# 開始
MAX_SONGS=200 CONCURRENCY=6 SEARCH_DELAY_MS=400 \
  nohup bun scripts/bulk-ingest.ts > /tmp/bulk.log 2>&1 &
echo $! > /tmp/bulk.pid

# 進捗ポーリング（他作業と並行）
while true; do
  cat /tmp/bulk.status.json 2>/dev/null
  if ! kill -0 "$(cat /tmp/bulk.pid)" 2>/dev/null; then break; fi
  sleep 30
done

# 途中で強制停止
kill "$(cat /tmp/bulk.pid)"
```

**「渋滞したら別の仕事をやる」**。ジャンル空白レーダー整理、アーティスト about 加筆、curated リンク補強など、Rate Limit に依存しない仕事は無限にある。

---

## 3. 動画の選び方（品質4階層 & 差し替え基準）

### 3.1 品質4階層

| 階層 | 例 | 扱い |
|---|---|---|
| 0. 門前払い | 別人・別曲・同名混同・事実誤認 | 即削除＋`blocklist` / `notMe` に反映 |
| 1. 正しいけど弱い | 晩年公式・代表性薄い・映像弱い・静止画のみ | 30枠から外す（😐） |
| 2. 入門ヒット | 初見のための代表曲 | 30本中5〜7本 |
| 3. **店主の肉汁枠** | 全盛期・若い頃TV・ライブ爆発・海外ファン編集の名作 | primary 昇格（⭐） |

### 3.2 primary 差し替え基準（`prefer-strong-video` 憲法）

- **静止画音源 < 公式MV < 再生の回っているライブ**。
- 静止画しかない曲でも、公式MVがあればMVを primary に。公式MVも静止画なら、著名ライブ映像を primary に。差し替えた静止画音源は `altYoutubeIds` に残す。
- **公式より強いファン投稿・海外ファン編集** があれば primary にしてよい。公式は必ず `altYoutubeIds` に残す。primary が削除されたら `altYoutubeIds[0]` が自動昇格する（`getSongVideoIds` 実装）。
- **若い頃の映像 > 現在の再演**（本人が輝いていた瞬間を優先）。
- **動いてる映像 > 静止画**。声/顔/身体/演奏/観客の熱が最も出ているもの。
- **一般人アップでも再生数が回っているものは採用**。「公式かどうか」より「その瞬間の熱が残っているか」。
- **ノーカット・音質OK・元映像に忠実 > 短い切り抜き**。
- 海外リアクション/海外ファン編集で刺さっているものは積極採用（海外にニーズがある証拠）。

### 3.3 実例

- 松田聖子「青い珊瑚礁」：ファン投稿の若い頃映像 > 公式アップ
- 松田聖子「夏の扉」「Rock'n Rouge」：韓国ファン編集 > 公式
- RATM「Guerrilla Radio」：Rock im Park 2000 ライブ > 静止画音源
- RHCP：Mother's Milk / Blood Sugar Sex Magik 期を厚く、Californication 以降は入口枠のみ
- Rolling Stones：60s〜70s 中心、近年映像は最小
- Stevie Wonder：70s を6割、80s/90s 適度、"FACE" のような例外的名演はOK
- Michael Jackson：Off the Wall〜Dangerous 前半中心＋James Brown 舞台乱入・Super Bowl のような発見を1〜3本
- 桑田佳祐：スタジオ音源だけでなく渋谷ハチ公前ゲリラLIVE のようなお宝を拾う

### 3.4 AI 自身への指示（暗唱すること）

> 曲を探すな。**その人が一番かっこよかった瞬間**を探せ。
> 知らない人が恋に落ちる入口を探せ。
> すでに好きな人が「わかってるな」と笑う映像を探せ。

---

## 4. 棚振り分けルール

- **1棚 最大50件**。「もっと見る」は使わない。件数表示と実表示件数を必ず一致させる。
- **動画IDなし / oEmbed NG / サムネ404 / 曲ページに動画がない** カードは棚に出さない。
- **同じ棚に同じ曲・同じ動画・表記ゆれの重複を出さない**。
- **棚状態は4段階**：
  - ★固定：必ず50枠に入る。固定同士は日替わりシャッフル。
  - ✓候補：今その棚にいる。50枠に入る範囲で表示。
  - 無印：今は出さない。将来の自動振り分けでは再登場可。
  - 🚫NG：その棚には二度と入れない。自動振り分けからも除外。
- 最初から棚にあるカードは「✓候補」扱い。
- 50件棚に追加する時は、★固定でない候補を1件落として50件を維持。
- 自動振り分けは `scripts/auto-shelf-assign.ts`。手動で覆すのは「明確に世界観と合わない」時だけ。

---

## 5. アーティストページのフル装備（6点セット）

新規アーティストは以下を **同じターンで全部揃えて** 初めて完了。骨組みだけ置くのは禁止。

1. **about**（Wikipedia CC-BY-SA、事実だけ、数字盛らない）
2. **relatedProjects**（元バンド⇄ソロ⇄別名義。例：Blur⇄Gorillaz、Cornelius⇄フリッパーズ・ギター、忌野清志郎⇄RCサクセション⇄タイマーズ）
3. **similarArtistsMap**（一曲サムネカード3〜5人。越境同ポジ優先。日本人には外国勢も混ぜる）
4. **代表曲 8曲目安**。**全曲 youtubeId＋年号必須**（年号漏れは絶対ダメ）
5. **curated ハブ&スポーク**：原曲／名カバー／コラボの相互リンク。同じ曲は原則、各アーティストで同じ `songId` を使う（例：jackson5 / twice / sheryl-crow はすべて `i-want-you-back`）。3バージョン以上ある曲は3ページ全部に他2バージョンが並ぶこと。curated には原曲側・カバー側の両方を書く。
6. **ヘッダー色**：`getArtistGradient` が自動で色を振る。手で似合う色を付けるなら `roomGradient`。同じ茶色が連続で並ぶのは禁止。

**既存アーティスト**へも指示がなくてもフル装備を **毎ターン数人ずつ逆流適用**。棚数の多い順に `scripts/audit-artist-completeness.ts` で選ぶ。

---

## 6. 新規曲追加の5点セット（同ターン完結）

1. `src/lib/coverGuide.ts` の artist を確認。なければ作る（フル装備）
2. artist の `songs[]` に song を追加。**`youtubeId` 必須**
3. 棚カードの `to` を `/cover-guide?artist=<id>&song=<songId>` にする
4. カバー曲なら `curated` に **原曲側・カバー側の両方** を登録
5. サムネ `https://img.youtube.com/vi/<id>/hqdefault.jpg` を設定

追加前に oEmbed で YouTube ID の有効性を確認。灰色「…」アイコンが出る状態は未完了扱い。

---

## 7. URL・共有・戻る導線の絶対ルール

- 音楽・カバー・コラボ・CM・笑い・ネット動画系の棚カードは `/cover-guide?artist=<artistId>&song=<songId>` に統一。
- **禁止**：
  - 音楽カードを `/room/card/...` のまま置く
  - 曲カードなのに `/cover-guide?artist=<id>` だけにする
  - `coverGuide.ts` に存在しない artist/song へリンクする
  - 棚から開いたのに案内所TOP・別アーティストTOP・真っ白画面へ飛ばす
- **例外**：食べ物・赤ちゃん・子供・動物・かわいい系・体験/料理/非アーティスト系は `/room/...` のままでよい。ただし共有・戻るは直前ページへ。
- 古い `/room/...` を見つけたら、食べ物/かわいい系以外は **同じターンで** `/cover-guide?...` へ正規化する。
- **共有URL** は曲直リンク：`https://joy-relief-station.lovable.app/cover-guide?artist=<id>&song=<songId>`。preview/dev ドメインを混ぜない。
- **戻るは直前ページ**。棚→曲なら棚へ、カバー間移動なら直前の曲ページへ、アーティストTOP→曲ならTOPへ。
- **動画再生・iframe状態変化・アコーディオン開閉・プレーヤー展開では絶対にURLを触らない**。曲ページで動画再生中に案内所TOPへ落ちるのは最悪の体験。

---

## 8. セルフレビュー機械チェック

コード・データを変更したら、AI自身が以下を回してから店主に渡す。ユーザーに1個ずつ検証させない。

```bash
# 基本検品
bash scripts/verify-project.sh
bun scripts/constitution-check.ts

# 個別チェック
rg 'to: "/room/' src/lib/worlds.ts                      # 残置 /room 検出
rg 'to: "/cover-guide\?artist=' src/lib/worlds.ts       # 正しい形の数
rg 'id: "<artistId>"' src/lib/coverGuide.ts             # 追加artistの重複確認（1件になっているか）
rg 'id: "<songId>"' src/lib/coverGuide.ts               # song重複確認
rg 'roomToCoverGuide|getCanonicalCardTo' src/lib/worlds.ts
rg 'name:\s*"<追加アーティスト名>"' src/lib/coverGuide.ts

# 監査
bun scripts/audit-artist-completeness.ts
bun scripts/audit-dead-youtube.ts
python3 scripts/audit-missing-years.py
```

**判定**：
- artist 0件 = 作り忘れ
- artist 2件以上 = 重複疑い（統合が必要）
- song 0件 = 曲ページなし
- 音楽/笑い/CM系なのに `/room` のまま = 原則NG
- 同じ曲なのに両アーティストに同じ songId が無い = ハブ&スポーク未成立

## 9. 実ブラウザ確認（Playwright）

最低限これだけは押す：

- トップ／世界ページの棚 → 曲カード = 曲ページが開く
- 曲ページ → 前のページに戻る = 元の棚に戻る
- 曲ページ → 共有 = 曲直リンクがコピーされる
- 曲ページ → 動画再生 = 案内所TOPへ落ちない
- 原曲ページ → カバー曲ページ → 戻る = 原曲ページに戻る

---

## 10. 完了の4段階と報告フォーマット

**完了は次の4段階**。1〜3で止まったら「完了」と呼ばない。

1. 実装・自動検品完了
2. GitHub PR 作成
3. GitHub `main` へ Merged
4. Lovable 公開画面（https://joy-relief-station.lovable.app）へ反映され、店主が実画面で合格

**日本語・短く**：

```
【変更点】
【検品結果】
【GitHub反映】
【Lovable反映】
【コミットID】
【店主が確認する場所】
【未達または唯一のブロッカー】
```

---

## 11. 合言葉

> 棚カードは「置いたら終わり」ではない。
>
> 棚に置く → artist/song を作る → 曲直リンクにする → 共有URLを曲直リンクにする → 戻る先を直前ページにする → 実ブラウザで押して確認する。
>
> この一連を同じターンで完了。**後回し禁止**。

そして仕入れは：

> 混雑で1回叩いて諦めるな。**遅く・少なく・長く**叩いて、成果は`BATCH_SAVE`で刻んで残せ。
> 渋滞している間は別の仕事をやれ。時間帯を変えれば必ず空く。
