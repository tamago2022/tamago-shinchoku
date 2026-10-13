# 1151 Genspark と Devin の棚卸し（やったこと／役に立ったか）

## いまどこ
- 資料の洗い出し完了。数字は全部下の出どころから取った。ブラウザ不使用・追加課金0円。
- 残り：紙を1枚書いて進捗表から繋ぐ。

## 出どころ（全部この repo の中。憶測ゼロ）
- 台帳 status/gaibu_ai/daicho.jsonl（50行）／status/ai_daicho.jsonl（95行）
- Genspark：status/1136_hikitsugi_genspark.md ／ 1058_hikitsugi_genspark.md ／ 1032_hikitsugi_genspark_1531.md
  ／ AI_NEDAN.md:28-52 ／ status/fukumen_kyaku/daicho.jsonl ／ 1130_MARUNAGE_TO_ANKEITO.md ／ 1143/te_5tsu.md ／ gsk/zan.json
- Devin：status/1059_hikitsugi_devin.md ／ devin_990_report.md ／ 1142/log.md:21-34
  ／ mac_jobs/done/1a_devin_jissoku.out（26本）／ devin-night-2026-09-18.md
- 横並び：status/public/soto_hatarakite.json ／ public/tekizai.json ／ public/uketori_machi.json

## 確定した数字
### Genspark
投げ22／返り16／本番2＋採用1／使った1,336.1credit（1924.937→588.837 実測）／残588.837（9/25が最後の実測・10/4で消滅）
★1,336.1のうち **1,326 は Claw 1回＋AI Developer 2回**（9/24）。この3回の**成果物はrepo内に1件も無い**（全文検索で0件）。
＝「急にガーッと減り出した」の正体。仕事に使ったのは約10.1credit だけ。
### Devin
投げ26／PR返り5（19.2%）／main3／本番1（3.8%）／1,327円（9/18〜20の15本＝$8.85）
1本88円／本番1件あたり1,327円。残ACUはAPI閉鎖（403/404）。画面実測＝週枠100%・リセット9/27・残高-$0.30。

## Devin 残ACU（たまごさんのスクショ実測・2026-09-26 依頼文より。APIでは取れないためこれが唯一の出どころ）
- 週の枠：100% 使用
- リセット：9/27
- 残高：-$0.30
## 運用の決まり（既出のルールの再掲）
- Devinは1本ずつ投げる／3時間で帰らなければ交代（status/1065_hikitsugi_tekizai.md の交代規則）
- サンドボックスからはgitを叩かない。status/commit_inbox に紙を置き、Mac側の5分便が載せる（tools/commit_kuchi.py）
