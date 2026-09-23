#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/kioku.py ── たまごさんの発言を自動で拾って台帳に入れる係。

━━ なぜ作ったか（2026-09-26・たまごさん原文）━━

  「俺に言われて動き出すのはもうダメだよ、30点。仕組みは作ってるの？」
  「俺がうるさく言うのは、もう仕組み化してほしいから。何回も言わせないで。
    何回も同じこと言うのってエネルギー使うから、それをやめたいから
    『早く仕組みにしてくれ』って言ってる。」
  「あなたたちすぐ忘れたりするからさ、忘れられない、もう逃げられない仕組みにしてよ。」

これまで宿題台帳（tools/shukudai.py）が拾っていたのは3か所だけ：
  queue.json / 引き継ぎ.md / dispatch_outbox.jsonl
**どれも「AIが書いた紙」。たまごさんが口で言ったことは、誰かが手で写さないと入らなかった。**
写し忘れた瞬間に消える＝「言ったのにやってない」の正体はここ。

★この係は、会話ログ（*.jsonl）を定期的に読んで、たまごさんの発言から
  「依頼らしき文」を機械で抜き出し、status/kioku/hatsugen.jsonl に貯める。
★同じことを何回言われたかを数える。**2回目を言わせた時点で赤。3回以上は最優先。**
★宿題台帳はここを4つ目の出どころとして読む（shukudai.harvest_kioku）。

━━ 守っていること ━━
  - AIを1回も呼ばない・外へ1回も出ない＝0円
  - 落ちても続きから。読んだ位置（byte offset）を status/kioku/.seen.json に残す
  - 何回走らせても同じ結果（冪等）。id は正規化した文から作る固定値
  - たまごさんのファイルを消さない・動かさない

使い方
    python3 tools/kioku.py              # 新しく増えた分だけ読んで貯める（心臓から）
    python3 tools/kioku.py --show       # 何回言われたかの多い順に人が読む形で
    python3 tools/kioku.py --self-test  # 自己試験（1バイトも書かない）
    python3 tools/kioku.py --rebuild    # 最初から読み直す（.seen.json を捨てる）
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DIR = os.path.join(ST, "kioku")
HATSUGEN = os.path.join(DIR, "hatsugen.jsonl")
SEEN = os.path.join(DIR, ".seen.json")
LOG = os.path.join(DIR, "kioku.log")

JST = datetime.timezone(datetime.timedelta(hours=9))

# 1回の実行で読む上限（心臓から2分おきに呼ばれても重くならない線）
MAX_BYTES_PER_RUN = 60 * 1024 * 1024
MAX_FILES_PER_RUN = 60

HOME = os.path.expanduser("~")

# 会話ログの置き場所。環境で場所が変わるので候補を全部見る。
LOG_GLOBS = [
    os.path.join(HOME, ".claude", "projects", "*", "*.jsonl"),
    os.path.join(HOME, "Library", "Application Support", "Claude",
                 "local-agent-mode-sessions", "*", "*", "*", "*.jsonl"),
    # Cowork/Dispatch の会話ログ。深さが環境で変わるので段を変えて全部見る。
    "/var/folders/*/*/T/claude-*/*/projects/session/*.jsonl",
    "/var/folders/*/*/T/claude-*/*/*/projects/session/*.jsonl",
    "/var/folders/*/*/T/claude-hostloop-plugins/*/*/projects/session/*.jsonl",
    "/var/folders/*/*/T/claude-hostloop-plugins/*/projects/session/*.jsonl",
    "/var/folders/*/*/T/claude-*/**/projects/session/*.jsonl",
    os.path.join(REPO, ".claude", "projects", "*", "*.jsonl"),
    os.path.join(os.path.dirname(REPO), ".claude", "projects", "*", "*.jsonl"),
]

