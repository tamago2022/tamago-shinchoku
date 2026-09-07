#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
朗読の道具（512番）: share/podcast/audio/ に置いた音声から
Apple Podcasts が読めるRSSフィード（share/podcast/feed.xml）を作る。

使い方（新しい音声を追加した時に毎回これを実行するだけ）:
    python3 tools/build_podcast_feed.py

音声ファイル名の形式: <番号>-<スラッグ>.m4a
title/pubDateは episodes.json（このスクリプトと同じフォルダ）に手で書く。
episodes.json に無いファイルは、ファイル名をそのままタイトルにして自動で載せる。
"""
import os
import json
import subprocess
from email.utils import formatdate
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PODCAST_DIR = os.path.join(REPO_ROOT, "share", "podcast")
AUDIO_DIR = os.path.join(PODCAST_DIR, "audio")
FEED_PATH = os.path.join(PODCAST_DIR, "feed.xml")
META_PATH = os.path.join(PODCAST_DIR, "episodes.json")
INDEX_PATH = os.path.join(PODCAST_DIR, "index.html")
INDEX_START = "<!-- EPISODES:START"
INDEX_END = "<!-- EPISODES:END -->"

SITE_BASE = "https://tamago2022.github.io/tamago-shinchoku"
FEED_URL = f"{SITE_BASE}/share/podcast/feed.xml"
IMAGE_URL = f"{SITE_BASE}/icon-512.png"


def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def audio_duration_seconds(path):
    try:
        out = subprocess.run(["afinfo", path], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            if "estimated duration" in line:
                return float(line.split(":")[1].strip().split(" ")[0])
    except Exception:
        pass
    return None


def fmt_duration(sec):
    if sec is None:
        return "0:00"
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def main():
    meta = load_meta()
    files = sorted(f for f in os.listdir(AUDIO_DIR) if f.endswith(".m4a"))

    items_xml = []
    for fname in files:
        key = os.path.splitext(fname)[0]
        info = meta.get(key, {})
        title = info.get("title", key)
        desc = info.get("description", "たまごさんの円卓ノートを、寝ながら聴けるように音声化したもの。")
        path = os.path.join(AUDIO_DIR, fname)
        size = os.path.getsize(path)
        dur = audio_duration_seconds(path)
        mtime = os.path.getmtime(path)
        pub_date = formatdate(mtime, usegmt=True)
        url = f"{SITE_BASE}/share/podcast/audio/{fname}"
        guid = f"tamago-podcast-{key}"
        items_xml.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(desc)}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{escape(url)}" length="{size}" type="audio/mp4" />
      <guid isPermaLink="false">{escape(guid)}</guid>
      <itunes:duration>{fmt_duration(dur)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>たまごの寝る前ノート</title>
    <link>{SITE_BASE}/share/podcast/</link>
    <language>ja</language>
    <description>Obsidianの円卓ノートを、AivisSpeechで自然な声に読み上げた、寝ながら聴くための音声。たまごさん個人用。</description>
    <itunes:author>たまご商店街</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{IMAGE_URL}" />
    <image>
      <url>{IMAGE_URL}</url>
      <title>たまごの寝る前ノート</title>
      <link>{SITE_BASE}/share/podcast/</link>
    </image>
    <itunes:category text="Technology" />
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"書き出し完了: {FEED_PATH} ({len(files)}本)")
    print(f"RSS URL: {FEED_URL}")


if __name__ == "__main__":
    main()
