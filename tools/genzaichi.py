#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""いまの現在地を1枚にする（status/genzaichi.md）。
Dispatchが会話の最初に必ず読む1枚。ルールではなく「今の状態」を書く。

2026-09-12 新設の理由：
  たまごさん「何も引き継がれてない。この現象が嫌だから何度も念を押したのに。二度と起こらぬよう仕組み化して」
  憲法の0番に「いまの現在地_チャット貼付用.md を読め（30分おき自動更新）」と書いてあったが、
  **そのファイルもGitHub版も生成スクリプトも存在しなかった。**
  そのせいで「Lovableの本番が5日止まっている」が誰にも引き継がれず、5日間放置された。
"""
import json, os, re, glob, subprocess, datetime, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(REPO, "status")
JST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(JST)

def jread(p, d=None):
    try:
        with open(os.path.join(ST, p), encoding="utf-8") as f: return json.load(f)
    except Exception: return d if d is not None else {}

def deploy_alive():
    """本番(Lovable)が生きているか。x-deployment-id を取って前回と比べる。"""
    url = "https://joy-relief-station.lovable.app/"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "genzaichi/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            did = r.headers.get("x-deployment-id") or r.headers.get("x-nf-request-id") or ""
    except Exception as e:
        return None, "取得できず(%s)" % str(e)[:40]
    hist_p = os.path.join(ST, "deploy_history.json")
    try:
        hist = json.load(open(hist_p, encoding="utf-8"))
    except Exception:
        hist = {}
    last_id = hist.get("id"); last_at = hist.get("at")
    if did and did != last_id:
        hist = {"id": did, "at": now.isoformat()}
        json.dump(hist, open(hist_p, "w", encoding="utf-8"), ensure_ascii=False)
        return 0.0, did
    if last_at:
        try:
            h = (now - datetime.datetime.fromisoformat(last_at)).total_seconds() / 3600
            return h, did
        except Exception: pass
    return None, did

def child_costs_today():
    tot = 0.0; n = 0
    today = now.strftime("%Y-%m-%d")
    for f in glob.glob(os.path.join(ST, "auto-launch-*.log")) + [os.path.join(ST, "auto_launch.log")]:
        try: lines = open(f, encoding="utf-8", errors="ignore").read().split("\n")
        except Exception: continue
        cur = False
        for ln in lines:
            if re.match(r"=== " + today + r" ", ln): cur = True
            m = re.search(r'"total_cost_usd":([0-9.]+)', ln)
            if m and cur:
                tot += float(m.group(1)); n += 1; cur = False
    return n, tot

def main():
    q = jread("queue.json", {"items": []}); items = q.get("items") or []
    h = jread("health.json"); p = jread("pace.json")
    today = now.strftime("%Y-%m-%d")
    done_today = sum(1 for x in items if x.get("status") == "done" and str(x.get("doneAt") or x.get("updatedAt") or "")[:10] == today)
    running = [x for x in items if x.get("status") == "running"]
    waiting = [x for x in items if x.get("status") == "waiting"]
    p1 = [x for x in waiting if x.get("priority") == 1]
    n_child, cost = child_costs_today()
    avg = (cost / n_child) if n_child else 0.0
    dep_h, dep_id = deploy_alive()

    L = []
    A = L.append
    A("# いまの現在地（%s 時点・自動生成）" % now.strftime("%m-%d %H:%M"))
    A("")
    A("**Dispatchは会話の最初に、返事をする前にこの1枚を読む。ルールではなく『今の状態』がここにある。**")
    A("")
    A("## ★止まっていないか（ここが赤なら他を全部止めてでも直す）")
    if dep_h is None:
        A("- 🔴 **本番(Lovable)：確認できず** — %s" % dep_id)
    elif dep_h > 24:
        A("- 🔴 **本番(Lovable)：%.0f時間 更新なし** ← コードを直しても画面は変わらない。最優先で復旧" % dep_h)
    else:
        A("- ✅ 本番(Lovable)：%.1f時間前に更新あり" % dep_h)
    hb = os.path.join(ST, "heartbeat.log")
    try:
        m = (now - datetime.datetime.fromtimestamp(os.path.getmtime(hb), JST)).total_seconds() / 60
        A(("- 🔴 **心臓：%.0f分 沈黙**" % m) if m > 10 else ("- ✅ 心臓：%.0f分前に動いた" % m))
    except Exception:
        A("- ⚠️ 心臓：ログが読めない")
    A("")
    A("## 数字")
    A("- 走行 **%s / %s**（発車待ち %d件・うちP1 %d件）" % (h.get("sessions"), h.get("safeMax"), len(waiting), len(p1)))
    A("- 今日の完了 **%d件**（9/06のピークは60件。20件を切ったら何かが詰まっている）" % done_today)
    A("- 今日の子セッション **%d本・合計 $%.2f・1本平均 $%.2f**%s" % (n_child, cost, avg, "  ← 🔴 $3超は異常" if avg > 3 else ""))
    A("- クレジット 今日 **%s / %s**・週 **%s%%**" % (p.get("usedToday"), p.get("budgetToday"), p.get("allPct")))
    A("")
    A("## 今すぐ走っているもの")
    if running:
        for x in running:
            st = x.get("startedAt") or x.get("launchedAt") or ""
            el = ""
            try:
                el = "（%.1fh%s）" % (((now - datetime.datetime.fromisoformat(st)).total_seconds() / 3600), " ★3時間超" if (now - datetime.datetime.fromisoformat(st)).total_seconds() > 10800 else "")
            except Exception: pass
            A("- %s %s%s" % (x.get("n"), (x.get("label") or "")[:44], el))
    else:
        A("- **0本**（クレジットが残っているなら、これは異常）")
    A("")
    A("## 次に出る（P1の先頭5件）")
    for x in sorted(p1, key=lambda y: -(y.get("n") or 0))[:5]:
        A("- %s %s" % (x.get("n"), (x.get("label") or "")[:48]))
    A("")
    A("## まだ渡していない完成品")
    try:
        rep = set(json.load(open(os.path.join(ST, "dispatch_reported.json"), encoding="utf-8")).get("reported", []))
    except Exception: rep = set()
    unrep = []
    try:
        for line in open(os.path.join(ST, "dispatch_outbox.jsonl"), encoding="utf-8"):
            try: d = json.loads(line)
            except Exception: continue
            if d.get("ok") and d.get("n") not in rep and str(d.get("ts", ""))[:10] == today:
                u = [x for x in (d.get("urls") or []) if "share/" in x or "lovable.app" in x]
                if u: unrep.append((d.get("n"), (d.get("title") or "")[:40], u[0]))
    except Exception: pass
    if unrep:
        for n_, t_, u_ in unrep[-8:]:
            A("- %s %s" % (n_, t_)); A("  %s" % u_)
    else:
        A("- なし")
    A("")
    A("---")
    A("*このファイルは tools/genzaichi.py が自動生成する。手で書き換えない。*")

    out = os.path.join(ST, "genzaichi.md")
    with open(out, "w", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
    print("wrote", out)

if __name__ == "__main__":
    main()
