# Lovable公式MCP — 登録済み。次のセッションがやること

## 状態（2026-09-19 21:10 実測）
- `claude mcp add --transport http --scope user lovable https://mcp.lovable.dev` が rc=0 で通った。
- `~/.claude.json` に入った。Scope: User config（全プロジェクトで使える）。
- **Status: Needs authentication** ＝ OAuthの同意がまだ。ここだけたまごさんの1回の操作が要る。

## たまごさんに1回だけお願いすること
Claude（Cowork/Claude Code）で **`/mcp`** → `lovable` → **Authenticate** を押す。
ブラウザでLovableの同意画面が出るので許可する。1回だけ。以後は要らない。

## 認証が通ったら
- 呼んでいいのは **`deploy_project`** と状態を読む系だけ。**クレジットを食わない。**
- **`create_project` / `send_message` は絶対に呼ばない。**（1回で何十クレジット飛ぶ）
- プロジェクトID: `8ebdb648-3686-4457-b42c-d01c493793b1`
- 出す順：① トップの軽量化(PR #432) ② 目安箱の統合(PR #425) ③ 金バッジの位置 ④ /watch の空白 ⑤ 扉「生」と /hidden/life
- **1つ出すごとに本番URLを自分で開いて確かめてから次へ。**

## 覚えておくこと
- `status/lovable_mcp_setup.log` に登録の実測ログがある。
- 仕込みは `tools/lovable_mcp_bootstrap.py` / `tools/lovable_mcp_check.py`。
  どちらも `status/.lovable_mcp_done` / `.lovable_mcp_check_done` で1回きり。もう走らない。
  `tools/top_status.py` の先頭から呼んでいる（心臓が毎周回で読み直す唯一の道だったため）。
