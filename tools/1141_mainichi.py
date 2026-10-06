#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1141番【常駐】毎日1回、完了の門をかけ直し、覆面（棚合わせ）を測り、1枚を描き直す。

たまごさん（2026-09-25）:
  「常駐にする。毎日1回、覆面を回して飴玉ゼロ率を記録する係。たまごさんが言わなくても測り続ける形。」

★新しい launchd 便は作らない（工場の決まり）。既存の心臓 tools/heartbeat.sh に相乗りする。
★ここで走る3つは全部 0円・ネットに出ない・ブラウザを使わない。
  ① tools/1141_kanryo_mon.py --apply  完了の門（門を通らない完了を未完了へ戻す）
  ② tools/1141_zaiko_awase.py         覆面100人の棚合わせ（在庫ゼロ率）
  ③ tools/1141_page.py                1枚を描き直す
★実機の覆面（tools/kyaku50.py・クレジットを使う）はここでは回さない。
  回すのは工場側の週次。ここは毎日ゼロ円で測れるぶんだけを測り続ける。
二重実行防止: status/.1141_last_run に最後に走った日付(JST)。
"""
import os,sys,subprocess,json,io,datetime
from datetime import timedelta,timezone
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
JST=timezone(timedelta(hours=9))
MARKER=os.path.join(ROOT,"status",".1141_last_run")
LOG=os.path.join(ROOT,"status","1141","mainichi.jsonl")
def main():
    today=datetime.datetime.now(JST).strftime("%Y-%m-%d")
    force="--force" in sys.argv
    if not force and os.path.exists(MARKER):
        try:
            if io.open(MARKER,encoding="utf-8").read().strip()==today: return 0
        except Exception: pass
    out={}
    for name,cmd in (("mon",[sys.executable,os.path.join(HERE,"1141_kanryo_mon.py"),"--apply"]),
                     ("zaiko",[sys.executable,os.path.join(HERE,"1141_zaiko_awase.py")]),
                     ("page",[sys.executable,os.path.join(HERE,"1141_page.py")])):
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=900)
        out[name]={"rc":r.returncode,"out":(r.stdout or "").strip()[:600],"err":(r.stderr or "").strip()[-300:]}
    rec={"at":datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),"r":out}
    try:
        m=json.load(io.open(os.path.join(ROOT,"status","1141","mon.json"),encoding="utf-8"))
        z=json.load(io.open(os.path.join(ROOT,"status","1141","zaiko.json"),encoding="utf-8"))
        rec["門"]={"見た":m.get("見た"),"通した":m.get("通した"),"弾いた":m.get("弾いた")}
        rec["在庫ゼロ率"]=z.get("summary",{}).get("在庫ゼロ率")
        # ★空回り検知（feedback_running_but_blind）。
        #   「全部通した」だけでは赤にしない。前回より完了が増えたのに1件も弾いていない日＝門が見ていない疑い。
        prev=None
        try:
            for line in io.open(LOG,encoding="utf-8"):
                prev=json.loads(line)
        except Exception: pass
        fueta = prev is not None and (m.get("見た",0) > (prev.get("門",{}) or {}).get("見た",0))
        rec["空回り疑い"]= bool(fueta and m.get("弾いた",0)==0)
    except Exception: pass
    os.makedirs(os.path.dirname(LOG),exist_ok=True)
    with io.open(LOG,"a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
    io.open(MARKER,"w",encoding="utf-8").write(today)
    print(json.dumps({k:v for k,v in rec.items() if k!="r"},ensure_ascii=False))
    return 0
if __name__=="__main__": sys.exit(main())
