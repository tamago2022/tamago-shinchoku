#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1159番【ずんだもん読み上げ窓口】Macの中でVOICEVOXがmp3を作って渡す。

なぜ要るか（2026-09-26 たまごさん実測での突き返し）:
  前の版はブラウザの合成音声に逃げていた。だから「ずんだもんの声で読めない／
  ロボットボイス」になった。逃げ道を消す。声はVOICEVOXだけ。

やること:
  ・文を受けて、細かく切って、ずんだもんで1本ずつmp3にする
  ・1本目が出来た時点で渡す（全部出来るのを待たせない）
  ・#円卓会議 のノートは、すでに作ったmp3があればその場で渡す
  ・外からも使えるように、トンネル（localhost.run）越しに開ける

窓口:
  GET  /health                     生きているか
  POST /say     {"text": "..."}    文を読む
  POST /url     {"url": "..."}     URLの本文を読む
  GET  /notes                      #円卓会議 のノート一覧
  POST /note    {"q": "名前の一部"} ノートを読む（#円卓会議 のものだけ）
  GET  /job/<id>                   出来た数
  GET  /audio/<id>/<n>.mp3         音
どれも ?t=<合言葉> が要る。
"""
import io
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
REPO = os.path.join(HOME, "Desktop", "tamago-shinchoku")
VAULT = os.path.join(HOME, "Library", "Mobile Documents",
                     "iCloud~md~obsidian", "Documents", "tamago_brain")
VAULT_AUDIO = os.path.join(VAULT, "AI出力", "40_プロジェクト", "円卓会議🔥", "音声")
STATE = os.path.join(REPO, "status", "zunda")
NOTES_CACHE = os.path.join(STATE, "notes.json")
JOBS_DIR = "/tmp/zunda_jobs"
ENGINE = "http://127.0.0.1:50021"
SPEAKER = 3
CHUNK = 55
PORT = 50023
TOKEN_FILE = os.path.join(STATE, "token.txt")

JOBS = {}
LOCK = threading.Lock()


def log(msg):
    os.makedirs(STATE, exist_ok=True)
    with io.open(os.path.join(STATE, "server.log"), "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%F %T"), msg))


def token():
    os.makedirs(STATE, exist_ok=True)
    if not os.path.exists(TOKEN_FILE):
        with io.open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(uuid.uuid4().hex[:16])
    return io.open(TOKEN_FILE, encoding="utf-8").read().strip()


TOKEN = token()


# ---------- 声 ----------

def wav_of(text):
    q = urllib.parse.quote(text)
    req = urllib.request.Request(
        "%s/audio_query?text=%s&speaker=%d" % (ENGINE, q, SPEAKER), method="POST")
    query = urllib.request.urlopen(req, timeout=600).read()
    req2 = urllib.request.Request("%s/synthesis?speaker=%d" % (ENGINE, SPEAKER),
                                  data=query,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    return urllib.request.urlopen(req2, timeout=600).read()


def wav_to_mp3(wav_bytes, dest):
    import lameenc
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        pcm = r.readframes(r.getnframes())
        sr, ch = r.getframerate(), r.getnchannels()
    e = lameenc.Encoder()
    # 48kbps。24kHzモノラルの喋りには十分で、細い穴（トンネル）でも待たされない。
    e.set_bit_rate(48)
    e.set_in_sample_rate(sr)
    e.set_channels(ch)
    e.set_quality(5)
    with open(dest, "wb") as f:
        f.write(e.encode(pcm) + e.flush())


# ---------- 文の掃除 ----------

def clean(t):
    t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"!?\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", t)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^\s*[-=|:\s]{3,}$", "", t, flags=re.M)
    t = re.sub(r"[*_`>#|]+", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def chunks(text):
    out, buf = [], ""
    for p in re.split(r"(?<=[。！？\n])", text):
        s = p.strip()
        if not s:
            continue
        while len(s) > CHUNK * 2:            # 句点が無い長文も切る
            out.append(s[:CHUNK])
            s = s[CHUNK:]
        if len(buf) + len(s) > CHUNK:
            if buf:
                out.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        out.append(buf)
    return [c for c in out if re.search(r"[ぁ-んァ-ヶ一-龠a-zA-Z0-9]", c)]


# ---------- 仕事 ----------

def make_job(text, title=""):
    cs = chunks(clean(text))
    jid = uuid.uuid4().hex[:12]
    d = os.path.join(JOBS_DIR, jid)
    os.makedirs(d, exist_ok=True)
    with LOCK:
        JOBS[jid] = {"id": jid, "title": title, "chunks": len(cs),
                     "ready": 0, "done": False, "error": None,
                     "texts": cs, "at": time.time()}
    threading.Thread(target=worker, args=(jid,), daemon=True).start()
    log("注文 %s %d切れ %s" % (jid, len(cs), title[:40]))
    return JOBS[jid]


def worker(jid):
    j = JOBS[jid]
    d = os.path.join(JOBS_DIR, jid)
    for i, c in enumerate(j["texts"]):
        try:
            wav_to_mp3(wav_of(c), os.path.join(d, "%d.mp3" % i))
            with LOCK:
                j["ready"] = i + 1
        except Exception as e:
            with LOCK:
                j["error"] = str(e)[:200]
            log("失敗 %s %s" % (jid, e))
            break
    with LOCK:
        j["done"] = True
    log("できた %s %d/%d" % (jid, j["ready"], j["chunks"]))


def serve_ready_mp3(path, title):
    """すでに作ってあるmp3を1切れの仕事として渡す"""
    jid = uuid.uuid4().hex[:12]
    d = os.path.join(JOBS_DIR, jid)
    os.makedirs(d, exist_ok=True)
    with open(path, "rb") as r, open(os.path.join(d, "0.mp3"), "wb") as w:
        w.write(r.read())
    with LOCK:
        JOBS[jid] = {"id": jid, "title": title, "chunks": 1, "ready": 1,
                     "done": True, "error": None, "texts": [], "at": time.time()}
    return JOBS[jid]


# ---------- ノート ----------

_NL = {"at": 0, "v": []}


def note_list():
    # iCloud上で106回 exists を見ると何十秒もかかる（実測でページが固まった）。60秒だけ覚える。
    if time.time() - _NL["at"] < 60 and _NL["v"]:
        return _NL["v"]
    v = _note_list_slow()
    _NL["at"], _NL["v"] = time.time(), v
    return v


def _note_list_slow():
    try:
        notes = json.load(io.open(NOTES_CACHE, encoding="utf-8"))
    except Exception:
        notes = []
    out = []
    for rel in notes:
        st = re.sub(r"[\\/:*?\"<>|#\[\]]", "", os.path.basename(rel)[:-3])[:60].strip()
        mp3 = os.path.join(VAULT_AUDIO, "円卓音声_" + st + ".mp3")
        out.append({"rel": rel, "title": os.path.basename(rel)[:-3],
                    "ready": os.path.exists(mp3)})
    return out


def find_note(q):
    q = (q or "").strip()
    if q.startswith("obsidian://"):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(q).query)
            q = (qs.get("file") or [""])[0]
        except Exception:
            pass
    q = os.path.basename(q)
    if q.endswith(".md"):
        q = q[:-3]
    if not q:
        return None
    cands = note_list()
    for n in cands:
        if n["title"] == q:
            return n
    for n in cands:
        if q in n["title"]:
            return n
    return None


def fetch_url_text(u):
    try:
        req = urllib.request.Request("https://r.jina.ai/" + u,
                                     headers={"User-Agent": "zunda/1.0"})
        return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    except Exception:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
        html = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ",
                      html, flags=re.S | re.I)
        return re.sub(r"<[^>]+>", " ", html)


# ---------- HTTP ----------

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _ok_token(self, qs):
        return (qs.get("t") or [""])[0] == TOKEN

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/health":
            return self._json({"ok": True, "voice": "ずんだもん", "engine": engine_ok()})
        if not self._ok_token(qs):
            return self._json({"error": "合言葉が違う"}, 403)
        if u.path == "/notes":
            return self._json({"notes": note_list()})
        m = re.match(r"^/job/([0-9a-f]+)$", u.path)
        if m:
            j = JOBS.get(m.group(1))
            if not j:
                return self._json({"error": "その注文は無い"}, 404)
            return self._json({k: v for k, v in j.items() if k != "texts"})
        m = re.match(r"^/audio/([0-9a-f]+)/(\d+)\.mp3$", u.path)
        if m:
            p = os.path.join(JOBS_DIR, m.group(1), m.group(2) + ".mp3")
            if not os.path.exists(p):
                return self._json({"error": "まだ出来ていない"}, 404)
            b = open(p, "rb").read()
            # Chrome の <audio> は Range で少しずつ取りに来る。
            # 206 を返さないと読み込みが止まる（トンネル越しで実測）。
            rng = self.headers.get("Range")
            if rng:
                m2 = re.match(r"bytes=(\d*)-(\d*)", rng)
                s = int(m2.group(1) or 0)
                e = int(m2.group(2)) if m2.group(2) else len(b) - 1
                e = min(e, len(b) - 1)
                part = b[s:e + 1]
                self.send_response(206)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", "bytes %d-%d/%d" % (s, e, len(b)))
                self.send_header("Content-Length", str(len(part)))
                self._cors()
                self.end_headers()
                return self.wfile.write(part)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(b)))
            self._cors()
            self.end_headers()
            return self.wfile.write(b)
        return self._json({"error": "そんな窓口は無い"}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if not self._ok_token(qs):
            return self._json({"error": "合言葉が違う"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            body = {}
        try:
            if u.path == "/say":
                t = (body.get("text") or "").strip()
                if not t:
                    return self._json({"error": "文が空"}, 400)
                j = make_job(t, "貼られた文")
            elif u.path == "/url":
                url = (body.get("url") or "").strip()
                if not url:
                    return self._json({"error": "URLが空"}, 400)
                if url.startswith("obsidian://"):
                    return self._note(url)
                j = make_job(fetch_url_text(url), url)
            elif u.path == "/note":
                return self._note(body.get("q") or "")
            else:
                return self._json({"error": "そんな窓口は無い"}, 404)
        except Exception as e:
            return self._json({"error": str(e)[:300]}, 500)
        return self._json({k: v for k, v in j.items() if k != "texts"})

    def _note(self, q):
        n = find_note(q)
        if not n:
            return self._json({"error": "#円卓会議 のノートに見つからない"}, 404)
        st = re.sub(r"[\\/:*?\"<>|#\[\]]", "", os.path.basename(n["rel"])[:-3])[:60].strip()
        mp3 = os.path.join(VAULT_AUDIO, "円卓音声_" + st + ".mp3")
        if os.path.exists(mp3):
            j = serve_ready_mp3(mp3, n["title"])
        else:
            src = os.path.join(VAULT, n["rel"])
            j = make_job(io.open(src, encoding="utf-8", errors="ignore").read(), n["title"])
        return self._json({k: v for k, v in j.items() if k != "texts"})


def engine_ok():
    try:
        urllib.request.urlopen(ENGINE + "/version", timeout=3).read()
        return True
    except Exception:
        return False


def main():
    os.makedirs(JOBS_DIR, exist_ok=True)
    log("窓口を開けます :%d 合言葉=%s" % (PORT, TOKEN))
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
