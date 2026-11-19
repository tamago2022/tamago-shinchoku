#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鍵の受け口（Macの中だけで開く入力ページ）。2026-10-05・たまごさん「チャットに貼らせない」。

  127.0.0.1 の1ページ。貼って「保存」→ 鍵の置き場(kagi.put＝ポストが有効ならキーチェーン、まだなら api_keys.env 600)へ入る → ページを閉じる。
  ・URL の末尾は毎回ランダムの合言葉（他のプログラム・他のタブが勝手に送れない）。Host/Origin も確認。
  ・入れる前に、その鍵が本物か公式APIで1回確かめる（違う鍵・違うチームは入れない）。値は表示も記録もしない。
  ・1回入ったら自分で終了。放置しても 24 時間で終了。

使い方:
    python3 tools/kagi_uketsukeguchi.py xai_management      # xAI 管理用キー（XAI_MANAGEMENT_KEY）
"""
import html
import http.server
import json
import os
import secrets
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kagi  # noqa: E402

ZERO_TEAM = "3e0b4d97-4d0d-458e-9f22-8758b9d65f2b"   # goodvibes（残高0・停止済み）。この鍵は入れない

KINDS = {
    "xai_management": {
        "title": "xAI 管理用キー（Management Key）",
        "name": "XAI_MANAGEMENT_KEY",
        "help": "console.x.ai → 10ドルを入れた方のチーム → Settings → Management Keys で1本作り、ここに貼ります（読み取りだけで足ります）。",
    },
}


def verify_xai_management(value):
    """(OK?, メッセージ, teamId)。値は書かない。"""
    req = urllib.request.Request("https://management-api.x.ai/auth/management-keys/validation",
                                 headers={"Authorization": "Bearer " + value, "User-Agent": "tamago-uketsukeguchi/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return False, "管理用キーとして通りませんでした（HTTP %d）。キーを作り直して、もう一度貼ってください。" % e.code, None
    except Exception:
        return False, "xAIに繋がりませんでした。少し待ってからもう一度。", None
    team = d.get("teamId") or (d.get("data") or {}).get("teamId")
    if team == ZERO_TEAM:
        return False, "これは残高0の方のチームの鍵です。10ドルを入れた方のチームで作り直してください。", team
    return True, "確認できました", team


VERIFY = {"xai_management": verify_xai_management}

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>鍵の受け口</title>
<style>body{font:18px/1.7 -apple-system,sans-serif;max-width:620px;margin:8vh auto;padding:0 20px;color:#222}
input[type=password]{width:100%%;font-size:18px;padding:12px;margin:12px 0;box-sizing:border-box}
button{font-size:18px;padding:12px 28px}small{color:#666}</style>
<h2>%(title)s</h2><p>%(help)s</p>
<form method=post action="%(action)s" autocomplete=off>
<input type=password name=key autofocus autocomplete=off placeholder="ここに貼る" required>
<button>保存</button></form>
<p><small>この画面はこのMacの中だけです。貼った鍵は表示も記録もされず、保存したらこのページは閉じます。</small></p>"""


def run(kind):
    spec = KINDS[kind]
    token = secrets.token_urlsafe(18)
    done = threading.Event()
    result = {"ok": False}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_host(self):
            return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if not self._ok_host() or self.path != "/" + token:
                return self._send(404, "not found")
            self._send(200, PAGE % {"title": html.escape(spec["title"]), "help": html.escape(spec["help"]),
                                    "action": "/" + token + "/save"})

        def do_POST(self):
            if not self._ok_host() or self.path != "/%s/save" % token:
                return self._send(404, "not found")
            origin = self.headers.get("Origin", "")
            if origin and origin.split("://")[-1].split(":")[0] not in ("127.0.0.1", "localhost"):
                return self._send(403, "forbidden")
            n = min(int(self.headers.get("Content-Length", "0") or 0), 4096)
            form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "ignore"))
            val = (form.get("key", [""])[0]).strip().strip('"').strip("'")
            if len(val) < 20 or any(c.isspace() for c in val):
                return self._send(200, "<meta charset=utf-8><p>鍵の形が違うようです。もう一度貼ってください。<p><a href='/%s'>戻る</a>" % token)
            ok, msg, team = VERIFY[kind](val)
            if not ok:
                return self._send(200, "<meta charset=utf-8><p>%s<p><a href='/%s'>戻る</a>" % (html.escape(msg), token))
            try:
                kagi.put(spec["name"], val)
            except Exception:
                return self._send(200, "<meta charset=utf-8><p>保存に失敗しました（値は残っていません）。もう一度試してください。")
            val = None
            result.update(ok=True, team=team)
            self._send(200, "<meta charset=utf-8><body style='font:20px sans-serif;padding:60px'>入りました。このページは閉じて大丈夫です。")
            done.set()

    port = 41777
    while True:
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            break
        except OSError:
            port += 1
    url = "http://127.0.0.1:%d/%s" % (port, token)
    out = os.path.join(REPO, "status", "kagi_uketsukeguchi_url.json")
    json.dump({"kind": kind, "url": url, "at": time.strftime("%F %T")}, open(out, "w"), ensure_ascii=False)
    os.chmod(out, 0o600)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(url, flush=True)
    done.wait(24 * 3600)
    time.sleep(1)
    srv.shutdown()
    try:
        os.remove(out)
    except Exception:
        pass
    if result["ok"] and kind == "xai_management":   # 入ったらすぐ残高を取って台帳へ
        subprocess.Popen([sys.executable, os.path.join(HERE, "xai_zandaka_yoru.py"), "--now"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == "__main__":
    k = sys.argv[1] if len(sys.argv) > 1 else ""
    if k not in KINDS:
        print(__doc__)
        sys.exit(2)
    run(k)
