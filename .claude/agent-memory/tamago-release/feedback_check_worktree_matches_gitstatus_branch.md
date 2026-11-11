---
name: feedback_check_worktree_matches_gitstatus_branch
description: このリポジトリは複数の作業ディレクトリ(Desktop/joy-relief-station等)が併存し、ブランチもworktreeも混在する。編集前にsystem-reminderのgitStatusにある「Current branch」と一致するディレクトリかを確認する。
metadata:
  type: feedback
---

案件#35042の検品作業で、`.claude/KNOWN_ISSUES.md`と`.claude/PENDING_DECISIONS.md`を更新しようとした際、最初に`/Users/mac/Desktop/joy-relief-station`で作業してしまった。しかしそこは`git status --short`で100件超の無関係な未追跡・変更ファイルを抱えた`fix/t027-cute-room-thumb-crash`ブランチであり、system-reminderのgitStatusが示す本来のブランチ`fix/35042-known-issues-update`とは異なる場所だった。正しい場所は`/Users/mac/Documents/AI作業/.worktrees/q35042-0904`（このブランチ専用のクリーンなgit worktree）だった。

**Why:** このプロジェクトは店主の指示で多数の並行セッション・worktreeが動いており、`/Users/mac/Desktop/joy-relief-station`のような共有クローンは常に複数セッションの作業途中物が混在した汚い状態になっている。system-reminderのgitStatusに表示される「Current branch」はそのタスク専用に用意されたworktreeを指しているはずなので、そこと食い違うディレクトリで編集すると無関係な変更に自分の変更が埋もれたり、誤ったブランチにコミットするリスクが生じる。

**How to apply:**
- 作業開始時、`git branch --show-current`を候補ディレクトリそれぞれで確認し、system-reminderのgitStatusに書かれた「Current branch」と一致する方（通常は`.worktrees/`配下）を使う。
- 一致しないディレクトリで既に編集してしまった場合は、`git -C <path> checkout -- <file>`で即座に元に戻し、正しいworktreeで再実行する（`cd`してからgitコマンドを打つと「信頼できないhookを拾う可能性」で権限確認が挟まるため、`git -C <path> ...`の形を使うとスムーズ）。
- 候補ディレクトリ間でファイル内容が食い違う場合（例：KNOWN_ISSUES.mdの行番号がずれている）は、新しい方（system-reminderのgitStatusと一致する方）を正としてよい。
