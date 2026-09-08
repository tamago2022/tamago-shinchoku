#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
652番「閉じられないブラウザタブを『あとで見る棚』に逃がして、Braveを軽くする」

たまごさんの Brave（プロフィール「あなたの Brave」＝Default）のセッションファイルを
直接読み取り（Braveアプリには一切触れない・タブは開かない・osascriptのactivateも使わない）、
開いているタブ相当のURL一覧を status/later_tabs.json へ書き出す。

読み取り方法:
  ~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Sessions/Session_*
  の最新ファイル（SNSSバイナリ）を生バイト走査し、http(s) URL文字列を正規表現で抽出する。
  完全なSNSSパーサ（pickle構造の厳密デコード）ではなく、URL文字列がpickle内でも
  ほぼ連続バイトのまま格納される性質を使った実用的な抽出（フォレンジックで一般的な手法）。
  広告・フォント等のインフラドメイン、画像/CSS/JS等の非ページURLは除外し、
  重複はURL単位で除去する（同一URLの最後の出現＝より新しい状態を採用）。

  History（閲覧履歴）DBが存在すれば、URLごとの最終アクセス時刻を突き合わせて表示する
  （無ければセッションファイルの更新時刻を使う）。

  ChatGPT/X/Grok/Googleドライブ等ログインが要るサービスは、ページを取得せず
  （ログイン画面のタイトルを誤って出さないため）URL構造から読める日本語ラベルを生成する。
  それ以外の公開ページは、タイトルタグ・og:imageを軽量取得する（各ドメイン最大4秒・並列）。

実行方法: python3 tools/later_tabs_snapshot.py [--push]
  --push を付けると、status/later_tabs.json の差分を git add/commit/push まで行う。
