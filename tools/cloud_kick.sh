#!/bin/bash
# クラウドセッション起動用の本文(JSON)を作る。使い方: tools/cloud_kick.sh <GitHubリポURL> <名前> <依頼文ファイル>
# 実際の送信は Claude Code の RemoteTrigger(action:"create", body=この出力) で行う。
# 理由: Macの `claude --cloud` は推論専用ログインで403。デスクトップアプリ側の正式ログインのトークンは RemoteTrigger だけが内部で使える（トークンはシェルに出ない）。
# run_once_at は「今+3分」。環境ID: env_01ViUZRqammQGqTudwQ68AwN
repo="$1"; name="$2"; pf="$3"
at=$(date -u -v+3M +%Y-%m-%dT%H:%M:%SZ)
python3 - "$repo" "$name" "$pf" "$at" <<'P'
import json,sys,uuid
repo,name,pf,at=sys.argv[1:5]
print(json.dumps({"name":name,"run_once_at":at,"enabled":True,"job_config":{"ccr":{"environment_id":"env_01ViUZRqammQGqTudwQ68AwN","session_context":{"model":"claude-sonnet-5-5","sources":[{"git_repository":{"url":repo}}],"allowed_tools":["Bash","Read","Write","Edit","Glob","Grep"]},"events":[{"data":{"uuid":str(uuid.uuid4()),"session_id":"","type":"user","parent_tool_use_id":None,"message":{"role":"user","content":open(pf).read()}}}]}}},ensure_ascii=False))
P
