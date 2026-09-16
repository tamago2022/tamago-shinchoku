# 917番：外部AI(Grok)検品の実地テストに xAI クレジット購入が必要（金銭・店主のみ操作可）

## 状況
`tools/gaibu_kenpin.py`（外部AI検品・関所の関門8）は実装済み・main合流・本番(GitHub Pages)反映済み。
ロジック自体はモックテスト4件（NG伝播・OK伝播・帳簿記録・日次上限SKIP）で検証済み。

## ブロック（金銭・AI側で実行不可）
xAIチーム「gokigen-voice」にクレジットが無く、実際のGrok API呼び出しが
`HTTP 403 permission-denied: Your newly created team doesn't have any credits or licenses yet`
で弾かれる（2026-09-17 07:26に実機で再確認済み）。モデル名(grok-4系)自体は実在することは確認できた。

## 必要な操作（店主本人のみ）
console.x.ai にログイン → チーム「gokigen-voice」でクレジットを購入。
購入後は追加の設定変更なしで、次回のsekisho実行から自動的に本物のOK/NG判定が動く設計。

## 金額の目安
1回あたり概算0.1〜0.2円程度（トークン量次第、モデル単価未確認のため概算）。
日次上限は既定30回・100円で自動停止するようコード側に実装済み（`status/gaibu_kenpin_ledger.json`）。
