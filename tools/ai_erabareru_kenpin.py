#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIに選ばれる準備ができているかを、毎回同じ手順で測る機械検査（1197番）。

なぜ:
  客はもうサイトに来ない。AI が代わりに探して名前を挙げる。
  「たぶん大丈夫」で終わらせないために、6項目を数字にして赤/緑を出す。

使い方:
  python3 tools/ai_erabareru_kenpin.py
  python3 tools/ai_erabareru_kenpin.py --origin https://joy-relief-station.lovable.app

出るもの:
  status/public/ai_erabareru.json  … 全項目の生の数字
  標準出力に1行                     … 赤なら赤の理由だけ、緑なら緑

依存なし（標準ライブラリだけ）。JS は実行しない＝AI クローラーと同じ見え方を測る。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_ORIGIN = "https://joy-relief-station.lovable.app"

# 弾いていないことを確認したいクローラー（2026-09 時点の主要どころ）
AI_BOTS = [
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
    "Applebot-Extended",
    "CCBot",
    "Bytespider",
]

# 本文の量を見るページ（トップ＋案内所）
BODY_PAGES = ["/", "/cover-guide"]
MIN_BODY_CHARS = 1000

UA = "tamago-ai-erabareru-kenpin/1.0 (+https://tamago2022.github.io/tamago-shinchoku/)"
TIMEOUT = 20


def fetch(url: str) -> tuple[int, str]:
    """(status, text) を返す。落ちたら (0, 理由)。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read()
            charset = res.headers.get_content_charset() or "utf-8"
            return res.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001 — 落ちた理由をそのまま残す
        return 0, f"{type(e).__name__}: {e}"


def strip_html(html: str) -> str:
    """script/style/タグを落として、見える文字だけ残す。"""
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def blocked_bots(robots: str) -> list[str]:
    """robots.txt を読んで、名指しで全面禁止されている AI ボットを返す。"""
    blocked: list[str] = []
    current: list[str] = []
    for raw in robots.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            current = []
            continue
        if ":" not in line:
            continue
        key, val = (p.strip() for p in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            current.append(val)
        elif key == "disallow" and val == "/":
            for agent in current:
                for bot in AI_BOTS:
                    if agent.lower() in (bot.lower(), "*") and bot not in blocked:
                        blocked.append(bot)
    return blocked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default=os.environ.get("TAMAGO_ORIGIN", DEFAULT_ORIGIN))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    origin = args.origin.rstrip("/")

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = args.out or os.path.join(repo, "status", "public", "ai_erabareru.json")

    result: dict = {
        "measuredAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "origin": origin,
        "checks": {},
    }
    reds: list[str] = []

    # 1. llms.txt
    status, text = fetch(f"{origin}/llms.txt")
    result["checks"]["llms_txt"] = {"status": status, "bytes": len(text.encode("utf-8"))}
    if status != 200:
        reds.append(f"/llms.txt が {status}")

    # 2. robots.txt が AI クローラーを弾いていないか
    status, robots = fetch(f"{origin}/robots.txt")
    blocked = blocked_bots(robots) if status == 200 else []
    result["checks"]["robots_txt"] = {
        "status": status,
        "blockedAiBots": blocked,
        "hasSitemapLine": bool(re.search(r"(?im)^\s*sitemap\s*:", robots or "")),
    }
    if status != 200:
        reds.append(f"/robots.txt が {status}")
    elif blocked:
        reds.append("robots.txt が弾いている: " + "・".join(blocked))

    # 3. sitemap.xml
    status, sitemap = fetch(f"{origin}/sitemap.xml")
    result["checks"]["sitemap_xml"] = {
        "status": status,
        "urlCount": len(re.findall(r"<loc>", sitemap or "")),
    }
    if status != 200:
        reds.append(f"/sitemap.xml が {status}")

    # 4〜6. 代表ページ：構造化データ・本文量・title/description
    pages: dict[str, dict] = {}
    for path in BODY_PAGES:
        status, html = fetch(f"{origin}{path}")
        body = strip_html(html) if status == 200 else ""
        ld = re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html or "")
        ld_types: list[str] = []
        for chunk in ld:
            ld_types += re.findall(r'"@type"\s*:\s*"([^"]+)"', chunk)
        title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
        desc = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html or "")
        info = {
            "status": status,
            "bodyChars": len(body),
            "ldJsonBlocks": len(ld),
            "ldTypes": sorted(set(ld_types)),
            "title": (title.group(1).strip() if title else ""),
            "descriptionChars": len(desc.group(1).strip()) if desc else 0,
        }
        pages[path] = info
        if status != 200:
            reds.append(f"{path} が {status}")
            continue
        if info["bodyChars"] < MIN_BODY_CHARS:
            reds.append(f"{path} は JS なしで本文 {info['bodyChars']}字（{MIN_BODY_CHARS}字未満）")
        if info["ldJsonBlocks"] == 0:
            reds.append(f"{path} に構造化データが無い")
        if not info["title"]:
            reds.append(f"{path} の title が空")
        if info["descriptionChars"] == 0:
            reds.append(f"{path} の description が空")
    result["checks"]["pages"] = pages

    result["red"] = bool(reds)
    result["reasons"] = reds

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
        f.write("\n")

    if reds:
        print("赤｜AIに選ばれる準備：" + " ／ ".join(reds))
        return 1
    print("緑｜AIに選ばれる準備：6項目すべて通った（" + origin + "）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
