# 世界の事例調査（案件828・「同じ脳みそ」設計の裏取り）

**正直な前置き**：本セッションでは外部ドキュメントへのcurl調査が自動モードの権限ブロックで実行できなかった（試した経路と結果は`AI_ENTRY_PROMPTS.md`の「Grokへの接続実験」節に記録）。そのため以下はAI自身の学習データ（2026年1月時点まで）に基づく記述であり、ライブ確認済みの事実ではない。次にネットワーク許可が下りたセッションで裏取りし直すこと。

| 調べるもの | 分かっていること | 今回の用途に使えるか |
|---|---|---|
| **MCP（Model Context Protocol）** | Anthropic発。2025年にOpenAI・Google DeepMindも採用を表明し、事実上の業界標準になりつつある。GitHub公式のMCPサーバーも存在する。 | △ 仕組み自体は強力だが、ChatGPT/Grokの**一般ユーザー向けチャット画面**からMCPサーバーへ常時接続する設定項目は、個人プランでは提供されていない（企業向けConnectors等が必要）。今回の「たまごさん個人のChatGPT/Grok画面」用途には不向き→見送り。 |
| **A2A（Agent2Agent）** | Google発、後にLinux Foundationへ寄贈されベンダー中立に。エージェント基盤同士が直接ハンドシェイクする規格。 | × 開発者がバックエンドのエージェント基盤を組む時のものであり、チャットUI越しの利用は想定外。見送り。 |
| **各社のカスタム指示／プロジェクト機能** | ChatGPTのProjects機能はプロジェクト単位でcustom instructionsを設定可能。Grokにもcustom instructions欄がある。 | ◎ **本命**。「毎回このURLを読め」と明示的に書ける。ただしURLを書くだけでは自動fetchされない場合があるため、「ブラウジング/検索機能で取得してから答えよ」まで明記する必要がある（`AI_ENTRY_PROMPTS.md`で対応済み）。 |
| **各社のツール連携（GitHub直接読み書き）** | ChatGPT: Connectors機能・Codex機能でGitHubに直接PR作成が可能（このリポジトリで`tamago-codex[bot]`の実績あり、ただし直近2ヶ月休眠）。Grok: 公式のGitHub直接連携は本セッションで確認できず。 | △ ChatGPT側は実績ありだが再稼働に課金判断が必要（`renkei.json`記載）。Grok側は未確認のまま。 |
| **実際にやっている人の事例（最低3つ）** | (1) LangGraphのmulti-agent handoffパターン（共有state/blackboard方式） (2) AutoGenのgroup chat with shared memory (3) CrewAIのhierarchical agent + shared context store | 参考: いずれも「エージェント基盤を自前で書く」前提のパターンで、たまごさんの用途（個人アカウントのチャットUI3枚）とは前提が異なる。考え方（1枚の共有状態を毎回読ませる）だけ拝借した。 |
| **共有メモリの実装例（一番壊れにくいのはどれか）** | ベクトルDB：検索は強いが監査・可読性が弱い／単純なgit(Markdown)：差分監査・人間可読・バージョン管理に強い／Issue駆動：往復には強いが「今の状態」のスナップショットには弱い | **git管理の1枚のMarkdown（NOW.md）が最も壊れにくい**と判断。このリポジトリの既存資産（`ai-brain/company-os/TAMAGO_COMMON_BRAIN.md`等）も同じ設計思想で、826番で先に検証済み。 |

## 結論（採用した設計）

「記憶を共有する」ではなく「毎回必ず読む1枚（`status/NOW.md`）を共有する」方式を採用。
理由：MCP/A2Aは個人アカウントのチャットUIには届かない。カスタム指示欄に1つのURLを書かせる方式が、3社の技術差を吸収できる唯一の共通点だったため。