"""
import argparse
import concurrent.futures
import datetime
import glob
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse, urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_PATH = os.path.join(REPO, "status", "later_tabs.json")

BRAVE_ROOT = os.path.expanduser(
    "~/Library/Application Support/BraveSoftware/Brave-Browser"
)
DEFAULT_PROFILE = os.path.join(BRAVE_ROOT, "Default")

EXCLUDE_DOMAINS = {
    "fonts.gstatic.com", "fonts.googleapis.com", "ajax.googleapis.com",
    "www.gstatic.com", "gstatic.com", "doubleclick.net", "googlesyndication.com",
    "google-analytics.com", "googletagmanager.com", "safebrowsing.googleapis.com",
    "clients2.google.com", "clients4.google.com", "update.googleapis.com",
    "accounts.google.com", "optimizationguide-pa.googleapis.com", "apis.google.com",
    "content-autofill.googleapis.com", "csp.withgoogle.com", "sb-ssl.google.com",
    "brave.com", "laptop-updates.brave.com", "variations.brave.com",
    "static1.brave.com", "safebrowsing.brave.com", "component-updater.brave.com",
    "go-updater.brave.com", "crxdownload.brave.com", "segment.io", "api.segment.io",
    "cdn.segment.com", "sentry.io", "browser.sentry-cdn.com",
    "lh3.googleusercontent.com", "yt3.ggpht.com", "play.google.com",
    "googlevideo.com",
}
EXCLUDE_SUFFIXES = (".googlevideo.com", ".grok-sandbox.com", ".googleapis.com")
EXT_EXCLUDE = re.compile(r"\.(png|jpg|jpeg|gif|svg|ico|css|woff2?|ttf|map|json|js)(\?|$)", re.I)

# ログインが要る＝ページ取得をせずURL構造からラベルを作るドメイン
AUTH_WALL = {
    "chatgpt.com": "C", "chat.openai.com": "C",
    "x.com": "X", "twitter.com": "X", "accounts.x.ai": "X",
    "grok.com": "G",
    "drive.google.com": "D", "docs.google.com": "D", "sheets.google.com": "D",
    "slides.google.com": "D", "mail.google.com": "D", "calendar.google.com": "D",
    "gemini.google.com": "G", "studio.workspace.google.com": "W",
    "contacts.google.com": "D", "notion.so": "N", "www.notion.so": "N",
}
TILE_COLORS = {
    "C": "#10a37f", "X": "#000000", "G": "#8b5cf6", "D": "#4285f4",
    "W": "#4285f4", "N": "#ffffff",
}


def log(msg):
    print("[later_tabs] %s" % msg)


def find_latest_session_file():
    sess_dir = os.path.join(DEFAULT_PROFILE, "Sessions")
    files = glob.glob(os.path.join(sess_dir, "Session_*"))
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p))
    return files[-1]


def extract_raw_urls(path):
    with open(path, "rb") as f:
        data = f.read()
    matches = re.findall(rb"https?://[!-~]{8,2000}", data)
    return [clean_url(m.decode("utf-8", "ignore")) for m in matches]


_NOISE_TAIL = re.compile(r"[()+<>{}\[\]|^~\"'`,]+$")
_DIGIT_PLUS_LETTER = re.compile(r"^(\d{6,})[a-zA-Z]$")


def clean_url(u):
    """SNSSバイナリの生バイト走査で拾った末尾1〜数文字のノイズを削る。

    pickleの次フィールド（4バイト整数等）の先頭1バイトがたまたま印字可能な
    ASCIIになり、regexがそれをURLの一部として飲み込んでしまうケースがある
    （例: ツイートID末尾に1文字だけ余計な英字が付く）。厳密なpickleパースは
    せず、実害の大きい「リンクが壊れる」ケースだけを狙い撃ちで直す。
    """
    u = u.rstrip("\\")
    u = _NOISE_TAIL.sub("", u)
    parts = u.rsplit("/", 1)
    if len(parts) == 2:
        m = _DIGIT_PLUS_LETTER.match(parts[1])
        if m:
            u = parts[0] + "/" + m.group(1)
    else:
        m = _DIGIT_PLUS_LETTER.match(u)
    return u


_YT_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
_YT_NOISE_PATH = re.compile(r"^/(results|signin_prompt|redirect)?$|^/embed/?$")


def is_useless_youtube(host, path):
    if host not in _YT_HOSTS:
        return False
    if path in ("", "/"):
        return True
    if path.startswith("/results") or path.startswith("/signin_prompt") or path.startswith("/redirect"):
        return True
    if path in ("/embed", "/embed/"):
        return True
    return False


def filter_and_dedupe(urls):
    kept_order = {}
    for i, u in enumerate(urls):
        try:
            p = urlparse(u)
        except Exception:
            continue
        if not p.netloc or p.scheme not in ("http", "https"):
            continue
        host = p.netloc.lower()
        if is_useless_youtube(host, p.path):
            continue
        if host in EXCLUDE_DOMAINS:
            continue
        if any(host.endswith(suf) for suf in EXCLUDE_SUFFIXES):
            continue
        if EXT_EXCLUDE.search(p.path):
            continue
        if len(u) > 500:
            continue
        kept_order[u] = i  # 後勝ち＝より新しい出現を採用
    return sorted(kept_order.keys(), key=lambda u: kept_order[u])


def load_history_times():
    """History sqlite（動いているBraveがロックしている可能性があるので一旦コピーして読む）"""
    src = os.path.join(DEFAULT_PROFILE, "History")
    if not os.path.exists(src):
        return {}
    times = {}
    with tempfile.TemporaryDirectory() as td:
        dst = os.path.join(td, "History.copy")
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            log("History コピー失敗（無視して続行）: %s" % e)
            return {}
        try:
            con = sqlite3.connect("file:%s?mode=ro" % dst, uri=True)
            cur = con.cursor()
            cur.execute("SELECT url, last_visit_time FROM urls")
            for url, wk_ts in cur.fetchall():
                if not wk_ts:
                    continue
                # Chromium時刻＝1601-01-01からのマイクロ秒
                try:
                    dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=wk_ts)
                    times[url] = dt.isoformat()
                except Exception:
                    pass
            con.close()
        except Exception as e:
            log("History 読み取り失敗（無視して続行）: %s" % e)
    return times


def make_tile_thumb(letter, color):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">'
        '<rect width="320" height="180" fill="%s"/>'
        '<text x="160" y="112" font-size="90" font-family="sans-serif" '
        'fill="%s" text-anchor="middle" font-weight="bold">%s</text></svg>'
    ) % (color, "#ffffff" if color != "#ffffff" else "#333333", html.escape(letter))
    import base64
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64,%s" % b64


def label_for_authwall(url, host):
    p = urlparse(url)
    path = p.path
    if host in ("chatgpt.com", "chat.openai.com"):
        if "/c/" in path:
            return "ChatGPT の会話（続き）"
        if "/g/" in path:
            return "ChatGPT プロジェクト"
        return "ChatGPT"
    if host in ("x.com", "twitter.com"):
        parts = [s for s in path.split("/") if s]
        if len(parts) >= 3 and parts[1] == "status":
            return "X: @%s の投稿" % parts[0]
        if len(parts) == 1:
            return "X: @%s のプロフィール" % parts[0]
        return "X (Twitter)"
    if host == "accounts.x.ai":
        return "x.ai アカウント"
    if host == "grok.com":
        return "Grok の会話（続き）"
    if host == "drive.google.com":
        return "Google ドライブのファイル"
    if host == "docs.google.com":
        return "Google ドキュメント"
    if host == "sheets.google.com":
        return "Google スプレッドシート"
    if host == "slides.google.com":
        return "Google スライド"
    if host == "mail.google.com":
        return "Gmail"
    if host == "calendar.google.com":
        return "Google カレンダー"
    if host == "gemini.google.com":
        return "Gemini の会話（続き）"
    if host == "studio.workspace.google.com":
        return "Google Workspace Studio"
    if host == "contacts.google.com":
        return "Google 連絡先"
    if host in ("notion.so", "www.notion.so"):
        return "Notion ページ"
    return host


def fetch_title_and_image(url, timeout=4):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200000)
        text = raw.decode("utf-8", "ignore")
    except Exception:
        return None, None
    title = None
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if m:
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:150]
    img = None
    m2 = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        text, re.I,
    )
    if not m2:
        m2 = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            text, re.I,
        )
    if m2:
        img = urljoin(url, m2.group(1))
    return title, img


def normalize_youtube_url(url):
    """oEmbedが受け付けやすい watch?v=/youtu.be 形式へ寄せる（embed/shorts対応）"""
    p = urlparse(url)
    m = re.search(r"/(?:embed|shorts)/([A-Za-z0-9_-]{6,})", p.path)
    if m:
        return "https://www.youtube.com/watch?v=%s" % m.group(1)
    return url


def youtube_oembed(url):
    lookup_url = normalize_youtube_url(url)
    oembed = "https://www.youtube.com/oembed?url=%s&format=json" % urllib.request.quote(lookup_url, safe="")
    try:
        with urllib.request.urlopen(oembed, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("title"), data.get("thumbnail_url"), data.get("author_name")
    except Exception:
        return None, None, None


def brave_process_stats():
    try:
        out = subprocess.run(["ps", "-axo", "rss,comm"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {"process_count": None, "rss_mb": None}
    total_rss_kb = 0
    count = 0
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        try:
            rss_str, comm = line.split(None, 1)
            rss = int(rss_str)
        except Exception:
            continue
        if "Brave Browser" in comm:
            total_rss_kb += rss
            count += 1
    return {"process_count": count, "rss_mb": round(total_rss_kb / 1024, 1)}


def build_entries(urls, history_times, file_mtime_iso):
    entries = []
    for u in urls:
        p = urlparse(u)
        host = p.netloc.lower()
        entries.append({
            "url": u,
            "host": host,
            "last_seen": history_times.get(u, file_mtime_iso),
        })
    return entries


def enrich(entries):
    def work(e):
        host = e["host"]
        url = e["url"]
        if host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
            title, thumb, author = youtube_oembed(url)
            e["title"] = title or "YouTube 動画"
            e["thumb"] = thumb or make_tile_thumb("▶", "#ff0000")
            e["group"] = "YouTube"
            e["sub"] = author or ""
        elif host in AUTH_WALL:
            e["title"] = label_for_authwall(url, host)
            letter = AUTH_WALL[host]
            e["thumb"] = make_tile_thumb(letter, TILE_COLORS.get(letter, "#555555"))
            e["group"] = {"C": "ChatGPT", "X": "X (Twitter)", "G": "Grok / Gemini",
                          "D": "Google", "W": "Google", "N": "Notion"}.get(letter, host)
            e["sub"] = host
        else:
            title, img = fetch_title_and_image(url)
            e["title"] = title or host
            e["thumb"] = img or make_tile_thumb((host[:1] or "?").upper(), "#3b4252")
            e["group"] = "その他のページ"
            e["sub"] = host
        return e

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(work, entries))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    session_file = find_latest_session_file()
    if not session_file:
        log("Braveのセッションファイルが見つかりませんでした")
        payload = {
            "generated_at": datetime.datetime.now().isoformat(),
            "error": "session_file_not_found",
            "entries": [],
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    file_mtime_iso = datetime.datetime.fromtimestamp(os.path.getmtime(session_file)).isoformat()
    raw_urls = extract_raw_urls(session_file)
    filtered = filter_and_dedupe(raw_urls)
    history_times = load_history_times()
    entries = build_entries(filtered, history_times, file_mtime_iso)
    entries = enrich(entries)
    # 最近アクセス順に並べる
    entries.sort(key=lambda e: e.get("last_seen") or "", reverse=True)

    stats = brave_process_stats()

    payload = {
        "generated_at": datetime.datetime.now().isoformat(),
        "session_file": os.path.basename(session_file),
        "session_file_updated": file_mtime_iso,
        "raw_url_count": len(raw_urls),
        "entry_count": len(entries),
        "brave_process_count": stats["process_count"],
        "brave_rss_mb": stats["rss_mb"],
        "entries": entries,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log("書きました: %s (%d件, Braveプロセス%s個 / %sMB)" % (
        OUT_PATH, len(entries), stats["process_count"], stats["rss_mb"]))

    if args.push:
        push_repo()


def push_repo():
    try:
        subprocess.run(["git", "add", "status/later_tabs.json"], cwd=REPO, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO)
        if diff.returncode == 0:
            log("git: 差分なし（コミット省略）")
            return
        subprocess.run(
            ["git", "commit", "-m", "later_tabs: あとで見る棚を自動更新（652番）"],
            cwd=REPO, check=True,
        )
        push = subprocess.run(["git", "push", "origin", "main"], cwd=REPO, capture_output=True, text=True)
        if push.returncode == 0:
            log("git push 成功")
        else:
            log("git push 失敗: %s" % push.stderr.strip()[:300])
    except subprocess.CalledProcessError as e:
        log("git操作失敗: %s" % e)


if __name__ == "__main__":
    main()
