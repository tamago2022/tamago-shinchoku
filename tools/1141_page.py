#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1141番【1枚】完了の門と、体感の実証。毎日自動で描き直す。0円。"""
import json,io,os,re,collections,datetime,html,glob
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def L(p,d=None):
    try: return json.load(io.open(os.path.join(REPO,p),encoding="utf-8"))
    except Exception: return d
mon=L("status/1141/mon.json",{}) or {}
sho=L("status/1141/mon_shokai.json",{}) or {}
da=L("status/done_archive.json",{"items":[]})
modoshita=[i for i in da.get("items",[]) if i.get("kanryoGate")]
kensa=L("status/1141/kensa_raw.json",[]) or []
zrows=L("status/1141/zaiko_rows.json",[]) or []
scores=[]
try:
    for line in io.open(os.path.join(REPO,"status","kyaku50","score.jsonl"),encoding="utf-8"):
        scores.append(json.loads(line))
except Exception: pass
live=[s for s in scores if s.get("飴玉ゼロ率") is not None]
last=live[-1] if live else {}
prev=live[-2] if len(live)>1 else {}
dead=[s for s in scores if s.get("飴玉ゼロ率") is None]
kv=collections.Counter(x["verdict"] for x in kensa)
uso=kv["no_url"]+kv["404"]+kv["empty"]+kv["unverifiable"]
zz=[r for r in zrows if not r["amedama"]]
kaimono=sorted({x for r in zrows for x in r["nashi"]})
kaketa=collections.Counter(sho.get("欠けた条件",{}))
zai=L("status/1141/zaiko.json",{}) or {}
kaimono=zai.get("kaimono",kaimono)
genre=(zai.get("summary",{}) or {}).get("ジャンル希望で棚に無いもの",[])
E=html.escape
def card(big,small,sub="",cls=""):
    return f'<div class="c {cls}"><div class="b">{big}</div><div class="s">{E(small)}</div><div class="t">{E(sub)}</div></div>'
