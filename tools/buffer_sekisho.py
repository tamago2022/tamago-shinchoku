#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1163番【二重投稿の関所】同じ本文・同じ曲は二度とBufferに入らない鍵。ここ1か所に集める。

■ 実際に起きたこと（2026-09-26 実測・そのまま残す）
  たまごさんが**同じ投稿が2本出ているのを見つけた**（松任谷由実「あの日にかえりたい」）。

    1本目 status/buffer_queue/done/1132t_deta.json
          id 6ab54aba47d3e0a6492c903c / status "sent" / sentAt 2026-09-24T16:58Z（＝9/25 01:58 JST）
    2本目 status/buffer_queue/hokyuu_result.json（2026-09-26 06:00:12）
          "before": 0 → 同じ本文を 9/26 07:30 に入れ、そのまま出た
          id 6ab6e0dff59168c9752abd4c

■ なぜ「三重の二重投稿防止」が効かなかったか（言い訳ではなく穴の形）
  防止は3つとも **「いま予約に並んでいるもの(status: scheduled)」** だけを見ていた。
    ① yoyaku.jsonl の n 照合  … 1135番の便の中だけ。補充便は見ない
    ② 同じ本文がBufferに居るか … filter.status が [scheduled] のみ＝**出し終わった投稿は見えない**
    ③ 同じ時刻が埋まっているか … 時刻が違えば通る
  → 出し終わった投稿(sent)は誰も見ていなかった。machi.json の行列には同じ本文が残っていた。
     結果、1本目が出て予約欄が空になった瞬間に、同じ本文が2本目として入った。

■ この関所が見るもの（全部）
  1. Bufferの scheduled（予約中）
  2. Bufferの sent（**もう出した分**）★ここが抜けていた
  3. Bufferの error
  4. 台帳 status/buffer_queue/dashita.jsonl（一度でも入れた本文・曲を永久に覚える）
     ★BufferのAPIが古い投稿を返さなくなっても、こちらは覚えている。

■ 突き合わせる鍵は2つ
  ・本文（記号と空白をそろえた形の全文）
  ・曲（本文の中の joy-relief-station のURLから artist/song を取り出したもの）
    → コピーを書き替えても、同じ曲は二度と入らない。

■ 使い方（入れる側は必ずこれを通す）
    import buffer_sekisho
    mon = buffer_sekisho.Mon(lambda q, v=None: gql(tok, q, v))
    mon.load(org_id, channel_id)
    ok, why = mon.tsukaeru(text)
    if not ok:  # ★弾いた数は mon.hajiita_kazu に入る
        ...
    mon.kiroku(text, due_iso, post_id, "hokyuu")
