#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
942番「【SNS】コンシェルジュ日記（中の人の奮闘をそのまま出す・投稿前に全部見せる）」

立ち位置＝「ごきげん補給所の案内所の中の人」。英語圏向け。顔を出さない。
曲紹介だけでなく「今日はこれに苦戦した／これができた」をそのまま見せる
プロセスエコノミー（ピーター・レベルズ方式）。

★1184号関所通過済み（票 hyo-1790991692・sonomama）：既存の実例
  tools/nikki_generator.py（700番・業務日誌）の構造（status配下のjsonlから
  当日分を機械抽出→HTML化→git push→index.html一覧）をそのまま踏襲して作る。
  差分はデータソースをfailures.jsonlの"-quick"のみに絞った点と、
  出力を英語ぼやき＋日本語併記にした点のみ。

作り話をしない。ネタは必ず下記の実在ファイルから拾う：
  - status/failures.jsonl       … その日の "-quick" 記録＝人から見える具体的な苦戦
  - status/dispatch_outbox.jsonl … 完了報告（ts付き行のみ）＝ok=False優先、無ければok=True
ネタが1件も無い日は「今日は静かな日でした」と正直に書く（作り話はしない）。

出力:
  share/concierge-diary/{date}.html   … 投稿前プレビュー（英語本文＋日本語併記＋出典＋
                                          音声/スクショの有無を正直に表示）
  share/concierge-diary/index.html    … 一覧
  status/concierge_diary_drafts/{date}.json … Buffer予約投稿用の下書き（未投稿。人の確認待ち）

★投稿はしない（③投稿前に必ず全部見せる、の原則）。実際にXへ出すのは、たまごさんが
  このページを見て良ければBuffer予約（status/BUFFER_YOYAKU.mdの手順）に乗せる別工程。
★音声（10秒・声=アイリス）は今回未生成（fal等の課金APIのため、本数と単価の見積もりを
  先に出す必要がある＝CLAUDE.md「お金が出る前に見積もりを出す」）。ページにはその事実を
  そのまま書く（弱い言い換えで「準備中」等とは書かない）。

実行方法:
  python3 tools/concierge_diary.py                 # 今日（Asia/Tokyo）の1枚を作る/更新する
  python3 tools/concierge_diary.py --date 2026-10-03
  python3 tools/concierge_diary.py --push           # 生成後 git add/commit/push まで行う
