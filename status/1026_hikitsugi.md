# 引き継ぎ 1026 ― Wikipediaの穴を塞いだ／#446 を起こした／仕入れ 84.6%→74.0%（2026-09-23 00:00〜）

前のセッション（1025番）が残した3件、**3件とも手を付けた。**

---

## ① それはありませんね率

| | 前（1025番） | 今 |
|---|---|---|
| **棚の率**（本当の数字） | 89.0% | **89.0%（1曲も出していない）** |
| **候補まで含めた率** | 84.6% | **74.0%** |
| 候補が積まれた組 | 10組 | **34組** |
| 候補の曲数 | 49曲 | **約170曲を追加**（見る場所は `share/check/990-shiire-kouho.html`） |

★**棚には1曲も出していない。**棚に出すかはたまごさんの判断なので候補で止めてある。
だから棚の率は動かない。動かせるのは候補込みのほうで、`tools/fes_meibo.py` が2本並べて出す。

積んだ組（1026番ぶん・24組）：
GEORDIE GREEP / SOFIA ISELLA / Yo-Sea / Riddim Saunter / DONAVON FRANKENREITER /
GRAPEVINE / 礼賛 / AMERICAN FOOTBALL / Trueno / BOHEMIAN BETYARS / a flood of circle /
Aooo / テレビ大陸音頭 / SIX LOUNGE / THE BETHS / THE LEMON TWIGS / 浅井健一 /
Lausbub / Wata Igarashi / 唾奇 / Soichi Terada / FRIKO / QUADECA / 石野卓球

## ★② Wikipediaの誤爆 ― 洗い出し18件・18件とも直した

### 何が壊れていたか
前の型は「音楽の記事らしさ」を点数にして選んでいた。**その点数では2つの抜け方が止まらない。**
どちらも「音楽の記事ではある」から点数が高く出る。

| 抜け方 | 実測で出たもの |
|---|---|
| (a) 本人ではなく**作品**を採る | LOYLE CARNER → `Hugo (album)` ／ DONAVON FRANKENREITER → `Donavon Frankenreiter (album)` |
| (b) 音楽の記事だが**別人・別物**を採る | GRAPEVINE → `AM Radio (band)` ／ TORO Y MOI(ja) → `Mabanua` ／ Yo-Sea(ja) → `LUNA SEA` ／ TURNSTILE(ja) → `ロードランナー・レコード` ／ KOTORI → `Kotori Koiwai`（声優）／ SON ROMPE PERA → `Tiny Desk Concerts` ／ 平沢進+会人 → `Susumu Hirasawa discography` |

### どう直したか（点数をやめて、関所を2つにした）
`tools/shiire_fetch.py`：

- **関所1＝その記事は人・バンドの記事か。**作品・映画・一覧・会社・衛星・改札機は落とす。
  書き出しは**1〜2文だけ**見る（700字見ていたときは、本人の記事の経歴中の
  「デビュー・アルバム『…』をリリース」を拾って本人を落としていた）。
- **関所2＝その記事は探している本人か。**題が名前と一致するか、題が別の文字体系のときだけ
  書き出しの括弧の綴りで照合（「モグワイ（Mogwai…）」「ジョーディー・ウェイド・グリープ（Geordie Wade Greep…）」）。
  ★同じ文字体系なら括弧の逃げ道を使わない＝`KOTORI` で `Kotori Koiwai` を拾う穴を開けない。
- **両方通らなければ `found=false`。**一番近いものを当てはめない。

### 機械で洗い出して、機械で直した（1件ずつ手で直していない）
```bash
python3 tools/shiire_fetch.py --audit            # 洗い出すだけ
python3 tools/shiire_fetch.py --audit --repair   # まとめて found=false に落とす
```
- **18件見つかって、18件とも落とした。**採っていた記事は `rejectedArticle` に残してある（消していない）。
- そのうえで Mac 側で取り直し。いまは `--audit` が **0件**。
- 書いてしまった候補の出典も機械で当たった（`tools/_1026_kouho_audit.py`）。
  **Wikipediaを出典にした31行／本人でない疑い 0件。**

### 再発したら機械が落ちる
```bash
python3 tools/shiire_fetch.py --selftest     # 通信しない。見本29件
```
見本は **実物のWikipediaから引いたもの**（`tools/sekisho/wiki_cases.json`・
採ったのは `tools/_1026_fetch_cases.py`）。★見本の文を手で書いていない。
たまごさんが名指しした4件（TURNSTILE→改札機／Trueno→車／IO→木星の衛星／
Riddim Saunter→フジロック）が見本に入っている。
**`--names` も `--from-queue` も、走る前に必ずこの見本を通る。落ちたら集めない。**

