---
name: gemini-delegate
description: 大きいファイル・大きいログを読む必要があるとき、まずこのスキルを検討する。Read/cat/headで350行を超えるような読み込みを、安いモデル（Gemini 2.5 Flash）へ委譲し「要約・調べ物の結果」だけを受け取る。編集・デバッグ・設計判断・安全性が絡む推論には使わない（判断は必ずClaude側が持つ）。
---

# Gemini委譲 — 重い調べ物・要約は安いモデルへ、判断はClaudeが持つ

下敷きはSpotify社のPortal/shunt方式（2026-09-03公開）。PreToolUseフックで「大きいファイルの
読み込み」を検知し、ワーカーモデル（安いモデル）へ委譲する。Javaモノレポでの実測でbulk-read
（複数ファイル要約）は平均90%のトークン削減。

tamago-shinchoku向けの実装は `tools/gemini_delegate.py`。詳細・料金・調査結果は
`docs/gemini_bridge_2026-09-17.md` を参照。

## いつ使うか

- **350行を超えるような大きいファイル・大きいログ**を読んで、中身から特定の情報を
  探し出したい／要約したいとき。
- 複数ファイルにまたがる調べ物（例：「この機能の実装がどのファイルに散らばっているか」）。
- 350行未満の小さいファイルには**向かない**。委譲1回あたり10〜30秒のレイテンシが乗るため、
  小さい読み込みは素直に`Read`ツールで直接読む方が速い。

## 使い方

```bash
# 複数ファイルへの質問をまとめて委譲する（bulk-read）
python3 tools/gemini_delegate.py bulk-read \
  --question "認証まわりの実装がどのファイルのどの関数にあるか教えて" \
  --paths tools/auth_watch.py tools/command_ingest.py tools/auto_launcher.py

# 1つの大きいファイル・ログを要約する（summarize）
python3 tools/gemini_delegate.py summarize \
  --path status/auto-launch-71d03d69.log \
  --question "エラーや却下(permission_denials)が起きた箇所を箇条書きで"
```

標準出力に回答（箇条書き）、標準エラーに委譲にかかった時間と文字数が出る。

`GEMINI_API_KEY`が`.env`に未設定の場合、分かりやすい日本語エラーを出して終了コード1で
終わる（工場全体は止めない）。

## 絶対にこのスキルへ投げない用途

- **コードの編集・デバッグ**（バグ修正・リファクタ・実装の変更判断）
- **設計判断・アーキテクチャの意思決定**
- **安全性が絡む推論**（例：この操作は削除してよいか、公開してよいか、スレッド安全か）
  Spotifyの実測でも、ワーカーモデルはスレッド安全性バグを見逃した。
  このスキルが返すのは「調べた結果の要約」だけであり、それをどう判断するかは
  常にこのスキルを呼び出したClaude側の責任のまま。

## 関連

- 実装本体：`tools/gemini_delegate.py`
- 効果測定：`tools/estimate_gemini_savings.py`
- まとめ：`docs/gemini_bridge_2026-09-17.md`
