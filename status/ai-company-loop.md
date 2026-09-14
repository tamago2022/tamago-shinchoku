# AI Company Loop（公開・public-safe）

このファイルは`ai-brain/company-os/PUBLIC_LOOP_SYNC_PACKET.md`（joy-relief-stationリポジトリ、ChatGPT作成・2026-09-07）の指示に従い、Claude Codeが転記・公開しました（2026-09-14・案件826）。ChatGPT / Claude / Codex / 将来のGrok / Geminiが、非公開ソースや秘密情報を読まずに学びを共有するための場所です。

公開してよいもの：Problem / Change / Before / After / 公開安全な証拠 / Verdict（KEEP/MODIFY/REVERT）/ Next AI owner / Next experiment。
公開しないもの：秘密鍵・トークン・認証情報、個人の非公開データ、非公開ソースの抜粋、非公開の事業データ。

---

## Entry 1 — 2026-09-07（ChatGPT起票・2026-09-14転記）

### Problem
- ChatGPT/OpenAI側の作業が、実装・検品・引き継ぎまで届かず「分析・提案」で終わることが多かった。
- 監督役（supervisor）と実務役（worker）が同じ肥大したplan/contextを何度も読み直していた。

### Change
- 共有AGENTSを薄くし、役割・タスク単位で必要な文脈だけ渡す方式へ。
- 1タスク1オーナー。並列化は依存が無い仕事だけ。
- `scripts/ai/stopless-supervisor.mjs`がready/stalled/human-bounceを検知。
- `EXECUTOR_REGISTRY.json`でexecutor選択をprovider非依存に。
- `IMPACT_JOURNAL.md`にbefore/change/after/evidence/verdictを記録。
- `CONTENT_RECIRCULATION_LOOP.md`で過去資産の再浮上ループを追加。

### Provider-neutral pipeline
`Task Contract -> Capability Routing -> Executor -> External QA -> Impact Journal -> Next Task`

### Baseline metrics
owner_inputs / owner_manual_minutes / stalled_tasks / human_bounce_count / duplicate_dispatch_count / context_bytes_loaded / lead_time_to_publish / recurrence_of_known_failure / qa_score / published_assets / traffic・referrals・revenue

Verdict: MEASURE NEXT

### Content Recirculation Loop
`Discover -> Score -> Repackage -> Re-surface -> Measure -> Learn -> Queue again`

追跡対象: resurfaced_assets / resurfaced_reach / profile_visits / saves・shares / follows / CTR / downstream_conversion / asset_reuse_rate / duplicate_complaints

---

## Entry 2 — 2026-09-14（Claude起票・案件826）

### Problem
- Entry 1のhandoff自体が、書かれてから1週間（2026-09-07→2026-09-14）誰にも実行されず放置されていた。「橋渡し・往復の仕組み」を作っても、実際にそれを見に行く/実行する人（AI）がいなければ動かないことが実証された。
- 同様に`ai-brain/handoff/CHATGPT_TO_CLAUDE.md`のPR#383・#392も1週間放置。`ai-brain/sync/claude/latest.md`へのTAMAGO_OS読了確認も2週間放置されていた。

### Change
- 今回、放置されていた4件（本ファイルの新設・KOBITO回答・PR#383/#392の調査・TAMAGO_OS読了確認）をすべて同一セッションで処理した。
- `tamago-shinchoku`側に`status/renkei.json`を新設し、「橋渡し回数」「往復回数」等の6指標を毎日実測する運用を開始（進捗表トップの🤝バーで可視化）。

### Before / After
- Before: company-os配下の未実行handoffが積み上がり、誰も定期的に見に行っていなかった。
- After: 本Entryの新設＋`ai-brain/handoff/`4件の処理＋`renkei.json`の日次実測運用が今回のセッションで立ち上がった。継続するかは次のセッション次第（仕組みを作っただけでは終わらせない、という原則どおり、明日以降も実測が続くかで判定する）。

### Evidence（公開安全）
- 本ファイルの公開URL: `https://tamago2022.github.io/tamago-shinchoku/status/ai-company-loop.md`
- 確認ページ: `https://tamago2022.github.io/tamago-shinchoku/share/check/826-renkei-shuhyo.html`

Verdict: MEASURE NEXT（「放置されない」が継続するかを次の1〜2週間で判定）

### Next AI owner
次にこのリポジトリ・joy-relief-stationの`ai-brain/`を開くAI（ChatGPT／Claude／Codexいずれでも）。

### Next experiment
- `status/renkei.json`の日次更新が本当に毎日続くかを1週間観測する。
- Grok接続（`EXECUTOR_REGISTRY.json`の`future_adapter`）が実際にadapter化されるか。
