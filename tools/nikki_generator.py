#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
700番「業務日誌を毎日1枚、自動で作る」

たまごさんの言葉：「勤務の日にちを書いてほしいんだよね。何月何日 担当キティ、何月何日 くろすけ、
みたいな。失敗・成功事例、もらった、やった、悪くなったから改善した、とか。GitHubに置いとくのが
いいのか。要は業務日誌みたいなこと。毎日がいいのかな。」

人が書く前提にしない（腐るから）。機械で下記4つの正本ファイルから毎日1枚を組み立てる。
  - status/queue.json           … その日 startedAt された依頼＝「もらった依頼」
  - status/dispatch_outbox.jsonl … 完了報告＝「やったこと」（ok=true/false・本番URL付き）
  - status/oni_kantoku_log.jsonl … 独立検品の合否＝「うまくいった／差し戻し」
  - git log                      … その日のコミット件数（参考数字）
  - status/failures.md           … その日付の失敗ブロックがあれば「失敗して改善したこと」に転記

出力先: share/nikki/{date}.html （1日1枚）＋ share/nikki/index.html（一覧）
このリポジトリは公開（GitHub Pages）なので、個人情報・鍵・第三者の事情を載せない
（load_secretsのマスク処理と、1MB超ガード＝この生成物は毎回数十KB程度で該当しない）。

実行方法:
  python3 tools/nikki_generator.py                 # 今日（Asia/Tokyo）の1枚を作る/更新する
  python3 tools/nikki_generator.py --date 2026-09-09
  python3 tools/nikki_generator.py --push           # 生成後 git add/commit/push まで行う
