# 944番【本丸】どこに話に行っても話が通じる ─ 外部AIへの共通の窓口

たまごさんの言葉（2026-09-18・原文）:

> あなたがセンターになるって意味だよ。俺がわざわざGrok開いてジェミニ開いていつもやってることを、
> あなたを通してできるようになるのかっていう。
> （中略）
> **1番望んでるのは、どこに話に行っても話が通じるってことだね。全部が筒になってるっていう状態。**
> GrokでLINEスタンプ修正したんだけど「誰か申請まで投げれますか？」って言ったら
> 「僕ができます」とか「こういうやり方がありました」とか、**個別に聞いてるのがめちゃくちゃ面倒くさいのよ。**

---

## 1. 何が変わったか

| | 前 | 後 |
|---|---|---|
| 聞く | Grokを開く→事情を説明→Geminiを開く→また事情を説明→ChatGPT→また説明 | `python3 tools/kiku.py "…"` の1行。3社が**同じ前提**で答える |
| 続き | 毎回ゼロから | `--n 915` を付けると**前回の続き**。向こうが「915号ね」と分かる |
| 頼む | 向こうの画面に見に行って、結果をコピーして持ち帰る | `python3 tools/tanomu.py …`。**成果物がこちらのフォルダに落ちる** |
| お金 | 分からない | 1回ごとに**円**で出る。合計も出る |

---

## 2. 使うのはこの2つだけ

### 聞く

```bash
cd /Users/mac/Desktop/tamago-shinchoku

# 3社に同時に聞く
python3 tools/kiku.py "この方針どう思う？" --n 915

# 1社だけ・Web検索させる
python3 tools/kiku.py "今1番伸びてる音楽系サイトは？" --ai gemini --search

# 続いている会話を見る
python3 tools/kiku.py --threads

# どの社の鍵があるか（値は絶対に表示しません）
python3 tools/kiku.py --keys
```

出るもの：**社名／答え／公式URL／かかった秒数／使った金額（円）**と、その**合計（円）**。

### 頼む（成果物が返ってくる）

```bash
# 世界中リサーチ
python3 tools/tanomu.py research "日本のカバー曲紹介サイトで今1番伸びているのはどこか" --ai gemini

# YouTubeリサーチしてレポートを上げさせる
python3 tools/tanomu.py youtube "1人で作る映像作品のチャンネルで直近伸びているもの" --ai gemini

# 今1番伸びてるサイトを探させる
python3 tools/tanomu.py site "音楽紹介メディア" --ai grok

# 画像を作らせる
python3 tools/tanomu.py image "夜の商店街、卵の看板、昭和の湿度、16:9" --ai gemini

# 作らせたものの一覧
python3 tools/tanomu.py --list
```

**★成果物の置き場はここ1か所：**

```
status/gaibu_seika/<日付>_<社名>_<件名>/
    レポート.txt   ← たまごさんが読む用
    レポート.md
    画像.png
    _材料.json     ← 何を頼んで・何秒で・何円か
```

**向こうの画面に見に行く必要はありません。全部ここに落ちます。**

### 逆向き（たまごさんが向こうの画面で作ったものを、こちらが拾う）

★**`status/gaibu_seika/_inbox/` に入れてください。**

```bash
python3 tools/tanomu.py --inbox
```

画像でもテキストでも何でも構いません。日付つきのフォルダに取り込んで台帳に載せます。

---

## 3. 「話が通じる」の実体 ── 共有ブリーフ

外部AIは記憶を持っていません。だから毎回ゼロから説明することになる。
それをやめるために、**毎回この1枚を先頭に付けて送っています。**

```
status/kyoyu_brief.txt   ← ★たまごさんが他社の画面に直接貼る用
status/kyoyu_brief.md    ← 機械が読む用
```

中身（全部**自動生成**。手で書きません）：

- **今やっている案件の一覧**（号番号・題名・状態・詰まっている点）← `status/queue.json` から
- **今日の数字**（クレジット・残タスク・完了件数）← `status/genzaichi.md` から
- **決まっている制約**（Lovableのチャットにプロンプトを打たせない／Braveを触らない／報告は1行＋URL／お金の前に見積 など）
- **固有名詞**（ごきげん補給所・名カバー案内所・Eden Loop・号番号・工場 など）
- **答え方のルール**（結論を先に1行／推測には「推測」と書く／URLは実在するものだけ）

作り直す：

```bash
python3 tools/kyoyu_brief.py --n 915
```

**たまごさんが自分でGrokやGeminiの画面を開いて使いたいときも、`status/kyoyu_brief.txt` を開いて
全部コピーして、質問の前に貼れば同じことが起きます。**（`.md` は向こうの画面で開けないので `.txt` で用意しています）

---

## 4. 回線のこと（ここが今日の一番の発見）

**Cowork/Dispatch のサンドボックスからは、外部AIのAPIに回線が出ません。**
`api.openai.com` / `api.x.ai` / `generativelanguage.googleapis.com` のどれも名前解決で落ちます。

**たまごさんのMac（＝工場）からは出ます。** 実際 `tools/kenpin_gate.py` が今日OpenAIと5往復しています。

だから外部AIを叩くコードは**全部「工場側で動くもの」として作りました。**

