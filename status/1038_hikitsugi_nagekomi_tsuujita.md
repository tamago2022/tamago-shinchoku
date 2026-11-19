# 1038番 引き継ぎ：投げ込み箱を通した／「毎日やること」を列から外した

2026-09-23 13:33 / このセッションで叩いた結果だけ。叩いていないものは「叩いていない」と書く。

---

## 1. 出したもの

| もの | URL / 場所 |
|---|---|
| 報告1枚 | https://tamago2022.github.io/tamago-shinchoku/share/check/1038-nagekomi-tsuujita.html |
| 投げ込み箱（前の便） | https://tamago2022.github.io/tamago-shinchoku/share/nagekomi-c5fd9d5791b32e88.html |

`tools/kazu_gate.py` 通過（「数字9件、全部に出どころがあります」）。
公開は `tools/kohyou.py`（GitHub API直叩き）。1枚目は job `20260923-132751-1313` で
**HTTP 200・must 4語すべて true** を実測（この報告は差し替え版なので、URLは同じ）。

---

## 2. 完了条件は3つとも通った（★機械が投げた。たまごさんには試させていない）

| 条件 | 結果 | 証拠 |
|---|---|---|
| ① テストURLを1本投げて台帳に入る | ◯ | `status/gaibu_jobs/done/20260923-131710-0661.json` via loca.lt HTTP 200 / 9.2秒 |
| ② 投げた瞬間に中身が自動で埋まる | ◯ 4つとも | `status/nagekomi.jsonl` → 題名 Bon Jovi - Livin' On A Prayer / BonJoviVEVO / 2009-06-17 / 4:09（YouTube Data API v3 200） |
| ③ 「あとでまとめて喋る」が残る | ◯ | `status/gaibu_jobs/done/20260923-131710-0685.json` HTTP 200 / `status/nagekomi_shiji.jsonl` 1行（unapplied） |

---

## 3. ★前の便の見立ては外れていた（ここが今回の本体）

前の便は「`relay_up.sh` が古いコードを見つけて自動で入れ直す」と書いていた。**外れ。**

- `relay_up.sh` は**もう誰も呼んでいない**（`tools/machine_status_push.sh`:402「relay_up.sh はもう呼ばない」）
- 今の見張りは `tools/relay_watch.py`。判定は**「外から叩いて200が返るか」だけ**だった
- → **外から繋がっている限り、受け口は古いコードのまま永久に走り続ける**
- 起動の判子 `status/.relay_server_started` は 09-16 22:14 のままだった

### 直し方（パイプを替えた）

`tools/relay_watch.py`:90 `restart_server_if_stale()` を足した。

- `tools/*.py` のいちばん新しい更新時刻 > 起動の判子 なら、**受け口だけ**入れ直す
- トンネル（localtunnel）は `localhost:8788` を見ているだけなので**URLは変わらない**
- 入れ直しは120秒に1回まで。判子は**起こす前に**押す（起こせなくても毎回 pkill し続けない）
- 入れ直した回はそこで `return 0`。続けて生死を見ると立ち上がりの数秒を
  「トンネルが死んだ」と誤読して**トンネルまで張り直す**（13:26 に実際に1回起きた）

**実測：自分で2回入れ直した。** `status/relay.log`
「13:21:31 受け口を入れ直しました（ローカル200・実測）」「13:26:00 同」

---

## 4. 足した口（工場側・`tools/gaibu_runner.py`）

| kind | 何をする | 実測 |
|---|---|---|
| `relayup` | 今すぐ受け口を入れ直す（`payload.force` で判子を無視） | job `20260923-131451-1533` restarted true / health 200 / 3.4秒 |
| `relaytest` | ★スマホの代わりに中継所へ1本投げる（`tools/relay_nage.py`） | 上の①③ |
| `mainichi` | 毎日やることの口を今すぐ走らせる | job `20260923-132400-0332` 5.6秒 / 0円 |

呼び方：
```
python3 -c "import sys;sys.path.insert(0,'tools');import gaibu_kuchi as g;print(g.enqueue_job('relaytest',{'action':'nagekomi','target':'https://…'}))"
```

---

## 5. ★「毎日やること」を列から外した

**替える前：** `daily_ingest_scheduler.py` が毎朝 `queue_add(priority=3)` で列に積む
→ 発車待ちが164件あって最後尾 → **11日ぶん積んで1本も走らなかった。**

**替えた後：** `tools/daily_ingest_scheduler.py`:177 `_mainichi_kuchi()` が
`tools/mainichi_kuchi.py` を呼ぶだけ。**列には積まない。**

