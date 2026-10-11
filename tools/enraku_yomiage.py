#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# kakeibo: 課金なし（音声の変換・写し・ページ作りだけ。外部APIは叩かない）
"""円卓会議の読み上げを1枚のページに（2026-10-11）

たまごさん：「音声で重くなるなら、1枚のHTMLにまとまっていればいい。カードの上にあればいい。軽いことが一番大事」

  1会議＝1カード（題名・日付・長さ・再生ボタン）。ページは最初に音声を1バイトも読まない。
  ▶を押したときだけ Google ドライブのプレーヤーをそのカードに差し込む（GitHub の1MBの関所に音声を載せない）。

材料：
  ・ずんだもん（status/zunda/progress.json の done ＝ #円卓会議 のノート110本。mp3は 2026-10-04 に
    ~/Library/Application Support/tamago_audio_outside_vault/音声 へ退避済み）
    → 64kbps未満のm4a（AAC・モノラル）に縮めて ドライブ「マイドライブ/朗読/円卓会議_読み上げ_ずんだもん/」へ
  ・Aoede の朗読（status/roudoku_enraku/result*.json ＝ finalize.py が書く）
    → tts_loop.py が最後までそろって finalize.py が result.json を書いたら、finalize.py の最後でこの道具が呼ばれ、
      カードが「途中まで」から「全編」に自動で入れ替わる。
  ・これから増える朗読：status/roudoku_*/result*.json を同じ形で書けば自動でカードになる。

使い方（Mac で）：
  python3 tools/enraku_yomiage.py --build            # ページだけ作り直す（速い）
  python3 tools/enraku_yomiage.py --upload --build   # ドライブへ上げてIDがそろうまで待ちながら作り直す
  python3 tools/enraku_yomiage.py --self-test
ページ：share/check/enraku-yomiage.html（心臓が share/ を公開する）
"""
import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.expanduser("~")
PROG = os.path.join(REPO, "status", "zunda", "progress.json")
AUDIO_DIR = os.path.join(HOME, "Library", "Application Support", "tamago_audio_outside_vault", "音声")
VAULT = os.path.join(HOME, "Library", "Mobile Documents", "iCloud~md~obsidian", "Documents", "tamago_brain")
ST = os.path.join(REPO, "status", "enraku_card")
IDS = os.path.join(ST, "drive_ids.json")
PAGE = os.path.join(REPO, "share", "check", "enraku-yomiage.html")
PAGE_URL = "https://tamago2022.github.io/tamago-shinchoku/share/check/enraku-yomiage.html"
SKIP = ("AI出力/_ルール/",)  # 会議ではない（引き継ぎメモ）


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def drive_root():
    c = sorted(glob.glob(os.path.join(HOME, "Library", "CloudStorage", "GoogleDrive-*", "マイドライブ")))
    return c[0] if c else None


def load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def save(p, o):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def drive_id(path):
    p = subprocess.run(["/usr/bin/xattr", "-p", "com.google.drivefs.item-id#S", path], capture_output=True)
    v = p.stdout.decode("utf-8", "replace").strip()
    return v if p.returncode == 0 and v and not v.startswith("local") else None


