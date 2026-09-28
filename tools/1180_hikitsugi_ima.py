#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1180号【引き継ぎは書かない。常に最新が1枚ある】2026-09-28

■ たまごさんの言葉（そのまま）
  「担当が変わっても同じ脳みそからスタートしたい」
  「前回は散々言ったのに半分も伝わってなくて、後ろを振り返りながら進むことになった」
  「また俺が説明するのかと思うと、担当を変えるのも気が重い」

■ なぜ「引き継ぎ文書を書く」をやめるのか
  交代のときに書く方式は、①書く暇がないときに書かれない ②書いた人の主観が入る
  ③書いた瞬間から古くなる、の3つで必ず腐る。だから**交代時に書くのをやめて**、
  機械で取れるものだけで**25分おきに作り直す**。
  人が書くのは「たまごさんに言われたこと」だけ＝それは受付台帳(status/daicho.json)が受け持つ。

■ 出すもの
  status/hikitsugi_ima.md              ← 常に最新の1枚（これが引き継ぎの正本）
  share/1180-hikitsugi-ima.html        ← スマホで開ける形（進捗表から飛ぶ）
  status/1180_aikotoba.json            ← 今日の合言葉（③の関所が照合する）

■ 材料（全部すでに機械が作っているもの。新種を発明しない）
  status/public/genzaichi.md   走っている仕組み／止まっている仕事／今日の実測値／未解決の真因
  status/daicho.json           たまごさんに言われたこと（kaisu＝同じことを言われた回数）
  status/public/ai_daicho.json 外部の駒（他のAI）が通っているか

■ 入れ方
  tools/genzaichi.py の main() の末尾から呼ばれる（＝心臓が毎周回読み直すPythonの側に置く）。
  heartbeat.sh は書き換えても動いている心臓に反映されないので、そこには1行も足していない。
