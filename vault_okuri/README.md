# Obsidianへの受け口（GH1230・2026-11-24）

Grokボット（や他のAI）が **git push するだけで** Obsidian の `00 inbox` にノートが届く受け口です。

## 使い方

1. `tamago2022/tamago-shinchoku` のこのフォルダ（`vault_okuri/` 直下）に `.md` ファイルを置いて
   コミット・プッシュする。
   - サブフォルダに置いても見てもらえません（直下のファイルだけが対象）。
   - `.md` 以外の拡張子は無視します。
   - 1ファイル1MB超は無視します。
   - ファイル名は好きに付けてよいですが、**同じ名前のファイルが既にVaultの `00 inbox` にあると、
     その回は何もしません（上書きしません）**。被りにくい名前（送信元や日付を頭に付ける等）を推奨します。
2. Macの心臓（`tools/heartbeat.sh`・1時間おき）が、`git pull` 済みのこのフォルダを見て、
   Obsidian Vault の `tamago_brain/00 inbox/` へ**一方向コピー**します（追加のみ）。
3. 結果は `status/public/vault_okuri.json` で確認できます。
   - 公開URL：`https://tamago2022.github.io/tamago-shinchoku/status/public/vault_okuri.json`
   - 1件ずつ `copied`（コピーした）／`skipped_exists`（同名あり・見送り）／
     `skipped_too_big`（1MB超）／`skipped_daily_cap`（1日の上限超え・次回）／`failed`（失敗）が載ります。

## 守っていること（追加のみ）

- 同名ファイルがVaultにあればコピーしない（`os.O_EXCL` で新規作成のみ・上書き不可）。
- Vault側のファイルは消さない・書き換えない。Vault → このリポジトリへの逆流もしない。
- このフォルダの元ファイルも消さない（処理済みかどうかはファイル名＋中身のハッシュの台帳で判断）。
- 1日の処理件数に上限があります（`tools/vault_okuri_tenso.py` の `DAILY_CAP`）。

## 止め方（無効化スイッチ）

`status/vault_okuri_off` というファイルを作ると、次の心臓の周回から何もしなくなります
（ファイルを消せば再開します）。

## 実体

`tools/vault_okuri_tenso.py`（台帳：`status/vault_okuri_daicho.json`）。
