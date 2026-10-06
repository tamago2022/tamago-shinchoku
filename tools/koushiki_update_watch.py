#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""939番：公式のアップデートを1日1回だけ自分で拾いに行く（2026-09-18新設）。

たまごさんの言葉（そのまま）：
「アップデートとかも自分で情報を取りに行ってね。毎日1回でもいいから、公式が発表している
ものもあるだろうし、いいもの、効率化するものはどんどん取り入れていって。」

設計の縛り（たまごさん指定）：
  - **公式の発表だけ。**SEOまとめ記事・SNSの伝聞は見に行かない（URLの許可リストで機械的に縛る）。
  - **効率化に効くものだけ**拾う（EFFICIENCY_KEYWORDSに当たった行だけ残す）。
  - **定期タスク（scheduled task）は作らない。**心臓（heartbeat.sh）が毎周回で呼ぶ
    tools/daily_ingest_scheduler.py に相乗りし、実際に外へ出るのは1日1回だけに間引く
    （check_anthropic_reply.py と同じ間引きパターン）。
  - **失敗しても他を止めない。**1つの取得元が落ちてもそこだけ諦めて先へ進む。

出す先：status/koushiki_updates.json（進捗表がトグルの中に1行ずつ出す。最新40件）
  {"updatedAt": ISO, "items": [{"date","source","title","url"}], "sourceErrors": [...]}

手で今すぐ動かしたいとき：
  python3 tools/koushiki_update_watch.py --now        # 間引きを無視して即取得
  python3 tools/koushiki_update_watch.py --dry-run    # 取るだけで書き込まない
"""
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    from urllib2 import Request, urlopen  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 公開先は status/public/ 配下でなければならない（.gitignoreが status/* を除外し、
# status/public/ だけを明示的に例外化している＝890番・896番の巻き戻り対策）。
# status/直下に書くとgitに乗らず、進捗表（GitHub Pages）から永久に読めない。
OUT = os.path.join(ROOT, "status", "public", "koushiki_updates.json")
MARKER = os.path.join(ROOT, "status", ".koushiki_update_last")
JST = timezone(timedelta(hours=9))
KEEP = 40
TIMEOUT = 25
UA = "tamago-shinchoku/1.0 (koushiki_update_watch)"

# ── 公式ドメインの許可リスト。ここに無いホストは絶対に見に行かない ──
#    「公式が発表しているものだけ」を人の記憶ではなく機械で守るための壁。
ALLOWED_HOSTS = (
    "code.claude.com",
    "platform.claude.com",
    "docs.claude.com",
    "support.claude.com",
    "www.anthropic.com",
    "anthropic.com",
    "openai.com",
    "help.openai.com",
    "docs.x.ai",
    "x.ai",
    "docs.lovable.dev",
    "lovable.dev",
    "docs.devin.ai",
    "devin.ai",
)

# 取得元。parserは下のparse_*の名前。落ちてもよい前提で並べる。
SOURCES = [
    # Claude Codeの週刊ダイジェスト＝「効率化に効くもの」が一番濃い公式一次情報
    {"source": "Claude Code", "url": "https://code.claude.com/docs/en/whats-new/index.md",
     "base": "https://code.claude.com", "parser": "mdx_update"},
    # API・Console（料金やキャッシュ＝お金と速さに直結する）
    {"source": "Claude API", "url": "https://platform.claude.com/docs/en/release-notes/overview.md",
     "base": "https://platform.claude.com", "parser": "dated_bullets"},
    # Claudeアプリ本体（Cowork・Dispatchの土台）
    {"source": "Claudeアプリ", "url": "https://support.claude.com/en/articles/12138966-release-notes",
     "base": "https://support.claude.com", "parser": "html_dated"},
    {"source": "OpenAI", "url": "https://help.openai.com/en/collections/9689435-release-notes",
     "base": "https://help.openai.com", "parser": "html_dated"},
    {"source": "xAI", "url": "https://docs.x.ai/docs/changelog",
     "base": "https://docs.x.ai", "parser": "html_dated"},
    {"source": "Lovable", "url": "https://docs.lovable.dev/changelog",
     "base": "https://docs.lovable.dev", "parser": "html_dated"},
    {"source": "Devin", "url": "https://docs.devin.ai/release-notes/overview",
     "base": "https://docs.devin.ai", "parser": "html_dated"},
]

# 「効率化に効くもの」の判定語。ここに1つも当たらない行は捨てる。
# （新機能の全部を並べると読まれないので、たまごさんの工場が速く・安く・並列に
#   なる方向の語だけに絞る）
EFFICIENCY_KEYWORDS = [
    "parallel", "concurren", "background", "faster", "speed", "latency",
    "cache", "caching", "cost", "cheaper", "price", "pricing", "free",
    "batch", "automat", "schedul", "routine", "cron",
    "skill", "plugin", "hook", "subagent", "agent team", "agent view",
    "project", "thread", "cloud session", "remote", "mobile", "phone",
    "mcp", "connector", "sandbox", "permission", "auto mode",
    "limit", "context window", "compact", "effort", "model",
    "artifact", "publish", "deploy", "credit", "usage",
]

NOISE = ("bug fix", "typo", "security advisory")


def log(msg):
    sys.stderr.write("[koushiki] %s\n" % msg)


def host_allowed(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return bool(m) and m.group(1).lower() in ALLOWED_HOSTS


def fetch(url):
    if not host_allowed(url):
        raise ValueError("公式の許可リストに無いURLなので見に行きません: %s" % url)
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/markdown, text/html, */*"})
    raw = urlopen(req, timeout=TIMEOUT).read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw


def strip_md(s):
    """Markdown/HTMLの飾りを落として1行の日本語に混ぜられる素の文にする。"""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", s)
    s = s.replace("**", "").replace("`", "").replace("→", "")
    s = re.sub(r"&[a-z]+;", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ·-—")


def is_efficient(text):
    t = (text or "").lower()
    if not t:
        return False
    if any(n in t for n in NOISE) and len(t) < 80:
        return False
    return any(k in t for k in EFFICIENCY_KEYWORDS)


def abs_url(base, href):
    if not href:
        return base
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href


def cut(s, n=160):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def readable_url(u):
    """取得用の .md 付きURLを、たまごさんがタップして読める人間用URLに戻す。"""
    u = u or ""
    if u.endswith(".md"):
        u = u[:-3]
    if u.endswith("/index"):
        u = u[: -len("index")]
    return u


# ── parser群。どれも「日付・題名・URL」の3つを取れれば十分 ──

def parse_mdx_update(text, src):
    """<Update label="Week 37" description="September 7–11, 2026"> ... </Update> の形。"""
    out = []
    for m in re.finditer(
        r'<Update\s+label="([^"]*)"\s+description="([^"]*)"[^>]*>(.*?)</Update>',
        text, re.S,
    ):
        label, desc, body = m.group(1), m.group(2), m.group(3)
        link = re.search(r"\]\((/[^\)\s]+)\)", body)
        url = abs_url(src["base"], link.group(1)) if link else src["url"]
        for line in [l.strip() for l in body.split("\n") if l.strip()]:
            if line.startswith("[") or line.startswith("<"):
                continue
            plain = strip_md(line)
            if len(plain) < 20 or not is_efficient(plain):
                continue
            out.append({"date": desc, "source": "%s %s" % (src["source"], label),
                        "title": cut(plain), "url": url})
    return out


def parse_dated_bullets(text, src):
    """### September 18, 2026 の見出し＋ * 箇条書き の形（Claude APIのリリースノート）。"""
    out = []
    cur = None
    for line in text.split("\n"):
        h = re.match(r"^#{2,4}\s+([A-Z][a-z]+ \d{1,2},? \d{4})\s*$", line.strip())
        if h:
            cur = h.group(1)
            continue
        if cur and re.match(r"^\s*[\*\-]\s+", line):
            plain = strip_md(re.sub(r"^\s*[\*\-]\s+", "", line))
            if len(plain) < 20 or not is_efficient(plain):
                continue
            out.append({"date": cur, "source": src["source"],
                        "title": cut(plain), "url": src["url"]})
    return out


