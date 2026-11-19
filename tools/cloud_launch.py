#!/usr/bin/env python3
"""クラウド(Claude Code on the web)へ仕事を1行で投げるための「発射本文」を作る。
使い方: python3 tools/cloud_launch.py <名前> <依頼文ファイル> [リポURL] [--run]
  既定リポ: https://github.com/tamago2022/joy-relief-station / 環境: env_01ViUZRqammQGqTudwQ68AwN
出力: RemoteTrigger(action=create) にそのまま渡せるJSON本文（今+2分の1回限り実行）。
送信: Macの `claude --cloud` は推論専用ログインで403のため、デスクトップ版Claude Codeの RemoteTrigger を使う。
      （トークンは道具の内部でだけ使われ、シェルには出ない）
回収: RemoteTrigger(list_runs, trigger_id) でセッションURL、get_run_log で最終発言(=PRのURL)を読む。
重要(2026-10-08の教訓): クラウドは対象リポの .claude/settings.json をそのまま読む。
  joy-relief-station の settings は allow に載っていないコマンド(npm install・node・npx tsx・&や()を含む複合)を
  「承認待ち」にするため、無人のクラウドでは誰も押せず無言で止まる(10/1の①②がABANDONED、10/8の③もrequires_action)。
  直すには、そのリポの .claude/settings.json の allow にクラウドで要るコマンドを足してmainへ入れる(要・店主判断)。
"""
import json, sys, datetime, uuid
args=[a for a in sys.argv[1:] if not a.startswith('--')]
name, pf = args[0], args[1]
repo = args[2] if len(args)>2 else "https://github.com/tamago2022/joy-relief-station"
env = "env_01ViUZRqammQGqTudwQ68AwN"
prompt = open(pf, encoding="utf-8").read()
at = (datetime.datetime.utcnow()+datetime.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:00Z")
ev = {"data":{"message":{"content":prompt,"role":"user"},"parent_tool_use_id":None,"session_id":"","type":"user","uuid":str(uuid.uuid4())}}
print(json.dumps({"name":name,"run_once_at":at,"enabled":True,
  "job_config":{"ccr":{"environment_id":env,"events":[ev],
  "session_context":{"model":"claude-sonnet-5-5","sources":[{"git_repository":{"url":repo}}]}}}}, ensure_ascii=False))
