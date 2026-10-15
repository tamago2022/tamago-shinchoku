#!/usr/bin/env python3
"""xAI(Grok Voice)の使った分を、Lovableの voice_usage_log を SELECT だけで集計して
status/subsc.json の xai 行を更新する（毎晩 deadline_watch.py から呼ぶ）。
★SELECT以外は送らない。実請求との照合は未（xAIの管理用キーが無いため）。
"""
import json, os, sys, re, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "status", "subsc.json")
PROJECT = "8ebdb648-3686-4457-b42c-d01c493793b1"
RATE_MIN = 0.08      # 公式単価 $/分
YEN = 157.83         # 目安（2026-10-02終値）
SQL = ("select count(*) filter (where duration_seconds>0) as n, coalesce(sum(duration_seconds),0) as sec, "
       "coalesce(sum(estimated_cost_usd),0) as est, min(created_at) as first, max(created_at) as last "
       "from voice_usage_log")


def tally():
    import kohyou_osu as k
    L = k.Lovable()
    if not L.ok():
        raise RuntimeError("Lovableの鍵が無い")
    assert SQL.lstrip().lower().startswith("select")
    L._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tamago", "version": "1"}})
    raw = L._rpc("tools/call", {"name": "query_database", "arguments": {"project_id": PROJECT, "sql": SQL}})
    line = [x for x in raw.splitlines() if x.startswith("data: ")][-1][6:]
    return json.loads(json.loads(line)["result"]["content"][0]["text"])["rows"][0]


def main():
    try:
        r = tally()
    except Exception as e:
        print("xai集計 失敗:", e); return 1
    n, sec, est = int(r["n"]), int(r["sec"]), float(r["est"])
    usd = round(sec / 60.0 * RATE_MIN, 2)
    yen = int(round(usd * YEN))
    d0, d1 = str(r["first"])[:10], str(r["last"])[:10]
    led = json.load(open(LEDGER, encoding="utf-8"))
    row = dict(id="xai", name="xAI（Grok Voice・コンシェルジュ）", usd=usd, yen=yen,
               kata="従量課金（使った分だけ）",
               gaku_moto=(f"実測：Lovableの voice_usage_log を直接集計（{d0}〜{d1}）＝話した{n}回・合計{sec:,}秒（{sec/60:.1f}分）、"
                          f"公式単価${RATE_MIN}/分で約${usd}（約{yen}円・1ドル{YEN}円の目安）。記録上の見積もり列は${est:.2f}（旧計算式で過大）。"
                          "★実請求との照合：未（xAIの管理用キーが無いため）"),
               tsugi="従量（決まった更新日が無い）", tsugi_moto="従量課金", kurikaeshi="nashi",
               harai="10ドルを入れたチーム（チームIDは鍵担当が台帳化中）。もう1つのチーム(console.x.ai/team/3e0b4d97-…)は$0・支払い方法なし＝使っていない",
               harai_moto="たまごさん報告（2026-10-05）",
               tsukau="使っている", tsukau_moto="voice_usage_log の集計（毎晩 tools/xai_voice_tally.py が更新）",
               yameru="取れていない（確かめていない）", kakunin=True,
               shuukei_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    for i, it in enumerate(led["items"]):
        if it["id"] == "xai":
            led["items"][i] = row; break
    else:
        led["items"].append(row)
    led["updatedAt"] = dt.date.today().isoformat()
    json.dump(led, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"xai: {n}回 {sec}秒 約${usd} 約{yen}円（見積列${est:.2f}）")


if __name__ == "__main__":
    sys.exit(main() or 0)