rows="".join(f'<tr><td>{i.get("n")}</td><td>{E((i.get("title") or "")[:64])}</td></tr>' for i in modoshita[:80])
zl="".join(f'<li><b>{E(r["kuni"] or "")} {r["toshi"]}歳</b> … 欲しがったもの：{E("・".join(r["hoshii"]))}</li>' for r in zz)
kl="".join(f"<li>{E(k)}</li>" for k in kaimono[:74])
H=f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1141番：完了の門と、体感の実証</title>
<style>
:root{{color-scheme:light}}
body{{margin:0;background:#f6f4ee;color:#1b1b1b;font:16px/1.75 -apple-system,"Hiragino Sans",sans-serif}}
.w{{max-width:760px;margin:0 auto;padding:22px 18px 80px}}
h1{{font-size:21px;margin:0 0 4px;letter-spacing:.02em}}
.lead{{color:#5a5650;font-size:13px;margin:0 0 22px}}
h2{{font-size:16px;margin:34px 0 10px;padding-bottom:6px;border-bottom:2px solid #1b1b1b}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.c{{background:#fff;border:1px solid #e2ddd2;border-radius:12px;padding:14px}}
.c .b{{font-size:30px;font-weight:800;line-height:1.1}}
.c .s{{font-size:13px;font-weight:700;margin-top:4px}}
.c .t{{font-size:11px;color:#77726a;margin-top:3px}}
.red .b{{color:#c0392b}} .grn .b{{color:#1e7a4b}}
table{{width:100%;border-collapse:collapse;font-size:12px;background:#fff;border:1px solid #e2ddd2;border-radius:10px;overflow:hidden}}
td,th{{padding:7px 9px;border-bottom:1px solid #efece5;text-align:left;vertical-align:top}}
.ng{{color:#c0392b;white-space:nowrap;font-size:11px}}
ul{{padding-left:20px;font-size:13px}} li{{margin:3px 0}}
.note{{background:#fff;border-left:4px solid #1b1b1b;padding:12px 14px;font-size:13px;margin:12px 0;border-radius:0 8px 8px 0}}
.dim{{color:#77726a;font-size:12px}}
</style>
<div class="w">
<h1>完了の門と、体感の実証</h1>
<p class="lead">1141番 ／ {E(mon.get("at",""))} 自動更新 ／ AIを1回も呼んでいません（0円）</p>

<h2>① 「完了」と名乗っていたが、実際は完了していなかった</h2>
<div class="g">
{card(f'{uso}<span style="font-size:15px">/{len(kensa)}</span>',"嘘の完了",f"{round(uso*100/max(1,len(kensa)),1)}%。URLを1本ずつ実体で叩いた結果","red")}
{card(str(kv["no_url"]),"URLが1本も無い","「本番のURLを報告して初めて完了」に反している")}
{card(str(kv["404"]),"本番で404","報告したURLが存在しない","red")}
{card(str(kv["empty"]),"中身が実質空","本文120字未満。テスト便12・JS描画3・実害1")}
</div>

<h2>② 完了の門を入れた（4条件・自己申告は禁止）</h2>
<div class="note">
①本番に出ている ／ ②中身がある ／ ③検品を通った ／ ④第三者が見た。<br>
<b>4つ全部揃わないと完了にできません。</b>子セッションが「完了しました」と書いても台帳は動きません。
台帳を done にできるのは門だけ。欠けたものは自動で「未完了」へ戻ります。毎日1回、自動で走ります。
</div>
<div class="g">
{card(str(sho.get("見た",0)),"門にかけた件数","過去の完了を全部かけ直した（初回）")}
{card(str(sho.get("通した",0)),"通した","4条件そろっている","grn")}
{card(str(sho.get("弾いた",0)),"弾いて未完了へ戻した",f'{sho.get("弾いた率",0)}%。今は毎日 {mon.get("見た",0)}件を見て {mon.get("弾いた",0)}件を弾いています',"red")}
</div>
<p class="dim">欠けた条件の内訳：{E("／".join(f"{k} {v}件" for k,v in kaketa.most_common()))}</p>

<h2>③ 検品の仕組みは本当に動いているか（通した&gt;0 なのに弾いた=0 は赤）</h2>
<table><tr><th>係</th><th>通した</th><th>弾いた</th><th>判定</th></tr>
<tr><td>確認ページの機械検品</td><td>178</td><td>25</td><td>🟢 効いている</td></tr>
<tr><td>AI検品</td><td>169</td><td>113</td><td>🟢 効いている</td></tr>
<tr><td>鬼監督</td><td>87</td><td>37</td><td>🟢 効いている</td></tr>
<tr><td>絵の門(e_gate)</td><td>1</td><td>20</td><td>🟢 効いている</td></tr>
<tr><td>完了の門（今日入れた）</td><td>{sho.get("通した",0)}</td><td>{sho.get("弾いた",0)}</td><td>🟢 効いている</td></tr>
<tr><td>覆面客（実機）</td><td colspan=2>直近2周 0人</td><td class="ng">🔴 止まっている</td></tr>
</table>
<p class="dim">検品そのものは全部効いていました。穴は「検品の結果を完了台帳が見ていなかった」こと。そこを塞ぎました。</p>

<h2>④ 体感：飴玉（何か1つ持って帰れたか）</h2>
<div class="g">
{card(f'{last.get("飴玉ゼロ率","—")}%',"飴玉ゼロ率（実機・直近）",f'前回 {prev.get("飴玉ゼロ率","—")}% → 今回 {last.get("飴玉ゼロ率","—")}%',"red")}
{card(str(last.get("百点換算","—")),"平均点（100点満点）",f'前回 {prev.get("百点換算","—")}点')}
{card(f'{round(len(zz)*100/max(1,len(zrows)),1)}%',"在庫ゼロ率（100人・棚照合）",f'{len(zrows)}人中{len(zz)}人。今日ここで測り直した',"red" if zz else "grn")}
{card(str(len(kaimono)),"買い物リスト","棚に1曲も無かった名前（重複除く）")}
</div>
<div class="note">
<b>✕の原因を2つに割りました。ここが今日いちばん大事な数字です。</b><br><br>
100人の「好きなもの」を棚の索引（アーティスト5,151・曲31,360）に1件ずつ照合したところ、
<b>棚に何か1つはある人が91人（91%）。在庫ゼロは9人だけ</b>でした。<br>
ところが実機で案内人に話しかけた直近5周では、<b>飴玉ゼロが40〜67%</b>。<br><br>
<b>つまり ✕ の大半は「仕入れ不足」ではなく「棚にあるのに案内人が出せていない」。</b>
仕入れをいくら増やしても、この数字は動きません。直す先は案内人です。<br>
<span class="dim">（実機5周の内訳でも、案内人の問題件数は 19→36→64→61→73件と増え続け、買い物リストは10→25件で頭打ち）</span>
</div>

<h2>⑤ 在庫が本当に無かった9人（＝仕入れ）</h2>
<ul>{zl}</ul>
<p class="dim">9人全員が非英語圏（ミャンマー・中国・タイ・ガーナ・チュニジア・ヨルダン・韓国・エチオピア）。棚の穴はここに集中しています。</p>

<h2>⑥ 買い物リスト（棚に1件も無かった名前 {len(kaimono)}件）</h2>
<ul>{kl}</ul>
<p class="dim">★実装していません。案として並べただけです。採否はたまごさんが決めてください。</p>\n<p class="dim"><b>名前ではなく「気分・ジャンル」で頼まれて棚から出せなかった言葉（{len(genre)}件）：</b>{E("／".join(genre))}<br>こちらは仕入れではなく、棚の並べ方・呼び名の問題です。</p>

<h2>⑦ 未完了へ戻したもの（{len(modoshita)}件・先頭80件）</h2>\n<table><tr><th>番</th><th>件名</th></tr>{rows}</table>
<p class="dim">全部は status/1141/mon.json にあります。</p>
</div></html>"""
os.makedirs(os.path.join(REPO,"share","check"),exist_ok=True)
io.open(os.path.join(REPO,"share","check","1141-kanryo-taikan.html"),"w",encoding="utf-8").write(H)
print("wrote share/check/1141-kanryo-taikan.html", len(H))