# 環境で置き場所が変わるときの逃げ道（`:` 区切り）。
# 心臓から呼ぶときは要らない。場所が増えたらここに足さず、環境変数で足す。
if os.environ.get("KIOKU_LOG_GLOBS"):
    LOG_GLOBS = os.environ["KIOKU_LOG_GLOBS"].split(":") + LOG_GLOBS


def now():
    return datetime.datetime.now(JST)


def stamp():
    return now().strftime("%Y-%m-%d %H:%M")


_YOUBI = "月火水木金土日"


def ja_nichiji(dt):
    """2026-09-26(土) 07:35 の形。★分まで出す。"""
    return "%s(%s) %s" % (dt.strftime("%Y-%m-%d"), _YOUBI[dt.weekday()], dt.strftime("%H:%M"))


def iso_to_jst(s):
    """会話ログの timestamp（ISO8601・UTC）を日本時間の datetime に。読めなければ None。"""
    if not s:
        return None
    try:
        t = str(s).replace("Z", "+00:00")
        d = datetime.datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d.astimezone(JST)
    except Exception:
        return None


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def load_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ────────────────────────────────────────────── 文の見分け

# 依頼・指摘・ダメ出しの形。**これに当たる文だけを拾う。**
_IRAI = re.compile(
    r"(してほしい|して欲しい|してくれ|してね|してよ|してください|して下さい|"
    r"やって|直して|作って|入れて|出して|足して|消して|止めて|変えて|戻して|"
    r"繋いで|つないで|測って|数えて|調べて|確かめて|見せて|教えて|決めて|"
    r"にして|にしてよ|しといて|しておいて|しておいて|"
    r"ダメ|だめ|おかしい|できてない|出来てない|進んでない|なってない|"
    r"何回も|なんかい|また同じ|二度と|もう一度言|前も言|さっきも言|"
    r"禁止|やめて|要らない|いらない)")

# 拾ってはいけない層。AIの復唱・システムの注記・引用・コード。
_SKIP = re.compile(
    r"^(\s*[<\[{#`|/>]|system-reminder|Caveat|Called the |This session|"
    r"注意：|例：|参考：|https?://\S+$)")

# 会話の潤滑油。依頼ではない。
_AIZUCHI = re.compile(
    r"^(はい|うん|おk|OK|ok|了解|ありがとう|ありがと|よろしく|おつかれ|お疲れ|"
    r"そう|そうだね|わかった|分かった|いいよ|どう|ん|w+)[。、！!？?\s]*$")


def norm(s):
    """突き合わせ用。記号・空白・装飾・強調の★を落とす。"""
    s = re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "")
    return s.lower()


def make_id(text):
    return hashlib.sha1(norm(text)[:60].encode("utf-8")).hexdigest()[:12]


def bunkatsu(text):
    """まとまった発言を「1つの言いつけ」に割る。

    たまごさんは1メッセージに10個の指示を書く。1メッセージ＝1件にすると
    9個が消える。**行と句点で割って、1つずつ台帳に入れる。**
    """
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or _SKIP.match(line):
            continue
        # 箇条書きの飾りを外す（中身は残す）
        line = re.sub(r"^\s*(?:[0-9]+[\.\)]|[-*＊・●○▪️]|【[^】]{0,12}】)\s*", "", line)
        # ★たまごさんは「★」を箇条書きの印にも強調にも使う。印として割ってから、
        #   文頭に残った飾り（★ ** 〉）を落とす。落とさないと同じ一言が
        #   「★付き」と「★無し」で別IDになり、回数が永久に1のまま＝赤が出ない。
        for s in re.split(r"(?<=[。！？!?])\s*|(?=★)", line):
            s = re.sub(r"^[\s★☆*＊>》・]+", "", re.sub(r"\s+", " ", s or "")).strip()
            if len(norm(s)) < 8 or len(norm(s)) > 200:
                continue
            if _AIZUCHI.match(s) or _SKIP.match(s):
                continue
            if not _IRAI.search(s):
                continue
            out.append(s[:160])
    return out


