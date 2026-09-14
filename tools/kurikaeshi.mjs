#!/usr/bin/env node
/**
 * kurikaeshi.mjs — 「3回以上言われて直っていないもの」を自動でカウントし、
 * 3回に到達した時点で joy-relief-station の REPEATED_UNFIXED.md へ自動追記、
 * Issue #390 へ他社AI(OpenAI鬼監督・Grok)向けの通知コメントを投稿する。
 *
 * たまごさんの指示（2026-09-14）：
 *   「これから3回言っても直らなかったのは、もう自動的に他の会社のAIが介入するから。」
 *
 * 使い方:
 *   node tools/kurikaeshi.mjs bump <key> --label "<日本語ラベル>" [--task <番号>] [--task <番号> ...]
 *   node tools/kurikaeshi.mjs mark-fixed <key> --by "<修正した人/チーム名>" [--note "<一言>"]
 *   node tools/kurikaeshi.mjs list
 *
 * テストモード:
 *   環境変数 KURIKAESHI_TEST=1 を立てると、
 *     ① 保存先が status/kurikaeshi.test.json に切り替わる
 *     ② REPEATED_UNFIXED.md への追記・git push・gh issue comment は実行せず、
 *        「実行されたであろう内容」を標準出力に表示するだけの dry-run になる
 *   本番の実データ（REPEATED_UNFIXED.md・Issue #390）は絶対に汚さない。
 *
 * 危険箇所への配慮:
 *   - status/kurikaeshi.json への書き込みは tmp書き込み→rename の原子的操作にし、
 *     書き込み中の破損・他ジョブとの競合を避ける。
 *   - 配列(items)を切り詰める操作は一切行わない（append-only）。
 *   - REPEATED_UNFIXED.md への追記は、joy-relief-station の独立したgit worktreeを
 *     一時的に作って行い、作業終了後に必ず片付ける（他セッションの未コミット変更を
 *     巻き込まないため）。既存のA〜Eセクションは絶対に書き換えず、末尾に追記のみ行う。
 */

import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..'); // tamago-shinchoku リポジトリ直下

const DATA_PATH = path.join(REPO_ROOT, 'status', 'kurikaeshi.json');
const TEST_DATA_PATH = path.join(REPO_ROOT, 'status', 'kurikaeshi.test.json');

const JOY_REPO = '/Users/mac/Desktop/joy-relief-station';
const REPEATED_UNFIXED_REL = 'ai-brain/company-os/REPEATED_UNFIXED.md';
const ISSUE_REPO = 'tamago2022/joy-relief-station';
const ISSUE_NUMBER = 390;

const ESCALATION_HEADING_TEXT =
  'F. kurikaeshi.json が自動検出したもの（3回到達・自動追記）';
const FIXED_HEADING_TEXT = 'G. 直ったもの';

// ---------------------------------------------------------------------------
// ユーティリティ
// ---------------------------------------------------------------------------

function isTestMode() {
  return process.env.KURIKAESHI_TEST === '1';
}

function dataPath() {
  return isTestMode() ? TEST_DATA_PATH : DATA_PATH;
}

function nowISO() {
  return new Date().toISOString();
}

function loadData() {
  const p = dataPath();
  if (!fs.existsSync(p)) {
    return { schema_version: 1, updated_at: nowISO(), items: [] };
  }
  const raw = fs.readFileSync(p, 'utf8');
  if (!raw.trim()) {
    return { schema_version: 1, updated_at: nowISO(), items: [] };
  }
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed.items)) {
    throw new Error(`${p} の items が配列ではありません。壊れたファイルの可能性があるため中断します。`);
  }
  return parsed;
}

