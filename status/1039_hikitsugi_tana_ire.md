# 1039番 引き継ぎ：棚とカードを結ぶ表が分かった／入れる係を作った／★入れる鍵が無い

2026-09-23 15:55 / このセッションで叩いた結果だけ。叩いていないものは「叩いていない」と書く。

---

## 1. ★結び目の表が分かった（前便の宿題）

**`admin_shelf_picks`。** 列は `id / shelf_id / stock_id / position / status / pinned`。

- 当てずっぽうの名前叩き（job `20260923-153749-9227`）は候補11個中**10個が404**で外れた。
  唯一200だった `cover_hub_edges` は曲どうしの関係で、棚とは無関係だった。
- 名前を当てるのをやめて、**joy-relief-station のコードを読んで確かめた。**
  `status/_1039/lib/adminShelves.functions.ts`:1199（画面の［棚に入れる］の中身）
  ```
  insert({ shelf_id, stock_id, position: max+1, status: "candidate", pinned: false })
  ```
- **表に出る条件**も正本で確かめた：`lib/publicShelves.functions.ts`:462
  → status が `excluded` と `unmarked` **以外**は表に出る。`candidate` も出る。
- だから入れる係は**画面のボタンと1文字も違わない行**（`candidate`）を作る。

★カードは `admin_stock`、棚との結び目は `admin_shelf_picks`。**2段。** ここを1段と思うと事故る。

---

## 2. ★入れる鍵が無い（これが今の壁。実測で確定）

job `20260923-155145-5529`（捨て行を1つ作って、通っても通らなくても必ず消して帰る下見）：

| 叩いたもの | 結果 |
|---|---|
| `POST /rest/v1/admin_stock` | **HTTP 401 `42501` row-level security policy** |
| `POST /rest/v1/admin_shelf_picks` | **HTTP 401 `42501`**（job `20260923-154909-9230` で実測） |
| `GET` 両方 | 200（読める） |
| `PATCH /rest/v1/admin_stock` | 200（`gaibu_copy_naoshi` が毎朝書けている） |

Macの `.env` にある一番強い鍵は `SUPABASE_PUBLISHABLE_KEY`。
`find_write_key`（`tools/gaibu_copy_naoshi.py`:362）は SERVICE_ROLE → SECRET → PUBLISHABLE の順に
探して**一番強いものを採る**作りで、それが PUBLISHABLE だった＝**service_role の鍵がMacに無い。**

→ **読む・直すはできる。新しく入れるだけができない。**
→ 入れる係は全部できているので、**鍵が1本来た日から動く。**

★**残骸はゼロ。**下見で作った行は全部消して帰った（`nokori` 空）。棚のデータは1文字も汚していない。

---

## 3. ★戻す係は「作ってから入れる」順で作った

`tools/nagekomi_shelf.py --modoshi <便番号>`。控えは `status/nagekomi_ireta.jsonl`。

- 消す前に、その行の `stock_id` と `shelf_id` が控えと一致するか**必ず確かめる。**違えば触らない。
- カードが**他の棚でも使われていたら、カードは残す**（結び目だけ外す）。他人の棚を壊さない。
- 元から在ったカードに結び目だけ足した場合は、**結び目だけ外す**（`madeStock` で見分ける）。
- 結び目を作れなかったときは、**その直前に作ったカードも取り消す**（倉庫に置き去りを作らない）。
  ★この取り消しは、今回の401で実際に効く形にしてある（今回はカードが元から在ったので発火せず）。

★**戻しの実測はできていない。**入れられていないので、戻すものが無い。鍵が来た日が実測の日。

---

## 4. 作ったもの

| ファイル | 何を |
|---|---|
| `tools/nagekomi_shelf.py` | ★新規。台帳→コピー→関所→棚。`--modoshi`／`--dry`／`--only`／`op=shirabe`／`op=kagi` |
| `tools/gaibu_runner.py` | kind `tanaire` を追加 |
| `tools/machine_status_push.sh` | 5分便に1行。**深夜0時すぎの最初の便で1日1回走る** |

**通る門（どれも新しい基準を発明していない。既にある正本を輸入している）：**

| 門 | 正本 |
|---|---|
| ボンジョビおじさん構文 | `tools/gaibu_copy_naoshi.py` の `PROMPT`（枠だけ「店主の方向性」に読み替え） |
| 水道水の判定 | `tools/gaibu_copy_nippou.py` の `judge()` |
| 鬼監督 | `tools/oni_gate.py` の `judge()` |
| 出典の取れない断定 | `fact_gate()`。材料に無い年号・「原曲」「代表曲」「カバー」「受賞」・固有名を落とす |
| アーティスト取り違え | ★`detected_artist_id` を**書かない。**紐づけないことで、字が一致しただけの事故を確実に防ぐ |

★**英語の原題は捨てずに日本語の題名を書く。**`nippou.judge` は「題名が英語の原題のまま」を落とすので、
落として捨てるのではなく日本語題名を書き、**原題は `note` に控えて残す**（`note` は公開側で読まれない）。

★**棚が指定されていないものは入れない。**「行き先未定」のまま `mitei` に出す。
（台帳の15:26の1本は `shelfId` が `cute`＝世界の名前で、棚の名簿に無い。だから未定に落ちる。）

---

## 5. ★もう1つの赤：コピーの書き手が今日は2人とも止まっている

job `20260923-154540-0300`（下見・入れずに走らせた）：

```
日本語の題名が書けなかった：
  claude -p ＝返らず ／ 控え＝openai 上限で止めました（今日の上限 0円・使った 0.00円）
                        gemini 鍵なし ／ grok 上限で止めました（今日の上限 0円）
```

今朝06:25の `gaibu_copy_naoshi` は控えの口（gpt-5-mini・0.522円）で**書けていた**。
＝**今日の外部の口の上限が0円に落ちている。**鍵が来ても、ここが0円のままだとコピーが書けない。

★だから道そのものを実測できるように、`--only` の1件に限り
**人（編集者）が書いた題名・ひとことを持ち込む口**を付けた（`teuchi`）。持ち込んでも関所は同じように通す。
毎日の便では使わない。

---

## 6. 通していないもの（正直に）

1. **棚に1行も入れていない。**INSERT は401で1件も通っていない（2）。
2. **戻しの実測をしていない。**入れていないので戻すものが無い（3）。
3. **本番の画面を見ていない。**入っていないので見るものが無い。375pxも撮っていない。
4. **`nagekomi_shiji.jsonl` を反映する係は、まだ無い**（1036番から変わらず）。

---

## 7. 次の便の最初の一手

```
# ① 鍵が来たか見る（値は見ない。名前だけ）
python3 -c "import sys;sys.path.insert(0,'tools');import gaibu_kuchi as g;print(g.enqueue_job('tanaire',{'op':'kagi','shelfId':'3bbc7c3d-ef34-485a-a47a-236e4a33a100'}))"
→ admin_stock INSERT / admin_shelf_picks INSERT が「通った」になったら次へ

# ② テスト用に1本だけ入れる（★たまごさんに試させない）
python3 -c "...enqueue_job('tanaire',{'only':'<台帳のid>','bin':'1039test'})"

# ③ 入ったか本番で見る → ④ 戻す
python3 -c "...enqueue_job('tanaire',{'op':'modoshi','bin':'1039test'})"
```

★**鍵は `SUPABASE_SERVICE_ROLE_KEY` をMacの `.env` に1行足すだけ。**
値はここに書かない。たまごさんがLovable/Supabaseの画面からコピーして貼る1手。