"""
import datetime
import hashlib
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")

GENZAICHI = [os.path.join(ST, "public", "genzaichi.md"), os.path.join(ST, "genzaichi.md")]
DAICHO = os.path.join(ST, "daicho.json")
AI_DAICHO = os.path.join(ST, "public", "ai_daicho.json")

OUT_MD = os.path.join(ST, "hikitsugi_ima.md")
OUT_HTML = os.path.join(REPO, "share", "1180-hikitsugi-ima.html")
OUT_AIKOTOBA = os.path.join(ST, "1180_aikotoba.json")

URL_HTML = "https://tamago2022.github.io/tamago-shinchoku/share/1180-hikitsugi-ima.html"

JST = datetime.timezone(datetime.timedelta(hours=9))

# 合言葉の語彙。日付から機械で1語決まる＝当てずっぽうでは入らない。
AIKOTOBA_GOI = [
    "たまご", "こんろ", "しんぞう", "かんもん", "だいちょう", "ひきつぎ", "おにかんとく",
    "みかん", "やかん", "ふうりん", "はしご", "とうだい", "こがねむし", "あさつゆ",
    "くじら", "たけのこ", "いかだ", "ほうき", "ひなたぼこ", "つりばし",
]


def _read(p):
    try:
        with io.open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def genzaichi_text():
    for p in GENZAICHI:
        t = _read(p)
        if t:
            return t, p
    return "", ""


def kiru(text, midashi):
    """genzaichi.md から「## 見出し」の節だけを切り出す。取れなければ空文字。"""
    m = re.search(r"^##\s*" + re.escape(midashi) + r"[^\n]*\n(.*?)(?=^##\s|\Z)",
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


def kyou_no_aikotoba(d):
    h = hashlib.sha256(d.isoformat().encode("utf-8")).hexdigest()
    return AIKOTOBA_GOI[int(h[:8], 16) % len(AIKOTOBA_GOI)]


def iwareta_koto():
    """受付台帳から『言われたこと』を出す。回数3以上を先頭に。"""
    d = _json(DAICHO, {"rows": []})
    rows = [r for r in (d.get("rows") or []) if r.get("jotai") != "潰した"]
    for r in rows:
        r["_k"] = int(r.get("kaisu") or 1)
    rows.sort(key=lambda r: (-r["_k"], r.get("saigo") or ""))
    kurikaeshi = [r for r in rows if r["_k"] >= 3]
    nokori = [r for r in rows if r["_k"] < 3]
    return kurikaeshi, nokori, len(rows)


def gaibu_no_koma():
    d = _json(AI_DAICHO, {})
    out = []
    for a in (d.get("ai") or []):
        out.append("- **%s**：%s%s" % (
            a.get("label") or a.get("ai"),
            a.get("state") or "（状態が取れません）",
            ("／止まっている理由：" + a["blockedWhy"]) if a.get("blockedWhy") else "",
        ))
    return out, (d.get("updatedAt") or "")


def build():
    now = datetime.datetime.now(JST)
    g, gpath = genzaichi_text()
    aikotoba = kyou_no_aikotoba(now.date())
    kurikaeshi, nokori, zen = iwareta_koto()
    koma, koma_at = gaibu_no_koma()

    L = []
    A = L.append
    A("# 引き継ぎ（いま）— %s 時点・自動生成" % now.strftime("%m-%d %H:%M"))
    A("")
    A("**これは交代のときに書く物ではない。25分おきに作り直している。**")
    A("だから中身は古くならないし、書き忘れも起きない。")
    A("手で書くのは『たまごさんに言われたこと』だけで、それは受付台帳が受け持っている。")
    A("")
    A("## 0. 今日の合言葉：**%s**" % aikotoba)
    A("")
    A("この1枚を開いた証拠として、関所がこの言葉を聞く。")
    A("通し方：`python3 tools/1180_hikitsugi_kanmon.py --yonda %s`" % aikotoba)
    A("")
    A("---")
    A("")
    A("## 0.5 オリジナル禁止（憲法・1184番）")
    A("")
    A("**一流に倣って、先人に倣って、常に。自分で発明しない。**")
    A("新しい仕組み・新しい方式を実装する前に、この5段階を順に埋める。飛ばせない。")
    A("")
    A("1. 公式ドキュメントの目次を通しで読む。**★特に『MCPはあるか』を毎回確認する。**")
    A("2. 公式サンプルをそのまま移植できないか。")
    A("3. 優れた実例（金をかけずに同じことをやっている人）をお手本にできないか。")
    A("4. 外部AIに**白紙で**聞いたか（こちらの結論を見せずに）。")
    A("5. ①〜④が全部✕だった**証拠**があるときだけ、自分で考えてよい。")
    A("")
    A("**「似せる」は不合格。「そのまま」が合格。**")
    A("通し方：`python3 tools/1184_kanmon.py shirabe --nani \"…\" --koushiki \"…\" "
      "--mcp \"…\" --sample \"…\" --jitsurei \"…\" --gaibu \"…\" --ketsuron sonomama`")
    A("票が無いまま新しい `.py`/`.mjs`/`.js`/`.ts`/`.sh` を Write すると関所が止める。")
    A("")
    A("---")
    A("")

    A("## 1. 何回も言われていること（★ここだけは絶対に外さない）")
    A("")
    if kurikaeshi:
        A("同じことを3回以上言われた＝伝わっていない。**他の全部より先にここを読む。**")
        A("")
        for r in kurikaeshi:
            A("- **【%d回】%s**" % (r["_k"], r.get("irai") or "（内容なし）"))
            A("  - いまどこ：%s" % (r.get("koko") or "—"))
            A("  - 次の一手：%s" % (r.get("tsugi") or "—"))
    else:
        A("いまは3回以上言われているものはありません（受付台帳 %d件中0件）。" % zen)
        A("★これは『無い』のではなく『まだ数えていない』可能性がある。"
          "受付台帳に入っていない発言は数えられない。")
    A("")

    A("## 2. 言われて、まだ治っていないこと（受付台帳の全件）")
    A("")
    if nokori:
        for r in nokori[:20]:
            A("- 【%d回】%s ── いまどこ：%s" % (
                r["_k"], r.get("irai") or "", (r.get("koko") or "—")[:60]))
        if len(nokori) > 20:
            A("- ほか %d件（`share/daicho.html` で全件）" % (len(nokori) - 20))
    else:
        A("なし（または台帳が空）。")
    A("")

    A("## 3. 止まっていないか／走っている仕組み")
    A("")
    A(kiru(g, "★止まっていないか") or "（genzaichi.mdから取れませんでした）")
    A("")

    A("## 4. 今日の実測値")
    A("")
    A(kiru(g, "数字") or "（取れませんでした）")
    A("")
    A(kiru(g, "今日 止まっていた時間") or "")
    A("")

    A("## 5. 止まっている仕事／返事を待っているもの")
    A("")
    A(kiru(g, "今すぐ走っているもの") or "")
    A("")
    A(kiru(g, "待っているもの（返事待ち・本人しかできないこと）") or "")
    A("")

    A("## 6. 未解決の真因（引き継ぎで見落とすな）")
    A("")
    A(kiru(g, "未解決の失敗（924番・引き継ぎで見落とすな）") or "（取れませんでした）")
    A("")

    A("## 7. 外部の駒（他のAI）は通っているか")
    A("")
    if koma:
        L.extend(koma)
        A("")
        A("*（%s 時点。残りクレジットの数字はここには出ない＝出せるのはGenspark/Devinだけで、"
          "他は残枠を返すAPIが無い。正直に言うとここは『通っているか』までしか分からない。）*" % koma_at[:16])
    else:
        A("（status/public/ai_daicho.json から取れませんでした）")
    A("")

    A("---")
    A("")
    A("*材料：%s ／ status/daicho.json ／ status/public/ai_daicho.json*" % (gpath or "genzaichi.md"))
    A("*このファイルは tools/1180_hikitsugi_ima.py が作る。手で書き換えない"
      "（書き換えても25分後に消える）。*")

    md = "\n".join(L) + "\n"
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    with io.open(OUT_AIKOTOBA, "w", encoding="utf-8") as f:
        json.dump({"date": now.date().isoformat(), "aikotoba": aikotoba,
                   "url": URL_HTML, "madeAt": now.isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=1)

    write_html(md, now, aikotoba, len(kurikaeshi))
    return md


def write_html(md, now, aikotoba, kurikaeshi_n):
    """スマホで開ける形。.mdはスマホで開けない（たまごさん指摘・7章）。"""
    body = md
    # 見出しと太字だけの最小変換。ライブラリを増やさない。
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.M)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.M)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"`([^`]+)`", r"<code>\1</code>", body)
    body = re.sub(r"^---$", "<hr>", body, flags=re.M)
    body = re.sub(r"^(\s*)- (.+)$", r"\1・\2<br>", body, flags=re.M)
    body = body.replace("\n\n", "</p><p>")
    html = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>引き継ぎ（いま）</title>