"""
import datetime
import hashlib
import io
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
JST = datetime.timezone(datetime.timedelta(hours=9))

Q_ALL = """
query($o: OrganizationId!, $c: [ChannelId!], $s: [PostStatus!]) {
  posts(input: { organizationId: $o, sort: [{ field: dueAt, direction: desc }],
                 filter: { status: $s, channelIds: $c } }) {
    edges { node { id text dueAt status channelId } }
  }
}
"""


def norm_text(t):
    """記号と空白のゆれを吸収した全文。ここで意味は変えない。"""
    t = unicodedata.normalize("NFKC", t or "")
    t = t.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def text_key(t):
    return hashlib.sha1(norm_text(t).encode("utf-8")).hexdigest()[:16]


def song_key(t):
    """本文の中の曲ページURLから artist/song を取り出す。無ければ空。"""
    m = re.search(r"joy-relief-station\.lovable\.app/cover-guide\?([^\s\"'>)]+)", t or "")
    if not m:
        return ""
    q = m.group(1).replace("&amp;", "&")
    a = s = ""
    for kv in q.split("&"):
        if kv.startswith("artist="):
            a = kv[7:].strip().lower()
        elif kv.startswith("song="):
            s = kv[5:].strip().lower()
    return "%s/%s" % (a, s) if a and s else ""


def _read_daicho():
    rows = []
    if os.path.exists(DAICHO):
        for ln in io.open(DAICHO, encoding="utf-8"):
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def _append(row):
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


class Mon(object):
    def __init__(self, gql):
        self.gql = gql
        self.texts = {}        # text_key -> どこで見たか
        self.songs = {}        # song_key -> どこで見たか
        self.dues = set()      # UTC ISO の分まで
        self.hajiita = []      # 弾いたものの記録
        self.mita = {"scheduled": 0, "sent": 0, "error": 0, "daicho": 0}
        self._load_daicho()

    # ---- 台帳（永久に覚えている側） ----
    def _load_daicho(self):
        for r in _read_daicho():
            tk, sk = r.get("text_key"), r.get("song_key")
            if tk:
                self.texts.setdefault(tk, "台帳:%s" % r.get("at", ""))
            if sk:
                self.songs.setdefault(sk, "台帳:%s" % r.get("at", ""))
            self.mita["daicho"] += 1

    # ---- Bufferの実物（予約中・出した分・失敗分を全部） ----
    def load(self, org_id, channel_id):
        mita_text = []
        for st in ("scheduled", "sent", "error"):
            try:
                r = self.gql(Q_ALL, {"o": org_id, "c": [channel_id], "s": [st]})
                edges = (((r.get("data") or {}).get("posts") or {}).get("edges") or [])
            except Exception:
                edges = []
            self.mita[st] = len(edges)
            for e in edges:
                n = e.get("node") or {}
                t = n.get("text") or ""
                self.texts.setdefault(text_key(t), "Buffer:%s(%s)" % (st, n.get("dueAt")))
                sk = song_key(t)
                if sk:
                    self.songs.setdefault(sk, "Buffer:%s(%s)" % (st, n.get("dueAt")))
                if st == "scheduled":
                    self.dues.add((n.get("dueAt") or "")[:16])
                mita_text.append((t, "Buffer:%s(%s)" % (st, n.get("dueAt"))))
        # ★実物を見たら台帳にも写す（BufferのAPIが古い投稿を返さなくなっても覚えておく）
        self.mita["daicho_ni_utsushita"] = self.seed_daicho(mita_text)
        return self.mita

    def seed_daicho(self, rows_texts):
        """Bufferから見えた本文を台帳へ写す（初回の種まき。重複は書かない）。"""
        have = set(x.get("text_key") for x in _read_daicho())
        n = 0
        for t, where in rows_texts:
            tk = text_key(t)
            if tk in have:
                continue
            have.add(tk)
            _append({"at": datetime.datetime.now(JST).strftime("%F %T"),
                     "text_key": tk, "song_key": song_key(t),
                     "where": where, "head": (t or "")[:60]})
            n += 1
        return n

    # ---- 入れていいか ----
    def tsukaeru(self, text, due_iso=None):
        tk, sk = text_key(text), song_key(text)
        if tk in self.texts:
            return False, "同じ本文が既にある（%s）" % self.texts[tk]
        if sk and sk in self.songs:
            return False, "同じ曲が既にある（%s / %s）" % (sk, self.songs[sk])
        if due_iso and due_iso[:16] in self.dues:
            return False, "同じ時刻に別の予約が居る（%s）" % due_iso
        return True, ""

    def hajiku(self, text, why, due_iso=None):
        self.hajiita.append({"head": (text or "")[:60].replace("\n", " "),
                             "song": song_key(text), "due": due_iso, "why": why})

    def kiroku(self, text, due_iso, post_id, where):
        """入れたら必ず呼ぶ。台帳に書き、次からは弾かれる。"""
        tk, sk = text_key(text), song_key(text)
        self.texts[tk] = "いま入れた(%s)" % where
        if sk:
            self.songs[sk] = "いま入れた(%s)" % where
        if due_iso:
            self.dues.add(due_iso[:16])
        _append({"at": datetime.datetime.now(JST).strftime("%F %T"),
                 "text_key": tk, "song_key": sk, "due_utc": due_iso,
                 "post_id": post_id, "where": where, "head": (text or "")[:60]})

    @property
    def hajiita_kazu(self):
        return len(self.hajiita)
