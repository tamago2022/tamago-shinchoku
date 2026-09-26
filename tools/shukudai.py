#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宿題台帳（shukudai） ― 「言われたのに返ってきていないもの」を1本の台帳にまとめる道具。

■ なぜ作ったか（2026-09-25）

たまごさん：
  「俺が言ったのに返ってきてないことがたくさんあるよ。だからリストアップしようよ。
   何十個もあるはずだから、それが自動で走ってゼロになるようにやってほしいのよ。」
  「俺が言わないと動かない・覚えてないっていうのはダメ。あなたが覚えて1個1個確実に減らして。」

これまで「言われたこと」は5か所にバラバラに散っていた：

  1. status/queue.json                … 発車待ちの正本（314件）。ただし hold / stuck に
                                        落ちたものは誰も数えていない＝事実上の行方不明
  2. status/*hikitsugi*.md（58本）     … 「次の人がやること」が書いてあるのに、次の人が
                                        その紙を開かないと永久に走らない
  3. status/dispatch_outbox.jsonl      … 工場からの申し送り。返事待ちのまま沈む
  4. status/kakunin_machi 系            … 確認待ち
  5. たまごさんの記憶                   … いちばん高くつく置き場所

**この道具は、5か所を毎日1本の台帳（status/shukudai/daicho.jsonl）に集め直す。**
集めるだけでは意味がないので、

  - 台帳に載って「発車待ちに積まれていない」ものは、queue_add() でその場で積む（--ingest）
  - 状態は queue.json から**自動で**書き戻す（人が手で ✅ を付けない）
  - 毎日、残り件数を数えて count.jsonl に1行。**減っていなければ赤**
  - たまごさんが見るのは share/check/1138-shukudai.html の1枚だけ

■ 使い方

    python3 tools/shukudai.py                 # 掘り出し＋状態同期＋数える＋紙を書き直す
    python3 tools/shukudai.py --ingest        # 上に加えて、未キューの宿題を発車待ちに積む
    python3 tools/shukudai.py --list          # 未完了を古い順に出す（人が読む用）
    python3 tools/shukudai.py --self-test     # 自己試験（ファイルを1つも書き換えない）

■ 守っていること

  - AIを1回も呼ばない・外へ1回も出ない＝0円
  - git を叩かない（tools/commit_kuchi.py に紙を置くだけ）
  - 何回走らせても同じ結果（冪等）。id は出どころ＋題名から作る固定値
  - 既存の台帳（queue.json）を書き換えるのは --ingest で積むときだけ
"""

from __future__ import annotations

import argparse
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
STATUS = os.path.join(REPO, "status")
DIR = os.path.join(STATUS, "shukudai")
DAICHO = os.path.join(DIR, "daicho.jsonl")
COUNT = os.path.join(DIR, "count.jsonl")
PUBLIC = os.path.join(STATUS, "public", "shukudai.json")
HTML = os.path.join(REPO, "share", "check", "1138-shukudai.html")

QUEUE = os.path.join(STATUS, "queue.json")
OUTBOX = os.path.join(STATUS, "dispatch_outbox.jsonl")

JST = datetime.timezone(datetime.timedelta(hours=9))


def now():
    return datetime.datetime.now(JST)


def today():
    return now().strftime("%Y-%m-%d")


def load_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- 状態の言葉

# queue.json の status → 台帳の状態。たまごさんが読む日本語に翻訳して持つ。
STATE_FROM_QUEUE = {
    "waiting": "未着手",
    "running": "走行中",
    "awaiting_check": "確認待ち",
    "stuck": "止まっている",
    "hold": "止まっている",
    "done": "完了",
    "merged": "完了",
}
OPEN_STATES = ("未着手", "走行中", "確認待ち", "止まっている", "引き継ぎ")


def norm(s):
    """題名の突き合わせ用。記号・空白・装飾を落とす。"""
    s = re.sub(r"[*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\\s]", "", s or "")
    return s.lower()


def make_id(source, title):
    return hashlib.sha1(("%s|%s" % (source, norm(title))).encode("utf-8")).hexdigest()[:12]


def done_when(title, what=""):
    """完了条件を1行で言い切る（憲法：「〜を検討する」は禁止）。

    引き継ぎ・指示文の中に「完了条件」が明記されていればそれを使う。
    無ければ題名から機械的に作る。**必ず「〜が〜で確認できる」の形で終わる。**
    """
    for line in (what or "").splitlines():
        m = re.search(r"完了条件[】\]：:]*\s*(.+)$", line)
        if m and len(m.group(1).strip()) > 3:
            return m.group(1).strip()[:120]
    t = re.sub(r"^【[^】]*】", "", title or "").strip()
    t = re.sub(r"[。\.]+$", "", t)
    return ("%s——が本番に出ていて、開いたページが200で返る" % t)[:120]


# ---------------------------------------------------------------- 掘り出し


def harvest_queue():
    """① status/queue.json ― 発車待ちの正本。hold / stuck も落とさず全部拾う。"""
    q = load_json(QUEUE, {}) or {}
    out = []
    for it in (q.get("items") or []):
        title = (it.get("title") or "").strip()
        if not title:
            continue
        st = STATE_FROM_QUEUE.get(it.get("status"), "未着手")
        out.append({
            "id": make_id("queue", title),
            "source": "queue",
            "queueN": it.get("n"),
            "saidAt": (it.get("cutAt") or it.get("restoredAt") or "")[:10] or None,
            "title": title[:120],
            "doneWhen": done_when(title, it.get("what") or ""),
            "state": st,
            "origin": it.get("origin") or "user",
            "priority": it.get("priority"),
            "evidence": None,
            "note": (it.get("holdNote") or "")[:200] or None,
        })
    return out


_NEXT_HEAD = re.compile(r"^#{2,4}\s*.*?(次|つぎ|残|未完|やり残|TODO|宿題|これから)")
_ITEM = re.compile(r"^\s*(?:[0-9]+[\.\)]|[-*＊・])\s+(.{6,})$")


def harvest_hikitsugi():
    """② status/*hikitsugi*.md ― 「次の人がやること」。紙を開かないと永久に走らない層。"""
    out = []
    paths = sorted(set(
        glob.glob(os.path.join(STATUS, "*hikitsugi*.md"))
        + glob.glob(os.path.join(STATUS, "*引き継*.md"))
    ))
    for p in paths:
        base = os.path.basename(p)
        try:
            lines = io.open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p), JST).strftime("%Y-%m-%d")
        inside = False
        for line in lines:
            if line.startswith("#"):
                inside = bool(_NEXT_HEAD.match(line))
                continue
            if not inside:
                continue
            m = _ITEM.match(line)
            if not m:
                continue
            title = re.sub(r"[*`]", "", m.group(1)).strip()
            title = re.sub(r"\s+", " ", title)
            if len(norm(title)) < 6:
                continue
            out.append({
                "id": make_id("hikitsugi:" + base, title),
                "source": "hikitsugi",
                "sourceFile": base,
                "queueN": None,
                "saidAt": mtime,
                "title": title[:120],
                "doneWhen": done_when(title),
                "state": "引き継ぎ",
                "origin": "user",
                "priority": None,
                "evidence": None,
                "note": None,
            })
    return out


_OUTBOX_WANT = ("stuck_escalation", "cost_confirm", "red", "kenpin_stuck",
                "sekisho_repeated_unfixed", "gate_fix", "renraku_check", "copy_fix")


def harvest_outbox():
    """③ status/dispatch_outbox.jsonl ― 工場からの申し送りで、返事待ちのまま沈んだもの。"""
    out = []
    seen = set()
    try:
        rows = [json.loads(l) for l in io.open(OUTBOX, encoding="utf-8") if l.strip()]
    except Exception:
        return out
    for r in rows:
        if r.get("type") not in _OUTBOX_WANT:
            continue
        title = (r.get("title") or r.get("message") or "").strip().splitlines()[0] if (
            r.get("title") or r.get("message")) else ""
        title = re.sub(r"[*`#]", "", title).strip()
        if len(norm(title)) < 6:
            continue
        k = norm(title)
        if k in seen:
            continue
        seen.add(k)
        out.append({
            "id": make_id("outbox", title),
            "source": "outbox",
            "queueN": r.get("n"),
            "saidAt": (r.get("ts") or "")[:10] or None,
            "title": title[:120],
            "doneWhen": done_when(title),
            "state": "止まっている",
            "origin": "factory",
            "priority": None,
            "evidence": None,
            "note": (r.get("type") or None),
        })
    return out


# 引き継ぎの箇条書きには「やること」ではない行も混ざる（感想・注意書き・経緯）。
# 発車待ちに積む対象から外すが、**台帳からは消さない**（消すと二度と見つからないため）。
_NOT_TASK = re.compile(
    r"(たまごさんが|たまごさんに見てもらう|注意：|ここが全部の親|わざと|参考|経緯|所感|——|だけ。$)")
_TASKISH = re.compile(r"(する|やる|直す|作る|足す|消す|測る|出す|見る|確かめる|試す|入れる|"
                      r"戻す|繋ぐ|つなぐ|閉じる|置く|投げる|通す|回す|書く|埋める|止める|"
                      r"продолж|続ける|takes|\[ \])")


def actionable(r):
    """発車待ちに積んでよいか。台帳への記録可否ではない。"""
    t = r.get("title") or ""
    if r.get("source") == "queue":
        return True
    if _NOT_TASK.search(t):
        return False
    return bool(_TASKISH.search(t))


KIOKU = os.path.join(STATUS, "kioku", "hatsugen.jsonl")


def harvest_kioku():
    """④ status/kioku/hatsugen.jsonl ― **たまごさんが口で言ったこと。**

    2026-09-26 たまごさん：
      「あなたたちすぐ忘れたりするからさ、忘れられない、もう逃げられない仕組みにしてよ。」

    ①②③はどれも「AIが書いた紙」。たまごさんの発言は、誰かが手で写さないと
    台帳に入らなかった＝写し忘れた瞬間に消えていた。ここが4つ目の出どころ。
    中身は tools/kioku.py が会話ログから機械で拾う（0円）。

    ★言われた回数で優先度を決める。**3回以上言わせたものは最優先(1)に繰り上げる。**
      2回で2、1回で3。たまごさんに二度言わせること自体が事故なので、
      2回目が付いた時点で列の前に出る。
    """
    out = []
    if not os.path.exists(KIOKU):
        return out
    for line in io.open(KIOKU, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        title = (r.get("title") or "").strip()
        if len(norm(title)) < 8:
            continue
        n = int(r.get("count") or 1)
        out.append({
            "id": make_id("kioku", title),
            "source": "kioku",
            "queueN": None,
            "saidAt": r.get("firstSaid"),
            "title": title[:120],
            "doneWhen": done_when(title),
            "state": "未着手",
            "origin": "user",
            "priority": 1 if n >= 3 else (2 if n >= 2 else 3),
            "saidCount": n,
            "lastSaid": r.get("lastSaid"),
            "evidence": None,
            "note": ("★%d回言わせている" % n) if n >= 2 else None,
        })
    return out


def harvest():
    rows = harvest_queue() + harvest_hikitsugi() + harvest_outbox() + harvest_kioku()
    # queue に同じ題名で載っているものは queue 側を正として1本にまとめる
    queue_keys = {norm(r["title"]) for r in rows if r["source"] == "queue"}
    queue_heads = {norm(r["title"])[:18] for r in rows if r["source"] == "queue"}
    merged, seen, heads = [], set(), set()
    for r in rows:
        k = norm(r["title"])
        if r["source"] != "queue":
            if k in queue_keys or k[:18] in queue_heads:
                continue  # queue 側で既に走っている
            if k[:18] in heads:
                continue  # 引き継ぎを跨いだ同じ一手（前の紙からの写し）
            heads.add(k[:18])
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        r["actionable"] = actionable(r)
        merged.append(r)
    return merged


# ---------------------------------------------------------------- 台帳の読み書き


def load_daicho():
    rows = {}
    if os.path.exists(DAICHO):
        for line in io.open(DAICHO, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows[r.get("id")] = r
    return rows


def save_daicho(rows):
    os.makedirs(DIR, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                   for r in sorted(rows.values(), key=lambda x: (x.get("firstSeen") or "", x.get("id"))))
    write_text(DAICHO, body)


def sync(dry=False):
    """掘り出した最新と台帳を突き合わせる。**状態は毎回上書きする＝手で書き換えない。**"""
    old = load_daicho()
    fresh = harvest()
    stamp = now().strftime("%Y-%m-%d %H:%M")
    newly_closed = []
    for r in fresh:
        prev = old.get(r["id"])
        if prev:
            was = prev.get("state")
            prev.update({k: v for k, v in r.items() if v is not None or k == "state"})
            prev["state"] = r["state"]
            prev["lastSeen"] = stamp
            if was in OPEN_STATES and r["state"] == "完了":
                prev["closedAt"] = stamp
                newly_closed.append(prev)
        else:
            r["firstSeen"] = stamp
            r["lastSeen"] = stamp
            r["closedAt"] = stamp if r["state"] == "完了" else None
            old[r["id"]] = r
    # 掘り出しから消えた＝queue から消えた＝片付いたとみなす（勝手に消さない・完了として残す）
    live = {r["id"] for r in fresh}
    for i, r in old.items():
        if i in live or r.get("state") not in OPEN_STATES:
            continue
        # 掘り出しから消えた＝発車待ちへ移したか、同じ一手が別の紙にもあった、のどちらか。
        # **ここで「完了」にしてはいけない。**やっていない仕事が減ったことになる＝
        # たまごさんに一番ついてはいけない嘘。完了は queue.json が done/merged に
        # なったときだけ付く（＝別のAIが本番で確認した印がそこに立つ）。
        r["state"] = "重複"
        r["note"] = ("発車待ちへ移したので数えない" if r.get("queuedAt")
                     else "同じ一手が別の紙にもあるので数えない")
    if not dry:
        save_daicho(old)
    return old, newly_closed


# ---------------------------------------------------------------- 数える


def tally(rows):
    open_rows = [r for r in rows.values() if r.get("state") in OPEN_STATES]
    by_state = {}
    for r in rows.values():
        by_state[r.get("state")] = by_state.get(r.get("state"), 0) + 1
    closed_today = len([r for r in rows.values()
                        if (r.get("closedAt") or "").startswith(today())])
    return {
        "total": len([r for r in rows.values() if r.get("state") != "重複"]),
        "open": len(open_rows),
        "closedToday": closed_today,
        "byState": by_state,
    }


def append_count(t, dry=False):
    """1日1行。**前の日より減っていなければ赤。**"""
    hist = []
    if os.path.exists(COUNT):
        for line in io.open(COUNT, encoding="utf-8"):
            if line.strip():
                try:
                    hist.append(json.loads(line))
                except Exception:
                    pass
    prev = [h for h in hist if h.get("date") != today()]
    yesterday_open = prev[-1]["open"] if prev else None
    red = (yesterday_open is not None and t["open"] >= yesterday_open and t["closedToday"] == 0)
    row = {"date": today(), "at": now().strftime("%H:%M"), "open": t["open"],
           "total": t["total"], "closedToday": t["closedToday"], "red": red,
           "prevOpen": yesterday_open}
    if not dry:
        os.makedirs(DIR, exist_ok=True)
        keep = [h for h in hist if h.get("date") != today()] + [row]
        write_text(COUNT, "".join(json.dumps(h, ensure_ascii=False) + "\n" for h in keep))
    return row, prev[-7:]


# ---------------------------------------------------------------- 発車待ちに積む


def ingest(rows, limit=40, dry=False):
    """台帳にあって発車待ちに載っていないものを、queue_add() でその場で積む。

    hikitsugi / outbox 由来だけが対象（queue 由来はすでに列に居る）。
    優先度：たまごさん発（user）＝2、工場発＝4。
    """
    sys.path.insert(0, HERE)
    try:
        import command_ingest  # noqa
    except Exception as e:
        return [], "command_ingest を読めません: %s" % e
    # 2026-09-25 実測した事故：鍵を取らずに積んだら、Mac側の auto_launcher が同じ瞬間に
    # queue.json を書いていて「queue.json.tmp が無い」で2回こけた（status/auto_launch.log
    # 08:40:55・08:43:14）。**積む側が鍵を取らないと、工場の発車そのものを転ばせる。**
    try:
        import queue_store
        lock = queue_store.queue_lock
    except Exception:
        import contextlib
        lock = contextlib.nullcontext
    added = []
    targets = [r for r in rows.values()
               if r.get("source") in ("hikitsugi", "outbox", "kioku")
               and r.get("state") in OPEN_STATES
               and r.get("actionable")
               and not r.get("queuedAt")]
    targets.sort(key=lambda r: (r.get("saidAt") or ""))  # 古いものから先に発車させる
    for r in targets[:limit]:
        # 引き継ぎの積み残し＝普通(3)。工場発の申し送り＝後回し(4)。
        # たまごさんが進捗表で付けたPは常にこれより強いので、割り込みにはならない。
        pri = 3 if r.get("origin") == "user" else 4
        # ★たまごさんの口から出たもの（kioku）は、言われた回数で列の前に出す。
        #   3回以上言わせた＝最優先(1)。2回＝2。二度言わせること自体が事故なので、
        #   2回目が付いた瞬間に割り込んでよい。
        if r.get("source") == "kioku":
            n = int(r.get("saidCount") or 1)
            pri = 1 if n >= 3 else (2 if n >= 2 else 3)
        body = "\n".join([
            "【タスク】%s" % r["title"],
            "【完了条件】%s" % r["doneWhen"],
            "【出どころ】%s（%s／%s）" % (r.get("sourceFile") or r.get("source"),
                                        r.get("saidAt") or "日付不明", r.get("id")),
            "【報告】完了/問題/判断待ちの3行以内。本番反映があれば直リンク必須。",
            "たまごさんに質問しない。判断は自分でして、報告に「こう決めた」と書く。",
        ])
        if dry:
            added.append((r["id"], "dry", r["title"]))
            continue
        try:
            with lock():
                st, msg = command_ingest.queue_add(body, priority=pri, label=r["title"][:60],
                                                   origin=r.get("origin") or "user")
        except Exception as e:
            st, msg = "failed", str(e)
        r["queuedAt"] = now().strftime("%Y-%m-%d %H:%M")
        r["queueResult"] = "%s:%s" % (st, msg)
        # queue_add は成功で "done"、既に列に居れば "skipped" を返す。どちらも
        # 「もう発車待ちに載っている」＝二度と積み直さない。
        if st in ("done", "ok", "skipped"):
            r["state"] = "未着手"
        added.append((r["id"], st, r["title"]))
        # queue.json は1.4MBあり1件ごとの保存が重い。途中で時間切れになっても
        # 「積んだのに台帳に残っていない」を作らないよう、こまめに書き戻す。
        if not dry and len(added) % 5 == 0:
            save_daicho(rows)
    if not dry:
        save_daicho(rows)
    return added, None


# ---------------------------------------------------------------- 紙を1枚


def build_html(rows, t, countrow, hist, pace, quota, health):
    open_rows = [r for r in rows.values() if r.get("state") in OPEN_STATES]
    order = {"止まっている": 0, "確認待ち": 1, "走行中": 2, "引き継ぎ": 3, "未着手": 4}
    open_rows.sort(key=lambda r: (order.get(r.get("state"), 9), r.get("saidAt") or ""))
    running = t["byState"].get("走行中", 0)
    remain = 100.0 - float(pace.get("allPct") or 0)
    cap = (health.get("同時上限") or {}).get("本数")
    haibun = load_json(os.path.join(STATUS, "haibun.json"), {}) or {}

    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ★いちばん大事な行：宿題が減らない「本当の理由」を一番上に出す。
    #   件数だけ出しても、工場が止まっていたら明日も同じ数字になる。
    banner = ""
    flag = os.path.join(STATUS, "no_launch.flag")
    if os.path.exists(flag):
        try:
            msg = io.open(flag, encoding="utf-8").read().strip()
        except Exception:
            msg = "発車が止まっています"
        since = ""
        try:
            import subprocess  # noqa
        except Exception:
            pass
        banner = ('<div class="banner"><b>いま宿題が減らない理由はこれ1つ</b><br>%s'
                  '<br><span class="bsub">これが消えるまで、発車待ち%d件は1本も本物が出ません'
                  '（空回しのテストだけが回っています）。たまごさんがClaudeのアプリで'
                  '1回ログインし直せば、auth_watch.py が気づいて自動で再開します。</span></div>'
                  % (msg.replace("<", "&lt;"), sum(1 for r in rows.values()
                                                   if r.get("state") == "未着手")))
    elif haibun.get("red"):
        banner = ('<div class="banner"><b>赤</b><br>%s</div>'
                  % "<br>".join(x.replace("<", "&lt;") for x in (haibun.get("reds") or [])))

    def card(label, value, sub, red=False):
        return ('<div class="c%s"><div class="k">%s</div><div class="v">%s</div>'
                '<div class="s">%s</div></div>' % (" red" if red else "", esc(label),
                                                   esc(str(value)), esc(sub)))

    # 題名と完了条件は**台帳から一字一句そのまま写した引用**であって、この紙自身の主張ではない。
    # <code> で括るのはそのため（見た目は変えていない。CSSで地の文と同じにしてある）。
    # 2026-09-26 実測：括らずに出していたら、宿題の題名に混ざっていた「375px」を
    #   関所(tools/sekisho.py)が「この紙がpxを主張している」と読んで push を止めた。
    #   引用と主張を機械が区別できる形にしていなかったこちらの落ち度。関所は正しい。
    trs = []
    for r in open_rows[:400]:
        trs.append(
            '<tr class="s-%s"><td class="st">%s</td>'
            '<td><code data-inyou="台帳">%s</code><div class="dw"><code data-inyou="台帳">%s</code></div></td>'
            '<td class="d">%s</td><td class="src">%s</td></tr>' % (
                order.get(r.get("state"), 9), esc(r.get("state")), esc(r.get("title")),
                esc(r.get("doneWhen")), esc(r.get("saidAt") or "—"),
                esc(r.get("sourceFile") or r.get("source"))))

    spark = " ".join("%s:%s" % (h["date"][5:], h["open"]) for h in hist)

    html = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>宿題台帳｜言われたのに返っていないもの</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:18px 14px 60px;font:16px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;background:#fbfaf7;color:#1b1b1b}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#777;font-size:13px;margin:0 0 16px}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px}
.c{flex:1 1 140px;background:#fff;border:1px solid #e6e2d8;border-radius:12px;padding:12px 14px}
.c.red{border-color:#d33;background:#fff5f4}
.k{font-size:12px;color:#888}
.v{font-size:28px;font-weight:700;letter-spacing:-.02em}
.c.red .v{color:#c22}
.s{font-size:12px;color:#999;margin-top:2px}
table{width:100%%;border-collapse:collapse;font-size:14px}
td{border-bottom:1px solid #eee;padding:9px 6px;vertical-align:top}
.st{white-space:nowrap;font-size:12px;color:#fff;width:1%%}
.s-0 .st{background:#c2352b}.s-1 .st{background:#c98a00}.s-2 .st{background:#2c7}.s-3 .st{background:#68c}.s-4 .st{background:#999}
.st{border-radius:6px;padding:2px 7px;display:inline-block}
.dw{color:#8a8578;font-size:12px;margin-top:2px}
/* 題名と完了条件は台帳からの引用。見た目は地の文と同じにして、意味づけだけ分ける */
code{font-family:inherit;font-size:inherit;color:inherit;background:none;padding:0}
.d,.src{color:#999;font-size:12px;white-space:nowrap}
.banner{background:#b3261e;color:#fff;border-radius:12px;padding:14px 16px;margin:0 0 16px;font-size:15px;line-height:1.6}
.banner b{font-size:16px}
.bsub{display:block;margin-top:6px;font-size:13px;opacity:.92}
.note{font-size:12px;color:#888;margin-top:22px;border-top:1px solid #e6e2d8;padding-top:10px}
a{color:#36c}
@media (prefers-color-scheme:dark){body{background:#141312;color:#eee}.c{background:#1e1d1b;border-color:#333}.c.red{background:#2a1716}td{border-color:#2a2a2a}}
</style></head><body>
<h1>宿題台帳</h1>
<p class="sub">言われたのに返っていないもの。%(at)s 時点。この紙は機械が書き換えている（人が手で✅を付けない）。</p>
%(banner)s
<div class="cards">
%(cards)s
</div>
<table>%(rows)s</table>
<p class="note">残り件数の推移：%(spark)s<br>
出どころ：発車待ち(queue.json)／引き継ぎ58本／工場からの申し送り(dispatch_outbox)。<br>
書き換えているもの：<code>tools/shukudai.py</code>（AIを呼ばない・外へ出ない＝0円）</p>
</body></html>""" % {
        "at": now().strftime("%m/%d %H:%M"),
        "banner": banner,
        "cards": "".join([
            card("宿題（未完了）", t["open"], "全%d件のうち" % t["total"], red=countrow.get("red")),
            card("今日減った", t["closedToday"], "前日 %s件" % (countrow.get("prevOpen") if countrow.get("prevOpen") is not None else "—"),
                 red=(t["closedToday"] == 0)),
            card("走行中", running, "同時上限 %s本" % (cap if cap is not None else "—")),
            card("週の残り", "%.0f%%" % remain, "リセット %s" % (quota.get("resetAt") or "—"),
                 red=(remain > 75)),
            card("いま出してよい本数", haibun.get("cap", "—"), (haibun.get("why") or "")[:40]),
        ]),
        "rows": "".join(trs),
        "spark": esc(spark or "（今日が初日）"),
    }
    return html


# ---------------------------------------------------------------- 自己試験


def self_test():
    ok, ng = [], []

    def check(name, cond):
        (ok if cond else ng).append(name)

    check("done_when が言い切りで終わる", done_when("画像が出ない").endswith("200で返る"))
    check("done_when が明記の完了条件を拾う",
          done_when("x", "【完了条件】ページが本番で開ける") == "ページが本番で開ける")
    check("id が固定値", make_id("queue", "あ い") == make_id("queue", "あい"))
    check("箇条書きを拾う", bool(_ITEM.match("1. Devinを1本測る（採用が付かなければ止める）")))
    check("見出し判定", bool(_NEXT_HEAD.match("## 次の人がやること")) and
          not _NEXT_HEAD.match("## 作ったもの"))
    h = harvest()
    check("掘り出しが30件以上ある（%d件）" % len(h), len(h) >= 30)
    check("全件に完了条件がある", all(r.get("doneWhen") for r in h))
    check("全件に状態がある", all(r.get("state") for r in h))
    rows, _ = sync(dry=True)
    t = tally(rows)
    check("未完了が数えられる（%d件）" % t["open"], t["open"] > 0)
    for n in ok:
        print("  ✔ %s" % n)
    for n in ng:
        print("  ✘ %s" % n)
    print("%d/%d" % (len(ok), len(ok) + len(ng)))
    return 0 if not ng else 1


# ---------------------------------------------------------------- 本体


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true", help="未キューの宿題を発車待ちに積む")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--hima", action="store_true",
                    help="心臓から呼ばれる用。1日1回だけ実際に走る（それ以外は何もしないで抜ける）")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    # 心臓（heartbeat.sh）に相乗りする。新しい常駐も定期タスクも作らない。
    mark = os.path.join(STATUS, ".shukudai_at")
    if a.hima:
        try:
            if io.open(mark, encoding="utf-8").read().strip() == today():
                return 0
        except Exception:
            pass
        write_text(mark, today())
        a.ingest = True

    rows, closed = sync(dry=a.dry)
    if a.ingest:
        added, err = ingest(rows, limit=a.limit, dry=a.dry)
        if err:
            print("積めませんでした: %s" % err)
        else:
            okn = len([x for x in added if x[1] in ("ok", "dry")])
            print("発車待ちに積んだ: %d件（試みた %d件）" % (okn, len(added)))
            for i, st, ti in added[:50]:
                print("   %-7s %s" % (st, ti[:60]))

    t = tally(rows)
    countrow, hist = append_count(t, dry=a.dry)

    if a.list:
        for r in sorted([r for r in rows.values() if r.get("state") in OPEN_STATES],
                        key=lambda r: (r.get("saidAt") or "")):
            print("%-6s %-10s %s" % (r.get("saidAt") or "—", r.get("state"), r.get("title")[:70]))

    pace = load_json(os.path.join(STATUS, "pace.json"), {}) or {}
    quota = load_json(os.path.join(STATUS, "quota.json"), {}) or {}
    health = load_json(os.path.join(STATUS, "health.json"), {}) or {}

    if not a.dry:
        pub = {"updatedAt": now().strftime("%Y-%m-%d %H:%M"), "tally": t,
               "count": countrow, "history": hist,
               "open": [{"id": r["id"], "title": r["title"], "state": r["state"],
                         "doneWhen": r["doneWhen"], "saidAt": r.get("saidAt"),
                         "source": r.get("sourceFile") or r.get("source")}
                        for r in rows.values() if r.get("state") in OPEN_STATES]}
        write_text(PUBLIC, json.dumps(pub, ensure_ascii=False, indent=1))
        write_text(HTML, build_html(rows, t, countrow, hist, pace, quota, health))
        try:
            sys.path.insert(0, HERE)
            import commit_kuchi
            commit_kuchi.cmd_request([DAICHO, COUNT, PUBLIC, HTML],
                                     why="宿題台帳の更新", who="shukudai.py")
        except Exception:
            pass

    print("宿題 %d件（未完了 %d件）／今日減った %d件／%s" % (
        t["total"], t["open"], t["closedToday"], "🔴減っていない" if countrow.get("red") else "🟢"))
    print("内訳: %s" % json.dumps(t["byState"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