<style>
:root{color-scheme:light dark}
body{margin:0;padding:16px 14px 64px;font-family:-apple-system,"Hiragino Sans",sans-serif;
line-height:1.75;max-width:760px;margin-inline:auto;font-size:16px}
h1{font-size:20px;line-height:1.4;margin:0 0 4px}
h2{font-size:17px;margin:28px 0 6px;padding:6px 10px;background:#00000010;border-radius:8px}
.aikotoba{font-size:26px;font-weight:800;letter-spacing:.1em;padding:14px;
text-align:center;border:3px solid currentColor;border-radius:12px;margin:12px 0}
p{margin:8px 0}code{background:#00000012;padding:1px 5px;border-radius:5px;font-size:14px}
hr{border:0;border-top:1px solid #00000022;margin:22px 0}
.mark{background:#ffe9a8;color:#000;padding:10px 12px;border-radius:8px;font-weight:700}
</style>
<div class="aikotoba">合言葉 %(aikotoba)s</div>
<div class="mark">何回も言われていること：%(n)d件</div>
<p>%(body)s</p>
<p style="opacity:.6;font-size:13px">作り直した時刻 %(at)s（25分おき・自動）</p>
</html>
""" % {"aikotoba": aikotoba, "n": kurikaeshi_n, "body": body,
       "at": now.strftime("%Y-%m-%d %H:%M")}
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with io.open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    build()
    print("wrote", OUT_MD, OUT_HTML, OUT_AIKOTOBA)
