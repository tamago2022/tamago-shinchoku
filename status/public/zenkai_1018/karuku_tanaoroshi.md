# Macを軽く：重い常駐・定期処理の棚卸し（120042番・2026-10-18）

機械で作った一覧（心臓・top_status・launchd・ps の実測）は同じ場所の `karuku_tanaoroshi.json`。
前後の数字は `karuku_jissoku.json`。一時ファイルは `kesu_kouho.md`。

## 1. 直す前の実測（06:0x）

| 項目 | 値 | 読み方 |
|---|---|---|
| ロード平均（1分／5分／15分） | 26.08／18.05／21.25（8コア） | 「待ち行列の長さ」。固まる手前に見える数字 |
| CPU使用率（user+sys） | 59.1%（idle 40.9%） | 実際は半分空いている |
| メモリ | 空き83%・スワップ 19.6/20.0GB | メモリ圧は緑。スワップは Brave で一日中張り付き |
| ディスク空き | 248GB | 問題なし |
| 工場の Python 同時本数 | 15〜17本（3回標本） | 心臓の相乗りが常にこれだけ立っている |
| 負荷判定（fuka_hassha） | 直近400件中 399件が「上限1本」 | ロード比（中央値1.12）だけで「重い」と判定していた |

**原因（初心者向け）**：ロード平均は「CPUの順番待ちをしている人数」。心臓が15秒ごとに約25本の小さな Python を一斉に起こすと、
どれも数秒で終わるのに、起きた瞬間は全員が列に並ぶので人数（ロード）だけ跳ね上がる。CPU そのものは半分空いていた。
そのロードだけを見て、工場は自分で自分の発車を止めていた。

## 2. 回数×重さで並べた重い常駐（上位）

| 順 | 何 | 回数 | 1回の重さ | 直し |
|---|---|---|---|---|
| 1 | `top_status.py` の相乗り（_okosu 22本） | 15秒ごと＝最大 約5,300本/時 | 1本 数十ms〜数秒 | **60秒に1回**へ（窓口 oneshot_runner・起動係 1401_kidou は毎周）→ 最大 約1,800本/時 |
| 2 | `heartbeat.sh` の相乗り（python 起動） | 約2,540本/時 | 同上 | 二重の2本を一本化（下記）。心臓本体は走行中なので再起動時から |
| 3 | `machine_health.py` の `top -l 1` | 2分おき＝720回/日 | **実測41秒・system CPU 7.6秒**（top は全プロセス・全スレッドを舐める） | `iostat`（1.2秒・CPUほぼ0）へ置き換え。読み手は無かった |
| 4 | 二重呼び出し | tomaranai：launchd 1分＋心臓1分／oni_codex hirou：心臓2分＋top_status 15秒／1163_kagi_machi：心臓30秒＋top_status 15秒 | — | 心臓側に一本化。tomaranai の心臓側は10分に |
| 5 | `1191_`/`1192_` の tar 展開 | 約4分おき×2本 | 140MB を消さずに帰る | atexit で自分で消す＋使い捨て1時間に追加（106個・+5.2GB） |
| 6 | Brave Browser Helper（GPU） | 常駐 | 9日平均 CPU 94.7% | **触らない**（たまごさんの場所）。記録のみ |
| 7 | com.apple.Virtualization.VirtualMachine | 常駐2日 | RSS 8.0GB | 持ち主は未確認。触らない。記録のみ |
| 8 | hps-patrol-*（joy-relief-station の esbuild） | 約400個/時 | 1個 数MB | 使い捨て1時間で消えている。作る側に exit で消す線を足すのが次の一手 |

launchd（17本）は 1分おき tomaranai・2分おき keep-warm（curl 2本）・10分おき genzaichi-sync・15分おき machine-status・30分おき video-patrol・1時間おき role-sweep・3時間おき disk-guardian、ほかは毎日1回＝それ自体は軽い。cron は無し。

## 3. 直したこと（全部、元に戻せる）

1. **負荷判定**（`tools/fuka_hassha.py`）：ロード比だけで止めない。CPU使用率（`iostat -c 2 -w 1` の us+sy）とメモリ圧で決める。
   CPU<50%→4本／<65%→3本／それ以外2本／≥75%→1本／≥92%→止める。CPUが測れない時だけ従来のロード比。
   スワップ90%超は「メモリ圧が緑で空き30%以上」なら数えない（10-15 の方針と同じ）。`top` は使わない（41秒かかる）。
   `--self-test` に11項目を追加（従来の落ちていた1件も10-15の方針に合わせて直した）。
2. **top_status.py の相乗り**：`_okosu` を60秒に1回へ。oni_codex hirou・1163_kagi_machi は心臓側に一本化。
3. **machine_health.py**：2分おきの `top -l 1` → `iostat`。
4. **heartbeat.sh**：tomaranai を tick_every 4（1分）→ 40（10分）。※動いている心臓には再起動時から効く。
5. **youryou_jougen.py**：使い捨てに `1191_`・`1192_`・`1192h_`。**1191／1192**：atexit で自分の一時フォルダを消す。
6. **台帳** `tools/jidou_daicho.json`：間引いた係に `mabiki_1018`（理由）を書いた。未登録だった定期タスク2件を「仮」で登録（関所 PASS）。

## 4. 直した直後の実測（07:44・この作業場で）

| 項目 | 前 | 後 |
|---|---|---|
| ロード平均（1分） | 26.08 | 12.36 |
| CPU使用率 | 59.1% | 41.0% |
| メモリ空き | 83% | 84%（圧＝緑） |
| 工場の Python 同時本数 | 15〜17 | 9 |
| 負荷判定 | 上限1本（399/400） | **上限4本**（CPU41%・緑） |
| 空き容量 | 248GB（df） | 247GB（df）／削除で +5.2GB（statvfs） |

注意：ロードと本数の「後」は、他のセッションの出入りも混ざる瞬間値。心臓の間引きは main 反映後に効くので、効き目は明日の `status/fuka_hassha.jsonl`（上限の分布）で見る。

## 5. 次の一手

- joy-relief-station `scripts/patrol/loadShelfCards.mjs`：`process.on("exit", () => rmSync(outdir, {recursive:true, force:true}))`（hps-patrol を作る側で消す）。
- 心臓（heartbeat.sh）の次回再起動後に `ps` で Python 同時本数を再測（目安：10本未満）。
- 8GB の VirtualMachine の持ち主を確かめる（lsof は許可が要る可能性があるので未確認）。