"""
import argparse
import datetime
import glob
import html
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS_DIR = os.path.join(REPO, "status")
DIARY_DIR = os.path.join(REPO, "share", "concierge-diary")
DRAFT_DIR = os.path.join(STATUS_DIR, "concierge_diary_drafts")
PAGES_BASE = "https://tamago2022.github.io/tamago-shinchoku/"

JST = datetime.timezone(datetime.timedelta(hours=9))

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


# ── ネタのカテゴリ判定 → 英語ぼやきテンプレ ──────────────────────
# 「毎日人が英訳する」を前提にしない（腐る）。キーワードでカテゴリを決め、
# カテゴリごとに固定の英語テンプレへ事実（短い要約）を埋め込む。
# 新しいカテゴリに当たらないネタは GENERIC を使う（作り話をしないための保険）。
CATEGORIES = [
    ("api_credit_zero", re.compile(r"API.*(残高|クレジット).*(0|ゼロ|insufficient_quota)|credit_balance"),
     {
         "en": "Tried to get an AI API to help with today's work... turned out the account credit hit zero. "
               "Can't even outsource the struggle.",
         "ja": "今日の作業をAI APIに手伝ってもらおうとしたら、アカウントの残高がゼロでした。苦労すら外注できない日。",
     }),
    ("disk_space", re.compile(r"ディスク(空き|容量)|disk.*(space|full)", re.IGNORECASE),
     {
         "en": "Running low on disk space again. Every time I think it's handled, something eats a few more GB overnight.",
         "ja": "またディスクの空きが減っていました。直したつもりでも、一晩でまたGBが削られています。",
     }),
    ("deploy_stuck", re.compile(r"デプロイ.*(完走|cancelled|pending)|force push.*(連打|繰り返す)"),
     {
         "en": "Tried to publish an update... the deploy pipeline kept canceling itself before it finished. "
               "Still digging into why.",
         "ja": "更新を公開しようとしたのに、デプロイが完走する前に何度もキャンセルされていました。原因はまだ調査中。",
     }),
    ("badge_thumb", re.compile(r"バッジ.*(大きさ|サイズ|揃わ)|サムネイル.*(揃わ|崩れ)"),
     {
         "en": "Spent way too long trying to get a little badge to line up the same size everywhere. "
               "It still isn't perfect.",
         "ja": "小さなバッジの大きさを全ページで揃えようとして、想定よりずっと時間を溶かしました。まだ完璧じゃない。",
     }),
    ("mobile_heavy", re.compile(r"スマホ.*(重い|落ちる)|モバイル.*(重い|落ちる)"),
     {
         "en": "A mobile page kept getting heavy and crashing when a link was pasted in. Chasing the root cause today.",
         "ja": "スマホ版の編集画面がURLを入れると重くなって落ちる問題を追いかけています。",
     }),
]

GENERIC_NG = {
    "en": "Something didn't go the way I planned today. Back to debugging.",
    "ja": "今日は思っていたようにいかないことがありました。また調査からやり直し。",
}
GENERIC_OK = {
    "en": "Small win today: shipped something that actually works.",
    "ja": "今日の小さな勝利：ちゃんと動くものが1つ本番に出ました。",
}
QUIET_DAY = {
    "en": "A quiet day in the back office. Nothing dramatic to report — just steady, unglamorous upkeep.",
    "ja": "今日は裏方として静かな1日でした。特に大きな出来事は無く、地味な保守が中心でした。",
}


def categorize(text):
    for key, pat, tpl in CATEGORIES:
        if pat.search(text or ""):
            return key, tpl
    return None, None


def collect_today_quick_failures(date):
    """status/failures.jsonl の当日分で id末尾が -quick（＝人が指摘した具体的事故）のものだけを拾う。
    F-{date}-ame / -uso / -ochita / -waku / -jouchuu のような定型の運用メトリクス行は、
    毎日同じ形で中身が無く日記のネタとして使うと「同じ話の繰り返し」になるため除外する。"""
    rows = load_jsonl(os.path.join(STATUS_DIR, "failures.jsonl"))
    out = []
    for r in rows:
        if r.get("date") != date:
            continue
        rid = r.get("id") or ""
        if not rid.endswith("-quick"):
            continue
        what = (r.get("what") or "").strip()
        if not what:
            continue
        out.append({"id": rid, "what": what, "queueRef": r.get("queueRef")})
    return out


def collect_today_outbox(date):
    rows = load_jsonl(os.path.join(STATUS_DIR, "dispatch_outbox.jsonl"))
    ok_items, ng_items = [], []
    for row in rows:
        ts = row.get("ts")
        if not isinstance(ts, str) or not ts.startswith(date):
            continue
        if "title" not in row or "n" not in row:
            continue
        n = row.get("n")
        if n == 999999:
            continue
        item = {
            "n": n,
            "title": mask_secrets(row.get("title") or ""),
            "urls": [u for u in (row.get("urls") or []) if isinstance(u, str) and u.startswith("http")],
            "result": mask_secrets((row.get("result") or "")[:200]),
        }
        if row.get("ok") is False:
            ng_items.append(item)
        elif row.get("ok") is True:
            ok_items.append(item)
    return ok_items, ng_items


def pick_topic(date):
    """今日のネタを1つ選ぶ。優先順位：
    1. failures.jsonl の -quick（具体的な苦戦。最も「中の人の奮闘」に近い）
    2. dispatch_outbox の ok=False（やってみて上手くいかなかった）
    3. dispatch_outbox の ok=True（今日できたこと）
    4. 何も無ければ「静かな日」と正直に書く
    決定論的にするため、各グループ内は最初に見つかったものを採用する（実行し直しても結果がブレない）。
    """
    quicks = collect_today_quick_failures(date)
    for q in quicks:
        cat, tpl = categorize(q["what"])
        if tpl:
            return {
                "source": "failures.jsonl(%s)" % q["id"],
                "ja_fact": q["what"],
                "en": tpl["en"],
                "ja": tpl["ja"],
                "mood": "struggle",
                "link": None,
            }
    if quicks:
        q = quicks[0]
        return {
            "source": "failures.jsonl(%s)" % q["id"],
            "ja_fact": q["what"],
            "en": GENERIC_NG["en"],
            "ja": GENERIC_NG["ja"],
            "mood": "struggle",
            "link": None,
        }

    ok_items, ng_items = collect_today_outbox(date)
    if ng_items:
        it = ng_items[0]
        cat, tpl = categorize(it["title"] + " " + it["result"])
        body = tpl if tpl else GENERIC_NG
        return {
            "source": "dispatch_outbox.jsonl(#%s)" % it["n"],
            "ja_fact": "%s — %s" % (it["title"], it["result"]),
            "en": body["en"],
            "ja": body["ja"],
            "mood": "struggle",
            "link": it["urls"][0] if it["urls"] else None,
        }
    if ok_items:
        it = ok_items[0]
        return {
            "source": "dispatch_outbox.jsonl(#%s)" % it["n"],
            "ja_fact": it["title"],
            "en": GENERIC_OK["en"],
            "ja": GENERIC_OK["ja"],
            "mood": "win",
            "link": it["urls"][0] if it["urls"] else None,
        }
    return {
        "source": None,
        "ja_fact": None,
        "en": QUIET_DAY["en"],
        "ja": QUIET_DAY["ja"],
        "mood": "quiet",
        "link": None,
    }


def build_page_html(date, topic):
    weekday_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
        datetime.datetime.strptime(date, "%Y-%m-%d").weekday()
    ]
    source_html = (
        '<p class="src">出典: <code>%s</code></p>' % esc(topic["source"])
        if topic["source"] else '<p class="src">出典: なし（今日は事実ベースのネタが見つからなかった日）</p>'
    )
    fact_html = (
        '<details><summary>元の事実（日本語・加工前）</summary><p>%s</p></details>' % esc(topic["ja_fact"])
        if topic["ja_fact"] else ""
    )
    link_html = (
        '<p><a href="%s" target="_blank" rel="noopener">関連ページ（スクショの代わりにこれを貼る）</a></p>' % esc(topic["link"])
        if topic["link"] else '<p class="muted">スクショ・関連リンク: なし</p>'
    )
    draft_path = os.path.join(DRAFT_DIR, "%s.json" % date)
    draft_rel = os.path.relpath(draft_path, REPO)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>Concierge Diary {date} — 投稿前プレビュー（未投稿）</title>
<style>
  :root{{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--ao:#3a5f7a;}}
  *{{box-sizing:border-box;}}
  body{{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 16px calc(env(safe-area-inset-bottom) + 40px);
    background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;
    font-size:16px;line-height:1.7;max-width:720px;margin-left:auto;margin-right:auto;}}
  a{{color:var(--ao);}}
  .badge{{display:inline-block;background:#c4483a;color:#fff;border-radius:999px;padding:4px 14px;font-size:0.78rem;margin-bottom:16px;}}
  h1{{font-size:1.25rem;margin:0 0 6px;}}
  .date{{color:var(--sub);font-size:0.85rem;margin-bottom:20px;}}
  .post{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:18px;}}
  .en{{font-size:1.08rem;margin:0 0 10px;}}
  .ja{{color:var(--sub);font-size:0.92rem;margin:0;}}
  .src, .muted{{color:var(--sub);font-size:0.8rem;}}
  .voice, .shot{{background:#fff;border:1px dashed var(--line);border-radius:10px;padding:10px 14px;margin-bottom:10px;font-size:0.88rem;}}
  details summary{{cursor:pointer;color:var(--ao);font-size:0.85rem;}}
  footer{{color:var(--sub);font-size:0.76rem;margin-top:30px;line-height:1.6;}}
  code{{background:#eee;border-radius:4px;padding:1px 5px;}}
  nav{{margin-top:20px;font-size:0.85rem;}}
</style>
</head>
<body>
<div class="badge">⚠️ 未投稿・投稿前プレビュー（942番：投稿前に必ず全部見せる）</div>
<h1>Concierge Diary — {date} ({weekday})</h1>
<div class="date"><a href="./">一覧へ</a></div>

<div class="post">
  <p class="en">{en}</p>
  <p class="ja">（日本語）{ja}</p>
</div>

{source}
{fact}

<div class="voice">🔇 音声（10秒・声=アイリス）: 未生成。理由＝課金API（fal等）のため、本数×単価の見積もりを先に出して承認を取る必要がある（まだ未承認）。</div>
<div class="shot">📷 スクショ: 未取得（ブラウザでのキャプチャはコスト・リスクが高いため、今回は下の関連リンクで代替）。</div>
{link}

<footer>
  機械生成（status/failures.jsonl・status/dispatch_outbox.jsonl から当日分を自動抽出。作り話はしていない）。<br>
  下書き（Buffer予約投稿用・未投稿）: <code>{draft}</code><br>
  生成: {generated}
</footer>
<nav><a href="./">← 一覧へ戻る</a></nav>
</body>
</html>
""".format(
        date=esc(date), weekday=weekday_en, en=esc(topic["en"]), ja=esc(topic["ja"]),
        source=source_html, fact=fact_html, link=link_html, draft=esc(draft_rel),
        generated=esc(datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")),
    )


def build_index_html():
    files = sorted(glob.glob(os.path.join(DIARY_DIR, "20*.html")), reverse=True)
    dates = [os.path.splitext(os.path.basename(f))[0] for f in files]
    items = "\n".join(
        '<li><a href="%s.html">%s</a></li>' % (esc(d), esc(d)) for d in dates
    ) if dates else '<li class="empty">まだ日記がありません</li>'
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>Concierge Diary — index（未投稿プレビュー一覧）</title>
<style>
  body{margin:0;padding:24px 16px 60px;background:#f4efe4;color:#2a2a2a;
    font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;font-size:16px;line-height:1.7;
    max-width:720px;margin-left:auto;margin-right:auto;}
  a{color:#3a5f7a;text-decoration:none;}
  h1{font-size:1.2rem;}
  ul{list-style:none;margin:0;padding:0;}
  li{background:#fff;border:1px solid #e2dccd;border-radius:10px;padding:12px 16px;margin:0 0 8px;}
</style>
</head>
<body>
<h1>Concierge Diary（942番・投稿前プレビュー一覧・未投稿）</h1>
<ul>
%s
</ul>
</body>
</html>
""" % items


def write_draft_json(date, topic):
    os.makedirs(DRAFT_DIR, exist_ok=True)
    draft = {
        "date": date,
        "status": "preview_only_not_posted",
        "text_en": topic["en"],
        "text_ja": topic["ja"],
        "source": topic["source"],
        "link": topic["link"],
        "voice": None,
        "voice_note": "未生成（課金API見積もり未承認）",
        "screenshot": None,
        "note": "942番：投稿前に必ず人の確認を通すこと。このJSONはBuffer予約投稿の下書きであり、まだ投稿していない。",
    }
    path = os.path.join(DRAFT_DIR, "%s.json" % date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return path


def _run(args, timeout=None):
    try:
        r = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout after %ss" % timeout
    except OSError as e:
        return -1, "", str(e)


def push_repo(date, retries=5, wait_sec=8):
    import time
    last_err = None
    paths = ["share/concierge-diary/", "status/concierge_diary_drafts/"]
    for attempt in range(1, retries + 1):
        rc, out, err = _run(["git", "add"] + paths)
        if rc != 0:
            last_err = "add失敗(試行%d): %s" % (attempt, (out + err).strip()[:300])
            print(last_err)
            time.sleep(wait_sec)
            continue
        diff_rc, _, _ = _run(["git", "diff", "--cached", "--quiet", "--"] + paths)
        if diff_rc != 0:
            rc, out, err = _run(["git", "commit", "-m", "concierge-diary: %s 投稿前プレビューを自動生成（942番）" % date])
            if rc != 0:
                last_err = "commit失敗(試行%d): %s" % (attempt, (out + err).strip()[:300])
                print(last_err)
                time.sleep(wait_sec)
                continue
        ahead_rc, ahead_out, _ = _run(["git", "rev-list", "--count", "HEAD", "^origin/main"])
        ahead = ahead_out.strip()
        if ahead_rc != 0 or ahead in ("", "0"):
            print("git: pushすべき新規コミットなし")
            return True
        rc, out, err = _run(["git", "push", "origin", "main"], timeout=60)
        if rc == 0:
            print("git push 成功")
            return True
        last_err = "push失敗(試行%d): %s" % (attempt, (out + err).strip()[:300])
        print(last_err)
        time.sleep(wait_sec)
    print("git操作: %d回試して失敗。最終エラー: %s" % (retries, last_err))
    return False


def generate_one(date):
    topic = pick_topic(date)
    os.makedirs(DIARY_DIR, exist_ok=True)
    page = build_page_html(date, topic)
    out_path = os.path.join(DIARY_DIR, "%s.html" % date)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    draft_path = write_draft_json(date, topic)
    print("書きました: %s" % out_path)
    print("書きました: %s" % draft_path)
    return out_path, topic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD（省略時は今日・Asia/Tokyo）")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    date = args.date or today

    out_path, topic = generate_one(date)

    index_html = build_index_html()
    with open(os.path.join(DIARY_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("書きました: %s" % os.path.join(DIARY_DIR, "index.html"))

    if args.push:
        push_repo(date)

    print("PAGE_URL: %s" % (PAGES_BASE + "share/concierge-diary/%s.html" % date))


if __name__ == "__main__":
    main()
