# AI同士の直通連携 設計（2026-10-17・期限 10/31）

## ① 現状の棚卸し（実測。分からないものは未確認）
| AI | 読める | 書ける | 実測メモ |
|---|---|---|---|
| Genspark | GitHub Issue/PR/コメント、AI Drive | Issue・コメント（店主と同じ tamago2022 名義）、AI Drive | ファイルpush不可。工場→Genspark は `gsk task create` で頼める（クレジット消費・栓あり） |
| Claude 工場 | GitHub 全部、AI Drive（`gsk drive download` 無料・10/17 実測で 89,770B 取得成功） | GitHub・Lovable公開・Buffer予約・Issueコメント | 受付係は【Claude Codeに頼む】の新Issueだけ見ていた→10/17【納品】コメントも見るよう追加 |
| ChatGPT(Codex) | `@codex` で呼ばれた Issue とリポジトリ | コメント・コミット・PR | #1008 は返答あり（10/16）。#1014 は「使用上限」で中身ゼロ（10/17） |
| Jules | リポジトリ（未確認） | PR（未確認） | 投げ161・返り10。#988〜#1017 に同じ依頼が溜まり続けている |
| Grok ボット | 未確認（公開ページなら読める見込み・未検証） | なし（未確認） | API は課金なしで 403（9/22）。掲示板 ai-kaigi は読む bot ゼロ |

## ② 掲示板1つ＋置き場1つの案
- **A（おすすめ）：掲示板＝joy-relief-station の Issue／置き場＝AI Drive `/tamago-inbox/<Issue番号>/`**
  Genspark はどちらにも今日書けている。工場はどちらも無料で読める。共有リンクも公開設定変更も要らない。足すのは受付係の【納品】拾いだけ（10/17 実装）。
- B：掲示板＝Issue／置き場＝GitHub Actions「郵便屋」（Genspark 提案の inbox-pipe.yml）
  AI Drive を「誰でも読める」リンクにする必要がある（店主の画面操作＋外に漏れる）。Actions の無料枠も食う。
- C：掲示板も置き場も Issue（コメントに本文を貼る）
  GitHub のコメント上限 65,536 字。今回の月特集 64,042 字でギリギリ、次は入らない。画像も無理。

## ③ 流れ（A）
店主が Genspark に1回言う → Genspark が原稿を `/tamago-inbox/<番号>/` に置き、Issue に `【納品】/tamago-inbox/<番号>/<名前>`
→ 受付係（5分おき）が AI Drive から取得・発車待ちへ・Issueに受領
→ 子セッションが実装・関所・本番公開・本番確認 → Buffer 注文票 → Issue に本番URL＋予約日時 → 閉じる。

## ④ 目安
- 10/24：設計確定（A）＋ 月の特集 #1015 を A の線で本番公開まで
- 10/31：「店主が Genspark に1回言う → 自動投稿」を新しい号で1本通す
