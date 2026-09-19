#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出たか・時刻通りかを機械で測る。失敗なら赤で出す。"""
import os, json, datetime, sys
BASE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(BASE)
RED="\033[31m"; GRN="\033[32m"; OFF="\033[0m"
JST=datetime.timezone(datetime.timedelta(hours=9))
def main():
    log=json.load(open(os.path.join(BASE,"log.json"),encoding="utf-8")) if os.path.exists(os.path.join(BASE,"log.json")) else []
    q=json.load(open(os.path.join(BASE,"queue.json"),encoding="utf-8"))
    now=datetime.datetime.now(JST); today=now.date()
    slots=[datetime.datetime.combine(today,datetime.time(int(s[:2]),int(s[3:])),JST) for s in q["slots_jst"]]
    due=[s for s in slots if s<=now]
    ok_today=[e for e in log if e.get("result")=="ok" and e["at"][:10]==str(today)]
    ng_today=[e for e in log if e.get("result")=="ng" and e["at"][:10]==str(today)]
    rows=[]; bad=False
    for i,s in enumerate(due):
        if i<len(ok_today):
            delay=(datetime.datetime.fromisoformat(ok_today[i]["at"])-s).total_seconds()/60
            rows.append(("OK",s.strftime("%H:%M"),f"{delay:+.0f}分",ok_today[i].get("permalink","")))
            if abs(delay)>30: bad=True
        else:
            rows.append(("未投稿",s.strftime("%H:%M"),"-","")); bad=True
    remaining=len(q["items"])-len([e for e in log if e.get("result")=="ok"])
    if remaining<=2: bad=True
    print(f"■ わえ自動投稿 検品 {now.strftime('%Y-%m-%d %H:%M')} JST")
    for r in rows:
        c=RED if r[0]!="OK" else GRN
        print(f"  {c}{r[0]:<6}{OFF} 予定{r[1]}  ずれ{r[2]}  {r[3]}")
    if ng_today:
        bad=True
        for e in ng_today: print(f"  {RED}失敗{OFF} {e['id']}: {e.get('error','')[:120]}")
    print(f"  在庫残り: {RED if remaining<=2 else GRN}{remaining}本{OFF}")
    json.dump({"updated":now.isoformat(),"ok":not bad,"color":"red" if bad else "green",
               "rows":rows,"remaining":remaining},
              open(os.path.join(ROOT,"status","wae_autopost_kenpin.json"),"w"),ensure_ascii=False,indent=2)
    return 1 if bad else 0
sys.exit(main())
