#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""98403番：Lovable MCP の deploy_project（＝「公開」）をブラウザ無しで押す。
チャット／エージェント／ビルド修正／コード編集は一切呼ばない。公開だけ。
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, "/Users/mac/tamago/tamago-shinchoku/tools")
import lovable_token_keeper as keeper  # noqa: E402

PROJECT_ID = "8ebdb648-3686-4457-b42c-d01c493793b1"
TOKEN = os.path.expanduser("~/.tamago/lovable_oauth.json")
LOG = "/private/tmp/q98403/lovable_mcp.log"


def log(m):
    line = "%s %s" % (time.strftime("%F %T"), m)
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    r = keeper.ensure_fresh()
    log("token keeper: %s" % r)
    tok = json.load(open(TOKEN))
    at = tok.get("access_token")
    if not at:
        log("access_token が無い")
        return 2
    sid = {"v": None}
    counter = [0]

    def mcp(method, params=None):
        counter[0] += 1
        pl = json.dumps({"jsonrpc": "2.0", "id": counter[0], "method": method, "params": params or {}}).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + at,
        }
        if sid["v"]:
            headers["Mcp-Session-Id"] = sid["v"]
        req = urllib.request.Request("https://mcp.lovable.dev", data=pl, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                s = resp.headers.get("Mcp-Session-Id")
                if s:
                    sid["v"] = s
                return resp.status, resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "ignore")[:600]
        except Exception as e:
            return 0, "ERR %r" % (e,)

    st, body = mcp("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tamago-98403", "version": "1"}})
    log("initialize http=%s %s" % (st, body[:200].replace("\n", " ")))
    if st != 200:
        return 3
    st, body = mcp("tools/list")
    names = []
    for chunk in body.split("\n"):
        chunk = chunk.strip()
        if chunk.startswith("data:"):
            chunk = chunk[5:].strip()
        if not chunk.startswith("{"):
            continue
        try:
            d = json.loads(chunk)
        except Exception:
            continue
        for t in (d.get("result") or {}).get("tools") or []:
            names.append(t.get("name"))
    log("tools/list http=%s names=%s" % (st, names))
    if "deploy_project" not in names:
        log("deploy_project が無い。公開は押せない（他の道具は呼ばない）")
        return 4
    if "--dry-run" in sys.argv:
        log("dry-run：押さない")
        return 0
    st, body = mcp("tools/call", {"name": "deploy_project", "arguments": {"project_id": PROJECT_ID}})
    log("deploy_project http=%s %s" % (st, body[:800].replace("\n", " ")))
    return 0 if st == 200 else 5


if __name__ == "__main__":
    sys.exit(main())
