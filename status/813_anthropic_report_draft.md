# 813番：Anthropicへの報告候補（下書き・送信前）

**方針（たまごさんの指示どおり）**：今日（2026-09-13）の12件の失敗は、ほぼ全部こちらの自作スクリプト側の問題（queue.jsonの排他制御・数字の二重計算・falの単価管理・検品の実装等）であり、**Anthropic起因ではない**。混ぜて報告しない。ここには「Claude/Cowork/Dispatch自体」に起因すると言えるものだけを候補として挙げる。

## 送信済み・重複させないもの

- **マイクの断続的な不具合**：`share/check/683-mic-issue-and-anthropic-mail.html`により2026-09-07に既にAnthropicサポートへ送信済み、返信も受け取っている（`share/check/626-anthropic-reply-watch.html`）。**今回は再送しない。**

## 新規候補①：Bash toolの作業ディレクトリが、実行のたびに元の場所へ戻る（今回のセッションで実際に発生・再現性あり）

- **症状**：本セッション（案件#813）で `cd /Users/mac/Desktop/tamago-shinchoku && ...` を実行しても、次のBash呼び出しでは自動的に最初の作業ディレクトリ（Primary working directory）へ戻っており、毎回のコマンドで `cd` を先頭に付け直す必要があった（ツールの応答に `Shell cwd was reset to <primary dir>` という注記が毎回付く）。
- **実害**：作業対象が「セッションの主ディレクトリとは別の場所」（今回は店主指示で明示された作業場所）の時、全コマンドに `cd <対象> && ...` を付け続ける必要があり、コマンドが長くなる・付け忘れると別ディレクトリで実行してしまう事故の元になる。
- **報告の要否**：これが意図された仕様（セッションごとに1つの作業ディレクトリに固定する安全設計）なのか、改善余地のある挙動なのか、こちらでは判断がつかない。**製品フィードバックとして「意図した動作か」を問い合わせる価値はあると判断した。**

## 保留（証拠不十分・今回は送らない）

- **セッション間で文脈が引き継がれない**：この工場（tamago-shinchoku）が`watchdog-handoff-*.log`のような引き継ぎ用の仕組みを自前で多数持っていること自体は事実として確認したが、これが「Anthropic側の不具合」なのか「長時間セッションを扱う上で当然必要な自前の設計」なのかを、今回の調査時間内で切り分けられなかった。**推測でAnthropicへの不具合として書くのは今回は見送る**（unei-houkokuスキルの方針「分からなければ、分かっている事実だけを簡潔にまとめる」に従う）。
- **Dispatchの会話コスト**：`status/cost_by_task.json`等でコストの記録はあるが、「Anthropic側の設計・不具合」と「こちらの使い方（長い会話を続けすぎている等）」のどちらが主因かを切り分ける実測がまだ無い。こちらも同様に見送る。
- 次にこの2つを送るなら、まず実測（頻度・具体的な再現手順・金額やトークン数）を先に揃えてから下書きを作る。

## 次のアクション

- ①（Bash toolの作業ディレクトリ）だけ、英語の下書きを用意すれば送信可能な状態。**実際にGmailを開いて送信するかどうかは、たまごさんの確認後に判断する**（本ファイルはその手前の下書き止まり）。
- 英語下書き（案）：

> Subject: Bash tool working directory resets to the session's primary directory after each call
>
> Hello,
>
> While working in a Claude Code session whose task explicitly required operating in a directory different from the session's primary working directory, I observed that every Bash tool invocation resets the shell's working directory back to the primary directory after the command finishes (each result included a note like "Shell cwd was reset to <primary directory>"). This meant every single command needed to be prefixed with `cd <target dir> &&` to stay in the intended directory, which is easy to forget and error-prone for multi-step work outside the primary directory.
>
> Could you clarify whether this is intended behavior (e.g., a deliberate safety boundary keeping sessions scoped to one directory) or something that could be improved (e.g., persisting `cd` across calls, or making the reset more visible/configurable)?
>
> Thank you.
