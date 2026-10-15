#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""後ろで流れている曲 → 曲ページの「関連」へ投稿を貼る係（2026-10-11 新設）。Mac で走らせる。

  python3 tools/oto_tsunagu.py --artist mj --song beat-it --url https://x.com/USER/status/ID \
      --title "…" --note "…" --by "たまごさん判断"
  python3 tools/oto_tsunagu.py --self-test

■ 決め
  ・書く先は本番DBの admin_song_overrides.related_videos（曲ページ「この曲の関連動画」の正本）。
    画面の［関連動画を追加］(adminAddRelatedVideo) と同じ形の1件を足すだけ。
  ・同じ投稿（投稿IDで判定）が既にあれば何もしない（冪等）。他の行・他の要素は触らない。
  ・admin_stock.detected_artist_id は**触らない**：そこは「動画に映っている本人」の欄で、
    BGMの歌手を入れると「本人が出ている」と嘘になる（watch.tsx 2026-08-02 の憲法）。
  ・入れた分は status/oto_hantei/tsunaida.jsonl に1行残す。--modoshi で自分が足した1件だけ外せる。
  ・自動判定（tools/oto_hantei.py）から呼ばれるときは by="自動判定" を入れる。
    自動判定の本番投入は、試験で誤判定0のときだけ（oto_hantei.py 側の関所）。
"""
import argparse
import importlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
JST = timezone(timedelta(hours=9))
LOG = os.path.join(REPO, "status", "oto_hantei", "tsunaida.jsonl")
HONBAN = "https://joy-relief-station.lovable.app"
RE_X = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", re.I)


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def lit(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\x00", "").replace("'", "''") + "'"


def canon(url):
    m = RE_X.match(url or "")
    if m:
        return "https://x.com/%s/status/%s" % (m.group(1), m.group(2)), r"(?:x|twitter)\.com/[^/?#]+/status/%s(?!\d)" % m.group(2)
    return url, re.escape(url)


def build_sql(artist, song, entry, rx):
    """1本のSQLで：行が無ければ作る → まだ同じ投稿が無ければ末尾に1件足す → 件数を返す。"""
    ej = json.dumps(entry, ensure_ascii=False)
    return (
        "with ins as (insert into admin_song_overrides (artist_id, song_id, related_videos) "
        "values (%(a)s, %(s)s, '[]'::jsonb) on conflict (artist_id, song_id) do nothing returning id), "
        "up as (update admin_song_overrides set related_videos = related_videos || jsonb_build_array(%(e)s::jsonb), "
        "updated_at = now() where artist_id = %(a)s and song_id = %(s)s and not exists ("
        "select 1 from jsonb_array_elements(related_videos) x where x->>'url' ~* %(rx)s) returning id) "
        "select (select count(*) from up) as added"
        % {"a": lit(artist), "s": lit(song), "e": lit(ej), "rx": lit(rx)})


def tsunagu(artist, song, url, title=None, note=None, thumb=None, by="", kiroku=None, db=None):
    ref, rx = canon(url)
    entry = {"url": ref, "kind": "other", "originArtistId": artist, "originSongId": song}
    if title:
        entry["title"] = title
    if note:
        entry["note"] = note
    if thumb:
        entry["thumbnailUrl"] = thumb
    if db is None:
        db = importlib.import_module("2210_tanaire").DB()
    # 行が無い場合、insert と update は同じ文の中では見えないので、2回目で確実に足す
    rows = db.q(build_sql(artist, song, entry, rx)) or []
    added = int((rows[0] or {}).get("added") or 0) if isinstance(rows, list) and rows else 0
    if not added:
        rows = db.q(build_sql(artist, song, entry, rx)) or []
        added = int((rows[0] or {}).get("added") or 0) if isinstance(rows, list) and rows else 0
    chk = db.q("select jsonb_array_length(related_videos) as n, exists(select 1 from jsonb_array_elements(related_videos) x "
               "where x->>'url' ~* %s) as aru from admin_song_overrides where artist_id = %s and song_id = %s"
               % (lit(rx), lit(artist), lit(song))) or []
    aru = bool(chk and chk[0].get("aru"))
    page = "%s/cover-guide?artist=%s&song=%s" % (HONBAN, artist, song)
    rec = {"at": now(), "artist": artist, "song": song, "url": ref, "added": added, "aru": aru,
           "by": by, "page": page, "kiroku": kiroku}
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def modoshi(artist, song, url, db=None):
    ref, rx = canon(url)
    if db is None:
        db = importlib.import_module("2210_tanaire").DB()
    db.q("update admin_song_overrides set related_videos = coalesce((select jsonb_agg(x) from jsonb_array_elements(related_videos) x "
         "where not (x->>'url' ~* %s)), '[]'::jsonb), updated_at = now() where artist_id = %s and song_id = %s"
         % (lit(rx), lit(artist), lit(song)))
    return {"modoshi": ref}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artist")
    ap.add_argument("--song")
    ap.add_argument("--url")
    ap.add_argument("--title")
    ap.add_argument("--note")
    ap.add_argument("--thumb")
    ap.add_argument("--by", default="")
    ap.add_argument("--modoshi", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        ref, rx = canon("https://twitter.com/G10Hung/status/2106882557421744248?s=20")
        sql = build_sql("mj", "beat-it", {"url": ref, "note": "it's"}, rx)
        ok = ref == "https://x.com/G10Hung/status/2106882557421744248" and "it''s" in sql and "on conflict" in sql
        ok = ok and re.search(rx, "https://x.com/g10hung/status/2106882557421744248") is not None
        ok = ok and re.search(rx, "https://x.com/a/status/21068825574217442489") is None
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    if not (a.artist and a.song and a.url):
        ap.print_help()
        return 2
    if a.modoshi:
        print(json.dumps(modoshi(a.artist, a.song, a.url), ensure_ascii=False))
        return 0
    print(json.dumps(tsunagu(a.artist, a.song, a.url, a.title, a.note, a.thumb, a.by), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
