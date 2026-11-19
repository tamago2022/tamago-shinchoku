#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""会話ログの全トークンを会話ごと・1時間ごと・モデルごとに集める（読むだけ・AIは呼ばない）。2026-11-19 店主「何が消費しているか割り出して」。
結果 status/teiki/z1119.json（公開しない・会話の頭80字を含むため）。集計は tools/teiki_uchiwake.py。重い（約25分）ので手動でだけ走らせる。"""
import os,json,time,re,glob,datetime as D,collections
OUT="/Users/mac/tamago/tamago-shinchoku/status/teiki/z1119.json"
A=os.path.expanduser("~/Library/Application Support/Claude")
J=D.timezone(D.timedelta(hours=9))
pat=re.compile(r'scheduled-task name=\\?"([^"\\]+)')
# 1) メタ（アプリが持つ会話の札）
meta={}
for kind,root in (("cowork",A+"/local-agent-mode-sessions"),("code",A+"/claude-code-sessions")):
  for f in glob.glob(root+"/*/*/local_*.json"):
    try:d=json.load(open(f,encoding="utf-8"))
    except Exception:continue
    cid=d.get("cliSessionId")
    keep={k:(v if isinstance(v,(str,int,float,bool)) or v is None else str(v)[:120]) for k,v in d.items() if re.search(r"(?i)title|sched|dispatch|parent|spawn|agent|orchestr|origin|kind|type|mode|created|initialMessage|isArchived",k)}
    for k in list(keep):
      if isinstance(keep[k],str):keep[k]=keep[k][:120]
    keep["_kind"]=kind;keep["_sid"]=d.get("sessionId")
    if cid:meta[cid]=keep
# 2) 会話ログ
files=[]
for r in (os.path.expanduser("~/.claude/projects"),A+"/local-agent-mode-sessions"):
  for dp,dn,fn in os.walk(r):
    for n in fn:
      if n.endswith(".jsonl") and n!="audit.jsonl":files.append(os.path.join(dp,n))
seen=set();rows=[];t0=time.time()
for f in files:
  src="cowork" if "local-agent-mode-sessions" in f else "mac"
  sid=os.path.basename(f)[:-6];side="/subagents/" in f
  task=None;head="";first=None;cwd=None;ent=None;hb=collections.defaultdict(lambda:[0,0,0,0]);models=collections.Counter()
  try:
    fh=open(f,encoding="utf-8",errors="ignore")
  except Exception:continue
  with fh:
    for l in fh:
      if first is None or not head or '"usage"' in l or task is None and "scheduled-task" in l:
        try:d=json.loads(l)
        except Exception:continue
      else:continue
      ts=d.get("timestamp")
      if ts and first is None:first=ts
      if cwd is None and d.get("cwd"):cwd=d["cwd"];ent=d.get("entrypoint")
      if task is None and isinstance(d.get("content"),str):
        m=pat.search(d["content"]);task=m.group(1) if m else task
      if d.get("type")=="user" and not head:
        c=d.get("message",{}).get("content")
        if isinstance(c,list):c=" ".join(x.get("text","") for x in c if isinstance(x,dict))
        c=c or "";m=pat.search(c[:3000])
        if m:task=m.group(1)
        head=c.strip().replace("\n"," ")[:80]
      if d.get("type")=="assistant":
        m=d.get("message",{});u=m.get("usage")
        if not u:continue
        key=(m.get("id"),d.get("requestId"))
        if key[0] and key in seen:continue
        seen.add(key)
        if not ts:continue
        h=D.datetime.fromisoformat(ts.replace("Z","+00:00")).astimezone(J).strftime("%Y-%m-%d %H")
        mo=(m.get("model") or "?");mc="opus" if "opus" in mo else "sonnet" if "sonnet" in mo else "haiku" if "haiku" in mo else "fable" if "fable" in mo else "other"
        b=hb[h+"|"+mc]
        for i,k in enumerate(("input_tokens","output_tokens","cache_creation_input_tokens","cache_read_input_tokens")):
          v=u.get(k);b[i]+=v if isinstance(v,int) else 0
        models[mc]+=1
  if not hb and not head:continue
  rows.append(dict(f=f[-160:],src=src,sid=sid,side=side,task=task,head=head,first=first,cwd=(cwd or "")[-90:],ent=ent,meta=meta.get(sid),hb=dict(hb)))
json.dump(dict(at=time.strftime("%F %T"),sec=int(time.time()-t0),nfiles=len(files),rows=rows),open(OUT+".tmp","w"),ensure_ascii=False)
os.replace(OUT+".tmp",OUT)
