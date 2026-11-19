# 引き継ぎ 1025 ― Copilotは通らなかった／仕入れを10組積んだ（2026-09-22 23:0x〜23:3x）

前のセッション（977番）からの3件、**3件とも手を付けて、3件とも決着している。**

---

## ① GitHub Copilot ＝ 通らない。投げるのをやめた

詳細は **`status/977_copilot_jissoku.md`**（叩いた4つの口と、返ってきたものを全部そのまま）。

**4つ叩いて4つとも閉じていた：**

| 叩いた口 | 返り |
|---|---|
| Issue #457 ＋ `@copilot` コメント | 返事0・**👀の反応も0**（受け取ってすらいない） |
| REST で `copilot-swe-agent[bot]` を担当者に | **403 Forbidden** |
| GraphQL `suggestedActors(CAN_BE_ASSIGNED)` 両リポ | **Copilotが候補に出ない**（`tamago2022` だけ） |
| `gh agent-task create`（gh 2.98.0・OAuth `gho_` で） | **403 Forbidden** |

**どのリポで動くのか＝どちらでも動かない。**公開/非公開の問題ではなく、アカウントに権利が無い。
開けるには **Copilotの有料プラン（Pro/Pro+/Business）＝課金**。たまごさんの判断なので触っていない。

**数：投げた1回 → 返り0回。**板では 🔴 のまま出す（実際に投げたので嘘にしない）。
`tools/nageru.py` の `copilot` を `how="blocked"` にしたので、**以後は投げずに止まる**（理由つき）。
Grok・Genspark と同じ扱い。

### 開けたくなったら、確かめ方はこの1行だけ
```bash
gh agent-task create "README.md を3行で要約してコメントで返してください" -R tamago2022/ai-kaigi
```

---

## ② 仕入れ ― それはありませんね率

| | 前 | 今 |
|---|---|---|
| **棚の率**（本当の数字） | 89.0% | **89.0%（変えていない）** |
| **候補まで含めた率** | 89.0% | **84.6%** |
| 候補が積まれた組 | 0組 | **10組（49曲）** |

★**棚には1曲も出していない。**棚に置くかはたまごさんの判断なので、候補で止めてある。
だから**棚の率は動かない。**動かせるのは「候補まで含めた率」のほうで、そちらを
`tools/fes_meibo.py` が2本並べて出すようにした（数字を薄めないため）。

積んだ10組（フジロック'26の名簿の上から）：
平沢進+会人 / TURNSTILE / MOGWAI / LOYLE CARNER / TORO Y MOI（DJ名義ぶんも同一人物として1組）/
JOEY VALENCE & BRAE / Bialystocks / KNEECAP / SON ROMPE PERA

見る場所：`share/check/990-shiire-kouho.html`

### 足した道具

| ファイル | 中身 |
|---|---|
| `tools/shiire_fetch.py` | Mac側で MusicBrainz と Wikipedia の**原文だけ**を集める。★**曲名を記憶から書かない。同定した mbid から引く**（`works()`）。名前一致で別人の曲を拾う事故を構造で止める |
| `tools/fes_meibo.py` | 「候補まで含めた率」を追加。棚の率と**必ず2本並べて**出す |

### ★この作業で踏んだ穴（次が踏まないように）

**Wikipediaの検索1件目をそのまま採ると事故る。**実測でこうなった：

| 探した名前 | 1件目に来たもの |
|---|---|
| TURNSTILE | **改札機**の記事 |
| Trueno | **トヨタ スプリンター トレノ**（車） |
| IO | **木星の衛星イオ** |
| GRAPEVINE | **ブドウの木（Vitis）** |
| Riddim Saunter | **フジロックの記事そのもの** |
| Yo-Sea | **CDレガネス**（スペインのサッカークラブ） |

→ `shiire_fetch.py` に「上位3件の本文を見て音楽の記事らしいものを採る。どれも音楽でなければ
**見つからなかったと返す**」を入れた。**一番近いものを当てはめるのが一番いけない。**
ただし今度は `(album)` の記事を人物の記事より先に採ることがある（Loyle Carner→Hugo (album)）。
**ここはまだ直っていない。**次のセッションで `(album)` を下げること。

### まだ素材だけあって候補にしていない組
`status/shiire_raw/` に、GEORDIE GREEP / SOFIA ISELLA / KOTORI / BOHEMIAN BETYARS /
GRAPEVINE / Riddim Saunter / Yo-Sea / TOMORA / IO / Trueno / DONAVON FRANKENREITER の原文がある。
このうち **MusicBrainzの同定が取れていない／Wikipediaが別物だった組**は、
先に `shiire_fetch.py` で取り直すこと（取り直さずに書くと嘘になる）。

---

## ③ アバターの返信拾いが81回走って0件（969番）＝原因だけ特定した

詳細は **`status/969_返信0件の原因.md`**。

**拾う側は壊れていない。拾う先に外部AIの返事が1件も無い。**

| 見張り先 | コメント |
|---|---|
| joy-relief-station #446 | 1件だけ。**書いたのは tamago2022 本人**で `<!-- tamago-factory -->` 付き＝設計どおり飛ばす |
| ai-kaigi #1 | **0件** |
| ai-kaigi #3 | **0件** |

ai-kaigi には bot が1体も居ない。#446 には **`jules` ラベルも `@codex` も付いていない**＝
**誰も起こしていなかった。**977番とまったく同じ病気。直すのは次（たまごさん指示）。

---

## 次の一手（上から）

1. **#446 に `jules` ラベルを貼る／`@codex` を打つ。**新しい号を立てるより安い。
   `targets.json` から bot の居ない ai-kaigi#1/#3 を外す。
2. **仕入れを続ける。**`python3 tools/fes_meibo.py --queue` の上から、
   Mac側で `python3 tools/shiire_fetch.py --from-queue 10` → 候補を書く、の繰り返し。
3. `shiire_fetch.py` の Wikipedia 選びで `(album)` を人物・バンドより下げる。
4. **★関所をひとつ足す：「見張る先／投げる先を足すとき、そこに起こす引き金があるかを確かめる」。**
   977番と969番で**同じ事故が2回**起きている＝仕組みの不在（憲法20条）。

## この工場の道具の場所（探さなくていいように）

- サンドボックスからは **api.github.com も musicbrainz.org も wikipedia.org も出られない**
  （proxy が CONNECT を 403 で切る）。**Macからは出られる。**
- Macに走らせたいものは `status/mac_jobs/pending/<名前>.sh` を置く。15秒以内に1回だけ走り、
  結果が `status/mac_jobs/done/<名前>.out` に出る。**同時に1本ずつ・180秒で強制終了。**
- **gitはサンドボックスから叩かない。**`python3 tools/commit_kuchi.py --request <path...>` で紙を置く。
  Mac側の5分便だけが、その紙を回収して本番へ載せる。口が1本なので取り合いが起きない。
- Mac上の棚 `~/Desktop/joy-relief-station/.../coverGuide.ts` は **09-09 で古い**。
  率の計算は `status/_936/keep/` のスナップショット（09-18）を使っている。こちらが新しい。