# ────────────────────────────────────────────── ログを読む


def user_text(rec):
    """会話ログ1行から、たまごさんが打った文だけを取り出す。

    道具の返り値（tool_result）はたまごさんの発言ではない。混ぜると
    台帳がゴミで埋まって誰も見なくなる＝仕組みが死ぬ。**必ず外す。**
    """
    if not isinstance(rec, dict):
        return None
    if rec.get("type") not in (None, "user"):
        return None
    msg = rec.get("message") or rec
    if not isinstance(msg, dict) or msg.get("role") != "user":
        return None
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if not isinstance(c, list):
        return None
    parts = []
    for b in c:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_result":
            continue          # ★道具の出力。たまごさんの声ではない
        if b.get("type") == "text":
            parts.append(b.get("text") or "")
    return "\n".join(parts) if parts else None


def log_files(limit=MAX_FILES_PER_RUN):
    seen, out = set(), []
    for g in LOG_GLOBS:
        try:
            for p in glob.glob(g, recursive=("**" in g)):
                rp = os.path.realpath(p)
                if rp in seen or not os.path.isfile(rp):
                    continue
                seen.add(rp)
                out.append(rp)
        except Exception:
            continue
    # 新しいものから。1回の実行で読む本数に上限を置く（心臓を詰まらせない）
    out.sort(key=lambda p: -os.path.getmtime(p))
    return out if limit is None else out[:limit]


def load_hatsugen():
    rows = {}
    if os.path.exists(HATSUGEN):
        for line in io.open(HATSUGEN, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows[r.get("id")] = r
    return rows


def save_hatsugen(rows):
    os.makedirs(DIR, exist_ok=True)
    body = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
        for r in sorted(rows.values(),
                        key=lambda x: (-int(x.get("count") or 1), x.get("firstSaid") or "")))
    write_text(HATSUGEN, body)


def hiroi(dry=False, rebuild=False, zenbu=False):
    """新しく増えた分だけ読んで、発言を拾って数える。

    ★落ちても続きから：ファイルごとに「どこまで読んだか」を .seen.json に残す。
      ファイルが小さくなっていたら（差し替え）先頭から読み直す。
    """
    rows = {} if rebuild else load_hatsugen()
    seen = {} if rebuild else (load_json(SEEN, {}) or {})
    # --zenbu＝過去ログを全部さらう掃除便。上限を外す。落ちても .seen.json に
    # 読んだ位置が残るので、次に呼べば続きから再開する（最初からやり直さない）。
    budget = (1 << 62) if zenbu else MAX_BYTES_PER_RUN
    added, bumped, files = 0, 0, 0

    for p in log_files(None if zenbu else MAX_FILES_PER_RUN):
        if budget <= 0:
            break
        try:
            size = os.path.getsize(p)
        except Exception:
            continue
        off = int((seen.get(p) or {}).get("off") or 0)
        if off > size:
            off = 0                      # 差し替えられた＝最初から
        if off >= size:
            continue
        files += 1
        read = 0
        try:
            with io.open(p, "rb") as f:
                f.seek(off)
                chunk = f.read(min(budget, size - off))
                read = len(chunk)
                # 途中で切れた最後の1行は次回に回す（半端なJSONを読ませない）
                nl = chunk.rfind(b"\n")
                if nl < 0:
                    continue
                body = chunk[:nl].decode("utf-8", "replace")
                off += nl + 1
        except Exception:
            continue
        budget -= read
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p), JST)
        for line in body.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            txt = user_text(rec)
            if not txt:
                continue
            # ★言われた日時は「分まで」持つ。過去ログから抜いた分も、その発言の
            #   タイムスタンプをそのまま入れる（拾った日時ではない）。日付だけだと
            #   「いつ言ったか」が曖昧になり、判定日が作れない＝うやむやが復活する。
            dt = iso_to_jst(rec.get("timestamp")) or mtime
            said = dt.strftime("%Y-%m-%d %H:%M")
            hi = dt.strftime("%Y-%m-%d")
            for s in bunkatsu(txt):
                i = make_id(s)
                r = rows.get(i)
                if r:
                    # ★同じ日の同じ一言は1回と数える（貼り直し・再送を水増ししない）
                    if hi in (r.get("days") or []):
                        continue
                    r["count"] = int(r.get("count") or 1) + 1
                    r["lastSaid"] = said
                    r["days"] = sorted(set((r.get("days") or []) + [hi]))[-12:]
                    r["seenAt"] = stamp()
                    bumped += 1
                else:
                    rows[i] = {
                        "id": i, "title": s, "count": 1,
                        "firstSaid": said, "lastSaid": said, "days": [hi],
                        "firstSaidJa": ja_nichiji(dt),
                        # ★判定日。ここで決めて台帳に焼く。あとから動かせない。
                        "hantei1w": (dt + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                        "hantei1m": (dt + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
                        "sonogo": None, "hanteiSumi": [],
                        "seenAt": stamp(), "from": os.path.basename(p),
                    }
                    added += 1
        seen[p] = {"off": off, "at": stamp()}

    if not dry:
        save_hatsugen(rows)
        os.makedirs(DIR, exist_ok=True)
        write_text(SEEN, json.dumps(seen, ensure_ascii=False, indent=1))
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": stamp(), "files": files, "added": added,
                                "bumped": bumped, "total": len(rows)},
                               ensure_ascii=False) + "\n")
    return rows, {"files": files, "added": added, "bumped": bumped, "total": len(rows)}