### ついでに塞いだ穴2つ（同じ型の事故）
1. **同名が並んでいるときは曲を引かない。**`identify_ok()`。
   実測：`IO` は1位ブラジルのアンビエント奏者(100)／2位カナダの実験音楽家(95)。
   1位で引くと**別人の曲が99曲**入ってくる（akiko の棚に矢野顕子 と同じ事故）。
   → **1位95以上かつ2位と10以上離れているとき**だけ引く。
   離れていないときは **MusicBrainz→Wikidata→Wikipedia の橋**を1回だけ見て、
   同じ人を指していれば通す（実測：Trueno＝Q98273264→`Trueno (rapper)`、平沢進）。橋が無ければ**保留**。
2. **取り直しで前より痩せた素材を上書きしない。**MusicBrainzが一時的に弾くと候補0件が返る。
   そのまま上書きすると mbid も曲も消えて「同定できない組」に化ける（TURNSTILEで実際に起きた）。

## ③ Jules と Codex ― 起こした。**返り3件・JulesはPRまで出した（実測）**

**原因（1025番の見立て）は当たっていた。誰も起こしていなかっただけ。**

| | 実測 |
|---|---|
| 起こした | **2回**（`jules` ラベル HTTP 200 ／ `@codex` コメント HTTP 201・00:13:13〜14） |
| 返ってきた | **3回**（00:13:20／00:13:35／**00:24:12**＝6秒後・21秒後・11分後） |

- `chatgpt-codex-connector[bot]` … 返事は来た。中身は **「You have reached your Codex usage limits」＝枠切れ。**
  口は通じている。仕事はできない。**課金はたまごさんの判断なので触っていない。**
- `google-labs-jules[bot]` … **「Jules is on it」**（00:13:35）→ **11分後の 00:24:12 に
  「Ready for a review! A PR ...」＝PRまで立った。**
  ★**81回走って0件だったものが、起こした瞬間に動いた。**拾い口は壊れていなかった。
  **次のセッションは、まずこのPRを見て検品すること。**

★**Copilot・Grok・Genspark には投げていない。**4つの口が閉じているのは実測済み（`status/977_copilot_jissoku.md`）。
催促も回数も増やしていない。

数え方：`python3 tools/_1026_446_hakaru.py`（Mac側・起こした回数と返り回数を台帳に書く。
★二度数えない作りにしてある）。

## ★保留にした組 ― `status/1026_shiire_horyuu.md`

**12組は、わざと積んでいない。**「たぶんこの人」で埋めれば率はもっと下がるが、嘘が増える。

| 組 | 止めた理由 |
|---|---|
| IO | 1位ブラジル(100)／2位カナダ(95)／3位オーストリア(90)。フジロックのIOが誰か決められない |
| KOTORI | 1位アメリカのEDM(100)／2位ノイズ(99)／**3位に日本のロックバンド(96)**。3位が本命に見えるが決め手が無い |
| TESTSET / the cabs | 1位が日本のバンドだが、2位3位と2〜3点しか離れていない |
| THURSTON MOORE GROUP | 同定は通るが MusicBrainz に曲が0件 |
| maya ongaku ほか | MusicBrainzが候補を返さなかった（FRIKO・QUADECAは取り直して積めた） |

**決めるのに要るもの**：その組の出身地か公式の綴り。フェスの名簿には名前しか無い（実測）。

---

## 次の一手（上から）

1. **Jules のPRを見る。**#446 に 00:24:12 に立っている。出たものを検品して取り込む。
2. **仕入れを続ける。**`status/mac_jobs/pending/` に `--from-queue 6` の紙を置くだけ。
   Macが15秒以内に走らせて `status/shiire_raw/` に素材が落ちる。そのあと
   `python3 tools/_1026_kouho_write.py <slug>...` で骨を作る。★手で曲名を書かない。
3. **保留12組**：たまごさんに「この組はどれ？」と見せるか、別の出どころ（公式サイトの出身地）を足す。
4. **棚出しはまだしない。**棚に出すときは、①音を聴いて `why` を書く（いまは並びから言えることしか書いていない）
   ②動画を検品する（素人カバー・静止画だけの動画を弾く。いま全件「未確認」）③初出年を取り直す
   （候補の年は**MusicBrainzの登録日**で、再録・再発があると初出と食い違う。実測：American Football「Never Meant」）。

## この工場の道具（探さなくていいように）

- サンドボックスからは api.github.com も musicbrainz.org も wikipedia.org も**出られない**。Macからは出られる。
- Macに走らせたいものは `status/mac_jobs/pending/<名前>.sh`。15秒以内に1回だけ走り、
  結果が `status/mac_jobs/done/<名前>.out`。**同時に1本・180秒で強制終了。**
  ★`gh` はPATHに居ない（launchd）。`export PATH="/opt/homebrew/bin:$PATH"` を書くか、
  `github_watch.gh_token()` でトークンを取って REST を直に叩く。
- **gitはサンドボックスから叩かない。**`python3 tools/commit_kuchi.py --request <path...>` で紙を置く。
