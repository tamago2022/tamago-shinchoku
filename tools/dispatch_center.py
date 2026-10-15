#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TAMAGO Company OS — Chief of Staff dispatch center.

新しい常駐は増やさない。既存の配管だけを呼び分ける薄い入口。
FounderはAI名を指定しなくてよい。仕事文から担当を決め、通電している口へ流す。

Routes:
- claude   : command_ingest.queue_add -> existing Mac factory
- gemini   : shigoto_furu.furu("gemini") -> GitHub Issue -> Jules
- genspark : local gsk search (prepaid credits; explicit --allow-genspark required)
- grok     : xAI text route only when kaitsuu says ok; otherwise deterministic fallback
- chatgpt  : codex login route for short judgment / fallback
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
STATUS=REPO/"status"
sys.path.insert(0,str(HERE))

import command_ingest
import shigoto_furu
import gaibu_kuchi

KAI=STATUS/"public"/"kaitsuu.json"
LOG=STATUS/"chief_dispatch.jsonl"
GSK="/Users/mac/.npm-global/bin/gsk"

RULES=[
 ("claude", ("実装","修正","バグ","コード","build","ビルド","lint","PR作成","コンポーネント","リファクタ","型エラー")),
 ("gemini", ("Google","Gemini","Gmail","Drive","Docs","Sheets","Slides","YouTube","画像解析","動画解析","マルチモーダル")),
 ("genspark", ("リサーチ","調査","検索","出典","競合","候補","市場","まとめ","クロスチェック")),
 ("grok", ("X ","Xの","Twitter","ツイッター","ミーム","世論","トレンド","リアルタイム反応")),
 ("chatgpt", ("判断","設計","優先順位","配車","方針","比較","QA","検品","原因")),
]

def now(): return time.strftime("%Y-%m-%d %H:%M:%S")

def append(rec):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open("a",encoding="utf-8") as f:
        f.write(json.dumps(rec,ensure_ascii=False)+"\n")

def kaitsuu(pid):
    try:
        d=json.load(open(KAI,encoding="utf-8"))
        for r in d.get("keys",[]):
            if r.get("id")==pid:
                return r.get("status"),r.get("detail")
    except Exception: pass
    return "unknown","status unavailable"

def classify(text):
    scores={}
    for who,words in RULES:
        scores[who]=sum(1 for w in words if w.lower() in text.lower())
    who=max(scores,key=scores.get)
    if scores[who]==0: who="chatgpt"
    # Google固有語が2つ以上ある仕事は、明示的なコード修正でない限りGeminiを優先。
    google_hits=scores.get("gemini",0)
    code_explicit=any(w.lower() in text.lower() for w in ("実装","修正","バグ","コード","build","ビルド","lint","pr作成","コンポーネント","リファクタ","型エラー"))
    if google_hits >= 2 and not code_explicit:
        who="gemini"
    elif code_explicit:
        who="claude"
    return who,scores

def fallback(who,text):
    if who=="grok":
        st,_=kaitsuu("xai")
        if st!="ok":
            # X/文化の調査ならGenspark、判断/文章ならChatGPT
            return "chatgpt"
    if who=="gemini":
        st,_=kaitsuu("gemini")
        if st!="ok": return "chatgpt"
    return who

def dispatch(text,priority=2,allow_genspark=False):
    chosen,scores=classify(text)
    who=fallback(chosen,text)
    rec={"at":now(),"task":text,"chosen":chosen,"route":who,"scores":scores}

    if who=="claude":
        st,msg=command_ingest.queue_add(text,priority=priority,label=("ChiefDispatch｜"+text)[:60],origin="chief_of_staff")
        rec.update(ok=st in ("done","ok","skipped"),result=f"{st}:{msg}")

    elif who=="gemini":
        r=shigoto_furu.furu("gemini",text,title=("【ChiefDispatch→Gemini】"+text[:42]))
        rec.update(ok=bool(r.get("ok")),result=r)

    elif who=="genspark":
        if not allow_genspark:
            rec.update(ok=False,held=True,result="Genspark credit gate: --allow-genspark required")
        elif not os.path.exists(GSK):
            rec.update(ok=False,result="gsk not found")
        else:
            before=None
            try: before=gaibu_kuchi.gsk_zandaka()
            except Exception: pass
            p=subprocess.run([GSK,"search",text],capture_output=True,text=True,timeout=180)
            after=None
            try: after=gaibu_kuchi.gsk_zandaka()
            except Exception: pass
            out=(p.stdout or "")[:200000]
            od=STATUS/"gsk"/"dispatch_kotae"; od.mkdir(parents=True,exist_ok=True)
            fn=od/(time.strftime("%Y%m%d-%H%M%S")+".txt"); fn.write_text(out,encoding="utf-8")
            rec.update(ok=p.returncode==0,result=str(fn.relative_to(REPO)),credit_before=before,credit_after=after,
                       credit_used=(round(before-after,3) if isinstance(before,(int,float)) and isinstance(after,(int,float)) else None),
                       stderr=(p.stderr or "")[-1000:])

    elif who=="chatgpt":
        system="あなたはTAMAGO Company OSのChief of Staff補佐。結論・根拠・次の一手をJSONで返す。"
        d,agent,err=gaibu_kuchi.kiku_codex(system,text,timeout=150)
        rec.update(ok=d is not None,result=d,agent=agent,error=err)

    else:
        rec.update(ok=False,result="unsupported route")

    append(rec)
    return rec

def self_test():
    cases=[
      ("Reactの表示バグを修正してテスト", "claude"),
      ("Google Sheetsのデータを調べて設計", "gemini"),
      ("競合サービスを出典付きでリサーチ", "genspark"),
      ("Xの今の反応とミームを調べて", "grok"),
      ("優先順位を決めて配車方針を考えて", "chatgpt"),
    ]
    bad=[]
    for text,want in cases:
        got,_=classify(text)
        if got!=want: bad.append((text,want,got))
    print(json.dumps({"ok":not bad,"cases":len(cases),"bad":bad},ensure_ascii=False))
    return 1 if bad else 0

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("task",nargs="?")
    ap.add_argument("--priority",type=int,default=2)
    ap.add_argument("--allow-genspark",action="store_true")
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test: return self_test()
    if not a.task: ap.error("task required")
    print(json.dumps(dispatch(a.task,a.priority,a.allow_genspark),ensure_ascii=False,indent=2,default=str))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