def tally(rows):
    """★進捗表の一番上に出す数。2回以上＝赤。3回以上＝最優先。"""
    two = [r for r in rows.values() if int(r.get("count") or 1) >= 2]
    three = [r for r in rows.values() if int(r.get("count") or 1) >= 3]
    return {"total": len(rows), "iwareta2": len(two), "iwareta3": len(three),
            "aka": len(two) > 0,
            "top": sorted(rows.values(), key=lambda r: -int(r.get("count") or 1))[:12]}


def main():
    a = sys.argv[1:]
    if "--self-test" in a:
        ng = []
        t = bunkatsu("もう仕組みにしてくれ。\nはい\n忘れられない仕組みにしてよ。")
        if len(t) != 2:
            ng.append("bunkatsu が2件にならない: %r" % (t,))
        if user_text({"type": "user", "message": {"role": "user", "content":
                      [{"type": "tool_result", "content": "直してほしい"}]}}):
            ng.append("tool_result を発言として拾っている")
        if make_id("★直してほしい。") != make_id("直してほしい"):
            ng.append("id が装飾で変わる")
        rows, s = hiroi(dry=True)
        print("自己試験：%s（読んだ %d ファイル／新規 %d／回数増 %d／合計 %d）"
              % ("OK" if not ng else "NG", s["files"], s["added"], s["bumped"], s["total"]))
        for x in ng:
            print("  ★NG %s" % x)
        return 1 if ng else 0
    if "--show" in a:
        rows = load_hatsugen()
        t = tally(rows)
        print("【たまごさんに言われたこと】貯まっている %d 件／"
              "2回以上言わせた %d 件／3回以上 %d 件"
              % (t["total"], t["iwareta2"], t["iwareta3"]))
        for r in t["top"]:
            print("  %2d回  %s  (%s〜%s)"
                  % (r["count"], r["title"][:56], r.get("firstSaid"), r.get("lastSaid")))
        return 0
    rows, s = hiroi(rebuild="--rebuild" in a, zenbu="--zenbu" in a)
    t = tally(rows)
    print("拾った：新規 %d 件／回数増 %d 件／台帳 %d 件（2回以上 %d／3回以上 %d）"
          % (s["added"], s["bumped"], s["total"], t["iwareta2"], t["iwareta3"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
