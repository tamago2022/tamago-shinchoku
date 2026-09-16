# 883番：~/.tamago/chrome-line(CDP 9224)が801番系セッションと競合中（記録・2026-09-16 22:2x）

## 状況
- 883番（LINE Creators Market申請の自動入力）の調査中、`node tools/line_login_check.mjs`は1回目 `LOGGED_IN` で成功したが、
  直後の`tools/line_stamp_fill.mjs oniyome-chan`実行時に一時的に成功→以後の再実行は
  `Protocol error (Browser.setDownloadBehavior): Browser context management is not supported` で連続失敗。
- `ps aux`で確認したところ、**同じ9224番・同じ`~/.tamago/chrome-line`プロファイルに対して、
  別セッション（801番系・`contact-cc.line.me`のLINE問い合わせフォーム送信）が21:58〜22:0x台にかけて
  `/tmp/line_inquiry_fill8.mjs`〜`fill14.mjs`、`line_inquiry_check.mjs`、`line_inquiry_fixemail.mjs`等を
  連続実行しており、同時多発でCDP接続を取り合っていたことが判明**。
- 現にタブ一覧に「送信完了│LINE(ライン)」（`contact-cc.line.me/ja/registerInquiry.nhn`）が残っており、
  801番系は一度送信完了まで到達した後もメールアドレス修正等で追加操作を続けていた形跡がある。
- 憲法（`AGENTS.md`/共通脳）の「複数のセッションが同時にブラウザを使わない。自分の前に誰かが使っていたら待つ」に反する状態。

## 883番としての対応
- 他セッションの活動を止める権限は無いため、**強制終了はせず、自分の側で一旦間隔を空けてから再試行**する方針にした。
- 883番は`creator.line.me`（スタンプ申請）、801番系は`contact-cc.line.me`（問い合わせフォーム）で
  対象URLが別なのでタブの奪い合いにはなっていないが、**同一ブラウザプロセスへの同時connectOverCDPがエラーの原因**の可能性が高い。

## 技術的な副産物（883番の前進）
- `node tools/line_login_check.mjs` は `LOGGED_IN` を確認済み（`https://creator.line.me/ja/dashboard`）。
  → ログイン自体は生きている。認証はクリア。
- `tools/line_stamp_fill.mjs oniyome-chan --shot ...` を1回実行できた際の結果：
  `url: https://creator.line.me/ja/stamp/47328304/edit` → **「指定されたページは存在しません」の404相当ページ**。
  つまり `/ja/stamp/{stamp_id}/edit` というURLパターンは誤り。正しい編集URLをダッシュボードのリンクから
  実地調査する必要がある（次の一手）。