"""
import argparse
import datetime
import glob
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS_DIR = os.path.join(REPO, "status")
NIKKI_DIR = os.path.join(REPO, "share", "nikki")
TANTOU_FILE = os.path.join(STATUS_DIR, "nikki_tantou.json")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/"

JST = datetime.timezone(datetime.timedelta(hours=9))

DEFAULT_TANTOU = "くろすけ"
# 秘密情報っぽい文字列が万一紛れ込んでいた場合の保険マスク（公開リポジトリのため）
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def mask_secrets(text):
    if not text:
        return text
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("［非表示：機密情報の可能性］", out)
    return out


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def parse_dt(s):
    """ISO風文字列を dt に。tzが無ければJST扱い。読めなければNone。"""
    if not s:
        return None
    try:
        s2 = s.strip()
        # "+0900" 形式を "+09:00" に正規化
        m = re.search(r"([+-]\d{2})(\d{2})$", s2)
        if m and ":" not in s2[-6:]:
            s2 = s2[: m.start()] + m.group(1) + ":" + m.group(2)
        dt = datetime.datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return dt.astimezone(JST)
    except (ValueError, TypeError):
        return None


def date_str(dt):
    return dt.strftime("%Y-%m-%d") if dt else None


def load_tantou(date):
    """status/nikki_tantou.json = {"2026-09-09": "キティ", ...}。無指定日はデフォルトの担当。"""
    data = load_json(TANTOU_FILE, {}) or {}
    return data.get(date, DEFAULT_TANTOU)


def collect_outbox(date):
    ok_items, ng_items = [], []
    for row in load_jsonl(os.path.join(STATUS_DIR, "dispatch_outbox.jsonl")):
        dt = parse_dt(row.get("ts"))
        if date_str(dt) != date:
            continue
        n = row.get("n")
        if n == 999999:
            continue  # テスト用エントリは日誌に出さない
        item = {
            "n": n,
            "title": mask_secrets(row.get("title") or ""),
            "urls": [u for u in (row.get("urls") or []) if isinstance(u, str) and u.startswith("http")],
            "elapsedMin": row.get("elapsedMin"),
            "time": dt.strftime("%H:%M") if dt else "",
        }
        if row.get("ok"):
            ok_items.append(item)
        else:
            ng_items.append(item)
    return ok_items, ng_items


def collect_oni(date):
    passed, failed = [], []
    for row in load_jsonl(os.path.join(STATUS_DIR, "oni_kantoku_log.jsonl")):
        dt = parse_dt(row.get("checkedAt"))
        if date_str(dt) != date:
            continue
        item = {
            "n": row.get("n"),
            "title": mask_secrets(row.get("title") or ""),
            "reason": mask_secrets((row.get("reason") or "")[:200]),
            "time": dt.strftime("%H:%M") if dt else "",
        }
        if row.get("decision") == "pass":
            passed.append(item)
        else:
            failed.append(item)
    return passed, failed


def collect_received(date):
    """その日 startedAt された依頼＝「もらった依頼（着手分）」。"""
    q = load_json(os.path.join(STATUS_DIR, "queue.json"), {}) or {}
    items = []
    for it in q.get("items", []):
        dt = parse_dt(it.get("startedAt"))
        if date_str(dt) != date:
            continue
        items.append({
            "n": it.get("n"),
            "title": mask_secrets(it.get("title") or ""),
            "time": dt.strftime("%H:%M") if dt else "",
            "status": it.get("status"),
        })
    items.sort(key=lambda x: x.get("time") or "")
    return items


def collect_git_commits(date):
    try:
        out = subprocess.run(
            ["git", "log", "--since=%s 00:00:00" % date, "--until=%s 23:59:59" % date,
             "--pretty=format:%h|%s", "--date=iso"],
            cwd=REPO, capture_output=True, text=True, timeout=15,
        )
        lines = [l for l in out.stdout.strip().split("\n") if l]
        return len(lines)
    except (subprocess.SubprocessError, OSError):
        return None


def collect_failures_md(date):
    """status/failures.md に「日付**：{date}」を含むブロックがあれば、その要約行を抜く。"""
    path = os.path.join(STATUS_DIR, "failures.md")
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    blocks = text.split("\n---\n")
    hits = []
    for b in blocks:
        if date not in b:
            continue
        title_m = re.search(r"^##\s*\d+\.\s*(.+)$", b, re.MULTILINE)
        sympt_m = re.search(r"\*\*症状\*\*[:：]\s*(.+)", b)
        fix_m = re.search(r"\*\*直し方\*\*[:：]\s*(.+)", b)
        if title_m:
            hits.append({
                "title": mask_secrets(title_m.group(1).strip()),
                "sympt": mask_secrets((sympt_m.group(1).strip() if sympt_m else "")[:200]),
                "fix": mask_secrets((fix_m.group(1).strip() if fix_m else "")[:200]),
            })
    return hits


def build_page_html(date, tantou, received, ok_items, ng_items, oni_pass, oni_fail, fail_blocks, commit_count):
    weekday = ["月", "火", "水", "木", "金", "土", "日"][
        datetime.datetime.strptime(date, "%Y-%m-%d").weekday()
    ]

    def li_received(items):
        if not items:
            return '<li class="empty">この日に新規着手した依頼の記録なし</li>'
        out = []
        for it in items:
            out.append('<li><span class="time">%s</span> #%s %s</li>' % (
                esc(it["time"]), esc(it["n"]), esc(it["title"][:120])))
        return "\n".join(out)

    def li_done(items):
        if not items:
            return '<li class="empty">この日の完了報告なし</li>'
        out = []
        for it in items:
            links = ""
            if it["urls"]:
                links = " ".join(
                    '<a href="%s" target="_blank" rel="noopener">本番URL</a>' % esc(u) for u in it["urls"][:3]
                )
            em = ("（%s分）" % it["elapsedMin"]) if it.get("elapsedMin") else ""
            out.append('<li><span class="time">%s</span> #%s %s%s %s</li>' % (
                esc(it["time"]), esc(it["n"]), esc(it["title"][:120]), esc(em), links))
        return "\n".join(out)

    def li_oni_pass(items):
        if not items:
            return '<li class="empty">この日の鬼監督PASSなし</li>'
        return "\n".join(
            '<li><span class="time">%s</span> #%s %s</li>' % (esc(it["time"]), esc(it["n"]), esc(it["title"][:120]))
            for it in items
        )

    fail_lines = []
    for it in ng_items:
        fail_lines.append(
            '<li><b>やって、うまくいかなかった：</b>#%s %s</li>' % (esc(it["n"]), esc(it["title"][:140]))
        )
    for it in oni_fail:
        fail_lines.append(
            '<li><b>鬼監督が差し戻した：</b>#%s %s — %s</li>' % (
                esc(it["n"]), esc(it["title"][:100]), esc(it["reason"][:160]))
        )
    for fb in fail_blocks:
        fail_lines.append(
            '<li><b>%s：</b>%s → %s</li>' % (esc(fb["title"]), esc(fb["sympt"]), esc(fb["fix"]))
        )
    if not fail_lines:
        fail_html = '<li class="empty">この日は差し戻し・失敗の記録なし</li>'
    else:
        fail_html = "\n".join(fail_lines)

    nums = (
        '<div class="nums">'
        '<div class="num"><b>%d</b><span>もらった依頼</span></div>'
        '<div class="num"><b>%d</b><span>完了（成功）</span></div>'
        '<div class="num"><b>%d</b><span>鬼監督PASS</span></div>'
        '<div class="num"><b>%d</b><span>失敗・差し戻し</span></div>'
        '<div class="num"><b>%s</b><span>コミット数</span></div>'
        "</div>"
    ) % (len(received), len(ok_items), len(oni_pass), len(ng_items) + len(oni_fail), commit_count if commit_count is not None else "—")

    html_out = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{date} 業務日誌（担当：{tantou}）</title>
<style>
  :root{{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--aka:#c4483a;--ao:#3a5f7a;--midori:#3a7a52;}}
  *{{box-sizing:border-box;}}
  body{{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 16px calc(env(safe-area-inset-bottom) + 40px);background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;font-size:16px;line-height:1.7;max-width:760px;margin-left:auto;margin-right:auto;}}
  a{{color:var(--ao);}}
  h1{{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.3rem;letter-spacing:0.06em;margin:0 0 6px;}}
  .date{{color:var(--sub);font-size:0.85rem;margin-bottom:6px;}}
  .tantou{{display:inline-block;background:#fff;border:1px solid var(--line);border-radius:999px;padding:4px 14px;font-size:0.85rem;margin-bottom:20px;}}
  h2{{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.05rem;letter-spacing:0.06em;margin:30px 0 12px;color:var(--sub);}}
  .nums{{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 20px;}}
  .num{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:100px;}}
  .num b{{display:block;font-size:1.4rem;line-height:1.2;}}
  .num span{{color:var(--sub);font-size:0.72rem;}}
  ul.log{{list-style:none;margin:0;padding:0;}}
  ul.log li{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 13px;margin:0 0 8px;font-size:0.92rem;}}
  ul.log li.empty{{color:var(--sub);background:transparent;border:1px dashed var(--line);}}
  ul.log .time{{color:var(--sub);font-size:0.8rem;margin-right:6px;}}
  .fail li{{border-left:3px solid var(--aka);}}
  .ok li{{border-left:3px solid var(--midori);}}
  nav{{margin:24px 0 0;font-size:0.85rem;}}
  footer{{color:var(--sub);font-size:0.78rem;margin-top:36px;line-height:1.6;}}
</style>
</head>
<body>
<div class="date"><a href="./">業務日誌の一覧</a></div>
<h1>{date}（{weekday}）業務日誌</h1>
<div class="tantou">担当：{tantou}</div>

{nums}

<h2>① もらった依頼</h2>
<ul class="log">
{received}
</ul>

<h2>② やったこと（本番URL付き）</h2>
<ul class="log ok">
{done}
</ul>

<h2>③ うまくいったこと（鬼監督PASS）</h2>
<ul class="log ok">
{oni_pass}
</ul>

<h2>④ 失敗して改善したこと</h2>
<ul class="log fail">
{fail}
</ul>

<nav><a href="./">← 業務日誌の一覧へ戻る</a></nav>
<footer>
機械生成（status/queue.json・dispatch_outbox.jsonl・oni_kantoku_log.jsonl・failures.md・git log から自動作成。人手での加筆はしない）。<br>
生成: {generated}
</footer>
</body>
</html>
""".format(
        date=esc(date), tantou=esc(tantou), weekday=weekday, nums=nums,
        received=li_received(received), done=li_done(ok_items), oni_pass=li_oni_pass(oni_pass),
        fail=fail_html, generated=esc(datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")),
    )
    return html_out


def build_index_html():
    files = sorted(glob.glob(os.path.join(NIKKI_DIR, "20*.html")), reverse=True)
    dates = [os.path.splitext(os.path.basename(f))[0] for f in files]
    items = []
    for d in dates:
        tantou = load_tantou(d)
        items.append('<li><a href="%s.html">%s</a><span class="tantou">担当：%s</span></li>' % (
            esc(d), esc(d), esc(tantou)))
    items_html = "\n".join(items) if items else '<li class="empty">まだ日誌がありません</li>'
    return """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>業務日誌の一覧</title>
<style>
  :root{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--ao:#3a5f7a;}
  *{box-sizing:border-box;}
  body{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 16px calc(env(safe-area-inset-bottom) + 40px);background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;font-size:16px;line-height:1.7;max-width:760px;margin-left:auto;margin-right:auto;}
  a{color:var(--ao);text-decoration:none;}
  h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.3rem;letter-spacing:0.06em;margin:0 0 20px;}
  ul{list-style:none;margin:0;padding:0;}
  li{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 16px;margin:0 0 8px;display:flex;justify-content:space-between;align-items:center;font-size:1rem;}
  li a{font-weight:600;}
  li .tantou{color:var(--sub);font-size:0.82rem;}
  li.empty{color:var(--sub);justify-content:flex-start;}
</style>
</head>
<body>
<h1>業務日誌の一覧（毎日1枚・自動作成）</h1>
<ul>
%s
</ul>
</body>
</html>
""" % items_html


def push_repo(date, retries=3, wait_sec=5):
    """このリポジトリは他の自動化プロセスも同時にgit操作するため、
    index.lock競合等で1回失敗することがある。少し待って最大retries回まで試す。"""
    import time

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(["git", "add", "share/nikki/"], cwd=REPO, check=True,
                            capture_output=True, text=True)
            diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", "share/nikki/"],
                                   cwd=REPO)
            if diff.returncode == 0:
                print("git: 差分なし（コミット省略）")
                return True
            commit = subprocess.run(
                ["git", "commit", "-m", "nikki: %s 業務日誌を自動生成（700番）" % date],
                cwd=REPO, capture_output=True, text=True,
            )
            if commit.returncode != 0:
                last_err = "commit失敗(試行%d): %s" % (attempt, (commit.stdout + commit.stderr).strip()[:300])
                print(last_err)
                time.sleep(wait_sec)
                continue
            # push前に最新を取り込み、他プロセスの先行pushと衝突しないようにする
            subprocess.run(["git", "fetch", "origin", "main"], cwd=REPO, capture_output=True, text=True, timeout=30)
            push = subprocess.run(["git", "push", "origin", "main"], cwd=REPO, capture_output=True, text=True)
            if push.returncode == 0:
                print("git push 成功")
                return True
            # 追従が必要な場合（他プロセスが先にpush済み）は rebase して再試行
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=REPO,
                            capture_output=True, text=True, timeout=60)
            push2 = subprocess.run(["git", "push", "origin", "main"], cwd=REPO, capture_output=True, text=True)
            if push2.returncode == 0:
                print("git push 成功（rebase後）")
                return True
            last_err = "push失敗(試行%d): %s" % (attempt, push2.stderr.strip()[:300])
            print(last_err)
            time.sleep(wait_sec)
        except subprocess.CalledProcessError as e:
            last_err = "git操作失敗(試行%d): %s" % (attempt, e)
            print(last_err)
            time.sleep(wait_sec)
        except subprocess.TimeoutExpired as e:
            last_err = "git操作タイムアウト(試行%d): %s" % (attempt, e)
            print(last_err)
            time.sleep(wait_sec)
    print("git操作: %d回試して失敗。次回の定時実行で再試行される想定。最終エラー: %s" % (retries, last_err))
    return False