`mainichi_kuchi.py` は `gaibu_copy_naoshi.py` と同じ型：
- 朝6時以降・1日1回のゲート（`status/.mainichi_kuchi_last`）
- ロック（`status/.mainichi_kuchi.lock`・60分で詰まりとみなす）
- 持ち時間5分。新しい常駐は増やしていない（心臓に相乗り）
- ★**取れなかった日はゲートを押さない**（走ったことにして黙るのが一番まずい）

### ★棚（Lovable / admin_stock）の扱い
- **拾う・調べる・下書きを作る** までが自動。**GETだけ**。棚には1文字も書かない
- 棚へ書く最後の1歩は `status/public/mainichi_oshidake.json` に「押すだけ」で並ぶ
- ★`status/public/uketori_machi.json` には**相乗りしていない**。
  あれは `tools/baton.py`:69 が毎回まるごと書き直す持ち物で、足しても次の回に消える（実装で確認）
- 判定基準は `gaibu_copy_nippou.judge()` をそのまま呼ぶ（新しい基準を発明しない）

実測（job `20260923-132400-0332`）：source `admin_stock` / seen 2 / drafts 1 / oshidake 1 / 0円。
下書きは「OTYKEN - GENESIS＝題名が英語の原題のまま」。

---

## 6. ★赤を1つ足した「積んだのに一度も走っていない」

`tools/hantei.py`:511 `hassha_machi()`（しきい値は :485 `NEVER_RAN_DAYS = 3`）。
`tools/kaitsuu.py` の「走ったのに1つも取れていないもの」の並びに出る（判定はhanteiが正本）。

日付の出どころ：その1件が持っているいちばん古い時刻。無い件は
**番号が自分より大きくて時刻を持っている件のいちばん早い時刻**を上限に使う
（番号は積んだ順なので、それ以前に積まれたのは確か）。★上限も取れない件は「日数不明」で赤にしない。

**今の実測：一度も走っていないのが78件（3日超え）。最古は42番＝17.2日。**

---

## 7. 発車待ち164件の内訳（★1件も消していない）

| 種類 | 件数 | 判断 |
|---|---|---|
| 全体 | 164 | — |
| 積んだのに一度も走っていない（3日超え） | 78 | 今日から赤に出る |
| 毎日やること（756番の重複） | 12（n=788,815,818,844,877,903,938,948,977,1004,1016,1037） | ★今日から積まれない。**消す許可待ち** |
| 人待ち（お金31／確認待ち26／裏方24・重なりあり） | 54 | 走らせても人が要る。列から外す候補 |
| 題名かぶり（GH446/453/459/461/467/468 各2） | 6 | 作り直せる＝消してよい候補 |
| すぐ見たい（urgent） | 7 | そのまま |

★壺と金庫には触っていない。捨てる判断（作り直せるか）は名指しの許可まで保留。

---

## 8. ★通っていないもの（次の便へ）

1. **絵と文字が合っているかの判定**は機械でできていない。`mainichi_kuchi.py`:146 で「未判定」と出している。
   やるならAIに絵を見せる口が要る（今は作っていない）。
2. **`nagekomi_shiji.jsonl` の指示を `nagekomi.jsonl` に反映する係が無い。**前の便から変わっていない。
3. **毎日やることの重複12件を消す許可**をもらっていない。
4. **5分便（`machine_status_push.sh`）が止まっていた。** `status/heartbeat.log`
   「13:12:59 🚨 …1797秒 更新していません」。別件。コミットの口の回収がここに乗っているので要注意。

---

## 9. 触ったファイル

| ファイル | 何を |
|---|---|
| `tools/relay_watch.py` | ★コードが新しければ受け口だけ入れ直す（90行目〜） |
| `tools/relay_nage.py` | 新規。スマホの代わりに中継所へ投げる試し投げ |
| `tools/mainichi_kuchi.py` | 新規。毎日やることの専用の口（列に積まない・棚に書かない） |
| `tools/daily_ingest_scheduler.py` | ★`queue_add` をやめて上の口を呼ぶ |
| `tools/gaibu_runner.py` | kind `relayup` / `relaytest` / `mainichi` を追加 |
| `tools/hantei.py` | ★`hassha_machi()`（積んだのに走っていない＝3日超えで赤） |
| `tools/kaitsuu.py` | 上の赤を毎朝の一覧に出す |
| `share/check/1038-nagekomi-tsuujita.html` | 報告1枚 |
