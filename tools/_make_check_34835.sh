#!/bin/bash
set -e
cd "$(dirname "$0")/.."
python3 tools/make_check_page.py \
  --n 34835 \
  --slug zenkantou-check-logic \
  --title "判定日赤34835番：全担当チェックのロジックは既に実在・本日も動作確認" \
  --what "店主が2026-08-08 05:48に『これを踏まえて全担当チェックのロジックを作ってください』と言った件が、判定日システムで1ヶ月以上未着手として赤判定されていた。調べたところ、同日2026-08-08のうちに joy-relief-station リポジトリへ実装・main反映済みだったと判明（commit 76e35ef34＝全担当チェック本体、commit ff82d252d＝つなげる担当の未接続カバー曲検出ロジック）。判定日システム側が過去の完了実績を拾えていなかっただけで、作業自体は未着手ではなかった。本日2026-10-10にあらためて両方のロジックを実際に実行し、今も正しく動くことを実測した。" \
  --num "15件|本日の実行で機械判定された担当の数" \
  --num "10件|つなげる担当の巡回ロジックが本日検出した未接続カバー曲（8タイトル組）" \
  --num "63日|この依頼が言われてから本日までの経過日数" \
  --link "全担当チェック本体の実装コミット(2026-08-08)|https://github.com/tamago2022/joy-relief-station/commit/76e35ef34e7c93250c2885baaa61b7ca1e427c67" \
  --link "つなげる担当の巡回ロジックの実装コミット(2026-08-08)|https://github.com/tamago2022/joy-relief-station/commit/ff82d252d5dc86a369c143698458500b8afa1ec1" \
  --link "30分おき無人実行のworkflow定義|https://github.com/tamago2022/joy-relief-station/blob/main/.github/workflows/tamago-role-sweep.yml" \
  --link "担当別の次の一手を見る管理画面(34833番・別件・Lovable公開待ちのため現在404)|https://joy-relief-station.lovable.app/admin/role-status" \
  --table "全担当チェックのロジックが実在し、本日も動くか|本日実行し15担当分を正しく出力|yes" \
  --table "つなげる担当の巡回が仕入れ→つなげるの未接続を自動検出するか|本日実行し10件の未接続カバー曲を検出（例：Come Together×The Beat Bugs）|yes" \
  --table "mainへ反映済みか|origin/mainに両コミットとも存在|yes" \
  --table "GitHub Actionsで30分おき無人稼働を続けているか|2026-09-05を最後に自動記録が止まっている。原因はtamago2022アカウントの支払い設定の問題で既に別件として店主判断待ちへ計上済み（このロジック自体の不具合ではない）|no" \
  --allow-no-screenshot "画面の見た目を変える作業ではなく、裏側の無人巡回ロジックの実在・動作確認のため、スクショではなく実行結果のJSON件数で裏取りした" \
  --print-url