def generate_one(date):
    tantou = load_tantou(date)
    received = collect_received(date)
    ok_items, ng_items = collect_outbox(date)
    oni_pass, oni_fail = collect_oni(date)
    fail_blocks = collect_failures_md(date)
    commit_count = collect_git_commits(date)

    os.makedirs(NIKKI_DIR, exist_ok=True)
    page = build_page_html(date, tantou, received, ok_items, ng_items, oni_pass, oni_fail, fail_blocks, commit_count)
    out_path = os.path.join(NIKKI_DIR, "%s.html" % date)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print("書きました: %s" % out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD（省略時は今日・Asia/Tokyo）")
    ap.add_argument("--also-yesterday", action="store_true", help="前日分も合わせて確定生成し直す")
    ap.add_argument("--push", action="store_true", help="生成後 git add/commit/push まで行う")
    args = ap.parse_args()

    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    target_dates = [args.date] if args.date else [today]
    if args.also_yesterday and not args.date:
        yday = (datetime.datetime.now(JST) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        target_dates.append(yday)

    for d in target_dates:
        generate_one(d)

    index_html = build_index_html()
    with open(os.path.join(NIKKI_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("書きました: %s" % os.path.join(NIKKI_DIR, "index.html"))

    if args.push:
        push_repo(target_dates[0])


if __name__ == "__main__":
    main()
