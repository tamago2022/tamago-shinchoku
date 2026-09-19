# falを触る前に（案件#437・2026-09-06）
**falを触る前に、Vaultの教材ファイル `MODEL_TABLE.md`（`AI出力/falの教科書_教材ファイル一式/fal-kyokasho/MODEL_TABLE.md`）を必ず見る。**
`share/check/316-fal-hayamihyo.html`等の早見表URLはこれまでどおり参考にしてよいが、型番・単価の正本は教材ファイルのMODEL_TABLE.md。

# falの予算管理・完了報告のルール（案件#632・2026-09-07）
たまごさん「何のモデルを使ったのかっていうのが気になるよね。何の動画で何を使ったのか」「捨てたものにいくら使ったか、ここが一番痛い数字」。

**falを使った作業の完了報告には、必ず「モデルの正式な型番／回数／単価／合計（円とドル）／かかった時間」を書く。書いていない報告は不合格。**

**1回投げるごとに、`tools/fal_cost_ledger.py` で帳簿（`status/fal_cost_ledger.json`）へ1行記録する。**
```
python3 tools/fal_cost_ledger.py --add --n <案件番号> --title "<何を作ったか>" \
  --model "<正式な型番>" --what "<何を作ったか>" --count <回数> \
  --unit-cost-yen <円> --result adopted|discarded|failed_no_charge \
  --elapsed-min <分> --note "<補足>"
```
既に同じ内容があれば二重に足さない（冪等）。**捨てた（不採用にした）ものも必ず記録する**（`--result discarded`）。金額がドルしか分からない場合は `--total-cost-usd` を使えば自動で円換算される。

**高い実行（目安：1回で100円を超える見込み）を投げる前に、上限を超えないか先に確認する：**
```
python3 tools/fal_cost_ledger.py --check-budget <見積もり円>
```
`ok: false` が返ったら、**たまごさんに聞く前に、まず安い経路（低解像度・短尺・別モデル）へ落とせないか試す。**

帳簿は進捗表（`index.html`）の「できたもの」棚のすぐ下、「💰 falの予算（モデル別）」に自動で表示される（今月合計・モデル別合計・1本あたり最安・捨てたものの合計）。詳細・実装の経緯は `share/check/632-fal-budget-ledger.html`。
