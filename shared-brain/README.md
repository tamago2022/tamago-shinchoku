# TAMAGO Shared Brain

ChatGPT・Claude Code・Grok（今後Gemini/Perplexity等が増えても同じ）が、
**同じ経路で読み書きするための共有記憶庫**です。

```
AI → GitHub Shared Brain (このディレクトリ) → Obsidian（tamago_brainボルト）
```

各AIはこれまでのように「自分のやり方でObsidianに書こうとする」のをやめ、
**このリポジトリの `shared-brain/` 配下へMarkdownをcommit/pushするだけ**にしてください。
Obsidian側は symlink で即座に同じ内容を表示します（別途pull作業は不要）。

## 目的

- AIごとに保存経路がバラバラだった状態をやめる
- 誰が書いても、たまごさんは同じVaultの同じ場所で全部読める
- 将来どのAIが参加しても「GitHubへ書ける」だけで参加資格を満たせるようにする

## 保存先ルール（フォルダ用途）

| フォルダ | 用途 |
|---|---|
| `00_INBOX/` | まだ仕分けていない生の情報・受け取ったばかりのメモ |
| `10_ROUNDTABLE/` | 複数AI・複数視点で「円卓」した議論・結論のログ |
| `20_DECISIONS/` | 決定事項・確定したルール・方針転換の記録 |
| `30_PROJECTS/` | プロジェクト単位の進行中メモ・企画・設計 |
| `40_AI_HANDOFF/` | AI間の引き継ぎメモ（誰が何をどこまでやったか） |

## ファイル形式

- **Markdownのみ**を基本とする（画像・バイナリは対象外。必要ならリンクで外部参照）。
- 拡張子は `.md` 固定。文字コードはUTF-8。

## ファイル名のルール

```
YYYY-MM-DD_内容が分かる短い日本語タイトル.md
```

例：`2026-09-08_test.md`、`2026-09-08_YOSHI四方よしプロダクト戦略.md`

## 同名ファイルがある場合の扱い

- **既存ファイルを勝手に上書きしない。** 同じテーマの続きを書きたい場合は、
  同じファイルの末尾に追記するか、日付を今日の日付にした新しいファイルを作る。
- 内容が重複する既存ファイルを見つけたら、消さずに末尾へ追記するか、
  新ファイルの冒頭に「関連: `既存ファイル名`」と一言書いて紐づける。
- **既存Obsidianノート（`shared-brain/`の外）には絶対に触らない。**

## Obsidianリンクの作り方

このリポジトリへ保存したファイルは、以下の形式でそのままObsidianから開けます
（ファイル名は拡張子`.md`を除いた部分）。

```
obsidian://open?vault=tamago_brain&file=shared-brain/<フォルダ名>/<ファイル名（拡張子なし）>
```

例：`shared-brain/10_ROUNDTABLE/2026-09-08_test.md` を保存したら、

```
obsidian://open?vault=tamago_brain&file=shared-brain/10_ROUNDTABLE/2026-09-08_test
```

このリンクをたまごさんに渡せば、押すだけでそのノートが開きます。

## 各AIの書き方（同じ出口）

- **Claude Code**：ローカルであれば `git add / commit / push` を直接実行してよい。
- **ChatGPT**：このリポジトリ（`tamago2022/tamago-shinchoku`）へ直接ファイル作成・更新のAPI/UIを使い、`shared-brain/` 配下へcommitする。
- **Grok**：円卓アプリでMarkdownを生成したら、Obsidianへ直接保存しようとせず、このリポジトリの `shared-brain/` 配下へcommitする。

いずれも保存先は同じ、経路は同じ。書いた後は上記の `obsidian://open?...` リンクを組み立てて返す。

## 守ること

- `shared-brain/` の外には書き込まない（このリポジトリの他のディレクトリ・Obsidian Vaultの他のノートは対象外）。
- Vault全体を同期する仕組みではない。同期対象は常に `shared-brain/` だけ。
- 機密情報・APIキー・パスワードはここに書かない。
