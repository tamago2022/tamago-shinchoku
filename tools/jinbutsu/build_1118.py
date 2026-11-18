# 1118：人物ノート3枚＋索引を作る（新しいファイルだけ。既存ノートは読むだけ）
# 使い方: build_1118.py <Vault> <出力dir> [--write]
import os,re,sys,json,collections
V,OUT=sys.argv[1],sys.argv[2]; WRITE="--write" in sys.argv
os.makedirs(OUT,exist_ok=True)
PEOPLE=[
 {"file":"梶谷健人","aliases":["梶谷健人","梶谷さん","梶谷健人さん","梶谷氏","梶谷健人氏","梶谷","kajikent"],
  "memo":"AI事業戦略家・発信者（X @kajikent／note kajiken063）。"},
 {"file":"中島聡（人物）","aliases":["中島聡","中島さん","中島聡さん","中島聡氏","中島氏","snakajima"],
  "memo":"エンジニア・元マイクロソフト（X @snakajima）。同じ「中島」でも中島みゆき・中島美嘉・中島ヨシキは別人なので入れていない。既存ノート [[00 inbox/中島聡|中島聡]] とは別に作った（同じ名前にすると、今ある [[中島聡]] のリンク先が変わるおそれがあるため）。"},
 {"file":"長嶋修（人物）","aliases":["長嶋修","長嶋さん","長嶋修さん","長嶋修氏","長島さん","長島修"],
  "memo":"Vault内の表記は「長嶋」（嶋）。「長島さん」と打っても着くように別表記も入れた。既存ノート [[モデリング　天才　人物　変態　変人 　発信者/長嶋修/長嶋修|長嶋修（フォルダのノート）]] とは別に作った。"},
]
SUF=r"(?:さん|氏|先生|くん|ちゃん|様)"
tagre=re.compile(r"(?<![\w&/])#([^\s#\[\]\(\),.;:!?、。「」『』（）]+)")
linkre=re.compile(r"\[\[([^\]\|#\n]+)(?:#[^\]\|\n]*)?(?:\|[^\]\n]*)?\]\]")
files={}
for root,ds,fs in os.walk(V):
    ds[:]=[d for d in ds if not d.startswith(".")]
    for f in fs:
        if f.endswith(".md"):
            p=os.path.join(root,f)
            try:
                if os.path.getsize(p)<3_000_000: files[os.path.relpath(p,V)]=open(p,encoding="utf-8",errors="ignore").read()
            except Exception: pass
def meta(t):
    tags=set(); people=[]; body=t
    m=re.match(r"^---\n(.*?)\n---",t,re.S)
    if m:
        fm=m.group(1); body=t[m.end():]
        mm=re.search(r"^tags:[ \t]*(.*?)(?=^\S|\Z)",fm,re.S|re.M)
        if mm: tags|={x.lstrip("-") for x in re.findall(r"[^\s\[\],\"'#]+",mm.group(1)) if x not in("-",)}
        mp=re.search(r"^people:[ \t]*(.*?)(?=^\S|\Z)",fm,re.S|re.M)
        if mp: people=[x.strip(" \"'-") for x in re.split(r"[,\n\[\]]",mp.group(1)) if x.strip(" \"'-")]
    b2=re.sub(r"```.*?```","",body,flags=re.S)
    tags|={x for x in tagre.findall(b2)}
    links={x.strip().split("/")[-1] for x in linkre.findall(t)}
    return tags,links,people,b2
M={k:meta(t) for k,t in files.items()}
report={"people":{}}
for P in PEOPLE:
    al=P["aliases"]; S=set(al)
    hits=[];body_hits=[]
    for rel,(tags,links,people,b2) in M.items():
        name=os.path.basename(rel)[:-3]
        why=[]
        tg=sorted({t for t in tags if t in S or t.split("/")[-1] in S})
        why+=["#"+t for t in tg]
        lk=sorted(links & S); why+=["[["+x+"]]" for x in lk]
        if any(x in S for x in people): why.append("people欄")
        if any(a in name for a in al): why.append("題名")
        if why: hits.append([rel,why])
        else:
            c=collections.Counter(a for a in al if len(a)>=3 and a in b2)
            if c: body_hits.append([rel,dict(c)])
    hits.sort(); body_hits.sort()
    # 本文の「中島さん」「長島さん」等の前後
    ctx=[]
    for a in ["中島さん","長島さん","梶谷さん"]:
        if a in al:
            for rel,t in files.items():
                for m in re.finditer(a,t):
                    if len(ctx)<12: ctx.append([a,rel,t[max(0,m.start()-60):m.end()+40].replace("\n"," ")])
    report["people"][P["file"]]={"hits":len(hits),"body_only":len(body_hits),"ctx":ctx}
    P["hits"]=hits; P["body_hits"]=body_hits
