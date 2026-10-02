#!/usr/bin/env python3
import json, pathlib, time, urllib.request
root=pathlib.Path.home()/"Desktop/tamago-shinchoku"
rows=[]
for line in (root/"status/ai_daicho.jsonl").read_text().splitlines()[-20:]:
    x=json.loads(line); rows.append({k:x.get(k) for k in ["at","dir","ai","thread","topic","ok","err"]})
criteria={
 "AIで進める":"Human decision is unnecessary; continue, retry, reroute, or implement with AI.",
 "鬼監督へ":"Work/PR/result exists and independent QA or verification is the next step.",
 "Founder判断":"Only new spend, irreversible major change, secrets/legal, fundamental brand change, or final human value judgment.",
 "重複・閉じる候補":"This is duplicate, stale, superseded, or merely a notification that should not remain an active task."
}
qs={}
for i in range(len(rows)):
    qs[f"r{i:02d}"]={"type":"choice","instructions":f"Choose the next route for state[{i}] under TAMAGO AI Company rules. Do not escalate routine AI work to Founder.","criteria":criteria}
payload=json.dumps({"state":rows,"model":"jev-latest","questions":qs},ensure_ascii=False).encode()
key=(pathlib.Path.home()/".config/typesafe/api_key").read_text().strip()
req=urllib.request.Request("https://api.typesafe.ai/v1/systemone",data=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
t0=time.time()
with urllib.request.urlopen(req,timeout=30) as resp: out=json.load(resp)
out["_elapsed_sec"]=round(time.time()-t0,3)
result=[]
for i,row in enumerate(rows):
    a=out["answers"][f"r{i:02d}"]
    result.append({"i":i,"at":row["at"],"ai":row["ai"],"topic":row["topic"][:120],"choice":a.get("choice"),"confidence":a.get("confidence")})
(root/"status/jev_route20_result.json").write_text(json.dumps({"model":out.get("model"),"usage":out.get("usage"),"elapsed":out["_elapsed_sec"],"results":result},ensure_ascii=False,indent=2))
print("OK",len(result),out.get("model"),out.get("usage"),out["_elapsed_sec"])
