joy-relief-station（main）の改善。調べて終わり禁止。PRまで作ること。終わりの合図はPRのURLだけ。承認待ちで止まらず、複合コマンド(&&や|)も使ってよい。質問せず自分で決めて最後までやる。

【ゴール】案内所の検索が「秋の曲」「雨の日 静か」「ナス パスタ トマト」のような、曲名やアーティスト名ではない"気分・季節・天気・時間帯・食材"の言葉で在庫（曲・食べ物・その他カード）を探せるようにする。そのための「裏タグ」を設計し、リポ内データに付与する。
【既存の基盤】src/lib/cardTags.ts（season/time_of_day/mood/era/life_moment）、cardTagQueries.ts、cardTags.generated.ts（現状422カード・scripts/build-card-tags.tsが生成）、searchCards.ts、searchNormalize.ts、foodCards.ts、foodProductRegistry.ts、homeTags.ts、bathTags.ts、placeTags.ts。まずこれらと検索の経路(src/routes/search.tsx, searchCards.functions.ts)を読んで現状を把握する。
【やること】
1. タグ設計書 docs/ura-tag-design.md：軸（季節・天気・時間帯・気分・場面・食材・味/料理ジャンル・温度感など）、各軸の語彙（日本語の同義語・ひらがな/カタカナ揺れ・英語も）、既存タグとの対応、検索語→タグの解釈表（例「秋の曲」→season=autumn かつ 曲、「ナス パスタ トマト」→食材タグ）。
2. 付与：在庫の大半（曲は約26,000件・食べ物ほか）を、機械ルール(キーワード辞書・年代・曲名/メモ文中の語・既存タグからの推定)で付与するスクリプト scripts/build-ura-tags.ts を書き、生成物はシャード分割(JSON)で出す。重い一括直書きJSはNG（バンドルを重くしない。lazy読み込み/検索時のみ取得）。嘘のタグは付けない：根拠が取れないカードにはタグを付けない。曲の事実（年号・原曲等）は触らない。
3. 検索側：タグ語で引ける最小限の接続（既存の見た目・機能は壊さない）。
4. 検証：tsc/ビルド/既存のテストやチェックスクリプトが通ること、付与件数・軸ごとの件数、タグ検索のサンプル10語の結果をPR本文に表で書く。
5. DB(Supabase)への書き込みが必要な部分は実行せず、supabase/ に移行SQLと手順としてPRに含める。
【禁止】本番DBへの書き込み、秘密情報の出力、食べ物・アフィリエイトを曲ページの関連おすすめに混ぜること、既存ファイルの大量書き換え。
最後の発言はPRのURLのみ。
