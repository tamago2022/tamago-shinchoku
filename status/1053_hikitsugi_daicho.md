# 1053番 引き継ぎ：受付台帳（言われたことを埋もれさせない）

## 出来たもの

| もの | 場所 | 状態 |
|---|---|---|
| 工場の待ち行列（正本） | `tools/shigoto_queue.py` | ✅ 本番で動いている（04:12に復活を実測） |
| 受付台帳（本体） | `tools/daicho.py` | 🟡 実装・自己試験済み |
| 台帳の種まき（数を機械で数える） | `tools/daicho_tane.py` | 🟡 21行を投入済み |
| 台帳の画面 | `share/daicho.html` | 🟠 **本番はまだ404**（下記） |
| Spotifyの押す入り口1枚 | `share/spotify-hitotsu.html` | 🟠 同上 |
| 心臓への相乗り | `tools/machine_status_push.sh` の `quick_tick` | 🟡 3行追加済み（`--kigen` `--hi` `--page`） |

## 直した故障（仕事0）

**症状**：09-24 03:35:42 を最後に工場が1件も仕事を拾わなくなった。ログにも何も出ない。

**原因（実測）**：03:38に `tools/gaibu_kuchi.py` が**丸ごと書き替えられた**（外部の判定役を呼ぶ別物に）。
その拍子に `JOBS_DIR` / `enqueue_job` / `wait_job` / `write_job_result` が巻き添えで消え、
`gaibu_runner.py` が **import の行で落ちる**ようになった。import で死ぬのでログにも残らない。

**直し方（穴を塞がずパイプごと替えた）**：
- 待ち行列を `tools/shigoto_queue.py` に**独立させた。**このファイルは待ち行列以外のことを一切しない
  （外部AIを叩かない・鍵を読まない）＝**書き換える理由が発生しない。**
- `gaibu_runner.py` は `shigoto_queue` を直接 import する。`gaibu_kuchi.py` が今後また
  丸ごと作り替えられても、工場は死なない。
- `gaibu_kuchi.py` は互換のために再輸出するだけ（既存の呼び出し元9本はそのまま動く）。
- ついでに：`net_ok()`（api.openai.com が出るか）が取れないだけで**列ごと止まる**作りも直した。
  kakunin / yomu / sumaho / daicho は外部APIを使わないのに、それで止まっていた。

**確認**：`python3 tools/shigoto_queue.py --selftest` → 置く→書く→待つ が通る。
本番でも 04:12:31 から仕事を拾い始め、03:42に詰まっていた票が流れた。

## いま止まっている1つ（次の人が最初にやること）

**`share/daicho.html` が本番で 404。** 台帳の3番目の行そのものが目の前で起きている。

実測（09-24）:
- 04:24:35 `pages_publish.sh` が main を `dc5c83c64` まで追従（＝share/daicho.html は入っている）
- 04:32:35 `…公開の push が落ちました（1回目）` → **その後「公開しました」の行が出ていない**
- トップ `https://tamago2022.github.io/tamago-shinchoku/` は **200**
- 同じコミットの `share/daicho.html` は **404**

→ **「pushした」と「本番に出た」がズレたまま。**
→ 潰す手：`pages_publish.sh` の push が落ちた回数と最後に成功した時刻を
  `status/public/` に数字で出し、落ちたままなら進捗表のトップに赤で出す。
  黙って古いまま生き続けるのが一番たちが悪い壊れ方。

## ★サンドボックスから git を叩かない（今日また踏んだ）

`status/commit_inbox/` に紙を置くだけが正しい：

```bash
python3 tools/commit_kuchi.py --request <パス> --why "<理由>" --from <名前>
```

直接 `git add/commit` を叩くと `.git/index.lock` が残り、サンドボックスからは
消せない（Operation not permitted）＝**工場のgitが丸ごと止まる。**
04:09に再発させた。台帳に `gitlock` の行として残してある。

## 台帳の使い方（これだけ覚えればいい）

```bash
python3 tools/daicho.py --ireru "<言われたこと>"        # 言われた（同じ内容なら回数が+1される）
python3 tools/daicho.py --susumu <id> --made "<1行>"    # どこまで進んだかを上書き
python3 tools/daicho.py --koutai <id> --riyuu "<理由>"  # 次の選手へ（--dare で名指しもできる）
python3 tools/daicho.py --tsubushita <id> --url <URL>   # ★URLが無いと機械が拒否する
python3 tools/daicho.py --ichiran                       # 端末で一覧
```

- **1人3時間。**超えると心臓が `--kigen` で機械的に交代させる。人が判断しない。
- **「どこまで進んだか」を残さずに終わると、台帳に「★進捗の記録なし（禁止事項）」が赤で残る。**隠せない。
- 選手の順：子セッション(Claude) → Jules → Devin → Genspark → Jev → たまごさんの1手
- **URLが無いものは「潰した」にできない。**push だけでは潰したことにならない。

## 数字の出どころ（手で書いた数字は1つも無い）

- 回数 ＝ その件に触れている**仕事票の本数**（`status/queue.json`）＋**引き継ぎメモの本数**（`status/*.md`）。
  内訳は台帳の `moto` に残る。`python3 tools/daicho_tane.py --dry` で数え直せる。
- 最初の日 ＝ `dispatch_outbox.jsonl` の実測 ts から n→日付を引く。
  引けない n は「**遅くともこの日には存在した**」側に倒して `推定` の印を付ける（＝日数は必ず控えめ）。

## 次にやること（上から）

1. **`share/daicho.html` を本番で開けるようにする**（＝台帳の3番目の行を潰す）
2. 投げ込み箱：`URL＋棚` の組み合わせだけが弾かれる（04:16 スマホの門で実測）。入力チェックの条件式
3. Spotify：たまごさんが `share/spotify-hitotsu.html` を押したら、`--hajime` → `--shirabe` → `--ireru` を一気に
4. 別人混入2230件：Jevで yes/no 判定（**約147円**。`tools/yosan.py` の栓を先に通すこと）
