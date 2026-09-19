#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
670番：YouTubeチャンネルの登録者数・再生回数を money.html の「YouTube」セクションに出す。

.env（リポジトリルート）の YOUTUBE_DATA_API_KEY を読み、YouTube Data API v3で
チャンネル統計・直近動画を取得する。キーが無い時はエラーにせず configured:false
で正直に書いて終わる（650番 money.html の既存方針＝「分からない数字は未登録と出す」と同じ）。

チャンネルID: UC9nX88C8m5GI6_p8ZROdeog（@OFFSafetoDisconnect の解決済みID・確認済み）

status/youtube_stats.json      : 最新値サマリ（money.htmlが直接読む）
status/youtube_stats_history.json : 実行日ごとの登録者数・再生回数の推移（伸びの表示に使う）

書き方の型（tmpファイル→os.replaceで原子的に置換、再実行しても安全）は
tools/fal_cost_ledger.py と同じにしてある。

使い方（CLI）:
  python3 tools/youtube_stats_sync.py
"""
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ENV_PATH = os.path.join(REPO, ".env")
STATS_JSON = os.path.join(REPO, "status", "youtube_stats.json")
HISTORY_JSON = os.path.join(REPO, "status", "youtube_stats_history.json")

CHANNEL_ID = "UC9nX88C8m5GI6_p8ZROdeog"
CHANNEL_URL = "https://www.youtube.com/@OFFSafetoDisconnect"
API_BASE = "https://www.googleapis.com/youtube/v3"


def _load_env(path):
    values = {}
    if not os.path.exists(path):
        return values
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def _load_json(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return default


def _atomic_save(path, data):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _now_iso():
    return datetime.now().astimezone().isoformat()


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "tamago-shinchoku/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    env = _load_env(ENV_PATH)
    api_key = (env.get("YOUTUBE_DATA_API_KEY") or "").strip()

    if not api_key:
        _atomic_save(STATS_JSON, {
            "configured": False,
            "updatedAt": _now_iso(),
            "note": "YOUTUBE_DATA_API_KEYが.envに未設定",
        })
        return

    try:
        ch_url = API_BASE + "/channels?" + urllib.parse.urlencode({
            "part": "statistics",
            "id": CHANNEL_ID,
            "key": api_key,
        })
        ch_data = _get_json(ch_url)
        items = ch_data.get("items") or []
        if not items:
            raise RuntimeError("チャンネル統計が取得できませんでした（items空）")
        stats = items[0].get("statistics") or {}
        subscriber_count = int(stats.get("subscriberCount", 0))
        view_count = int(stats.get("viewCount", 0))
        video_count = int(stats.get("videoCount", 0))

        search_url = API_BASE + "/search?" + urllib.parse.urlencode({
            "part": "snippet",
            "channelId": CHANNEL_ID,
            "order": "date",
            "maxResults": 5,
            "type": "video",
            "key": api_key,
        })
        search_data = _get_json(search_url)
        video_ids = [
            it["id"]["videoId"]
            for it in (search_data.get("items") or [])
            if it.get("id", {}).get("videoId")
        ]

        recent_videos = []
        if video_ids:
            videos_url = API_BASE + "/videos?" + urllib.parse.urlencode({
                "part": "statistics,snippet",
                "id": ",".join(video_ids),
                "key": api_key,
            })
            videos_data = _get_json(videos_url)
            for it in videos_data.get("items") or []:
                snippet = it.get("snippet") or {}
                vstats = it.get("statistics") or {}
                recent_videos.append({
                    "title": snippet.get("title") or "",
                    "viewCount": int(vstats.get("viewCount", 0)),
                    "publishedAt": snippet.get("publishedAt"),
                    "videoId": it.get("id"),
                })
    except Exception as e:
        _atomic_save(STATS_JSON, {
            "configured": True,
            "error": str(e),
            "updatedAt": _now_iso(),
        })
        return

    today = datetime.now().strftime("%Y-%m-%d")
    history = _load_json(HISTORY_JSON, {"history": []})
    entries = history.get("history") or []
    entries = [e for e in entries if e.get("date") != today]
    entries.append({
        "date": today,
        "subscriberCount": subscriber_count,
        "viewCount": view_count,
        "videoCount": video_count,
    })
    entries.sort(key=lambda e: e.get("date") or "")
    _atomic_save(HISTORY_JSON, {"history": entries})

    _atomic_save(STATS_JSON, {
        "configured": True,
        "updatedAt": _now_iso(),
        "channelUrl": CHANNEL_URL,
        "subscriberCount": subscriber_count,
        "viewCount": view_count,
        "videoCount": video_count,
        "recentVideos": recent_videos,
    })


if __name__ == "__main__":
    main()
