#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Buffer API で予約投稿を作る道具（jsonl → 予約／下書き）。

入力 jsonl（1行1件）: {"text": "...", "scheduled_at": "2026-10-08 21:00", "channel": "oasisjoyrelief"}
  scheduled_at は JST。channel は name / displayName / service(例: twitter) のどれか。

使い方:
  python3 tools/buffer_api_post.py --channels            # 読むだけ：組織・チャンネル一覧
  python3 tools/buffer_api_post.py in.jsonl              # dry-run（既定）：Bufferを叩かず計画だけ表示
  python3 tools/buffer_api_post.py in.jsonl --go         # 実投入（予約。二重投稿の関所を通る）
  python3 tools/buffer_api_post.py in.jsonl --draft      # 下書き保存（公開されない）。--go 併用で実行

鍵は tools/kagi.py 経由のみ。値は表示しない。叩く前の枠の門（buffer_waku／buffer_kura）は
buffer_yoyaku.gql をそのまま使う＝新しいBuffer叩きは作らない。
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import buffer_yoyaku as by

M_DRAFT = """
mutation CreateDraft($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id text status channelId dueAt } }
    ... on MutationError { message }
  }
}
"""
Q_DRAFTS = """
query GetDrafts($orgId: OrganizationId!, $channelIds: [ChannelId!]) {
  posts(input: { organizationId: $orgId, filter: { status: [draft], channelIds: $channelIds } }) {
    edges { node { id text status dueAt channelId } }
  }
}
"""


def load_channels(tok):
    orgs = (((by.gql(tok, by.Q_ORGS).get("data") or {}).get("account") or {})
            .get("organizations") or [])
    chans = []
    for o in orgs:
        for c in (by.gql(tok, by.Q_CHANNELS, {"orgId": o["id"]}).get("data") or {}).get("channels") or []:
            c["_org"] = o["id"]
            chans.append(c)
    return orgs, chans


def find_channel(chans, want):
    w = (want or "").lstrip("@").lower()
    for c in chans:
        if w in by.names_of(c) or w == (c.get("service") or "").lower():
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="?")
    ap.add_argument("--channels", action="store_true")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    if a.jsonl and not a.go and not a.channels:
        # dry-run：鍵に触らず、Bufferも叩かない。入力の形だけ検査して計画を出す
        for i, l in enumerate([l for l in open(a.jsonl, encoding="utf-8") if l.strip()], 1):
            r = json.loads(l)
            miss = [k for k in ("text", "channel") if not r.get(k)] + ([] if a.draft or r.get("scheduled_at") else ["scheduled_at"])
            if not a.draft and r.get("scheduled_at"):
                by.due_utc_iso(r["scheduled_at"])
            print("[%d] %s → %s : %s %s" % (i, "下書き" if a.draft else "予約 %s JST" % r.get("scheduled_at"), r.get("channel"), (r.get("text") or "")[:40].replace("\n", " "), ("【不足: %s】" % ",".join(miss)) if miss else "OK"))
        print("dry-run：Bufferは叩いていません（実投入は --go）")
        return 0
    tok = by.token()
    if not tok:
        print("鍵なし（tools/kagi.py に BUFFER_ACCESS_TOKEN が無い）"); return 2
    if a.channels or not a.jsonl:
        orgs, chans = load_channels(tok)
        print("組織 %d / チャンネル %d" % (len(orgs), len(chans)))
        for c in chans:
            print("  %s | %s | %s | paused=%s" % (c.get("service"), c.get("name"), c.get("displayName"), c.get("isQueuePaused")))
        return 0
    rows = [json.loads(l) for l in open(a.jsonl, encoding="utf-8") if l.strip()]
    orgs, chans = (load_channels(tok) if (a.go or True) else (None, None))
    rc = 0
    mons = {}
    for i, r in enumerate(rows, 1):
        ch = find_channel(chans, r.get("channel"))
        if not ch:
            print("[%d] チャンネルなし: %s" % (i, r.get("channel"))); rc = 1; continue
        mode = "下書き" if a.draft else "予約 %s JST" % r.get("scheduled_at")
        print("[%d] %s → %s/%s : %s" % (i, mode, ch.get("service"), ch.get("name"), (r["text"] or "")[:40].replace("\n", " ")))
        if not a.go:
            continue
        inp = {"text": r["text"], "channelId": ch["id"], "assets": [],
               "needsApproval": False, "schedulingType": "automatic"}
        if a.draft:
            inp.update({"mode": "addToQueue", "saveToDraft": True})
        else:
            due_iso, _ = by.due_utc_iso(r["scheduled_at"])
            import buffer_sekisho
            if ch["id"] not in mons:
                mons[ch["id"]] = buffer_sekisho.Mon(lambda q, v=None: by.gql(tok, q, v))
                mons[ch["id"]].load(ch["_org"], ch["id"])   # 1チャンネル1回だけ読む（叩く数を節約）
            mon = mons[ch["id"]]
            ok, why = mon.tsukaeru(r["text"], due_iso)
            if not ok:
                print("   二重投稿の関所で止めた: %s" % why); rc = 1; continue
            inp.update({"mode": "customScheduled", "dueAt": due_iso})
        res = by.gql(tok, M_DRAFT, {"input": inp})
        cp = (res.get("data") or {}).get("createPost") or {}
        if cp.get("message") or res.get("errors"):
            print("   失敗: %s" % (cp.get("message") or str(res.get("errors"))[:200])); rc = 1; continue
        p = cp.get("post") or {}
        print("   登録 id=%s status=%s due=%s" % (p.get("id"), p.get("status"), p.get("dueAt")))
        if not a.draft:
            mon.kiroku(r["text"], due_iso, p.get("id"), "api_post")
        time.sleep(1)
        if a.draft:
            q = by.gql(tok, Q_DRAFTS, {"orgId": ch["_org"], "channelIds": [ch["id"]]})
            ed = (((q.get("data") or {}).get("posts") or {}).get("edges")) or []
            hit = [e["node"] for e in ed if e["node"]["id"] == p.get("id")]
            print("   読み戻し: %s" % ("一致" if hit and by.norm(hit[0]["text"]) == by.norm(r["text"]) else "不一致/見つからず"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
