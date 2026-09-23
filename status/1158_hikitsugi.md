# 1158番 引き継ぎ（2026-09-26）

## 何を直したか
鍵が消える真因は期限切れではなく**同時起動の競合**。
`status/dojisu_jougen.json` は前から「同時上限1」と出していたが、**起動口で強制していなかった**
（同ファイルの calibration標本数が証拠：2本=534回 3本=89回 4本=8回 5本=1回 6本=1回）。

→ `tools/1158_kanmon.py`（関所）を作り、claude を起動する経路を全部そこに通した。
   flock でスロットを取ってから本物の claude を exec する。exec 後もロックが生きるので
   投げっぱなし起動にも効く。プロセスが死ねばカーネルが解放＝残骸が出ない。

関所を通した6本：
  auto_launcher.py / command_ingest.py / gaibu_copy_naoshi.py /
  session_watchdog.py / auth_watch.py / auth_keeper.py

入れ子（claudeの中からclaude）は `KANMON_SLOT` で素通し＝上限1本でも詰まらない。

## 実測
偽のclaude5本を同時投入 → **17秒**（1本ずつなら15秒／取り合いのままなら3秒）。
見張り `tools/1158_mihari.py` が1分おきに本数を記録（top_status.py から呼ぶ）。
本番：https://tamago2022.github.io/tamago-shinchoku/1158-kagi.html （HTTP 200 実測）

## まだ塞がっている口（ここだけ人間が要る）
**鍵は 2026-09-20 04:30 から死んだまま。**7日間で379回の失敗、復活0回。
関所は「これ以上消えないようにする」もので、**既に空になった鍵は戻せない。**
→ ログインし直しが1回だけ要る（`status/LOGIN.md`）。
   戻したあとは、上のURLの「2本以上になった回数」が0のまま伸びるかで効き目を見る。

## 認証の取り直しは止めてある
承認画面が出続けた実害があったため `status/ninshou_stop.flag` を立てた。
1156_login_ichioshi.py / 975_login_1pon.py / auth_login_helper.py は
この札があるあいだ即座に戻る（実測済み）。**解除はこのファイルを消すだけ。**
ログインし直すときは、先にこの札を消すこと。

## 戻し方
git checkout -- tools/auto_launcher.py tools/command_ingest.py tools/gaibu_copy_naoshi.py \
  tools/session_watchdog.py tools/auth_watch.py tools/auth_keeper.py tools/top_status.py \
  tools/1156_login_ichioshi.py tools/975_login_1pon.py tools/auth_login_helper.py
rm -f tools/1158_kanmon.py tools/1158_mihari.py tools/1158_page.py 1158-kagi.html
