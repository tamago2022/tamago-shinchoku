#!/usr/bin/env python3
import json,pathlib,urllib.request,time,collections
R=pathlib.Path.home()/"Desktop/tamago-shinchoku"
q=json.load(open(R/"status/queue.json"))
items=[x for x in q.get("items",[]) if x.get("status")=="waiting"][:50]
criteria={
"今やる":"工場を止めない、再発防止、現在の不具合、Founder負担削減、売上/顧客体験に直結。",
"次にやる":"重要だが、工場復旧や現在の不具合の後でよい。",
"後回し":"1か月後でも3か月後でも損失が小さい改善・研究・装飾・将来案。",
"止める候補":"重複、古い自動タスク、目的を失ったもの、既に別案件で解決済みの可能性が高い。",
"Founder判断":"新規支出・契約・不可逆重大変更・秘密法務・ブランド根幹・最終価値判断だけ。"
}
key=(pathlib.Path.home()/".config/typesafe/api_key").read_text().strip()
rows=[]; total_tokens=0; t0=time.time()
for base in range(0,len(items),10):
    chunk=items[base:base+10]; qs={}
    for j,x in enumerate(chunk):
        qs[f"q{j}"]={"type":"choice","instructions":{
          "task":x.get("title",""),
          "detail":(x.get("what") or "")[:900],
          "priority":x.get("priority"),
          "redoCount":x.get("redoCount"),
          "rule":"Founderにバックログ優先順位を決めさせない。工場停止・現在の不具合・再発・Founder負担・売上/顧客体験を先に。明示的に後回しなら後回し。"
        },"criteria":criteria}
    payload=json.dumps({"state":"TAMAGO backlog prioritization","model":"jev-latest","questions":qs},ensure_ascii=False).encode()
    req=urllib.request.Request("https://api.typesafe.ai/v1/systemone",data=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=60) as resp: out=json.load(resp)
    total_tokens += int((out.get("usage") or {}).get("input_tokens") or 0)
    for j,x in enumerate(chunk):
        a=out["answers"][f"q{j}"]
        rows.append({"n":x.get("n"),"title":x.get("title"),"oldPriority":x.get("priority"),"choice":a.get("choice"),"confidence":a.get("confidence"),"probabilities":a.get("probabilities")})
res={"at":time.strftime("%F %T"),"elapsed":round(time.time()-t0,3),"input_tokens":total_tokens,"rows":rows}
json.dump(res,open(R/"status/jev_priority50.json","w"),ensure_ascii=False,indent=2)
print("COUNT",len(rows),"ELAPSED",res["elapsed"],"TOKENS",total_tokens,"CHOICES",dict(collections.Counter(r["choice"] for r in rows)))
for r in rows: print(r["n"],r["choice"],r["confidence"],r["title"][:70])
