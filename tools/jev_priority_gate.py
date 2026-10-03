#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Founder発言を「記録」と「実行」に分けるJev門。
目的: 思いつき・将来案を忘れず保存するが、勝手に発車させない。
"""
import io,json,os,pathlib,urllib.request

KEY=pathlib.Path.home()/".config/typesafe/api_key"
API="https://api.typesafe.ai/v1/systemone"
STATUS=os.path.join(os.path.dirname(os.path.dirname(__file__)),"status")
POLICY_PATH=os.path.join(STATUS,"founder_priority_os.md")
LEGACY_PRIORITY_PATH=os.path.join(STATUS,"yusen_2026-10-01.md")

def _policy_excerpt():
    parts=[]
    for p in (POLICY_PATH, LEGACY_PRIORITY_PATH):
        try:
            parts.append(io.open(p,encoding="utf-8").read())
        except Exception:
            pass
    return "\n\n".join(parts)[:16000]

def classify(title, body="", source="conversation"):
    key=KEY.read_text().strip() if KEY.exists() else ""
    if not key:
        return {"choice":"記録だけ","confidence":0.0,"error":"no_key"}
    state={
      "title":title or "",
      "body":(body or "")[:4000],
      "source":source,
      "current_policy":_policy_excerpt(),
      "operating_principles":[
        "Founderが言ったことは忘れない。ただし発言=今すぐ実行ではない。",
        "今直す: 工場停止/重さ/退行/再発/Founder水汲み/固定費浪費/売上・商品・認知に直結。",
        "続ける: 仕入れ・パーソナライズ・集客の自動ループ。ただし現在の重要案件を邪魔しない。",
        "後回し: 1〜3か月後でも損失が小さい研究・装飾・将来案。",
        "新規支出・契約・不可逆重大変更・秘密/法務・ブランド根幹はFounder判断。",
        "古いという理由だけでP1にしない。言われた回数だけでもP1にしない。"
      ]
    }
    criteria={
      "今走らせる":"現在の障害・退行・再発・Founder負担、または商品/売上/集客に直結し、今週やる価値が高い。",
      "次に回す":"重要だが現在の最優先が閉じた後でよい。自動キューには置けるがP1にしない。",
      "記録だけ":"忘れないよう保存するが、今は発車しない。将来案・研究・装飾・低緊急。",
      "Founder判断":"新規支出/契約、不可逆重大変更、秘密/法務、ブランド根幹、最終価値判断。"
    }
    qs={"route":{"type":"choice","instructions":"Choose whether this founder statement should actually consume execution capacity now. Do not confuse remembering with executing.","criteria":criteria}}
    data=json.dumps({"state":state,"model":"jev-latest","questions":qs},ensure_ascii=False).encode()
    req=urllib.request.Request(API,data=data,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp: out=json.load(resp)
        a=(out.get("answers") or {}).get("route") or {}
        return {"choice":a.get("choice"),"confidence":a.get("confidence"),"probabilities":a.get("probabilities"),"usage":out.get("usage")}
    except Exception as e:
        # 壊れた時に勝手に発車するより、記録側へ倒す
        return {"choice":"記録だけ","confidence":0.0,"error":str(e)[:160]}

if __name__=="__main__":
    import sys
    print(json.dumps(classify(sys.argv[1] if len(sys.argv)>1 else "", " ".join(sys.argv[2:])),ensure_ascii=False,indent=2))
