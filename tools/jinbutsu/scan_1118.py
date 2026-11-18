# 1118：Vaultの人の呼び方のゆれを洗い出す（読むだけ・書かない）
import os,re,sys,json,collections,time
V,OUT=sys.argv[1],sys.argv[2]
t0=time.time()
res={"vault_exists":os.path.isdir(V)}
res["top"]=sorted(os.listdir(V))
pl=os.path.join(V,".obsidian","plugins"); res["plugins"]=sorted(os.listdir(pl)) if os.path.isdir(pl) else []
dv=os.path.join(pl,"dataview","data.json")
if os.path.exists(dv):
    try: res["dataview_settings"]=json.load(open(dv))
    except Exception as e: res["dataview_settings"]=repr(e)
cp=os.path.join(V,".obsidian","community-plugins.json")
if os.path.exists(cp): res["enabled_plugins"]=json.load(open(cp))
SUF=r"(?:さん|氏|先生|くん|ちゃん|様)"
tagre=re.compile(r"(?<![\w&/])#([^\s#\[\]\(\),.;:!?、。「」『』（）]+)")
linkre=re.compile(r"\[\[([^\]\|#\n]+)(?:#[^\]\|\n]*)?(?:\|[^\]\n]*)?\]\]")
tags=collections.Counter(); links=collections.Counter()
tagfiles=collections.defaultdict(set); linkfiles=collections.defaultdict(set)
names=[]; aliases={}; skipped=0
B3=["梶谷","中島","長島"]; forms={b:collections.Counter() for b in B3}; samples={b:[] for b in B3}
sanre=re.compile(r"([一-龥々ァ-ヶーA-Za-z]{1,6})さん")
sanbody=collections.Counter()
for root,ds,fs in os.walk(V):
    ds[:]=[d for d in ds if not d.startswith(".")]
    for f in fs:
        if not f.endswith(".md"): continue
        p=os.path.join(root,f); rel=os.path.relpath(p,V)
        names.append(rel)
        try:
            if os.path.getsize(p)>3_000_000: skipped+=1; continue
            t=open(p,encoding="utf-8",errors="ignore").read()
        except Exception: skipped+=1; continue
        body=t
        m=re.match(r"^---\n(.*?)\n---",t,re.S)
        if m:
            fm=m.group(1); body=t[m.end():]
            mm=re.search(r"^tags:[ \t]*(.*?)(?=^\S|\Z)",fm,re.S|re.M)
            if mm:
                for x in re.findall(r"[^\s\[\],\"'#]+",mm.group(1)):
                    if x not in("-","tags:"): x=x.lstrip("-"); tags[x]+=1; tagfiles[x].add(rel)
            ma=re.search(r"^aliases:[ \t]*(.*?)(?=^\S|\Z)",fm,re.S|re.M)
            if ma: aliases[rel]=ma.group(1).strip()[:200]
        body2=re.sub(r"```.*?```","",body,flags=re.S)
        for x in tagre.findall(body2):
            if re.fullmatch(r"[0-9a-fA-F]{3,8}|\d+",x): continue
            tags[x]+=1; tagfiles[x].add(rel)
        for x in linkre.findall(t):
            x=x.strip(); links[x]+=1; linkfiles[x].add(rel)
        for x in sanre.findall(body2): sanbody[x+"さん"]+=1
        for b in B3:
            if b in t:
                for mm2 in re.finditer(b+r"[^\s、。,.「」『』()（）\[\]#:：/|]{0,6}",t):
                    forms[b][mm2.group(0)]+=1
                    if len(samples[b])<60: samples[b].append([rel,t[max(0,mm2.start()-40):mm2.end()+40].replace("\n"," ")])
res["md_count"]=len(names); res["skipped"]=skipped
def pick(c): return {k:v for k,v in c.items() if re.search(SUF+r"$",k.split("/")[-1])}
res["tags_suffix"]=pick(tags); res["links_suffix"]=pick(links)
bases=set(B3)
for k in list(res["tags_suffix"])+list(res["links_suffix"]):
    b=re.sub(SUF+"$","",k.split("/")[-1]).strip()
    if b: bases.add(b)
cand={}
for b in sorted(bases):
    cand[b]={"tags":{k:v for k,v in tags.items() if b in k},
             "links":{k:v for k,v in links.items() if b in k},
             "files":[x for x in names if b in os.path.basename(x)][:30],
             "body_san":sanbody.get(b+"さん",0)}
res["cand"]=cand
res["aliases_existing"]=aliases
res["ctx"]={b:{"forms":dict(forms[b].most_common(50)),"samples":samples[b]} for b in B3}
res["tagfiles_suffix"]={k:sorted(tagfiles[k])[:60] for k in res["tags_suffix"]}
res["linkfiles_suffix"]={k:sorted(linkfiles[k])[:60] for k in res["links_suffix"]}
res["folders_jinbutsu"]=[x for x in names if x.split("/")[0] in("人物","People","people","人")][:100]
res["sanbody_top"]=dict(sanbody.most_common(150))
res["sec"]=round(time.time()-t0,1)
json.dump(res,open(OUT+".tmp","w"),ensure_ascii=False,indent=1); os.replace(OUT+".tmp",OUT)
