#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定期で回っているもの一覧（2026-11-18 店主「10分おきなんかやらなくていい。いろんなものが走っていて把握できない」）。

棚卸し（tools/jidou_tanaoroshi.py → status/public/jidou_tanaoroshi.json）の全行に、
「AIを呼ぶか」「1週間の実行回数」「本当に要る頻度」「11/18にどうしたか」を足して、表を2枚出す。
  share/check/teiki.html            … 進捗表から1クリック
  status/teiki/teiki_ichiran_1118.md … ~/Documents/AI作業/teiki_ichiran_1118.md へ写す元
使い方：python3 tools/teiki_ichiran.py   ／ --self-test
作るもの：上の2ファイルだけ（上書き）。消す役：不要（毎回上書き・増えない）。
"""
import html
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "status", "public", "jidou_tanaoroshi.json")
OUT_HTML = os.path.join(REPO, "share", "check", "teiki.html")
OUT_MD = os.path.join(REPO, "status", "teiki", "teiki_ichiran_1118.md")

# AIを呼ぶもの（呼び方・1週間のAI呼び出し 前→後・どうしたか）。数字は 11/11〜11/18 のログの実測か、間隔からの計算。
AI = {
    "claude-teiki:rusuban-mimawari-30min": ("Claudeの会話を30分おきに起こす（中身は10/11に停止済み・起きて「停止済み」と返すだけ）", 336, 0, "止めた（有効→無効）"),
    "claude-teiki:weekly-reset-wakeup": ("週枠リセット直後に発車しているか見る（Coworkの会話1回）", 1, 1, "そのまま（週1回）"),
    "auth_keeper.py": ("ログインの生死を Sonnet に「1+1は？」と聞いて確かめる", 336, 7, "30分おき→1日1回"),
    "hyoudai.py": ("進捗表の見出しをAIで1行に書き直す（実測 11/11〜18 で619回）", 619, 7, "10分おき→1日1回"),
    "1192_title_romaji.py": ("新しい曲名のローマ字をAIで付ける（新曲がある時だけ。実測 8回/週）", 8, 7, "1時間おき→1日1回"),
    "kenpin_gate.py": ("終わった仕事をAIで検品（終わった仕事がある時だけ）", None, None, "そのまま（出来た時だけ動く＝定期ではない）"),
    "command_ingest.py": ("たまごさん／Dispatchの指示を列へ。止まった会話の再開にAI", None, None, "そのまま（指示が来た時だけ）"),
    "auto_launcher.py": ("工場の発車係。列の仕事をClaudeの子で走らせる＝仕事そのもの", None, None, "止めない（発車は仕事。空回りの見張りは延ばした）"),
    "suno_mcp.py": ("Sunoがつながったかを claude -p で確かめる（つながるまで）", None, None, "そのまま（ログイン待ちで止まっている）"),
    "grok_tsuushin.py": ("Reasonのネットワークで claude を待ち受ける（頼まれた時だけ）", None, None, "そのまま（頼まれた時だけ）"),
    "kaizen_loop.py": ("毎時の採点はAIなし。直す便を列に積む→発車係が走らせる", None, None, "そのまま（採点はAIなし）"),
    "gokigen_tane.py": ("LINE一粒の下書き（配信はGrok担当になり、今は何もしない）", 0, 0, "5分おき→6時間おき"),
    "cloud_mainichi.py": ("クラウド枠を毎日使う係（11/1で期限切れ・毎時「期限後」と書くだけ）", 0, 0, "止めた"),
    "muse_renraku.py": ("Museへの依頼の返事を GitHub で見る（AIは呼ばない）", 0, 0, "10分おき→依頼中だけ1日2回・依頼が無ければ何もしない"),
    "com.tamago.machine-status": ("15分便。中の gaibu_copy_naoshi・2210_tanaire・daimei_naoshi は1日1回だけAI、session_watchdog は止まった時だけAI", None, None, "そのまま（中で1日1回に間引き済み）"),
}

# 11/18 に間隔を延ばした・止めたもの（AIを呼ばない空回り）
NOBASHITA = {
    "zeikin_kakari.py": "10分おき→3時間おき（中で1日1回）", "1140_mainichi.py": "10分おき→3時間おき（中で1日1回）",
    "1141_mainichi.py": "10分おき→3時間おき（中で1日1回）", "daily_ingest_scheduler.py": "10分おき→3時間おき（中で1日1回）",
    "check_page_pruner.py": "10分おき→6時間おき", "check_anthropic_reply.py": "10分おき→6時間おき",
    "check_line_reply.py": "10分おき→6時間おき", "check_line_shinsa.py": "10分おき→6時間おき",
    "cloud_credit_henji.py": "1時間おき→1日1回（クレジットは11/5で期限切れ）", "kakeibo.py": "20分おき→6時間おき",
    "tokushu.py": "20分おき→6時間おき", "subsc_shirase.py": "1時間おき→6時間おき", "subsc_calendar.py": "1時間おき→4時間おき",
    "genzaichi_matome.py": "1時間おき→6時間おき", "git_souji.py": "1時間おき→1日1回", "obsidian_mamoru.py": "1時間おき→6時間おき",
    "soto_hatarakite.py": "1時間おき→6時間おき",
}

TEIAN = {  # 本当に要る頻度の提案（AIなし・今回は触っていないもの）
    "github_watch.py": "5分おき", "ai_daicho.py": "1時間おき", "nagekomi_list.py": "5分おき", "1163_kagi_machi.py": "鍵待ちの間だけ",
    "kioku.py": "30分おき", "kioku_page.py": "30分おき", "oni_codex.py": "30分おき", "genzaichi.py": "10分おき",
    "com.tamago.joy-relief-station.keep-warm": "10分おき", "com.tamago.gdrive-md-mirror": "30分おき",
    "com.tamago.joy-relief-station.video-patrol": "6時間おき", "com.tamago.tomaranai": "5分おき",
}


def per_week(freq):
    """頻度の文字 → 1週間の実行回数（だいたい）。分からなければ None。"""
    f = freq or ""
    m = re.match(r"(\d+)分おき", f)
    if m:
        return 7 * 24 * 60 // int(m.group(1))
    m = re.match(r"(\d+)時間おき", f)
    if m:
        return 7 * 24 // int(m.group(1))
    if f.startswith("毎周（15秒"):
        return 7 * 24 * 240
    if f.startswith("毎日"):
        return 7
    if f in ("常駐",):
        return None
    m = re.match(r"(\S+) (\S+) (\S+) (\S+) (\S+)$", f)   # cron
    if m:
        mi, h, dom, mon, dow = m.groups()
        a = len(mi.split(",")) * (24 if h == "*" else len(h.split(",")))
        return a * (7 if dow == "*" else len(dow.split(",")))
    return None


EXTRA = [  # 棚卸しから消えた（止めた）もの・工場の外の常駐も表に残す
    {"name": "claude-teiki:rusuban-mimawari-30min", "kind": "Claudeの定期タスク（画面に通知が出る）", "freq": "7,37 * * * *"},
    {"name": "cloud_mainichi.py", "kind": "心臓", "freq": "60分おき"},
    {"name": "com.google.GoogleUpdater.wake", "kind": "launchd（工場の外）", "freq": "60分おき", "tsukuru": "Chromeの更新確認"},
    {"name": "com.adobe.GC.Invoker-1.0", "kind": "launchd（工場の外）", "freq": "毎日 01:52", "tsukuru": "Adobeの点検"},
    {"name": "app.desktopcommander.remote", "kind": "launchd（工場の外）", "freq": "常駐", "tsukuru": "Desktop Commander の遠隔口"},
    {"name": "com.reasonmachines.network", "kind": "launchd（工場の外）", "freq": "常駐", "tsukuru": "Reason のネットワーク（Grok等とつなぐ口）"},
    {"name": "cron", "kind": "cron", "freq": "なし", "tsukuru": "crontab は空"},
]


def rows():
    d = json.load(open(SRC, encoding="utf-8"))
    have = {r["name"] for r in d["rows"]}
    out = []
    for r in d["rows"] + [e for e in EXTRA if e["name"] not in have]:
        n = r["name"]
        freq = r.get("freq", "")
        if n.startswith("claude-teiki:rusuban"):
            freq = "30分おき（7,37分）"
        ai = AI.get(n)
        wk = per_week(freq) if not n.startswith("claude-teiki:rusuban") else 336
        if n in NOBASHITA:
            hen = NOBASHITA[n]
        elif ai:
            hen = ai[3]
        else:
            hen = "そのまま"
        kind = r["kind"]
        uses = "呼ぶ" if ai and (ai[1] or ai[1] is None) and n not in ("muse_renraku.py", "cloud_mainichi.py", "gokigen_tane.py", "kaizen_loop.py") else "呼ばない"
        if n in ("kaizen_loop.py",):
            uses = "間接（列に積む）"
        if kind.startswith("GitHub"):
            uses = "呼ばない（GitHubの機械）"
            wk = None
        nani = ai[0] if ai else (r.get("tsukuru") or "")
        hituyou = TEIAN.get(n, "")
        if not hituyou and hen.startswith("止めた"):
            hituyou = "不要"
        if not hituyou:
            hituyou = hen.split("→")[-1] if "→" in hen else ("今のまま" if hen.startswith("そのまま") else hen)
        out.append({"name": n, "kind": kind, "nani": nani, "freq": freq, "ai": uses,
                    "wk": wk, "ai_mae": ai[1] if ai else 0, "ai_ato": ai[2] if ai else 0,
                    "hituyou": hituyou, "hen": hen})
    return out


def summary(rs):
    mae = sum(r["ai_mae"] or 0 for r in rs)
    ato = sum(r["ai_ato"] or 0 for r in rs)
    tometa = [r["name"] for r in rs if r["hen"].startswith("止めた")]
    nobashi = [r["name"] for r in rs if "→" in r["hen"] and not r["hen"].startswith("止めた")]
    return mae, ato, tometa, nobashi


def render(rs):
    mae, ato, tometa, nobashi = summary(rs)
    at = time.strftime("%Y-%m-%d %H:%M")
    head = ("定期で回っているもの（%s 時点・%d件）\n\n"
            "- 止めた：%d件（%s）\n- 間隔を延ばした：%d件\n"
            "- 見回りのAI呼び出し（1週間）：約%d回 → 約%d回\n"
            "- 工場の仕事そのもの（発車係が走らせる子セッション）は別枠。止めていない。\n"
            "- cron は無し。Claudeの定期タスクで有効なのは weekly-reset-wakeup（火曜1回）だけになった。\n") % (
        at, len(rs), len(tometa), "・".join(tometa), len(nobashi), mae, ato)
    cols = ["名前", "種類", "何をする", "頻度（棚卸しの時点）", "AI", "1週間の実行回数", "AI呼び出し/週 前→後", "本当に要る頻度", "11/18にしたこと"]
    order = sorted(rs, key=lambda r: (0 if r["ai"].startswith("呼ぶ") or r["ai_mae"] else 1,
                                      0 if "→" in r["hen"] or r["hen"].startswith("止めた") else 1, r["kind"], r["name"]))
    md = ["# " + head.split("\n")[0], ""] + head.split("\n")[2:] + ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    tr = []
    for r in order:
        aiw = ("%s→%s" % (r["ai_mae"], r["ai_ato"])) if (r["ai_mae"] or r["ai_ato"]) else ("出来た時だけ" if r["ai"].startswith("呼ぶ") else "0")
        cells = [r["name"], r["kind"], r["nani"][:80], r["freq"], r["ai"],
                 "" if r["wk"] is None else "{:,}".format(r["wk"]), aiw, r["hituyou"], r["hen"]]
        md.append("| " + " | ".join(c.replace("|", "／") for c in cells) + " |")
        hl = ' class="hen"' if ("→" in r["hen"] or r["hen"].startswith("止めた")) else ""
        tr.append("<tr%s>%s</tr>" % (hl, "".join("<td>%s</td>" % html.escape(c) for c in cells)))
    page = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>定期で回っているもの</title><style>
body{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:16px;color:#222}h1{font-size:20px}
ul{line-height:1.7}table{border-collapse:collapse;font-size:12px;width:100%%}th,td{border:1px solid #ddd;padding:4px 6px;vertical-align:top}
th{background:#f4f4f4;position:sticky;top:0}tr.hen td{background:#fff7e0}.w{overflow-x:auto}
</style></head><body><h1>定期で回っているもの</h1><ul>%s</ul>
<p style="font-size:12px;color:#666">黄色＝11/18に止めた・間隔を延ばした行。元データ status/public/jidou_tanaoroshi.json（1時間おきに作り直し）。</p>
<div class="w"><table><tr>%s</tr>%s</table></div></body></html>""" % (
        "".join("<li>%s</li>" % html.escape(x[2:]) for x in head.split("\n")[2:] if x.startswith("- ")),
        "".join("<th>%s</th>" % c for c in cols), "".join(tr))
    return "\n".join(md) + "\n", page


def main():
    rs = rows()
    md, page = render(rs)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write(md)
    open(OUT_HTML, "w", encoding="utf-8").write(page)
    mae, ato, tometa, nobashi = summary(rs)
    print("行 %d／止めた %d／延ばした %d／AI %d→%d" % (len(rs), len(tometa), len(nobashi), mae, ato))


def self_test():
    assert per_week("10分おき") == 1008 and per_week("6時間おき") == 28 and per_week("3 18 * * 2") == 1
    assert per_week("7,37 * * * *") == 336
    print("teiki_ichiran self-test OK")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()