def parse_html_dated(text, src):
    """素のHTML用の保険。日付らしい文字列の近くの見出し文字列を拾うだけ。

    各社のページ構造は前触れなく変わるので、**構造に依存しない**やり方にしてある
    （見出しタグの中身を全部拾って、効率化の語に当たったものだけ残す）。
    取れなかったらその取得元だけ0件になる＝他を止めない。
    """
    out = []
    date = None
    dm = re.search(r"([A-Z][a-z]+ \d{1,2},? \d{4})", text)
    if dm:
        date = dm.group(1)
    seen = set()
    for m in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", text, re.S | re.I):
        plain = strip_md(m.group(1))
        if len(plain) < 15 or len(plain) > 200:
            continue
        if not is_efficient(plain) or plain in seen:
            continue
        seen.add(plain)
        out.append({"date": date or "", "source": src["source"],
                    "title": cut(plain), "url": src["url"]})
        if len(out) >= 8:
            break
    return out


PARSERS = {
    "mdx_update": parse_mdx_update,
    "dated_bullets": parse_dated_bullets,
    "html_dated": parse_html_dated,
}


def collect():
    items, errors = [], []
    for src in SOURCES:
        try:
            text = fetch(src["url"])
            got = PARSERS[src["parser"]](text, src)
            items.extend(got[:8])  # 1取得元あたり最大8件（進捗表を埋めないため）
        except Exception as e:
            errors.append({"source": src["source"], "error": "%s: %s" % (type(e).__name__, e)})
    # 同じ題名の重複を落とす
    uniq, seen = [], set()
    for it in items:
        key = it.get("title", "")[:60]
        if key in seen:
            continue
        seen.add(key)
        it["url"] = readable_url(it.get("url"))
        uniq.append(it)
    return uniq, errors


def already_ran_today(today):
    try:
        return io.open(MARKER, encoding="utf-8").read().strip() == today
    except Exception:
        return False


def main(argv):
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    force = "--now" in argv
    dry = "--dry-run" in argv

    if not force and not dry and already_ran_today(today):
        return 0

    items, errors = collect()

    if dry:
        print(json.dumps({"items": items, "sourceErrors": errors},
                         ensure_ascii=False, indent=2))
        return 0

    # 前回の分と混ぜて、新しいものを上に。最新KEEP件だけ残す。
    old = []
    try:
        old = (json.load(io.open(OUT, encoding="utf-8")) or {}).get("items") or []
    except Exception:
        old = []
    seen = set(x.get("title", "")[:60] for x in items)
    merged = items + [x for x in old if x.get("title", "")[:60] not in seen]

    payload = {
        "updatedAt": now.isoformat(),
        "note": "公式の発表だけを1日1回見に行って、効率化に効くものだけ残した一覧（tools/koushiki_update_watch.py）",
        "items": merged[:KEEP],
        "sourceErrors": errors,
    }
    try:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        io.open(OUT, "w", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        io.open(MARKER, "w", encoding="utf-8").write(today)
    except Exception as e:
        log("書き込み失敗: %s" % e)
        return 1
    log("%d件（新規%d件・取得失敗%d件）" % (len(payload["items"]), len(items), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