// 一時ファイルに書いてから rename する原子的書き込み（書き込み中の破損防止）。
function saveData(data) {
  data.updated_at = nowISO();
  const p = dataPath();
  const dir = path.dirname(p);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.${path.basename(p)}.tmp-${process.pid}-${Date.now()}`);
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + '\n', 'utf8');
  fs.renameSync(tmp, p);
}

function sh(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { encoding: 'utf8', ...opts });
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim();
    throw new Error(`${cmd} ${args.join(' ')} が失敗しました (exit ${result.status}): ${detail}`);
  }
  return result.stdout;
}

// GitHubのMarkdown見出し→アンカーの生成規則を再現する。
// 例: "F. kurikaeshi.json が自動検出したもの（3回到達・自動追記）"
//  -> "f-kurikaeshijson-が自動検出したもの3回到達自動追記"
function githubSlug(text) {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, '') // 句読点・記号を除去（ハイフンには置換しない）
    .trim()
    .replace(/\s+/g, '-');
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const hasVal = i + 1 < argv.length && !argv[i + 1].startsWith('--');
      const val = hasVal ? argv[++i] : true;
      if (args[key] === undefined) {
        args[key] = val;
      } else if (Array.isArray(args[key])) {
        args[key].push(val);
      } else {
        args[key] = [args[key], val];
      }
    } else {
      args._.push(a);
    }
  }
  return args;
}

function toArray(v) {
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

// ---------------------------------------------------------------------------
// REPEATED_UNFIXED.md への追記（見出しの直下、次の見出しの手前に挿入する）
// ---------------------------------------------------------------------------

function insertUnderHeading(content, headingLine, lineToAdd) {
  const headingIdx = content.indexOf(headingLine);
  if (headingIdx === -1) {
    const sep = content.endsWith('\n') ? '\n' : '\n\n';
    return `${content}${sep}${headingLine}\n\n${lineToAdd}\n`;
  }
  const rest = content.slice(headingIdx + headingLine.length);
  const nextHeadingMatch = rest.match(/\n## /);
  if (!nextHeadingMatch) {
    return `${content.replace(/\s*$/, '')}\n${lineToAdd}\n`;
  }
  const insertPos = headingIdx + headingLine.length + nextHeadingMatch.index + 1;
  return `${content.slice(0, insertPos)}${lineToAdd}\n\n${content.slice(insertPos)}`;
}

function withJoyWorktree(fn) {
  const tmpDir = path.join(
    os.tmpdir(),
    `kurikaeshi-wt-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  );
  sh('git', ['-C', JOY_REPO, 'fetch', 'origin', 'main', '--quiet']);
  sh('git', ['-C', JOY_REPO, 'worktree', 'add', '--detach', tmpDir, 'origin/main']);
  try {
    return fn(tmpDir);
  } finally {
    try {
      sh('git', ['-C', JOY_REPO, 'worktree', 'remove', '--force', tmpDir]);
    } catch (e) {
      // 片付けの失敗は握りつぶさず出力だけする（次回起動時の手動掃除の手がかりを残す）
      console.error(`[warn] worktree掃除に失敗: ${e.message}`);
    }
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch {
      /* best effort */
    }
  }
}

// 見出し配下へ1行追記し、専用worktree経由でcommit・pushする。戻り値はcommit sha。
function appendToRepeatedUnfixedAndPush(headingLine, lineToAdd, commitMessage) {
  return withJoyWorktree((tmpDir) => {
    const filePath = path.join(tmpDir, REPEATED_UNFIXED_REL);
    const content = fs.readFileSync(filePath, 'utf8');
    const next = insertUnderHeading(content, headingLine, lineToAdd);
    fs.writeFileSync(filePath, next, 'utf8');
    sh('git', ['-C', tmpDir, 'add', REPEATED_UNFIXED_REL]);
    sh('git', ['-C', tmpDir, 'commit', '-m', commitMessage]);

    let attempts = 0;
    // 他セッションが同時にmainへpushしている可能性があるため、
    // 失敗したら rebase して 3回までリトライする。
    for (;;) {
      try {
        sh('git', ['-C', tmpDir, 'push', 'origin', 'HEAD:main']);
        break;
      } catch (e) {
        attempts += 1;
        if (attempts >= 3) throw e;
        sh('git', ['-C', tmpDir, 'pull', '--rebase', 'origin', 'main']);
      }
    }
    return sh('git', ['-C', tmpDir, 'rev-parse', 'HEAD']).trim();
  });
}

