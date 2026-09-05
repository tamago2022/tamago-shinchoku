#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""進捗表（スマホ）→ Mac への中継所。

2026-09-04 たまごさんの言葉：
  「これ付けてくれたのはいいんだけれども、**Obsidianに飛んじゃうよ。
    Obsidianに飛ぶというアクションは、この進捗表ではもうありえないから。**」

これまでPWAのボタンは `obsidian://new` を開いてVault経由でMacへ渡していた。
確実ではあるが、押すたびにObsidianアプリへ画面が切り替わる。たまごさんはこれを全面禁止した。

そこで、Mac側に小さな受け口（このサーバー）を立て、PWAから直接HTTPSで受ける。
外から届くようにするのは cloudflared のクイックトンネル（アカウント不要）で、
払い出されたURLを status/relay.json に書き、PWAがそれを読んで送り先にする。

  PWA ──HTTPS──▶ trycloudflare.com ──▶ このサーバー ──▶ command_ingest.process()

受け付ける中身は command_ingest.py と同じ（queue_ok / queue_later / queue_redo /
queue_prio / queue_add / priority_set / resume / stop / close_app / handoff）。
それ以外は弾く。キューの並び替え以上のことはできないので、URLが漏れても被害は小さい。
"""
import io
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import command_ingest  # noqa: E402

ALLOWED = {
    "queue_ok", "queue_later", "queue_redo", "queue_prio", "queue_add", "queue_pause", "queue_delete", "queue_order",
    "priority_set", "resume", "stop", "close_app", "handoff", "launch_pause", "launch_resume", "launch_cap", "git_unlock", "push_unlock",
}
ORIGIN = "https://tamago2022.github.io"
LOG = os.path.join(REPO, "status", "relay.log")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def apply_priority(payload):
    """PWAが持っている優先度の全体像をそのまま受け取り、priority.json へ反映する。

    PWA側は {"T001":{"p":1,"t":"..."}, "Q37":{"p":2,...}} の形で持っている。
    Q付き（発車待ち）は queue.json の item.priority へ、それ以外は priority.json へ。
    """
    try:
        prio = json.loads(payload)
    except Exception:
        return "failed", "優先度の中身が読めません"
    qn, tn = 0, 0
    for k, v in (prio or {}).items():
        p = int((v or {}).get("p") or 0)
        if str(k).startswith("Q"):
            try:
                command_ingest.queue_prio("%s:%d" % (str(k)[1:], p))
                qn += 1
            except Exception:
                pass
        else:
            tn += 1
    if tn:
        path = os.path.join(REPO, "status", "priority.json")
        try:
            d = json.load(io.open(path, encoding="utf-8"))
        except Exception:
            d = {}
        d.setdefault("priority", {})
        d.setdefault("stamps", {})
        for k, v in (prio or {}).items():
            if str(k).startswith("Q"):
                continue
            p = int((v or {}).get("p") or 0)
            if p:
                d["priority"][k] = p
                d["stamps"][k] = (v or {}).get("t") or ""
            else:
                d["priority"].pop(k, None)
        d["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        d["source"] = "進捗表（中継所経由）"
        json.dump(d, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return "done", "優先度を反映しました（発車待ち%d件・依頼%d件）" % (qn, tn)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        # 2026-09-05 **進捗表そのものをMacから配る。**
        #   トンネル（cloudflared / localtunnel）は、たまごさんの回線では張れたり切れたりを
        #   繰り返し、そのたびURLが変わって進捗表が迷子になった（10:15〜10:39に5回変わった）。
        #   家のWi-Fiの中なら、トンネルを通さずMacへ直接届く。**遅れゼロ・切れない・URLも変わらない。**
        #   ここは http なので、同じ http のこのページから読む限り混在コンテンツにもならない。
        if self.path in ("/", "/index.html") or self.path.startswith("/?"):
            try:
                with io.open(os.path.join(REPO, "index.html"), "rb") as f:
                    body = f.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})
        # 2026-09-05 たまごさん「ブラウザ探すのが面倒くさい。ホーム画面でできるようにして」
        #   → アイコンと manifest も配る。これでホーム画面に足せば、アプリのように一発で開ける。
        for name, ct in (("manifest.webmanifest", "application/manifest+json"),
                         ("apple-touch-icon.png", "image/png"),
                         ("icon-192.png", "image/png"),
                         ("icon-512.png", "image/png"),
                         ("favicon.ico", "image/x-icon"),
                         ("sw.js", "text/javascript")):
            if self.path.split("?")[0] == "/" + name:
                p = os.path.join(REPO, name)
                if not os.path.exists(p):
                    return self._json(404, {"ok": False})
                try:
                    with io.open(p, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self._cors()
                    self.send_header("Content-Type", ct)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    return self.wfile.write(body)
                except Exception as e:
                    return self._json(500, {"ok": False, "error": str(e)})
        # 進捗表が「status/なんとか.json」を相対パスで読むので、そのまま返せるようにする
        if self.path.startswith("/status/"):
            name = self.path[len("/status/"):].split("?")[0]
            if "/" not in name and ".." not in name:
                p = os.path.join(REPO, "status", name)
                if os.path.exists(p):
                    try:
                        with io.open(p, "rb") as f:
                            body = f.read()
                        self.send_response(200)
                        self._cors()
                        ct = "application/json" if name.endswith(".json") else "text/plain; charset=utf-8"
                        self.send_header("Content-Type", ct)
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        return self.wfile.write(body)
                    except Exception as e:
                        return self._json(500, {"ok": False, "error": str(e)})
            return self._json(404, {"ok": False})
        # 2026-09-05 たまごさん「押しても動かない、完了に入らない、後に回らない」
        #   原因：押した結果はMacにちゃんと届いていた（記録あり）が、画面が読んでいた台帳は
        #   GitHub Pages側の**公開済みコピー**で、公開は5分以上遅れる。
        #   そのため押した直後に画面が古い状態へ戻り、何度も押すことになっていた。
        #   → 中継所からMacの**生の台帳**をそのまま返す。押した瞬間に画面へ反映される。
        for name, path in (("/queue", "queue.json"), ("/machine", "machine.json"),
                           ("/quota", "quota.json"), ("/commands", "commands.json")):
            if self.path.startswith(name):
                try:
                    with io.open(os.path.join(REPO, "status", path), encoding="utf-8") as f:
                        return self._json(200, json.load(f))
                except Exception as e:
                    return self._json(500, {"ok": False, "error": str(e)})
        return self._json(404, {"ok": False})

    def do_POST(self):
        if not self.path.startswith("/cmd"):
            return self._json(404, {"ok": False})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return self._json(400, {"ok": False, "error": "本文が読めません"})
        results = []
        for cmd in (data.get("commands") or [])[:50]:
            action = cmd.get("action")
            if action not in ALLOWED:
                results.append({"id": cmd.get("id"), "status": "failed", "message": "使えない指示: %s" % action})
                continue
            try:
                if action == "priority_set":
                    st, msg = apply_priority(cmd.get("target"))
                elif action == "queue_add":
                    st, msg = command_ingest.queue_add(cmd.get("target"), cmd.get("priority"))
                else:
                    st, msg = command_ingest.process(cmd)
            except Exception as e:
                st, msg = "failed", "エラー: %s" % e
            log("%s %s → %s / %s" % (action, cmd.get("target"), st, msg))
            results.append({"id": cmd.get("id"), "status": st, "message": msg})
        # 進捗表が結果を読めるように commands.json へも残す
        try:
            p = os.path.join(REPO, "status", "commands.json")
            try:
                d = json.load(io.open(p, encoding="utf-8"))
            except Exception:
                d = {"results": []}
            for r in results:
                r2 = dict(r)
                r2["doneAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                d["results"].append(r2)
            d["results"] = d["results"][-200:]
            json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
        return self._json(200, {"ok": True, "results": results})

    def log_message(self, *a):
        pass


def main():
    port = int(os.environ.get("RELAY_PORT") or 8788)
    log("中継所を起動 port=%d" % port)
    # 2026-09-05 127.0.0.1 だと**Mac自身からしか届かない。**
    #   たまごさんはスマホで進捗表を見るので、家のWi-Fiの中から直接届くよう 0.0.0.0 で待つ。
    #   外（インターネット）からは家のルータが遮るので、開くのは家の中だけ。
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
