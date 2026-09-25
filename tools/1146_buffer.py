#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1146 Buffer をログイン無しで動かす口。

Buffer は 2026-05-27 に公開API・MCPサーバ・CLI を出し、全プラン（無料含む）で使える。
鍵は publish.buffer.com/settings/api で1回作るだけ。期限の記載は公式に無い。
出典: https://developers.buffer.com/guides/authentication.html

使い方:
    export BUFFER_API_KEY=...            # または ~/.tamago/keys/api_keys.env に書く
    python3 tools/1146_buffer.py channels
    python3 tools/1146_buffer.py post --channel <id> --text "本文" --at 2026-09-27T09:00:00+09:00
    python3 tools/1146_buffer.py post --channel <id> --text "本文" --dry-run

--dry-run は1バイトも送らず、送る中身だけを出す（鍵は伏せる）。
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_kata  # noqa: E402  ★1153番【Xの投稿の型】URLを必ず一番最後に置く係

API = "https://api.buffer.com"
ENVFILE = os.path.expanduser("~/.tamago/keys/api_keys.env")


def get_key() -> str:
    k = os.environ.get("BUFFER_API_KEY")
    if k:
        return k.strip()
    if os.path.exists(ENVFILE):
        with open(ENVFILE, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip().startswith("BUFFER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("BUFFER_API_KEY が無い。publish.buffer.com/settings/api で1回だけ作って "
             "~/.tamago/keys/api_keys.env に BUFFER_API_KEY= で入れる。")


def gql(query: str, variables=None, dry=False):
    body = {"query": query, "variables": variables or {}}
    if dry:
        print("POST " + API)
        print("Authorization: Bearer ****（伏せた）")
        print("Content-Type: application/json")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return None
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + get_key(),
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read().decode())
    if out.get("errors"):
        sys.exit("Buffer が断った: " + json.dumps(out["errors"], ensure_ascii=False))
    return out["data"]


Q_ACCOUNT = "{ account { id email organizations { id name } } }"
Q_CHANNELS = """query($org:String!){ channels(organizationId:$org){
  edges{ node{ id name service type } } } }"""
M_POST = """mutation($in:CreatePostInput!){ createPost(input:$in){
  ... on Post { id status text dueAt } } }"""


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("account")
    c = sub.add_parser("channels"); c.add_argument("--org")
    p = sub.add_parser("post")
    p.add_argument("--channel", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--at", help="ISO8601（例 2026-09-27T09:00:00+09:00）。無ければ列の末尾")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.cmd == "account":
        print(json.dumps(gql(Q_ACCOUNT), ensure_ascii=False, indent=2))
    elif a.cmd == "channels":
        org = a.org or gql(Q_ACCOUNT)["account"]["organizations"][0]["id"]
        print(json.dumps(gql(Q_CHANNELS, {"org": org}), ensure_ascii=False, indent=2))
    else:
        # ★1153番【Xの投稿の型】ここがBufferへ渡る最後の扉。
        #   URLが末尾でないと、Xはカードを出した上に本文のURLの文字列も残す＝「リンクが2回」。
        #   だから言葉は1文字も変えず、URLの行だけ一番最後へ動かしてから渡す。
        #   出典: status/X_TOUKOU_KATA.md
        text = x_kata.normalize(a.text)
        if text != a.text:
            print("★型で直した（URLを一番最後へ動かした・1153番）", file=sys.stderr)
        if not x_kata.check(text):
            sys.exit("★型に合わない本文を止めた（末尾がURLでない）。status/X_TOUKOU_KATA.md を見る")
        inp = {"channelId": a.channel, "schedulingType": "automatic",
               "text": text,
               "mode": "customScheduled" if a.at else "addToQueue"}
        if a.at:
            inp["dueAt"] = a.at
        if a.draft:
            inp["saveToDraft"] = True
        out = gql(M_POST, {"in": inp}, dry=a.dry_run)
        if out:
            print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
