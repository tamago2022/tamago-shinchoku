---
name: project_35130_pages_publish_cadence_diagnosis
description: GitHub Pages 404が「main合流済みなのに出ない」場合の確定的な原因切り分け手順（35130号で確立）。gh未インストール環境でもActions実行履歴はWebFetchで見られる
metadata:
  type: project
---

35130号（確認ページ `share/check/35130-kaisetsu-bun-hyoujun.html`）で、commit `8d81b61e6d` がmainに入って10分近く経っても公開URLが404だった件を診断・解消した。

**確定した仕組み（この工場固有の構造）：**
- `.github/workflows/pages.yml` は **`gh-pages`ブランチへのpushだけ**をトリガーにする（`main`へのpushでは動かない）。
- `tools/pages_publish.sh` が唯一の書き手で、mainの最新を取り込み→`status/public/`の関所（1MB超・秘密情報名を除外）を通し→gh-pagesへ1コミット固定でforce push する。
- このスクリプトの起動元は`~/Library/LaunchAgents/`を`pages_publish`で直接grepしても見つからなかった（他の定期スクリプトから呼ばれている可能性）。実測した間隔は`status/pages_publish.log`で06:30/06:49/06:52/07:14/07:28と**だいたい15〜20分間隔（まれに3分間隔）**。

**Why:** 新しいcommitがmainに入った直後は、直前の公開サイクルがすでに走った後であることが多く、次のサイクルが回ってくるまで普通に404のままになる。これはGitHub Actionsの課金枠切れ（joy-relief-station側で過去に発生、[[project_bash_network_denied]]参照）とは別物で、**こちらは正常な定期反映の待ち時間**。

**How to apply（確定診断フロー）：**
1. `git fetch origin main gh-pages` → `git merge-base --is-ancestor <commit> origin/main` でmain合流を確認。
2. `git log origin/gh-pages --oneline -5` でgh-pages側の最新コミットメッセージ（`公開（進捗表）... / main=<短縮sha>`）を見て、**mainのどの地点まで既に反映済みか**を確認する。目的のcommitがそれより後ろならまだ未反映なだけ。
3. `tail -30 status/pages_publish.log` で直近の「main の中身を A → B へ追従しました」「公開しました」のタイムスタンプ間隔を見る。目的commitのcommit時刻と見比べ、最後の公開サイクルより後に作られたcommitなら「次のサイクル待ち」と判断できる。
4. Actions自体が壊れていないかは、`gh`コマンドが無い環境でも**WebFetchで`https://github.com/<owner>/<repo>/actions/workflows/pages.yml`を直接開けば実行履歴(success/failure/queued)が読める**（2026-10-22確認。`gh api`はBash権限拒否だがWebFetchは公開ページとして普通に読める）。ここがsuccess続きなら配信パイプライン自体は健全。
5. 404が続く場合はBash `run_in_background` + `until`風ポーリング（30秒間隔でnode fetch、`sleep`はバックグラウンドジョブ内のみ）で待ち、`status/pages_publish.log`に新しい「公開しました」が出た直後に再取得すれば200になる。35130号ではcommit作成から約10分後（次の公開サイクル）でPASSした。

**関連:** [[project_34975_sql_apply_check_deploy_lag]]（同じ「合流済みでも反映ラグ」事例だが原因は推測止まり）、[[project_bash_network_denied]]（gh/curl不可の件、本件でWebFetchがActions確認の代替手段になることを追記）

**追記（35155号・2026-10-22）:** 「concurrency groupの先頭でゾンビ実行(queued)が詰まる」を疑う依頼だったが、`GET /repos/{owner}/{repo}/actions/workflows/pages.yml/runs?per_page=5`（WebFetch・認証無し）で直近5件すべて`completed`/`success`、queuedで止まったものは無しと確認。最新run（例: id 39728229399）は`head_branch: gh-pages`・push event、`created_at`から`updated_at`まで約1.5分で完走しており、詰まりは無かった。push報告時刻から15分以上404が続いたのは、`pages_publish.sh`の定期サイクル待ち＋デプロイ自体の数分ラグの範囲内で、確認し直した時点では公開URLが通常コンテンツを返していた（ゾンビ化はしていなかった）。なお`GET /repos/{owner}/{repo}/pages`は認証無しWebFetchだと404を返す（publicリポジトリでもこのエンドポイントは未認証では読めない模様）。build_type（workflow経由かbranch直接か）を確認したい場合はこの手段は使えないため、別の確証（gh-pagesブランチの内容そのものを見る、または`pages.yml`の中身を読む）で代替する。
