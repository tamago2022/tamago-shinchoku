# 「お金の流れ」公開データ 実測結果（2026-09-23）

web_fetch で実URLを叩いた結果のみを記載。叩いていないもの・本文が空で確認できなかったものは「未確認」と明記。

| # | データ | 叩いたURL | 結果(HTTP/Content-Type/中身) | 判定(4択) | キー要否 | 何が分かるデータか | 自動化の難易度 |
|---|---|---|---|---|---|---|---|
| 1 | 政府調達 落札実績（調達ポータル） | https://www.p-portal.go.jp/pps-web-biz/UAB02/OAB0201 | 200 / text/html。ページ本文に「令和08年度 successful_bid_record_info_all_2026.zip」等の直リンクが列挙されている。CSV(UTF-8 BOM付き)をzip圧縮、との明記あり | **CSV/Excelで引ける**（全件データURL例: `https://www.p-portal.go.jp/pps-web-biz/.../successful_bid_record_info_all_2026.zip`。差分データは日次で過去2ヶ月分） | 不要（ログイン不要でDLページ到達） | 全省庁統一資格の落札実績＝相手方名・金額・案件名など | 低（zip DL→解凍→CSV読み込みだけ。国交省分もこの中に含まれる＝項目10と同一データ源） |
| 1' | 政府調達ポータル トップ | https://www.p-portal.go.jp/ | 200 / Content-Type取得できず、本文テキストが空（JS描画のSPAシェルと推定） | **HTMLをスクレイピングすれば引ける**（ただしJS必須の可能性、トップ直叩きは不可） | ― | ― | 中（トップは不可、個別ページURLを直叩きすれば可＝実際に1で成功） |
| 1'' | 調達情報等公開機能API（GEPS/調達総合情報システム） | https://api-catalog.e-gov.go.jp/info/ja/apicatalog/view/42 | 200 / text/html。カタログ説明ページで「統一資格者情報(CSV,XML)・調達情報(CSV)を提供するREST API」と明記。実エンドポイントは `https://www.chotatujoho.geps.go.jp/va/com/information_m.html#20150326-2` | **未確認**（実エンドポイントは未着弾。説明ページのみ確認） | 未確認 | 統一資格者情報・調達情報 | 未確認 |
| 2 | 官報 | https://www.kanpo.go.jp/ | 200 / text/html。本紙・号外・政府調達（第175号など）の当日リンクはすべてPDFへのリンク（例: `.../full00010056f.html`もPDF埋め込みページ） | **PDF/画像だけ＝機械では読めない**（HTML一覧は取れるがリンク先は全てPDF。検索APIやテキストAPIは見当たらない） | ― | 政府調達公告・法令等の官報テキスト | 高（PDFパース or OCRが必要。日次リンク一覧のスクレイピング自体は可） |
| 3 | e-Stat API | https://www.e-stat.go.jp/api/ | 200 / text/html。ページに「API機能をご利用いただくには、e-Statでのユーザ登録が必要です」と明記 | **API（JSON/XML）で引ける**（バージョン3.0、GitHubにサンプルあり） | **キー必要**（アプリケーションID、無料ユーザ登録制） | 各種政府統計（人口・経済等）の統計表 | 低〜中（登録後は素直なREST API） |
| 4 | EDINET API（有価証券報告書） | https://api.edinet-fsa.go.jp/api/v2/documents.json?date=2026-09-01&type=2 | 200 / application/json。本文: `{"StatusCode":401,"message":"Access denied due to invalid subscription key..."}` | **API（JSON）で引ける**（構造は確認済み） | **キー必要**（サブスクリプションキー必須。キー無しでは401で弾かれることを実測で確認） | 有価証券報告書等の提出書類一覧・書類ID | 低（キー取得後は素直なJSON API） |
| 5 | 法人番号システムWeb-API（国税庁） | https://www.houjin-bangou.nta.go.jp/webapi/ | 200 / text/html。「Web-APIを利用するためにはアプリケーションIDが必要」「発行に2週間〜1か月程度」と明記 | **API（RESTで各バージョンごとにCSV/XML/JSON系）で引ける** | **キー必要**（アプリケーションID、無料だが申請制・発行に数週間） | 法人番号⇄商号・所在地の名寄せ、更新差分 | 中（キー取得まで数週間かかる点がボトルネック。取得後は仕様書どおりのREST） |
| 6 | 財務省 予算書・決算書データベース | https://www.bb.mof.go.jp/ 、 /hyoka/2 、 /hdocs/bxsselect.html 、 /archive/reiwa8.html | 200だがいずれも本文テキストが空（フレーム構成の可能性が高く、通常のGETでは中身が抽出できない） | **未確認**（Web検索では「CSV/Excel形式でzip配布」との情報はあるが、実URLをweb_fetchで直接確認できなかった） | 未確認 | 国の予算書・決算書の数値明細 | 未確認（frame構成なら中のframe src URLを個別に特定してから再検証が必要） |
| 7 | jGrants 公開API（補助金） | https://api.jgrants-portal.go.jp/exp/v1/public/subsidies?keyword=IT&sort=created_date&order=DESC&acceptance=1 | 200 / application/json。実データ7件を取得（募集名・上限額・対象地域・受付期間など） | **API（JSON）で引ける** | **不要**（キー無しでそのまま実データが返った＝実測確認済み） | 補助金公募の一覧（名称・上限額・対象地域・受付期間） ※交付先ではなく公募情報 | 低（今日すぐ自動化可能） |
| 8 | 国の補助金交付先データ（財務省「補助金等の交付決定についての情報の公表」） | https://www.mof.go.jp/about_mof/mof_budget/release/kouhukettei/index.html | 200 / text/html。令和3年度〜7年度、上半期・下半期ごとにExcelへの直リンクあり（例: `hojyokin20260515.xlsx`） | **CSV/Excelで引ける**（半期ごとのxlsx一括DL） | 不要 | 補助金等の交付決定情報（省庁横断、半期ごと集計） | 中（半期ファイルが分かれているため名寄せ・結合が必要。xlsx自体の中身は未検証） |
| 9 | 東京都議会 会議録検索 | https://www.record.gikai.metro.tokyo.lg.jp/ 、および検索結果URL（`Template=list&QueryType=New&Cabinet=1&...`） | トップは200/HTMLでフォーム構造を確認。検索結果URLは200だが本文テキストが空（JS必須のDiscussNet系システムと推定） | **HTMLをスクレイピングすれば引ける**（ただしJS必須の可能性が高く、通常のGETでは検索結果本文が取得できないことを実測で確認） | ― | 本会議・委員会の発言録全文 | 高（ヘッドレスブラウザ等が必要、通常のHTTP GETでは不可と実測） |
| 10 | 国交省 入札結果CSVオープンデータ | 項目1と同一（`p-portal.go.jp` 落札実績オープンデータに全省庁分が統合済み。GEPS統合済みのため国交省単独の全国版CSVは現在ここに集約） | 項目1参照 | **CSV/Excelで引ける**（項目1と同じ） | 不要 | 国交省含む全省庁の入札結果（案件名・相手方・金額） | 低（項目1と同じ） |
| 10' | 国交省 各地方整備局の個別公表ページ | 例: qsr.mlit.go.jp、kkr.mlit.go.jp 等（Web検索でヒットしたのみ、web_fetch未実施） | 未叩き | **未確認** | 未確認 | 地方整備局単位の月別入札結果（Excel等） | 未確認 |

## 結論（3行）

1. **今日すぐ無料・キー不要で自動化できるのは「jGrants公開API」（項目7、JSON実測済み）と「調達ポータルの落札実績オープンデータCSV」（項目1・10、CSV直リンク実測済み）の2つ。**
2. e-Stat・EDINET・法人番号Web-APIはいずれも構造はAPIだが「キー必須」（EDINETはキー無しで401を実測、法人番号は発行に数週間かかる）なので即日着手は無理、申請だけ今日中に出す価値あり。
3. 官報・都議会会議録・財務省予算決算DBは、PDFのみ／JS必須／フレーム構成のいずれかで機械可読な即時取得ルートが実測できず、現状は「スクレイピング要検証」または「PDF処理」の追加工数が必要と判断した。
