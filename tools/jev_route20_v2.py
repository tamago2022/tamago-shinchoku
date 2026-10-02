#!/usr/bin/env python3
import json,pathlib,time,urllib.request
root=pathlib.Path.home()/"Desktop/tamago-shinchoku"
rows=[json.loads(x) for x in (root/"status/ai_daicho.jsonl").read_text().splitlines()[-20:]]
criteria={"AIで進める":"Continue/retry/reroute with AI; no human needed.","鬼監督へ":"A PR/result exists and independent verification is now the next step.","Founder判断":"Only new spend, irreversible major change, secrets/legal, fundamental brand change, or final human value judgment.","重複・閉じる候補":"Notification, duplicate, stale, superseded, or not an active task."}
qs={}
for i,x in enumerate(rows):
    event={k:x.get(k) for k in ["at","dir","ai","thread","topic","ok","err"]}
    qs[f"r{i:02d}"]={"type":"choice","instructions":{"event":event,"question":"What is the single best next route for this event under TAMAGO AI Company rules? If a PR is ready for review, choose 鬼監督へ. If it is merely an acknowledgement/status notification with no action needed, choose 重複・閉じる候補. Routine retry/reroute belongs to AIで進める. Founder only for true founder-only gates."},"criteria":criteria}
payload=json.dumps({"state":"Route recent AI-company events","model":"jev-latest","questions":qs},ensure_ascii=False).encode()
key=(pathlib.Path.home()/".config/typesafe/api_key").read_text().strip()
req=urllib.request.Request("https://api.typesafe.ai/v1/systemone",data=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
t=time.time()
with urllib.request.urlopen(req,timeout=30) as resp: out=json.load(resp)
res=[]
for i,x in enumerate(rows):
    a=out["answers"][f"r{i:02d}"]; res.append({"i":i,"topic":x.get("topic","")[:120],"choice":a.get("choice"),"confidence":a.get("confidence")})
(root/"status/jev_route20_v2_result.json").write_text(json.dumps({"model":out.get("model"),"usage":out.get("usage"),"elapsed":round(time.time()-t,3),"results":res},ensure_ascii=False,indent=2))
print("OK",len(res),out.get("usage"),round(time.time()-t,3))
