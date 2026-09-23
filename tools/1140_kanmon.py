#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1140番【門・仕入れの入口】完成していないものは棚に入れない。

たまごさん（2026-09-25）:
  「二度と増やさない。仕入れの入口に同じ検査を門として置く。満たさないものは棚に入らない。」
  「弾いた数を毎回ログに出す。弾き0が続いたら門が効いていない＝赤。」

■ 見るもの（＝表に出す条件と同じ4つ。判定の言葉も src/lib/kansei.ts と揃える）
  ① 再生できる動画が1本以上ある  ← ★oEmbedで**実測**する。「IDが入っている」は証拠にならない
  ② サムネイルが出せる           ← ①と同じ根（サムネは再生できるIDから作る）
  ③ 曲名とアーティスト名がある
  ④ コピーがある（空・TODO・仮 は不可）

  1つでも欠けたら棚に入れない。理由を1行で返す。

■ 回線が無い場所で呼ばれたとき
  実測に出られない（サンドボックスからは youtube.com → 000）ときは **通さない**。
  「たぶん生きている」で入れない。取れなければ入れない。

■ 弾いた数のログ
  status/1140_kanmon.jsonl        … 1件1行（通した／弾いた・理由）
  python3 tools/1140_kanmon.py --tally   … 直近の通過/弾きの数を出す
  ★何日も弾き0が続いたら、門を通っていない（呼ばれていない）疑い＝赤。
"""
from __future__ import annotations
import io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "1140_kanmon.jsonl")

YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
KARIOKI = re.compile(r"^\s*(\?+|-+|未定|不明|仮|（仮）|\(仮\)|unknown|untitled|no title)\s*$", re.I)
PLACEHOLDER = re.compile(r"^(TODO|TBD|placeholder|ここにコピー|未設定|未記入|仮|coming soon|N/A)", re.I)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"


def playable(vid: str):
    """再生できるか実測する。戻り値: (True/False, 理由)"""
    if not vid or not YT_ID.match(vid or ""):
        return False, "動画IDの形がYouTubeのものではない（%r）" % (vid,)
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({
        "url": "https://www.youtube.com/watch?v=" + vid, "format": "json"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                    timeout=15) as r:
            json.loads(r.read().decode("utf-8", "ignore"))
        return True, ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return False, "YouTube側で再生できない（削除・非公開・埋め込み禁止／HTTP %d）" % e.code
        return False, "実測できなかった（HTTP %d）。証拠が取れないので入れない" % e.code
    except Exception as e:  # noqa: BLE001
        return False, "実測に出られなかった（%s）。証拠が取れないので入れない" % type(e).__name__


def judge(title="", artist="", youtube_id="", copy="", label=""):
    """通れば None。落ちたら理由を1行で返す。★ここが仕入れの唯一の門。"""
    why = None
    if not (title or "").strip() or KARIOKI.match(title or ""):
        why = "曲名が無い（または仮置き）"
    elif not (artist or "").strip() or KARIOKI.match(artist or ""):
        why = "アーティスト名が無い（または仮置き）"
    elif not (copy or "").strip() or PLACEHOLDER.match((copy or "").strip()):
        why = "コピーが無い（または書きかけ）"
    else:
        ok, reason = playable(youtube_id)
        if not ok:
            why = reason
    _log({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label, "title": title,
          "artist": artist, "youtubeId": youtube_id, "passed": why is None, "why": why})
    return why


def _log(row):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def tally(n=500):
    if not os.path.exists(LOG):
        print("まだ1件も通っていない＝門が呼ばれていない疑い（赤）")
        return 1
    rows = [json.loads(x) for x in io.open(LOG, encoding="utf-8") if x.strip()][-n:]
    ok = sum(1 for r in rows if r.get("passed"))
    ng = Counter(r.get("why") for r in rows if not r.get("passed"))
    print("直近%d件: 通した%d / 弾いた%d" % (len(rows), ok, sum(ng.values())))
    for why, c in ng.most_common():
        print("  %4d  %s" % (c, why))
    if sum(ng.values()) == 0:
        print("★弾き0。門が効いていない疑い＝赤。呼ばれているか確かめる。")
    return 0


if __name__ == "__main__":
    if "--tally" in sys.argv:
        sys.exit(tally())
    print(judge(title="テスト", artist="テスト", youtube_id="dQw4w9WgXcQ", copy="テスト用",
                label="selftest") or "通った")