# 同一の可能性が高い組（共起：さんタグのノートにフルネームも出てくる数）
PAIRS=[("石田さん","石田和靖"),("高城さん","高城剛"),("安野さん","安野貴博"),("深津さん","深津貴之"),("エミンさん","エミン・ユルマズ"),
 ("苫米地さん","苫米地英人"),("奥野さん","奥野卓志"),("阿部さん","阿部敏郎"),("南場さん","南場智子"),("金子さん","金子吉友"),("内海さん","内海聡"),
 ("安宅さん","安宅和人"),("長倉さん","長倉顕太"),("瀧本さん","瀧本哲史"),("松浦さん","松浦勝人"),("菅原くん","菅原由一"),("菅原さん","菅原由一"),
 ("鴨さん","鴨頭嘉人"),("神谷さん","神谷宗幣"),("家入さん","家入一真"),("藤原さん","藤原ヒロシ"),("ジェイさん","ジェイ・エイブラハム"),
 ("前澤さん","前澤友作"),("國光さん","國光宏尚"),("友村さん","友村晋"),("迫くん","迫佳志浩"),("はちえん坂田さん","坂田"),("原口さん","原口一博"),("伊木さん","伊木"),("和佐さん","和佐大輔"),("北原さん","北原"),("井川さん","井川"),("高山さん","高山"),("石濱さん","石濱"),("白沢さん","白沢"),("鳥羽さん","鳥羽"),("とねくん","とね"),("窪塚くん","窪塚洋介"),("中島さん","中島聡"),("梶谷さん","梶谷健人"),("長嶋さん","長嶋修")]
pr=[]
for a,b in PAIRS:
    fa=[k for k,(tags,links,ppl,b2) in M.items() if a in tags or a in b2 or a in os.path.basename(k)]
    fb=[k for k,(tags,links,ppl,b2) in M.items() if b in tags or b in b2 or b in os.path.basename(k)]
    both=set(fa)&set(fb)
    tag_a=sum(1 for k,(tags,*_) in M.items() if a in tags); tag_b=sum(1 for k,(tags,*_) in M.items() if b in tags)
    pr.append({"san":a,"full":b,"notes_san":len(fa),"notes_full":len(fb),"both":len(both),"tag_san":tag_a,"tag_full":tag_b})
report["pairs"]=pr
# 同姓の別人（混ざると危ない）
homo={}
for s in ["中島","阿部","深津","藤原","長嶋","石田","金子","松浦","菅原","前澤","神谷","高城"]:
    c=collections.Counter()
    for k,(tags,links,ppl,b2) in M.items():
        for m in re.finditer(s+r"[一-龥々]{1,3}",b2+" "+os.path.basename(k)): c[m.group(0)]+=1
    homo[s]=dict(c.most_common(12))
report["homonyms"]=homo
for chk in ["人物"]: report["exists_"+chk]=os.path.exists(os.path.join(V,chk))
report["dataview_main"]=os.path.exists(os.path.join(V,".obsidian/plugins/dataview/main.js"))
report["dataview_data"]=os.path.exists(os.path.join(V,".obsidian/plugins/dataview/data.json"))
for ex in ["00 inbox/中島聡.md","モデリング　天才　人物　変態　変人 　発信者/長嶋修/長嶋修.md"]:
    report["head_"+ex]=files.get(ex,"(なし)")[:400]
