---
name: env-no-network-curl
description: tamago-verifierサブエージェントのBashサンドボックスではcurl等のネットワークアクセスが権限確認待ちになり、対話承認が無いこの実行形態では実行不可能
metadata:
  type: project
---

tamago-verifierとしてサブエージェント経由で起動された場合、Bashツールでの`curl`（本番URLのHTTPステータス確認等）は「interactive approval」を要求され、
「permission prompts are not available in this session」として必ず拒否される。`dangerouslyDisableSandbox: true`を付けても同様に拒否される。
git・ls・node・npmなどローカルコマンドは問題なく実行できる。ネットワークを使う確認（本番URL実測、WebFetch相当）だけが不可。

**Why:** サブエージェント実行形態では、ユーザーがその場で許可ダイアログに答える手段が無いため、ネットワーク系コマンドは一律ブロックされる。

**How to apply:** 依頼元（親エージェント）が「本番URLにアクセスして200か確認して」のような検品を求めても、このサブエージェント環境では直接確認できない。
無理に「できた」と報告せず、「このサンドボックスではcurlがブロックされ実測できなかった。親セッション（通常のClaude Code環境）側で`curl -sI <url>`を実行して確認してほしい」と正直に限界を報告する。
推測で「たぶん200だろう」とPASS判定に混ぜ込まない。関連: 不合格項目には必ず「実行していない検証をOKと書かない」の原則を適用する。
