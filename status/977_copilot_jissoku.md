# 977番：GitHub Copilot を実測した（2026-09-22 23:0x〜23:16）

**結論：通りませんでした。4つの口を全部叩いて、全部「権利が無い」で閉じています。**
**投げるのをやめました。**催促も回数も増やしていません。

数：**投げた1回 → 返ってきた0回。**（板でも 🔴 のまま出ます。実際に投げたので嘘にしない）

---

## 1. 先に読んだこと（公式）

GitHub の公式ドキュメント／公式ブログで確認した、Copilot coding agent の起き方：

- 起こし方は **@メンションではなく「Issueの担当者に Copilot を入れること」**。
  受け取ると Copilot が **👀 の絵文字を付けて**、GitHub Actions の上でセッションを開始する。
- APIから割り当てるときの相手の名前は **`copilot-swe-agent[bot]`** ちょうどこの文字列。
- Copilot は**利用者ごとの課金**なので、APIから割り当てるには
  その利用者のトークン（PAT）が要る。
- **そのリポで使えるかどうかは、割り当て候補（suggestedActors）に Copilot が出るかで分かる。**

出典：
- https://docs.github.com/copilot/concepts/agents/coding-agent/about-coding-agent
- https://github.blog/ai-and-ml/github-copilot/assigning-and-completing-issues-with-coding-agent-in-github-copilot/
- https://github.com/orgs/community/discussions/164267

※ `docs.github.com` の本文取得はこの環境では許可が下りなかったので、
 目次と要点は検索結果から取り、**判断は下の実測だけで下しています。**

---

## 2. 叩いた4つの口と、返ってきたもの（全部そのまま）

| # | 叩いた口 | 返ってきたもの |
|---|---|---|
| ① | **Issue #457 を立てて `@copilot 上のお題をお願いします。` を機械で打った**（joy-relief-station） | **コメントは自分の呼びかけ1件だけ。bot返信0。👀の反応も0** |
| ② | REST で担当者に `copilot-swe-agent[bot]` を入れる（公式の起こし方） | **403 Forbidden** |
| ②b | 同じく `Copilot` で入れる | 黙って無視。`assignees` は **空のまま** |
| ③ | GraphQL `suggestedActors(capabilities:[CAN_BE_ASSIGNED])` を両リポで引く | **どちらも `tamago2022` ただ1人。Copilotが候補に出ない** |
| ④ | `gh agent-task create`（gh 2.98.0 の専用コマンド・preview） | **403 Forbidden**。★PATではなく **gh 自身のOAuth（`gho_`・tamago2022でログイン済み）** で叩いてもこれ |

④は一度こちらのミスで落としています。最初に `GH_TOKEN` にPATを差し込んで叩き、
`this command requires an OAuth token` と言われました。**差し込んだPATがMacの既存ログインを
上書きしていた**ためで、Copilotの都合ではありません。差し込まずに叩き直して、上の403が出ました。

## ★どのリポで動くのか（聞かれていた点）

**どちらでも動きません。**
`ai-kaigi`（公開）も `joy-relief-station`（非公開）も、割り当て候補にCopilotが出ません。
リポジトリの公開・非公開の問題ではなく、**アカウントに権利が無い**ということです。

## 3. なぜ閉じているのか（推測ではなく、公式の条件と実測の突き合わせ）

公式の条件は「Copilot の有料プラン（Pro / Pro+ / Business / Enterprise）に入っていて、
かつ coding agent が有効になっているリポジトリ」。
実測ではそのどちらの入口も 403 か「候補に出ない」。
→ **このアカウントに Copilot coding agent の権利が無い**と読むのが自然です。

**開けるには Copilot の有料プランに入ること＝課金。課金はたまごさんの判断**なので、
こちらでは一切触っていません。

## 4. したこと

| ファイル | 何をしたか |
|---|---|
| `tools/nageru.py` | `copilot` を `how="blocked"` にした。**理由を全部その場に書いた**ので、次のセッションが同じ4回を叩き直さなくてよい |
| 板（977-ai-renkei.html / hantei.py） | Copilot は **投げ1 → 返り0（🔴）／今は閉鎖・投げていない** と出る |

Grok・Genspark と同じ扱いです。**穴は塞いでいません。素材を替えます**（chappy か Jules へ）。

## 5. もし開けたくなったら、次にやること1つだけ

たまごさんが Copilot の有料プランに入ったら、**確かめ方はこの1行だけ**です：

```bash
gh agent-task create "README.md を3行で要約してコメントで返してください" -R tamago2022/ai-kaigi
```

403 が消えて task が立てば通っています。そのとき `tools/nageru.py` の `copilot` を
`how="gh-issue"` に戻せば、他のAIと同じ1本の口で投げられます。