json.dump(report,open(os.path.join(OUT,"report.json"),"w"),ensure_ascii=False,indent=1)
# ---- ノートを組む ----
DVJS=r'''```dataviewjs
// この人の呼び方は、上の aliases が正本。呼び方が増えたら aliases に1行足すだけ。
const me = dv.current();
const yobi = [...new Set([me.file.name.replace(/（人物）$/, ""), ...dv.array(me.aliases ?? []).values]
  .map(s => String(s).trim()).filter(Boolean))];
const S = new Set(yobi);
const rows = [];
for (const p of dv.pages()) {
  if (p.file.path === me.file.path) continue;
  const why = [];
  for (const t of p.file.tags ?? []) {               // タグ（#梶谷さん も #梶谷健人 も）
    const n = t.replace(/^#/, "");
    if (S.has(n) || S.has(n.split("/").pop())) why.push(t);
  }
  for (const l of p.file.outlinks ?? []) {            // リンク（[[梶谷さん]] も [[梶谷健人]] も）
    const n = l.path.split("/").pop().replace(/\.md$/, "");
    if (S.has(n) || l.path === me.file.path) why.push("[[" + n + "]]");
  }
  if (dv.array(p.people ?? []).some(x => S.has(String(x).trim()))) why.push("people欄");
  if (yobi.some(y => p.file.name.includes(y))) why.push("題名");
  if (why.length) rows.push([p.file.link, [...new Set(why)].join(" "), p.file.mtime]);
}
rows.sort((a, b) => b[2] - a[2]);
dv.paragraph(`呼び方 ${yobi.length} 通り（${yobi.join("・")}）で **${rows.length} 件**`);
dv.table(["ノート", "どれで拾ったか", "更新"], rows);
```'''
def note(P):
    al="\n".join("  - "+a for a in P["aliases"])
    lines=[f"---\naliases:\n{al}\ntags:\n  - 人物\ncreated: 2026-11-18\n---",
           f"# {P['file'].replace('（人物）','')}","",P["memo"],"",
           "## この人が出てくるノート（自動）","",DVJS,"",
           "## 作成時点（2026-11-18）に拾えたノート","",
           "Dataviewが止まっていても見られるよう、作成時に同じ決まりで拾った一覧を写しておく。",""]
    for rel,why in P["hits"]:
        lines.append(f"- [[{rel[:-3]}|{os.path.basename(rel)[:-3][:60]}]] — {' '.join(why)}")
    if P["body_hits"]:
        lines+=["","### タグ・リンクは無いが、本文に名前が出てくるノート","",
                "（Dataviewは本文の文字を数えないので、ここだけ作成時の写し。タグを足すと上の自動の表に入る）",""]
        for rel,c in P["body_hits"]:
            lines.append(f"- [[{rel[:-3]}|{os.path.basename(rel)[:-3][:60]}]] — "+"・".join(f"{k}×{v}" for k,v in c.items()))
    return "\n".join(lines)+"\n"
os.makedirs(os.path.join(OUT,"preview"),exist_ok=True)
outs={}
for P in PEOPLE: outs[f"人物/{P['file']}.md"]=note(P)
# 索引
idx=["---\ntags:\n  - 人物\ncreated: 2026-11-18\n---","# 人物一覧","",
 "人ごとに1枚。呼び方（〇〇さん／フルネーム／〇〇氏）は各ノートの aliases にまとめてある。検索・リンクでどの呼び方を打っても、その人のノートに着く。","",
 "```dataviewjs","const ps = dv.pages('\"人物\"').where(p => p.file.name !== dv.current().file.name);",
 "dv.table([\"人\", \"呼び方（aliases）\"], ps.sort(p => p.file.name).map(p => [p.file.link, dv.array(p.aliases ?? []).join(\"・\")]));","```","",
 "## 作った人物ノート（2026-11-18）",""]
for P in PEOPLE: idx.append(f"- [[人物/{P['file']}|{P['file'].replace('（人物）','')}]] — {'・'.join(P['aliases'])}（作成時 {len(P['hits'])} 件）")
idx+=["","## 呼び方のゆれ：同じ人の可能性が高い組（店主の確認待ち・まだノートは作っていない）","",
 "数字＝その書き方が出てくるノートの数（タグ・本文・題名のどれか）／両方＝同じノートに両方出てくる数","",
 "| 〇〇さん表記 | フルネーム | さん側 | フル側 | 両方 |","|---|---|---|---|---|"]
for x in pr:
    if x["san"] in ("中島さん","梶谷さん","長嶋さん"): continue
    idx.append(f"| {x['san']} | {x['full']} | {x['notes_san']} | {x['notes_full']} | {x['both']} |")
outs["人物/00_人物一覧.md"]="\n".join(idx)+"\n"
for k,v in outs.items():
    pp=os.path.join(OUT,"preview",k.replace("/","__")); open(pp,"w").write(v)
if WRITE:
    os.makedirs(os.path.join(V,"人物"),exist_ok=True)
    for k,v in outs.items():
        dst=os.path.join(V,k)
        if os.path.exists(dst): print("既にあるので書かない",k); continue
        open(dst,"w",encoding="utf-8").write(v); print("書いた",k)
print("ok")
