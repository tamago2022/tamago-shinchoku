#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【魂の口・HTTPの窓口】サーバーから叩く脳（webhook型の道具）のための扉。

  ブラウザの中で鳴る脳は tamashii/kuchi.mjs を直接読めばよい（住所もお金も要らない）。
  ただし ElevenAgents の「サーバー側の道具（webhook tool）」のように、
  **向こうから叩きに来る**形の脳もある。そのための窓口がこれ。

  ★AIを1回も呼ばない。★1円もかからない。★標準ライブラリだけ（入れるものは何も無い）。

      python3 tamashii/server.py            # 127.0.0.1:8787
      python3 tamashii/server.py --port 9000
      python3 tamashii/server.py --self-test # ★実際に叩いて200が返るか確かめる

  叩き方（3つとも同じ形）:
      POST /osusume    {"konomi":["久保田利伸","犬"],"hito":"seki-7"}
      POST /shiraberu  {"go":"久保田"}
      POST /jinkaku    {}
      GET  /tools?hougen=elevenlabs        … 脳に貼る関数定義
      GET  /kenko                          … 生きているか

  ★この窓口は鍵を1本も持たない。誰の鍵も要求しない。持っているのは魂だけ。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuchi  # noqa: E402

PORT = 8787


class Mado(BaseHTTPRequestHandler):
    def _out(self, code: int, body: dict):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._out(200, {"ok": True})

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/kenko":
            kuchi._load()
            return self._out(200, {"ok": True, "artists": len(kuchi._soul["artists"]), "kuchi": list(kuchi.FUNCS)})
        if p.path == "/tools":
            q = urllib.parse.parse_qs(p.query)
            hougen = (q.get("hougen") or ["realtime"])[0]
            t = kuchi.tools_json()
            if hougen not in t:
                return self._out(400, {"ok": False, "error": f"知らない方言: {hougen}", "aru": [k for k in t if not k.startswith('_') and k != 'tsukutta']})
            return self._out(200, {"ok": True, "hougen": hougen, "tools": t[hougen]})
        if p.path in ("/", "/kuchi"):
            return self._out(200, {"ok": True, "kuchi": list(kuchi.FUNCS), "tsukaikata": "POST /osusume など"})
        self._out(404, {"ok": False, "error": f"そんな窓口はない: {p.path}"})

    def do_POST(self):
        name = urllib.parse.urlparse(self.path).path.lstrip("/")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            args = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._out(400, {"ok": False, "error": f"中身が読めない: {e}"})
        r = kuchi.call(name, args if isinstance(args, dict) else {})
        self._out(200 if r.get("ok") else 400, r)

    def log_message(self, *a):  # 黙る（鍵も中身もログに残さない）
        pass


def run(port: int = PORT):
    kuchi._load()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Mado)
    print(f"魂の口：http://127.0.0.1:{port}  （{len(kuchi._soul['artists'])}人・口は {', '.join(kuchi.FUNCS)}）")
    srv.serve_forever()


def self_test() -> int:
    """★叩いて確かめる。立てて、実際にHTTPで3つとも呼んで、200を見る。"""
    ng = []
    kuchi._load()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mado)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def tataku(path, body=None):
        req = urllib.request.Request(
            base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())

    try:
        for path, body in [
            ("/kenko", None),
            ("/osusume", {"konomi": ["久保田利伸", "犬"], "hito": "seki-7"}),
            ("/shiraberu", {"go": "久保田"}),
            ("/jinkaku", {}),
        ]:
            code, r = tataku(path, body)
            if code != 200 or not r.get("ok"):
                ng.append(f"{path} が通らない: {code}")
            else:
                print(f"  ○ {'POST' if body is not None else 'GET '} {base}{path} → {code}")
        for hougen in ("openai", "realtime", "elevenlabs", "gemini"):
            code, r = tataku(f"/tools?hougen={hougen}")
            if code != 200:
                ng.append(f"/tools?hougen={hougen} が通らない: {code}")
            else:
                print(f"  ○ GET  {base}/tools?hougen={hougen} → 200")
    finally:
        srv.shutdown()

    for line in ng:
        print("✕", line)
    if not ng:
        print("○ HTTPの窓口：3つの口＋4方言、全部200（実際に叩いた）")
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    p = PORT
    if "--port" in sys.argv:
        p = int(sys.argv[sys.argv.index("--port") + 1])
    run(p)