function buildAnchorUrl(headingText) {
  const anchor = githubSlug(headingText);
  return `https://github.com/${ISSUE_REPO}/blob/main/${REPEATED_UNFIXED_REL}#${anchor}`;
}

// ---------------------------------------------------------------------------
// コマンド: bump
// ---------------------------------------------------------------------------

function cmdBump(args) {
  const key = args._[1];
  if (!key) {
    console.error('使い方: node tools/kurikaeshi.mjs bump <key> --label "<ラベル>" [--task <番号>]');
    process.exit(1);
  }
  const label = typeof args.label === 'string' ? args.label : undefined;
  const taskNums = toArray(args.task)
    .map((v) => Number(v))
    .filter((n) => Number.isFinite(n));

  const data = loadData();
  let item = data.items.find((i) => i.key === key);
  const now = nowISO();

  if (!item) {
    if (!label) {
      console.error(`新規key「${key}」には --label が必須です。`);
      process.exit(1);
    }
    item = {
      key,
      label,
      count: 0,
      task_numbers: [],
      first_mentioned_at: now,
      last_mentioned_at: now,
      status: 'tracking',
      escalated: false,
      escalated_at: null,
      fixed_by: null,
      fixed_at: null,
      fix_note: null,
    };
    data.items.push(item);
  } else if (label) {
    item.label = label;
  }

  item.count += 1;
  item.last_mentioned_at = now;
  for (const t of taskNums) {
    if (!item.task_numbers.includes(t)) item.task_numbers.push(t);
  }

  // 注意：escalated確定はhandleEscalation成功後まで保留する。
  // ここで先にescalated=trueを保存してしまうと、直後のgit push/gh issue comment失敗時に
  // 「エスカレーション済みだが実際は未通知」という状態がJSONに固定され、
  // !item.escalated ゲートにより以後二度と自動リトライされなくなる（2026-09-14検品指摘・修正）。
  let escalationInfo = null;
  if (item.count >= 3 && !item.escalated) {
    escalationInfo = {
      key: item.key,
      label: item.label,
      task_numbers: [...item.task_numbers],
      escalated_at: now,
    };
  }

  saveData(data);

  console.log(
    `[bump] key=${item.key} label="${item.label}" count=${item.count} escalated=${item.escalated} tasks=[${item.task_numbers.join(',')}]`
  );

  if (escalationInfo) {
    try {
      handleEscalation(escalationInfo);
      // ここまで例外なく完了して初めてescalated=trueを保存する。
      item.escalated = true;
      item.escalated_at = escalationInfo.escalated_at;
      item.status = 'escalated';
      saveData(data);
    } catch (err) {
      console.error(
        `[escalate] エスカレーション処理が失敗しました（escalatedは未確定のまま保存済み。次回bumpで自動的に再試行されます）: ${err.message}`
      );
    }
  }
}

function handleEscalation(info) {
  const headingLine = `## ${ESCALATION_HEADING_TEXT}`;
  const taskStr = info.task_numbers.length ? info.task_numbers.join(', ') : 'なし';
  const line = `- **${info.label}**（key: ${info.key}／番号: ${taskStr}／到達: ${info.escalated_at}）`;
  const url = buildAnchorUrl(ESCALATION_HEADING_TEXT);

  if (isTestMode()) {
    console.log('--- [DRY-RUN] ここから先はテストモードのため実行しません ---');
    console.log(`[DRY-RUN] REPEATED_UNFIXED.md 見出し: ${headingLine}`);
    console.log(`[DRY-RUN] REPEATED_UNFIXED.md 追記行: ${line}`);
    console.log(`[DRY-RUN] git push は行いません（joy-relief-station main への追記をスキップ）`);
    console.log(
      `[DRY-RUN] gh issue comment ${ISSUE_NUMBER} --repo ${ISSUE_REPO} は投稿しません`
    );
    console.log(`[DRY-RUN] 想定コメント本文: 🔔 kurikaeshi.json 自動検出：3回到達「${info.label}」（key: ${info.key}）を REPEATED_UNFIXED.md に追記しました → ${url}`);
    console.log('--- [DRY-RUN] ここまで ---');
    return;
  }

  const commitMsg = `docs: kurikaeshi.json 3回到達「${info.label}」を自動追記`;
  const sha = appendToRepeatedUnfixedAndPush(headingLine, line, commitMsg);
  console.log(`[escalate] REPEATED_UNFIXED.md へ追記・push完了 (commit ${sha})`);

  const commentBody = `🔔 kurikaeshi.json 自動検出：3回到達「${info.label}」（key: ${info.key}）を REPEATED_UNFIXED.md に追記しました → ${url}`;
  sh('gh', ['issue', 'comment', String(ISSUE_NUMBER), '--repo', ISSUE_REPO, '--body', commentBody]);
  console.log(`[escalate] Issue #${ISSUE_NUMBER} へ通知コメントを投稿完了`);
}