```
サンドボックス側                      工場側（Mac）
─────────────                      ─────────────
kiku.py / tanomu.py
  │
  ├ 回線が出るか自分で判定
  │   出る  → その場で叩く（＝たまごさんがターミナルで打ったときはこれ。即答）
  │   出ない→ status/gaibu_jobs/pending/ に仕事票を1枚置く
  │                                     │
  │                          tools/gaibu_runner.py が拾って叩く
  │                            ・5分便(machine_status_push.sh)の15秒巡回から
  │                            ・心臓(heartbeat.sh)の15秒ループから  ←二重化
  │                                     │
  └ status/gaibu_jobs/done/ を見て結果を表示 ←─────┘
```

★**呼ぶ側は何も意識しなくていい。** どちらの環境でも同じコマンドが動きます。

★**たまごさんがターミナルで打つ場合は、工場が止まっていても関係なく即座に動きます。**

---

## 5. ChatGPTのプロジェクト（ごきげん補給所編集部）について

**結論：APIからは届きません。ブラウザ（ログイン済みのChatGPT画面）だけです。**

- ChatGPTの「プロジェクト」は、チャット・ファイル・プロジェクト指示を1か所にまとめる**ChatGPT製品側の機能**です。
- OpenAIは**カスタム指示にAPIは用意しない**と明言しています（「Chat Completions APIのsystemメッセージを使え」）。
- Enterprise向けの Compliance API でプロジェクトの**管理情報**は取れますが、
  これは監査用であって「そのプロジェクトのスタッフを動かす」ためのものではありません。
- つまり `tools/kiku.py --ai openai` は、**あのプロジェクトとは別人**です。同じ会社の、まっさらなGPTです。

**では、あのプロジェクトのスタッフを動かしたいときは？**

→ `status/kyoyu_brief.txt` を開いて全部コピーし、ChatGPTのプロジェクト画面に貼ってから用件を書く。
　 これで、あのプロジェクトのカスタム指示＋ファイル＋工場の現在地が**両方揃った状態**になります。
　 （これが、APIでは絶対に作れない状態です）

出典：
- https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- https://help.openai.com/en/articles/8096356-chatgpt-custom-instructions

---

## 6. 外部AIの検品（「実際に動いてるの？ やりとり見れるの？」）

**動いています。今まで読める形で出ていなかっただけです。**

```bash
python3 tools/kenpin_mieru.py --all
```

- `status/kenpin/<号>/やりとり.txt` … ★たまごさんが読む用。
  **FIX（直させた）→ 修正 → FIX → … → PASS** が上から順に並びます。
  各回に「Claudeが出したもの」「外部AIの指摘」「見落としていそうな点」「費用」が付きます。
- `status/public/kenpin/<号>.txt` … 進捗表から押せる場所（同じ中身）
- **進捗表（index.html）に「外部AIの検品」カードを足しました。**
  見えるのは1行だけ。開くと号ごとの往復が全部出ます。

915号の実績：**5往復・直させたのが4回・最後はPASS・合計2.084円**。

---

## 7. お金

- 1回ごとに円で出ます。台帳は `status/gaibu_kenpin_ledger.json`（検品と同じ台帳に相乗り）。
- 成果物の台帳は `status/gaibu_seika_ledger.jsonl`。
- **1日の上限は100円のまま変えていません。**
- 回数の上限だけ 30回→120回 に広げました。理由：
  今日、**金額はまだ28.96円／100円（7割の余裕あり）なのに、回数30回で検品ゲートが止まって**いました
  （850号の失敗 `F-20260918011032`）。実測単価は1回あたり約0.97円なので、
  **100円の方が先に当たります＝お金の歯止めは一切弱まっていません。**

---

## 8. 鍵

`tools/kiku.py --keys` で**有無だけ**確認できます。**値は画面にもログにも一切出しません。**

探す場所（この順）：

1. 環境変数
2. `~/.tamago/keys/api_keys.env`
3. `/Users/mac/Desktop/tamago-shinchoku/.env`
4. `/Users/mac/Desktop/joy-relief-station/.env.local` など
5. `~/Documents/AI作業/_鍵/keys.env`

必要な名前：`XAI_API_KEY`（Grok）／`OPENAI_API_KEY`（ChatGPT）／`GEMINI_API_KEY`（Gemini）

**Geminiの鍵が無い場合でも、GrokとOpenAIの2社で動きます。**その場合は画面に
「Geminiは鍵が無いので未接続」と出ます（黙って落ちません）。

---

## 9. ファイル一覧

| ファイル | 役割 |
|---|---|
| `tools/kyoyu_brief.py` | 共有ブリーフを自動生成（話が通じる状態の実体） |
| `tools/kiku.py` | 聞く。3社に同じ前提で。号番号ごとに会話が続く |
| `tools/tanomu.py` | 頼む。リサーチ・画像。成果物がこちらに落ちる |
| `tools/gaibu_kuchi.py` | 3社を同じ形で叩く土台（鍵・料金・円換算） |
| `tools/gaibu_runner.py` | 工場側の代行係。サンドボックスの代わりに叩く |
| `tools/kenpin_mieru.py` | 検品のやりとりを読める形にする |
| `index.html` | 進捗表に「外部AIの検品」カードを追加 |