def seconds(path):
    try:
        out = subprocess.run(["/usr/bin/afinfo", path], capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
        m = re.search(r"estimated duration:\s*([\d.]+)", out)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def note_date(rel):
    try:
        st = os.stat(os.path.join(VAULT, rel))  # 中身が手元に無い(dataless)ノートでも時刻は読める
        return time.strftime("%Y-%m-%d", time.localtime(getattr(st, "st_birthtime", st.st_mtime)))
    except Exception:
        return None


def title_of(rel):
    t = os.path.splitext(os.path.basename(rel))[0]
    t = re.sub(r"^円卓会議[_｜|　 ]+", "", t).strip()
    return t or os.path.basename(rel)


def zunda_items():
    prog = load(PROG, {})
    out = []
    for rel, v in (prog.get("done") or {}).items():
        if rel.startswith(SKIP):
            continue
        # 2026-10 の作り直し(v2)で音声の名前は entaku_<題名のsha1先頭8桁>.mp3 にそろった。
        #   progress.json の file が古い名前(円卓音声_…)のままの行があるので、実物の名前を計算で引く。
        f = "entaku_%s.mp3" % hashlib.sha1(os.path.splitext(os.path.basename(rel))[0].encode("utf-8")).hexdigest()[:8]
        if not os.path.exists(os.path.join(AUDIO_DIR, f)) and os.path.exists(os.path.join(AUDIO_DIR, v["file"])):
            f = v["file"]
        out.append({"rel": rel, "file": f})
    return out


def upload(wait_min=240):
    root = drive_root()
    if not root:
        log("ドライブが見つからない"); return
    dest = os.path.join(root, "朗読", "円卓会議_読み上げ_ずんだもん")
    os.makedirs(dest, exist_ok=True)
    ids = load(IDS, {})
    for it in zunda_items():
        key = it["file"]
        src = os.path.join(AUDIO_DIR, key)
        if not os.path.exists(src):
            ids.setdefault(key, {})["missing"] = True; continue
        m4a = os.path.join(dest, os.path.splitext(key)[0] + ".m4a")
        rec = ids.setdefault(key, {})
        if rec.get("sec") is None:
            rec["sec"] = seconds(src)
        if not os.path.exists(m4a):
            tmp = "/tmp/enraku_%d.m4a" % os.getpid()
            r = subprocess.run(["/usr/bin/afconvert", "-f", "m4af", "-d", "aac", "-c", "1", "-b", "48000", src, tmp],
                               capture_output=True)
            if r.returncode != 0:
                rec["err"] = r.stderr.decode("utf-8", "replace")[:200]; log("変換失敗", key); continue
            shutil.move(tmp, m4a)
            log("上げた", key, os.path.getsize(m4a))
        rec["m4a"] = os.path.basename(m4a)
        save(IDS, ids)
    t0 = time.time(); last = -1
    while True:
        n = 0
        for key, rec in ids.items():
            if rec.get("id") or not rec.get("m4a"):
                n += bool(rec.get("id")); continue
            fid = drive_id(os.path.join(dest, rec["m4a"]))
            if fid:
                rec["id"] = fid; n += 1
        save(IDS, ids)
        total = sum(1 for r in ids.values() if r.get("m4a"))
        if n != last:
            log("ドライブのID %d/%d" % (n, total)); build(); last = n
        if n >= total or time.time() - t0 > wait_min * 60:
            break
        time.sleep(60)


SEG_ROOT = os.path.join(REPO, "share", "check", "enraku-yomiage", "a")


def seg_items():
    """朗読 v2：share/check/enraku-yomiage/a/<名>/index.json（status/roudoku_enraku/tts_loop.py が1区切りごとに書く）。
    約3分ずつの m4a を GitHub Pages から直接、順に流す（ドライブを通さない＝押してすぐ鳴る）。"""
    out = []
    for p in sorted(glob.glob(os.path.join(SEG_ROOT, "*", "index.json"))):
        r = load(p, {})
        segs = r.get("segments") or []
        slug = os.path.basename(os.path.dirname(p))
        out.append({"title": r.get("title") or slug, "date": r.get("date"), "voice": r.get("voice") or "Aoede（Gemini）",
                    "segs": ["enraku-yomiage/a/%s/%s" % (slug, s["file"]) for s in segs],
                    "min": sum(s.get("sec", 0) for s in segs) / 60.0 if segs else None,
                    "partial": len(segs) < (r.get("total") or 0), "done_n": len(segs), "total": r.get("total"),
                    "extra": True, "id": "seg:" + slug if segs else None})
    return out


def roudoku_items():
    """status/roudoku_*/result*.json（finalize.py が書く）。全編(result.json)があれば途中までは出さない。
    v2（seg_items）がある朗読は、古いドライブ版を出さない。"""
    if any(x["segs"] for x in seg_items()):
        return []
    out = []
    for d in sorted(glob.glob(os.path.join(REPO, "status", "roudoku_*"))):
        res = [p for p in glob.glob(os.path.join(d, "result*.json"))]
        full = [p for p in res if os.path.basename(p) == "result.json"]
        use = full or [p for p in res if "partial" in p]
        for p in use[:1]:
            r = load(p, {})
            url = r.get("url")
            m = re.search(r"/file/d/([\w-]+)", url or "")
            if not m:
                continue
            name = os.path.basename(r.get("local") or r.get("drive_path") or "")
            t = re.sub(r"_朗読_.*$", "", os.path.splitext(name)[0])
            t = re.sub(r"^円卓会議[_｜]+", "", t).replace("_", " ")
            out.append({"title": t or "円卓会議 朗読", "date": (r.get("at") or "")[:10], "id": m.group(1),
                        "min": r.get("minutes"), "voice": "Aoede（Gemini）",
                        "partial": not full, "extra": d.endswith("roudoku_enraku")})
    return out


CSS = """
:root{--paper:#f6f1e7;--ink:#1d1b18;--sub:#6b645a;--line:#d9d0bf;--acc:#b8432f}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Hiragino Mincho ProN","Yu Mincho",serif;-webkit-text-size-adjust:100%}
header{padding:28px 18px 10px;max-width:760px;margin:auto}
h1{font-size:26px;letter-spacing:.06em;margin:0 0 6px}
.lead{color:var(--sub);font-size:13px;line-height:1.7;margin:0}
.bar{max-width:760px;margin:10px auto 0;padding:0 18px}
input{width:100%;font-size:16px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fffdf8;font-family:inherit}
main{max-width:760px;margin:auto;padding:12px 18px 60px;display:grid;gap:12px}
.c{background:#fffdf8;border:1px solid var(--line);border-radius:14px;padding:14px 14px 12px}
.c.new{border-color:var(--acc)}
.t{font-size:16px;line-height:1.55;margin:0 0 8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.m{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font:12px/1.4 -apple-system,"Hiragino Sans",sans-serif;color:var(--sub)}
.k{border:1px solid var(--line);border-radius:99px;padding:2px 8px}
.k.a{color:var(--acc);border-color:var(--acc)}
button{margin-left:auto;font-size:15px;padding:9px 18px;border-radius:99px;border:0;background:var(--ink);color:var(--paper);font-family:-apple-system,"Hiragino Sans",sans-serif}
button[disabled]{background:var(--line);color:var(--sub)}
.p{margin-top:10px}.p iframe{width:100%;height:96px;border:0;border-radius:8px;background:#eee}
.p a{font:12px -apple-system,sans-serif;color:var(--sub)}
.p audio{width:100%}.s{font:12px -apple-system,sans-serif;color:var(--sub);margin:4px 0}
.r{display:flex;gap:6px;align-items:center;font:12px -apple-system,sans-serif;color:var(--sub);margin-top:6px}
.r .rb{margin:0;padding:6px 12px;font-size:13px;background:#fffdf8;color:var(--ink);border:1px solid var(--line)}
.r .rb.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
footer{max-width:760px;margin:auto;padding:0 18px 40px;color:var(--sub);font:11px/1.7 -apple-system,sans-serif}
"""

JS = """
var RATE=1.0,CUR=null;
function rates(){return '<div class="r">速さ '+[0.8,1.0,1.2,1.5].map(function(x){return '<button type="button" class="rb'+(x==RATE?' on':'')+'" onclick="setRate(this,'+x+')">'+x.toFixed(1)+'</button>'}).join('')+'</div>'}
function setRate(b,x){RATE=x;document.querySelectorAll('audio').forEach(function(a){a.playbackRate=x});
document.querySelectorAll('.rb').forEach(function(e){e.classList.toggle('on',e.textContent==x.toFixed(1))})}
function play(b){var c=b.closest('.c'),id=c.dataset.id,p=c.querySelector('.p');
if(p.innerHTML){var a0=p.querySelector('audio');if(a0)a0.pause();p.innerHTML='';b.textContent='▶ 聞く';return}
if(c.dataset.segs){var L=JSON.parse(c.dataset.segs),i=0;
if(CUR&&CUR!==p){var o=CUR.querySelector('audio');if(o)o.pause()}CUR=p;
p.innerHTML='<audio controls preload="auto"></audio><div class="s"></div>'+rates();
var a=p.querySelector('audio'),s=p.querySelector('.s'),nx=null;
function go(k){i=k;a.src=L[i];a.playbackRate=RATE;a.play();s.textContent=(i+1)+' / '+L.length+' 区切り'+(c.dataset.more?'（続きは作成中）':'');}
a.addEventListener('playing',function(){a.playbackRate=RATE;if(i+1<L.length){nx=new Audio();nx.preload='auto';nx.src=L[i+1]}});
a.addEventListener('ended',function(){if(i+1<L.length)go(i+1)});
go(0);b.textContent='閉じる';return}
p.innerHTML='<iframe loading="lazy" allow="autoplay" src="https://drive.google.com/file/d/'+id+'/preview"></iframe>'+
'<div><a href="https://drive.google.com/file/d/'+id+'/view" target="_blank" rel="noopener">鳴らないときはドライブで開く ↗</a></div>';
b.textContent='閉じる'}
function f(q){q=q.trim();document.querySelectorAll('.c').forEach(function(c){c.style.display=!q||c.dataset.q.indexOf(q)>=0?'':'none'})}
"""


def card(it):
    t = html.escape(it["title"])
    meta = []
    if it.get("date"):
        meta.append('<span>%s</span>' % html.escape(it["date"]))
    if it.get("min"):
        meta.append('<span>%d分</span>' % max(1, round(it["min"])))
    meta.append('<span class="k%s">%s</span>' % (" a" if "Aoede" in it["voice"] else "", html.escape(it["voice"])))
    if it.get("partial"):
        meta.append('<span class="k a">%s</span>' % ("%d/%d区切り・続きは毎朝つくり足し中" % (it["done_n"], it["total"]) if it.get("total") else "途中まで（続きは毎朝つくり足し中）"))
    elif it.get("segs"):
        meta.append('<span class="k">押してすぐ鳴る・速さ変更可</span>')
    if it.get("extra"):
        meta.append('<a href="enraku-roudoku-koe.html" style="color:inherit">声の聞き比べ</a>')
    btn = '<button onclick="play(this)">▶ 聞く</button>' if it.get("id") else '<button disabled>準備中</button>'
    extra_attr = ""
    if it.get("segs"):
        extra_attr = ' data-segs="%s"%s' % (html.escape(json.dumps(it["segs"])), ' data-more="1"' if it.get("partial") else "")
    return ('<article class="c%s" data-id="%s"%s data-q="%s"><p class="t">%s</p><div class="m">%s%s</div><div class="p"></div></article>'
            % (" new" if "Aoede" in it["voice"] else "", html.escape(it.get("id") or ""), extra_attr, html.escape(it["title"]), t, "".join(meta), btn))


def build():
    ids = load(IDS, {})
    items = [x for x in seg_items() if x["segs"]] + roudoku_items()
    for z in zunda_items():
        rec = ids.get(z["file"], {})
        if rec.get("missing"):
            continue
        items.append({"title": title_of(z["rel"]), "date": note_date(z["rel"]), "id": rec.get("id"),
                      "min": (rec["sec"] / 60.0) if rec.get("sec") else None, "voice": "ずんだもん"})
    items.sort(key=lambda x: (x.get("date") or "", "Aoede" in x["voice"]), reverse=True)
    ready = sum(1 for x in items if x.get("id"))
    body = "".join(card(x) for x in items)
    doc = ("<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">"
           "<meta name=robots content=noindex><title>円卓会議 読み上げ</title><style>%s</style></head><body>"
           "<header><h1>円卓会議 読み上げ</h1><p class=lead>1会議＝1枚。▶を押したカードだけ音が読み込まれます（ページ自体は音声を持たない）。"
           "%d本（再生できる %d本）。Aoede の朗読はこのページから直接・約3分ずつ順に流れ、速さを変えられます。"
           "ずんだもんの110本は Google ドライブ（たまごさんのアカウント）から流すので、鳴るまで少しかかります。</p></header>"
           "<div class=bar><input type=search placeholder=\"題名でしぼる\" oninput=\"f(this.value)\"></div>"
           "<main>%s</main><footer>更新 %s ／ ずんだもん＝VOICEVOX（2026-09〜10）・Aoede＝Gemini TTS。"
           "朗読の続きができると自動でここに載ります。</footer><script>%s</script></body></html>"
           % (CSS, len(items), ready, body, time.strftime("%Y-%m-%d %H:%M"), JS))
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    tmp = PAGE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(doc)
    os.replace(tmp, PAGE)
    log("ページ", PAGE, len(doc.encode("utf-8")), "bytes", "%d/%d" % (ready, len(items)))
    return len(items), ready


KOE_DIR = os.path.join(REPO, "share", "check", "enraku-roudoku")
KOE_PAGE = os.path.join(REPO, "share", "check", "enraku-roudoku-koe.html")
KOE_NOTE = {"Aoede": "本編に採用・抑揚（声の高さの揺れ）が最初の5人で一番小さい", "Despina": "2番目に平ら・少し速め",
            "Kore": "しっかりめ", "Sulafat": "高めで温かい・上下が大きい", "Leda": "若め・抑揚が大きい・ゆっくり"}


def build_koe():
    """聞き比べページ（同じ一節を男女10声）。tts_loop.py が1声できるたびに koe.json を書いて呼ぶ。"""
    k = load(os.path.join(KOE_DIR, "koe.json"), {})
    vs = k.get("voices") or []
    rows = []
    for v in vs:
        f = v.get("file")
        note = KOE_NOTE.get(v["name"], "2026-10-11 追加")
        au = ('<audio controls preload="none" src="enraku-roudoku/%s"></audio>' % html.escape(f)) if f else '<div class="m">準備中（無料枠の範囲で毎日少しずつ作っています）</div>'
        rows.append('<div class="v%s"><span class="n">%s</span><span class="sx">%s</span><div class="m">%s</div>%s</div>'
                    % (" pick" if v["name"] == "Aoede" else "", html.escape(v["name"]), html.escape(v["sex"]), html.escape(note), au))
    ready = sum(1 for v in vs if v.get("file"))
    doc = ("<!doctype html><html lang=ja><head><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">"
           "<meta name=robots content=noindex><title>円卓会議 朗読｜声の聞き比べ（Gemini TTS）</title><style>"
           "body{font-family:-apple-system,'Hiragino Sans',sans-serif;max-width:640px;margin:0 auto;padding:20px 16px 60px;background:#faf7f2;color:#222;line-height:1.7}"
           "h1{font-size:20px;margin:0 0 4px}.sub{color:#666;font-size:13px;margin:0 0 14px}"
           ".v{background:#fff;border:1px solid #e6e0d6;border-radius:12px;padding:12px 14px;margin:0 0 12px}.v.pick{border:2px solid #b5651d}"
           ".n{font-weight:700;font-size:17px}.sx{font-size:12px;border:1px solid #ccc;border-radius:6px;padding:1px 7px;margin-left:8px;color:#555}"
           ".m{font-size:12px;color:#666}audio{width:100%%;margin-top:6px}.r{position:sticky;top:0;background:#faf7f2;padding:8px 0;font-size:13px;z-index:2}"
           ".r button{font-size:14px;padding:6px 12px;margin-left:4px;border-radius:99px;border:1px solid #ccc;background:#fff}.r button.on{background:#222;color:#fff}"
           ".t{font-size:13px;background:#fff;border-left:3px solid #b5651d;padding:8px 10px;margin:0 0 14px;color:#444}"
           "</style></head><body><h1>円卓会議 朗読｜声の聞き比べ</h1>"
           "<p class=sub>Gemini の TTS の声（Aoede などは声の名前）。全員が下の同じ一節を読みます。%d/%d声。音量はそろえてあります。</p>"
           "<p class=t>%s</p>"
           "<div class=r>速さ <button onclick=\"R(this,.8)\">0.8</button><button class=on onclick=\"R(this,1)\">1.0</button><button onclick=\"R(this,1.2)\">1.2</button><button onclick=\"R(this,1.5)\">1.5</button></div>"
           "%s<p class=m>更新 %s ・ 課金0円（Gemini 無料枠）・ <a href=\"enraku-yomiage.html\">円卓会議 読み上げへ</a></p>"
           "<script>var X=1;function R(b,x){X=x;document.querySelectorAll('audio').forEach(function(a){a.playbackRate=x});"
           "document.querySelectorAll('.r button').forEach(function(e){e.classList.toggle('on',e===b)})}"
           "document.addEventListener('play',function(e){var a=e.target;a.playbackRate=X;document.querySelectorAll('audio').forEach(function(o){if(o!==a)o.pause()})},true)</script>"
           "</body></html>" % (ready, len(vs), html.escape(k.get("text") or ""), "".join(rows), time.strftime("%Y-%m-%d %H:%M")))
    tmp = KOE_PAGE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(doc)
    os.replace(tmp, KOE_PAGE)
    log("聞き比べページ", ready, "/", len(vs))


def self_test():
    assert title_of("00 inbox/円卓会議_【YouTube】題.md") == "【YouTube】題"
    assert title_of("円卓会議｜AIが.md") == "AIが"
    c = card({"title": "<a>", "date": "2026-10-11", "id": "X1", "min": 15.4, "voice": "Aoede（Gemini）", "partial": True})
    assert "&lt;a&gt;" in c and "途中まで" in c and "▶" in c and "drive" not in c  # 最初は iframe を持たない
    c2 = card({"title": "t", "id": None, "voice": "ずんだもん"})
    assert "準備中" in c2 and "disabled" in c2
    print("self-test OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        self_test(); sys.exit(0)
    os.makedirs(ST, exist_ok=True)
    if "--upload" in a:
        build(); upload()
    if "--koe" in a:
        build_koe()
    if "--build" in a or not a:
        build()
