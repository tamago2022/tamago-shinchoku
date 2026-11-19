---
name: project_34975_sql_apply_check_deploy_lag
description: 34975番の確認ページ(share/check/34975-sql-apply-check.html)でmain合流後もGitHub Pagesに反映されず複数回FAILになった事例
metadata:
  type: project
---

2026-10-12、`https://tamago2022.github.io/tamago-shinchoku/share/check/34975-sql-apply-check.html` の再検品依頼。origin/mainには修正commit `8f03cc262`（①〜④見出し・非公開リンク撤去・SQL本文直接埋め込み）が確認済みだったが、WebFetchで`?v=3`と`?nocache=20261012b`の2つの異なるキャッシュバスターで取得しても、どちらも旧内容（①④見出し無し・非公開リンク`apply-missing-sql.md`が残存・`CREATE TABLE public.henshin_orders`が無い）のまま一致して返ってきた。

**Why:** 異なるキャッシュバスターで一貫して同じ古い内容が返るのは、WebFetch自身の15分キャッシュでは説明できない（パラメータが毎回変わっているため別キャッシュエントリになるはず）。GitHub Pagesのビルド・デプロイ自体がまだ追いついていない可能性が高いと判断した。

**How to apply:**
- この案件の再検品を依頼されたら、まず`git log origin/main`で該当commitが本当にmainに入っているかを確認し（[[project_bash_network_denied]]参照）、入っていればWebFetchで複数の異なるキャッシュバスターを試す。
- 一貫して古い内容が返る場合は「WebFetchキャッシュ」ではなく「デプロイ未反映」の可能性が高いとして報告する（店主への誤った楽観報告を避ける）。
- GitHub Pagesは通常push後数分で反映されるはずなので、長時間（30分以上等）古いままなら、Pagesのビルド自体が止まっている可能性を疑い、gh api（通常のClaude Codeセッションなら使える）でActionsの状態を見るよう引き継ぐ。

**2026-10-12追記：** 同日の別セッションから`?v=final1`で再検品依頼が来た際は、①〜④見出し全部あり・非公開リンク`apply-missing-sql.md`は無し・`/room/henshin`リンクあり・`CREATE TABLE public.henshin_orders`ありで一発PASSした（commit `434abf1e8`）。つまり最初のFAILはやはり「デプロイ未反映」が原因で、時間が経てば（この時は数時間〜半日程度）追いついて正常化した。再検品依頼では毎回Pages反映ラグを疑いつつ、まず素直に1回フェッチして確認するのが正しい初動（いきなり再試行クエリを変える必要はない場合もある）。

**2026-10-22追記（35110番）：** 同じ型のラグを再確認。`share/check/35110-food-radar-tag-widen.html`は`git show origin/main:...`では非公開リポリンク無し（push済み・commit `99365f177f`→`61d8e349d6`）だが、WebFetchで通常URLと`?nocache=`付きURLの両方を取得しても、古い版（「④ 押せるリンク」に`github.com/tamago2022/joy-relief-station/commit/...`への非公開リンクが残存）が一貫して返ってきた。判定手順（`git log origin/main` → `git show origin/main:<path>`でソースの真実を確定 → WebFetchの実測と食い違えば「デプロイ未反映」と報告）がそのまま有効だったことを再確認。この時はBashのcurlがサンドボックス権限ダイアログで止まり実行できず（[[project_bash_network_denied]]とは別症状＝許可待ちで止まる）、WebFetchのみで判定した。
