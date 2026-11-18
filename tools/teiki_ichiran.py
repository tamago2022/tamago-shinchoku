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
AI = {  # 2026-11-19 作り直し：数字は会話ログの実測（tools/teiki_uchiwake.py・11/10 18時〜11/17 18時の1週）。後＝上限。
    "claude-teiki:rusuban-mimawari-30min": ("Claude Code の定期タスク。30分おき（毎時18分・48分）に Opus の会話を起こし、10/11からは「停止済み」と返すだけ。実測：1日48回・週336回・道具を使った回0", 336, 0, "止めた（中身 SKILL.md を控えへ。アプリは台帳の行を自分で書き戻すが、中身が無いので毎回 start_failed＝会話は作られない。teiki_jougen.py が毎日中身の復活を止める）"),
    "claude-teiki:weekly-reset-wakeup": ("週枠リセット直後に発車しているか見る（Coworkの会話1回）", 1, 1, "そのまま（週1回）"),
    "auth_keeper.py": ("ログインの生死を Sonnet に「1+1は？」と聞いて確かめる（実測：週203回）", 203, 7, "30分おき→1日1回"),
    "hyoudai.py": ("進捗表の見出しをAIで1行に書き直す（実測：週378回）", 378, 7, "10分おき→1日1回・1回20件まで（AI1回）"),
    "1192_title_romaji.py": ("新しい曲名のローマ字をAIで付ける（新曲がある日だけ。実測：週8回）", 8, 7, "1時間おき→1日1回"),
    "gaibu_copy_naoshi.py": ("外部カードのコピーをAIで書き直す（15分便から1日1回。1回25件まで＝最大25回/日。11/16〜18は書き戻しが弾かれAI0回）", 0, 14, "1回25件→2件（AI最大2回/日）"),
    "daimei_naoshi.py": ("外部カードの題名をAIで書き直す（30分おき・1日20件まで。11/11〜18は0件）", 0, 14, "30分おき→12時間おき・1日20件→2件"),
    "1191_honyaku_jidou.py": ("入荷した文を4言語へAIで訳す（実測：10/20週628回・11/05に停止済み）", 0, 0, "止まっている（11/05）"),
    "kenpin_gate.py": ("終わった仕事をAIで検品（仕事が終わるたび。実測：週117回）", None, None, "店主の判断待ち：仕事ごとに1回なので週14回を超える（止めると検品なしで公開に進む）"),
    "command_ingest.py": ("たまごさん／Dispatchの指示を列へ。止まった会話の再開にAI", None, None, "そのまま（指示が来た時だけ）"),
    "auto_launcher.py": ("工場の発車係。列の仕事をClaudeの子で走らせる＝仕事そのもの（実測：週360会話・使った量の63%）", None, None, "止めない（仕事そのもの）"),
    "suno_mcp.py": ("Sunoがつながったかを claude -p で確かめる（つながるまで）", None, None, "そのまま（ログイン待ちで止まっている・11/11〜18のAI0回）"),
    "grok_tsuushin.py": ("Reasonのネットワークで claude を待ち受ける（頼まれた時だけ）", None, None, "そのまま（頼まれた時だけ）"),
    "kaizen_loop.py": ("毎時の採点はAIなし。直す便を列に積む（実測：11/11〜18に3便）", None, None, "そのまま（週3便）"),
    "gokigen_tane.py": ("LINE一粒の下書き（配信はGrok担当になり、今は何もしない）", 0, 0, "5分おき→6時間おき"),
    "cloud_mainichi.py": ("クラウド枠を毎日使う係（11/1で期限切れ・毎時「期限後」と書くだけ）", 0, 0, "止めた"),
    "muse_renraku.py": ("Museへの依頼の返事を GitHub で見る（AIは呼ばない）", 0, 0, "10分おき→依頼中だけ1日2回・依頼が無ければ何もしない"),
    "com.tamago.machine-status": ("15分便。中の gaibu_copy_naoshi（1日1回）・daimei_naoshi（12時間おき）・2210_tanaire（1日1回）、session_watchdog は止まった時だけAI", None, None, "中のAI係を1日2回までに"),
    "teiki_jougen.py": ("AIを呼ぶ定期が1日2回を超えていないか・止めた定期の中身が戻っていないかを見る（AIは呼ばない）", 0, 0, "新設（11/19・1日1回）"),
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
    naka = {"gaibu_copy_naoshi.py": "15分便の中（1日1回）", "daimei_naoshi.py": "15分便の中（12時間おき）",
            "1191_honyaku_jidou.py": "心臓（11/05に止めた）", "teiki_jougen.py": "心臓（24時間おき）"}
    plus = [{"name": k, "kind": "心臓" if k.startswith(("1191", "teiki")) else "launchd（machine-status の中）", "freq": v}
            for k, v in naka.items() if k not in have]
    for r in d["rows"] + [e for e in EXTRA if e["name"] not in have] + plus:
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
        uses = "呼ぶ" if ai and n not in ("muse_renraku.py", "cloud_mainichi.py", "gokigen_tane.py", "kaizen_loop.py", "teiki_jougen.py", "1191_honyaku_jidou.py") else "呼ばない"
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


UCHI = os.path.join(REPO, "status", "public", "teiki_uchiwake.json")
JUN = ["留守番の見回り", "ほかの定期タスク", "心臓のAI係", "工場の検品", "工場の子セッション", "Dispatchの子", "Dispatch本体", "店主との会話", "不明"]


def uchiwake():
    try:
        return json.load(open(UCHI, encoding="utf-8"))
    except Exception:
        return None


def oku(n):
    return "%.2f億" % (n / 1e8) if n >= 1e7 else "{:,}".format(n)


def u_html(u):
    if not u:
        return "<p>（内訳はまだ集めていない：tools/teiki_uchiwake_atsume.py → tools/teiki_uchiwake.py）</p>"
    W = u["weeks"]
    ru = u["rusuban"]
    top = [
        "留守番の見回り（10/11から『停止済み』と返すだけ）：%d会話・%sトークン。直近4週（10/20〜11/17）の合計で週枠の約%.1f%%ぶん＝1週あたり1.0〜2.3%%【推測】" % (
            ru["tometa_ato"]["kaiwa"], oku(ru["tometa_ato"]["goukei"]),
            sum((w["cats"].get("留守番の見回り") or {}).get("waku_suisoku", 0) for w in W[:4])),
        "時計で動くAIの係（見出し係・ログイン確認・翻訳・ローマ字）は直近4週の合計で週枠の約%.1f%%ぶん＝1週あたり5〜8%%【推測・Haikuの係は多めに出る】。留守番と合わせて4週で約%.1f%%" % (
            sum((w["cats"].get("心臓のAI係") or {}).get("waku_suisoku", 0) for w in W[:4]),
            sum((w["cats"].get(k) or {}).get("waku_suisoku", 0) for w in W[:4] for k in ("心臓のAI係", "留守番の見回り"))),
        "いちばん使っているのは工場の子セッション（週の重みの56〜82%）とDispatchの子（6〜28%）＝仕事そのもの",
        "留守番の見回りの累計（ログが残る %s 以降）：%s会話・%sトークン（10/11までは着火などの本体を実行していた）" % (
            ru["saisho"], "{:,}".format(ru["kaiwa"]), oku(ru["goukei"])),
    ]
    th = "<tr><th>出どころ</th>" + "".join("<th>%s<br><small>週枠 %s%%</small></th>" % (html.escape(w["label"]), w["pct"]) for w in W) + "</tr>"
    tr = []
    names = [k for k in JUN if any(k in w["cats"] for w in W)]
    for k in names:
        cells = []
        for w in W:
            x = w["cats"].get(k)
            cells.append("<td>%s</td>" % ("—" if not x else "%d会話<br>%s<br>重み%.1f%%<br>週枠≈%.1f%%" % (x["kaiwa"], oku(x["goukei"]), x["wari"], x["waku_suisoku"])))
        tr.append('<tr%s><td>%s</td>%s</tr>' % (' class="ru"' if k == "留守番の見回り" else "", html.escape(k), "".join(cells)))
        if k == "心臓のAI係":
            subs = sorted({s for w in W for s in w["heart"]})
            for sname in subs:
                cells = []
                for w in W:
                    x = w["heart"].get(sname)
                    cells.append("<td>%s</td>" % ("—" if not x else "%d会話・%s・週枠≈%.1f%%" % (x["kaiwa"], oku(x["goukei"]), x["waku_suisoku"])))
                tr.append("<tr><td>　└ %s</td>%s</tr>" % (html.escape(sname), "".join(cells)))
    tr.append("<tr><td>合計</td>%s</tr>" % "".join("<td>%s</td>" % oku(w["goukei"]) for w in W))
    note = ("トークン＝会話ログの usage の input＋output＋キャッシュ書き込み＋キャッシュ読みの合計（同じ返事の二重書きは除く・子エージェントは親へ）。"
            "重み＝input×1＋書き込み×1.25＋読み×0.1＋output×5（APIの料金の比。Opus／Sonnet／Haikuの違いは入れていない＝Opusの留守番は少なめ、Haikuの係は多めに出る）。"
            "週枠≈＝重みの割合×その週の％【推測】。週枠の％の出どころ：" + "／".join("%s：%s" % (w["label"], w["pct_src"]) for w in W) +
            "。分からないこと：週枠が何トークンか（公開されていない）。Dispatch本体の11/12より前の会話ログは見つからない。店主との会話は直近4週のログに無い。集めた時刻 %s。" % u.get("at"))
    raw = ["実測：会話ログ %s 集計（tools/teiki_uchiwake_atsume.py → tools/teiki_uchiwake.py）。週｜週枠%%（記録）｜出どころ｜会話数｜トークン [input, output, 書き込み, 読み]｜重みの割合%%" % u.get("at")]
    for w in W:
        for k, x in sorted(w["cats"].items(), key=lambda kv: -kv[1]["wari"]):
            raw.append("%s｜%s｜%s｜%d｜%s｜%.2f" % (w["label"], w["pct"], k, x["kaiwa"], x["tok"], x["wari"]))
    ru = u["rusuban"]
    raw.append("留守番の見回り 10/11 23時以降：%d会話 %s／8/31以降：%d会話 %s" % (ru["tometa_ato"]["kaiwa"], ru["tometa_ato"]["tok"], ru["kaiwa"], ru["tok"]))
    return ("<ul>%s</ul><div class=\"w\"><table class=\"u\">%s%s</table></div><p class=\"note\">%s</p><details><summary>実測の生データ</summary><pre style=\"font-size:11px;white-space:pre-wrap\">%s</pre></details>" % (
        "".join("<li>%s</li>" % html.escape(x) for x in top), th, "".join(tr), html.escape(note), html.escape("\n".join(raw))))


def render(rs):
    mae, ato, tometa, nobashi = summary(rs)
    at = time.strftime("%Y-%m-%d %H:%M")
    u = uchiwake()
    head = ("定期で回っているもの（%s 時点・%d件）\n\n"
            "- 1週間のAI呼び出し（時計で動く定期）：変更前 %d回 → 変更後 上限%d回（11/10〜17の会話ログ実測。各係1日2回まで）\n"
            "- 留守番の見回り：11/18 17:48 の会話が最後。アプリの記録では 11/18 18:37 から30分おきに毎回『start_failed／task_file_missing』（会話は作られない）。会話ログでも 17:48 より後の留守番の会話は0件（11/19 04:18 確認）\n"
            "- 前の便の『留守番の見回り 週3,012回』は誤り。正しくは1日48回・週336回（30分おき＝毎時18分と48分に1回ずつ）\n"
            "- 止めた：%d件（%s）／間隔を延ばした：%d件\n"
            "- 仕事そのもの（工場の子・Dispatchの子・検品）は止めていない。検品（週117回）は1日2回を超えるので店主の判断待ち\n") % (
        at, len(rs), mae, ato, len(tometa), "・".join(tometa), len(nobashi))
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
.u td{text-align:right}.u td:first-child{text-align:left}.u tr.ru td{background:#ffe9e9;font-weight:bold}.note{font-size:12px;color:#555;line-height:1.6}
</style></head><body><h1>何が使っているか</h1>%s<h1>定期で回っているもの</h1><ul>%s</ul>
<p style="font-size:12px;color:#666">黄色＝11/18に止めた・間隔を延ばした行。元データ status/public/jidou_tanaoroshi.json（1時間おきに作り直し）。</p>
<div class="w"><table><tr>%s</tr>%s</table></div></body></html>""" % (
        u_html(u),
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