// ---------------------------------------------------------------------------
// コマンド: mark-fixed
// ---------------------------------------------------------------------------

function cmdMarkFixed(args) {
  const key = args._[1];
  if (!key) {
    console.error('使い方: node tools/kurikaeshi.mjs mark-fixed <key> --by "<チーム名>" [--note "<一言>"]');
    process.exit(1);
  }
  const by = typeof args.by === 'string' ? args.by : undefined;
  if (!by) {
    console.error('--by は必須です。');
    process.exit(1);
  }
  const note = typeof args.note === 'string' ? args.note : null;

  const data = loadData();
  const item = data.items.find((i) => i.key === key);
  if (!item) {
    console.error(`key「${key}」は見つかりません。`);
    process.exit(1);
  }

  const now = nowISO();
  item.fixed_by = by;
  item.fixed_at = now;
  item.fix_note = note;
  item.status = 'fixed';
  saveData(data);

  console.log(`[mark-fixed] key=${item.key} fixed_by=${by} fixed_at=${now} note=${note ?? '-'}`);

  const headingLine = `## ${FIXED_HEADING_TEXT}`;
  const noteSuffix = note ? `（${note}）` : '';
  const line = `- ${item.label}：${by}が${now}に修正${noteSuffix}`;

  if (isTestMode()) {
    console.log('--- [DRY-RUN] ここから先はテストモードのため実行しません ---');
    console.log(`[DRY-RUN] REPEATED_UNFIXED.md 見出し: ${headingLine}`);
    console.log(`[DRY-RUN] REPEATED_UNFIXED.md 追記行: ${line}`);
    console.log('--- [DRY-RUN] ここまで ---');
    return;
  }

  const commitMsg = `docs: kurikaeshi.json「${item.label}」の修正完了を自動追記`;
  const sha = appendToRepeatedUnfixedAndPush(headingLine, line, commitMsg);
  console.log(`[mark-fixed] REPEATED_UNFIXED.md へ追記・push完了 (commit ${sha})`);
}

// ---------------------------------------------------------------------------
// コマンド: list
// ---------------------------------------------------------------------------

function cmdList() {
  const data = loadData();
  console.log(`schema_version=${data.schema_version} updated_at=${data.updated_at} items=${data.items.length}`);
  if (!data.items.length) {
    console.log('(項目なし)');
    return;
  }
  for (const item of data.items) {
    console.log(
      `- ${item.key} | ${item.label} | count=${item.count} | escalated=${item.escalated} | status=${item.status} | tasks=[${item.task_numbers.join(',')}] | fixed_by=${item.fixed_by ?? '-'}`
    );
  }
}

// ---------------------------------------------------------------------------
// エントリポイント
// ---------------------------------------------------------------------------

function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0];
  switch (cmd) {
    case 'bump':
      cmdBump(args);
      break;
    case 'mark-fixed':
      cmdMarkFixed(args);
      break;
    case 'list':
      cmdList();
      break;
    default:
      console.error('使い方: node tools/kurikaeshi.mjs <bump|mark-fixed|list> ...');
      process.exit(1);
  }
}

main();
