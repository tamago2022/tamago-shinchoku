# -*- coding: utf-8 -*-
"""共有ボタン（全マガジン・全特集の共通部品・2026-10-16 たまごさん「URLをコピーしてLINEに貼る手間は全部潰して」）
- 2026-10-18 たまごさん「SNSの分離」：
  ・段1「この特集をシェア」＝記事を読み終えた直後（締め cw-close の直後）。並び：LINE → WhatsApp → X → Facebook → Threads → リンクをコピー → 端末の共有
    場所の根拠：シェアしたい気持ちがいちばん高いのは読み終えた瞬間。OTHER MAGAZINES は「次へ進む」ための案内なので、その下に回すと押されない。
  ・段2「ごきげん補給所のSNSアカウント」＝ページのいちばん下。X・TikTok・YouTube。形も変える（共有＝丸い枠のアイコン／アカウント＝塗りの札＋@名前）
- 下書き入り（押したら送るだけ）の根拠（status/share_btn/evidence/ に原文保存）：
  LINE＝line.me/R/share?text=（LINE Developers「Share with画面を開き、textを入れる」）／WhatsApp＝wa.me/?text=（WhatsApp FAQ「pre-filled message」）／
  X＝x.com/intent/tweet?text=&url=（X docs「pre-populated text」）／Threads＝threads.com/intent/post?text=&url=（Meta Threads docs）／Facebook＝sharer.php?u= はURLだけ（本文を入れる口が無い）。
  下書きはサービスごとに変える：友だち1人に送るLINE・WhatsAppは「話しかける一言＋題名＋URL」、不特定に向けるX・Threadsは「短い一言＋題名」（URLは別の欄）。
- アイコンだけ（ロゴ。文字なし）。外部スクリプトなし・SVG内蔵（<symbol> を1回だけ定義して <use> で使い回す＝軽い）
- 共有文＝タイトル＋本番URL（canonical）。タイトルは押した瞬間の document.title（5言語の切替に追従）
- 同じ部品を React（/feature）でも使う：joy-relief-station src/components/ShareBar.tsx（中身は同じ並び・同じ大きさ）
アイコンは Simple Icons（CC0）。
"""
import json, os

# 2026-10-17 たまごさん：上の共有ボタン（LINE・X等）は一旦外す。別デザインが決まったら True に戻す。
TOP = False
HERE = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_X = 'https://x.com/oasisjoyrelief'   # サイト内の既存リンク（src/components/XFollowBand.tsx）
OFFICIAL_TIKTOK = 'https://www.tiktok.com/@joyreliefstation'  # サイト内の既存リンク（XFollowBand.tsx）
OFFICIAL_YOUTUBE = 'https://www.youtube.com/@joy-relief-station'  # 2026-10-18 たまごさん指定

P = {  # Simple Icons（CC0）
 'line': 'M19.36 9.86c.349 0 .63.28.63.63 0 .345-.281.63-.63.63H17.61v1.12h1.75c.349 0 .63.28.63.63 0 .344-.281.62-.63.62h-2.38c-.345 0-.627-.285-.627-.629V8.10c0-.345.28-.63.63-.63h2.38c.346 0 .627.28.627.63 0 .349-.281.63-.63.63H17.61v1.12h1.75zm-3.85 3.01c0 .27-.174.51-.432.59-.064.02-.133.03-.199.03-.211 0-.391-.09-.51-.25l-2.44-3.31v2.94c0 .344-.279.62-.631.62-.346 0-.626-.285-.626-.629V8.10c0-.27.17-.51.43-.595.06-.023.13-.033.19-.033.19 0 .375.10.495.25l2.46 3.33V8.10c0-.345.28-.63.63-.63.34 0 .63.28.63.63v4.77zm-5.74 0c0 .344-.282.62-.631.62-.345 0-.627-.285-.627-.629V8.10c0-.345.28-.63.63-.63.34 0 .628.28.628.63v4.77zm-2.46.629H4.91c-.345 0-.63-.285-.63-.629V8.10c0-.345.28-.63.63-.63.34 0 .63.28.63.63v4.14h1.75c.348 0 .629.28.629.63 0 .344-.282.62-.629.62M24 10.31C24 4.94 18.61.572 12 .572S0 4.94 0 10.31c0 4.81 4.27 8.84 10.03 9.60.391.08.923.25 1.05.59.12.30.079.76.038 1.08l-.164 1.02c-.045.30-.24 1.18 1.04.645 1.29-.539 6.91-4.07 9.43-6.97C23.17 14.39 24 12.45 24 10.31',
 'wa': 'M17.47 14.38c-.297-.149-1.75-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.29-.767.96-.94 1.16-.173.19-.347.22-.644.07-.297-.15-1.25-.463-2.39-1.47-.883-.788-1.48-1.76-1.65-2.05-.173-.297-.018-.458.13-.606.13-.133.29-.347.44-.52.14-.174.19-.298.29-.497.09-.198.05-.371-.025-.52-.075-.149-.669-1.61-.916-2.20-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.07-.792.37-.272.29-1.04 1.01-1.04 2.47 0 1.46 1.06 2.87 1.21 3.07.149.19 2.09 3.2 5.07 4.48.709.30 1.26.489 1.69.625.71.227 1.36.19 1.87.118.57-.085 1.75-.719 2.00-1.41.248-.694.24-1.28.173-1.41-.074-.124-.272-.198-.57-.347m-5.42 7.40h-.004a9.87 9.87 0 01-5.03-1.37l-.361-.214-3.74.982.99-3.64-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.43-9.88 9.88-9.88 2.64 0 5.12 1.03 6.98 2.89a9.82 9.82 0 012.89 6.99c-.003 5.45-4.43 9.88-9.88 9.88m8.41-18.29A11.81 11.81 0 0012.05 0C5.49 0 .16 5.33.157 11.89c0 2.09.547 4.14 1.58 5.94L.057 24l6.30-1.65a11.88 11.88 0 005.68 1.44h.005c6.55 0 11.89-5.33 11.89-11.89a11.82 11.82 0 00-3.48-8.41Z',
 'yt': 'M23.49 6.18a3.01 3.01 0 0 0-2.12-2.13C19.50 3.54 12 3.54 12 3.54s-7.50 0-9.37.505A3.01 3.01 0 0 0 .502 6.18C0 8.07 0 12 0 12s0 3.93.50 5.81a3.01 3.01 0 0 0 2.12 2.13c1.87.505 9.37.505 9.37.505s7.50 0 9.37-.505a3.01 3.01 0 0 0 2.12-2.13C24 15.93 24 12 24 12s0-3.93-.502-5.81zM9.54 15.56V8.43L15.81 12l-6.27 3.56z',
 'x': 'M18.90 1.15h3.68l-8.04 9.19L24 22.84h-7.40l-5.8-7.58-6.63 7.58H.474l8.6-9.83L0 1.15h7.59l5.24 6.93ZM17.61 20.64h2.03L6.48 3.24H4.29Z',
 'fb': 'M9.10 23.69v-7.98H6.62v-3.66h2.47v-1.58c0-4.08 1.84-5.97 5.85-5.97.401 0 .955.04 1.46.103a8.68 8.68 0 0 1 1.14.195v3.32a8.62 8.62 0 0 0-.653-.036 26.80 26.80 0 0 0-.733-.009c-.707 0-1.25.096-1.67.309a1.68 1.68 0 0 0-.679.62c-.258.42-.374.99-.374 1.75v1.29h3.91l-.386 2.10-.287 1.56h-3.24v8.24C19.39 23.23 24 18.17 24 12.04c0-6.62-5.37-12-12-12s-12 5.37-12 12c0 5.62 3.87 10.35 9.10 11.64Z',
 'th': 'M12.18 24h-.007c-3.58-.024-6.33-1.20-8.18-3.50C2.35 18.44 1.5 15.58 1.47 12.01v-.017c.03-3.57.879-6.43 2.52-8.48C5.84 1.20 8.6.02 12.18 0h.014c2.74.02 5.04.725 6.82 2.09 1.67 1.29 2.85 3.13 3.50 5.46l-2.04.56c-1.10-3.96-3.89-5.98-8.30-6.01-2.91.02-5.11.93-6.54 2.71C4.30 6.50 3.61 8.91 3.58 12c.027 3.08.718 5.49 2.05 7.16 1.43 1.78 3.63 2.69 6.54 2.71 2.62-.02 4.35-.631 5.8-2.04 1.64-1.61 1.61-3.59 1.09-4.79-.31-.71-.873-1.3-1.63-1.75-.192 1.35-.622 2.44-1.28 3.27-.886 1.10-2.14 1.70-3.73 1.79-1.20.065-2.36-.218-3.25-.801-1.06-.689-1.68-1.74-1.75-2.96-.065-1.19.40-2.28 1.33-3.08.88-.76 2.11-1.20 3.58-1.29a13.85 13.85 0 0 1 3.02.14c-.126-.742-.375-1.33-.75-1.75-.513-.586-1.30-.883-2.35-.89h-.029c-.844 0-1.99.232-2.72 1.32L7.73 7.84c.98-1.45 2.56-2.25 4.47-2.25h.044c3.19.02 5.09 1.97 5.28 5.38.108.04.216.09.321.14 1.49.7 2.58 1.76 3.15 3.07.79 1.82.87 4.79-1.54 7.15-1.85 1.81-4.09 2.62-7.27 2.65Zm1.00-11.69c-.242 0-.487.00-.739.02-1.83.103-2.98.94-2.91 2.14.067 1.25 1.45 1.83 2.78 1.76 1.22-.065 2.81-.543 3.08-3.71a10.5 10.5 0 0 0-2.21-.221z',
 'cp': 'M10.6 13.4a1 1 0 0 1 0-1.4l3.5-3.5a3 3 0 1 1 4.2 4.2l-1.8 1.8a1 1 0 0 1-1.4-1.4l1.8-1.8a1 1 0 1 0-1.4-1.4L12 13.4a1 1 0 0 1-1.4 0Zm2.8-2.8a1 1 0 0 1 0 1.4l-3.5 3.5a3 3 0 1 1-4.2-4.2l1.8-1.8a1 1 0 0 1 1.4 1.4l-1.8 1.8a1 1 0 1 0 1.4 1.4l3.5-3.5a1 1 0 0 1 1.4 0Z',
 'ok': 'M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6 11-11-1.4-1.4z',
 'sh': 'M12 2.6 7.3 7.3l1.4 1.4L11 6.4V15h2V6.4l2.3 2.3 1.4-1.4L12 2.6ZM5 11v9.5c0 .8.7 1.5 1.5 1.5h11c.8 0 1.5-.7 1.5-1.5V11h-2v9H7v-9H5Z',
}
LABEL = {'line': 'LINE', 'wa': 'WhatsApp', 'x': 'X', 'fb': 'Facebook', 'th': 'Threads', 'cp': 'Copy link / リンクをコピー', 'sh': 'Share / 共有'}

CSS = ('.cw .cw-share{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:22px 0}'
       '.cw .cw-share a,.cw .cw-share button{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;'
       'border:1px solid var(--line);color:var(--ink);background:transparent;cursor:pointer;transition:background .15s}'
       '.cw .cw-share a:hover,.cw .cw-share button:hover{background:rgba(237,230,214,.1)}'
       '.cw .cw-share svg{width:18px;height:18px;fill:currentColor}'
       '.cw .cw-share [data-sh=sh]{display:none}.cw .cw-share.can-sh [data-sh=sh]{display:inline-flex}'
       '.cw .cw-share__msg{font-size:12px;opacity:.9}.cw .cw-share__msg:empty{display:none}'
       '.cw .cw-share__raw{display:block;width:100%;max-width:420px;height:32px;margin-top:6px;padding:0 10px;border:1px solid var(--line);border-radius:6px;background:none;color:var(--ink);font-size:12px}'
       '.cw .cw-sharebox{margin:36px 0 8px;padding:18px 0 4px;border-top:1px solid var(--line)}'
       '.cw .cw-sharebox__h{margin:0;font-size:13px;letter-spacing:.14em;font-weight:700}'
       '.cw .cw-sharebox .cw-share{margin:12px 0 0}')


def symbols():
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
            + ''.join(f'<symbol id="i-{k}" viewBox="0 0 24 24"><path d="{v}"/></symbol>' for k, v in P.items()) + '</svg>')


def ic(k):
    return f'<svg aria-hidden="true"><use href="#i-{k}"/></svg>'


def bar(pos):
    btn = ''.join(f'<a href="#" data-sh="{k}" aria-label="{LABEL[k]}">{ic(k)}</a>' for k in ('line', 'wa', 'x', 'fb', 'th'))
    btn += f'<button type="button" data-sh="cp" aria-label="{LABEL["cp"]}">{ic("cp")}</button>'
    btn += f'<button type="button" data-sh="sh" aria-label="{LABEL["sh"]}">{ic("sh")}</button>'
    follow = ''
    if False:  # 2026-10-17：公式アカウントは共有ボタンと分けて sns() に
        follow = '<span class="cw-share__sep"></span>' + f'<a href="{OFFICIAL_X}" target="_blank" rel="noopener" aria-label="X @oasisjoyrelief">{ic("x")}</a>'
        if OFFICIAL_YOUTUBE:
            follow += f'<a href="{OFFICIAL_YOUTUBE}" target="_blank" rel="noopener" aria-label="YouTube">{ic("yt")}</a>'
    b = f'<div class="cw-share cw-share--{pos}" data-share="{pos}">{btn}{follow}</div>'
    if pos == 'bottom':  # 見出し付きの段（2026-10-18）
        b = f'<section class="cw-sharebox" aria-label="この特集をシェア"><p class="cw-sharebox__h" data-i18n="c_share_h">この特集をシェア</p>{b}</section>'
    return b


SCRIPT = ('<script>(function(){var c=document.querySelector("link[rel=canonical]"),E=encodeURIComponent,'
          # 下書き（言語ごと）：p＝友だち1人に送る一言（LINE・WhatsApp）、s＝みんなに向けた一言（X・Threads）、k＝コピーできた、r＝コピーできない時の案内
          'D={ja:{o:"「",c:"」",p:"これ、ちょっと読んでみて。おもしろかった。",s:"読み終えて、だれかに渡したくなった。",k:"コピーしました",r:"長押しして選んでコピー"},'
          'en:{o:"“",c:"”",p:"Have a read of this — I enjoyed it.",s:"Finished this and wanted to pass it on. ",k:"Copied",r:"Select and copy"},'
          '"zh-Hans":{o:"《",c:"》",p:"这篇你读读看，挺有意思的。",s:"读完了，想转给别人看看。",k:"已复制",r:"长按选择后复制"},'
          'es:{o:"«",c:"»",p:"Échale un ojo a esto, me ha gustado.",s:"Lo terminé y me dieron ganas de pasarlo. ",k:"Copiado",r:"Selecciona y copia"},'
          'ko:{o:"「",c:"」",p:"이거 한번 읽어 봐. 재밌더라.",s:"다 읽고 나니 누군가에게 건네고 싶어졌다. ",k:"복사했어요",r:"길게 눌러 선택해서 복사"}};'
          'document.querySelectorAll("[data-share]").forEach(function(b){if(navigator.share)b.classList.add("can-sh");'
          'b.addEventListener("click",function(ev){var a=ev.target.closest("[data-sh]");if(!a)return;'
          'var k=a.getAttribute("data-sh"),u=(c&&c.href)||location.href.split("#")[0].split("?")[0],t=document.title.split("｜")[0].trim(),w=D[document.documentElement.lang]||D.ja,q=w.o+t+w.c,pt=w.p+"\\n"+q+"\\n"+u,st=w.s+q,h;'
          # fl＝アイコンを一瞬✓にする／cp＝クリップボード→駄目なら旧式（textarea）→それも駄目なら ng
          'var fl=function(id){var y=a.querySelector("use");if(y){y.setAttribute("href","#i-ok");setTimeout(function(){y.setAttribute("href",id)},1800)}},'
          'cp=function(s,ok,ng){var f=function(){var x=document.createElement("textarea");x.value=s;x.style.cssText="position:fixed;top:0;left:0;opacity:0";document.body.appendChild(x);x.focus();x.select();var r=0;try{r=document.execCommand("copy")}catch(e){}x.remove();r?ok():ng&&ng()};'
          'navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(s).then(ok,f):f()};'
          # LINE（2026-10-17 店主指示）：スマホ＝line.me/R/share（アプリの送り先選択）、PC＝共有シート→無ければコピー＋line://。ログイン画面には飛ばさない
          'if(k==="line"){ev.preventDefault();if(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)){location.href="https://line.me/R/share?text="+E(pt);return}'
          'var fb=function(){cp(pt,function(){fl("#i-line")});var l=document.createElement("a");l.href="line://msg/text/"+E(pt);l.style.display="none";document.body.appendChild(l);try{l.click()}catch(e){}l.remove()};'
          'navigator.share?navigator.share({title:t,text:w.p+q,url:u}).catch(function(e){if(!e||e.name!=="AbortError")fb()}):fb();return}'
          'if(k==="wa")h="https://wa.me/?text="+E(pt);else if(k==="x")h="https://x.com/intent/tweet?text="+E(st)+"&url="+E(u);'
          'else if(k==="fb")h="https://www.facebook.com/sharer/sharer.php?u="+E(u);else if(k==="th")h="https://www.threads.com/intent/post?text="+E(st)+"&url="+E(u);'
          'if(h){ev.preventDefault();window.open(h,"_blank","noopener");return}'
          'if(k==="sh"){navigator.share({title:t,text:t,url:u}).catch(function(){});return}'
          # リンクをコピー（2026-10-18 120051：押しても無反応の指摘→押した瞬間に必ず画面で返事する）
          #   成功＝✓＋「コピーしました」の文字／クリップボードが使えない（未許可・無人ブラウザ・古い端末）＝URLを選択状態の欄で見せる
          'if(k==="cp"){var s=t+" "+u,m=b.querySelector(".cw-share__msg");if(!m){m=document.createElement("span");m.className="cw-share__msg";m.setAttribute("role","status");b.appendChild(m)}'
          'cp(s,function(){m.textContent=w.k;fl("#i-cp");clearTimeout(m._t);m._t=setTimeout(function(){m.textContent=""},2400)},'
          'function(){m.textContent=w.r;var i=document.createElement("input");i.readOnly=true;i.value=s;i.className="cw-share__raw";m.appendChild(i);try{i.select()}catch(e){}})}'
          '})})})();</script>')


SNS_PATH_TT = 'M16.6 3c.3 2.4 1.7 3.9 4 4.1v3.1c-1.5.1-2.9-.4-4-1.2v6.2c0 3.1-2.5 5.5-5.6 5.5S5.4 18.3 5.4 15.2c0-3.4 2.9-5.9 6.2-5.5v3.2c-1.7-.5-3.1.7-3.1 2.3 0 1.3 1 2.4 2.4 2.4 1.4 0 2.4-1 2.4-2.5V3h3.3z'
SNS_CSS = ('.cw .cw-sns{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:40px 0 24px}'
           '.cw .cw-share.cw-sns>span{flex-basis:100%;font-size:12px;letter-spacing:.12em;opacity:.8;margin-bottom:2px}'
           '.cw .cw-share.cw-sns a{width:auto;height:34px;border-radius:999px;padding:0 14px 0 11px;gap:7px;background:var(--ink);color:var(--bg,#111);border-color:var(--ink);font-size:12px;letter-spacing:.02em;text-decoration:none}.cw .cw-share.cw-sns b{font-weight:500}'
           '.cw .cw-share.cw-sns a:hover{background:var(--ink);opacity:.85}.cw .cw-share.cw-sns svg{width:15px;height:15px}')


def sns():
    """ごきげん補給所のSNSアカウント（2026-10-17 店主指示）：共有ボタンとは分けて、ページのいちばん下にまとめる。サイト内の既存リンクだけ。"""
    tt = f'<svg aria-hidden="true" viewBox="0 0 24 24"><path d="{SNS_PATH_TT}"/></svg>'
    return ('<div class="cw-wrap"><div class="cw-share cw-sns" data-sns="1"><span data-i18n="c_sns">ごきげん補給所をフォロー</span>'
            f'<a href="{OFFICIAL_X}" target="_blank" rel="noopener" aria-label="X @oasisjoyrelief">{ic("x")}<b>@oasisjoyrelief</b></a>'
            f'<a href="{OFFICIAL_TIKTOK}" target="_blank" rel="noopener" aria-label="TikTok @joyreliefstation">{tt}<b>@joyreliefstation</b></a>'
            f'<a href="{OFFICIAL_YOUTUBE}" target="_blank" rel="noopener" aria-label="YouTube @joy-relief-station">{ic("yt")}<b>@joy-relief-station</b></a></div></div>')


def add(h):
    """組み上がったマガジンのHTMLに共有ボタンを入れる（何度通しても同じ）。上＝ヘッダー（cw-hero）の直後、下＝締め（cw-close）の直後。"""
    import re as R
    h = R.sub(r'<section[^>]*class="cw-sharebox"[^>]*>.*?</section>', '', h, flags=R.S)  # 属性の順番が違っても外す（uke-01 の残骸・2026-10-18）
    h = R.sub(r'<div class="cw-share[^"]*" data-share="[a-z]+">.*?</div>(?=)', '', h, flags=R.S)
    h = R.sub(r'<svg [^>]*style="position:absolute"[^>]*>\s*<symbol id="i-line".*?</svg>', '', h, flags=R.S)  # 属性の順番が違っても外す
    h = R.sub(r'<script>\(function\(\)\{var c=document\.querySelector\("link\[rel=canonical\]"\).*?</script>', '', h, flags=R.S)
    h = R.sub(r'<style id="cw-share">.*?</style>', '', h, flags=R.S)
    # 上：2026-10-17 たまごさん「上の共有ボタンは一旦外す（別デザインを探し中）。下だけ残す」→ TOP=False の間は入れない
    if TOP:
        h, n = R.subn(r'(</header>\s*<div class="cw-wrap">)', lambda m: m.group(1) + bar('top'), h, count=1)
        if not n:  # ヒーローの無いページ（バックナンバー等）は最初の見出しブロックの直後
            h = R.sub(r'(</header>)', lambda m: m.group(1) + bar('top'), h, count=1)
    # 下：締めの直後
    m = R.search(r'<section[^>]*class="cw-close"[^>]*>.*?</section>', h, flags=R.S)
    if m:
        h = h[:m.end()] + bar('bottom') + h[m.end():]
    else:  # 締めが無いページ（バックナンバー等）は出典の前／本文の最後
        h = h.replace('</main>', '<div class="cw-wrap">' + bar('bottom') + '</div></main>', 1)
    h = R.sub(r'<div class="cw-wrap"><div class="cw-share cw-sns" data-sns="1">.*?</div></div>', '', h, flags=R.S)
    h = h.replace('</main>', sns() + '</main>', 1)
    h = h.replace('</head>', '<style id="cw-sns">' + SNS_CSS + '</style></head>', 1) if 'id="cw-sns"' not in h else h
    h = h.replace('<main class="cw"', symbols() + '<main class="cw"', 1) if 'id="i-line"' not in h else h
    h = h.replace('</head>', '<style id="cw-share">' + CSS + '</style></head>', 1)
    h = h.replace('</body>', SCRIPT + '</body>', 1)
    return h


def check(h):
    bad = []
    if h.count('data-share="top"') != (1 if TOP else 0): bad.append('上の共有ボタン')
    if h.count('data-share="bottom"') != 1: bad.append('下の共有ボタン')
    if 'id="i-line"' not in h or 'id="i-wa"' not in h: bad.append('アイコン定義')
    if h.count('class="cw-sharebox"') != 1 or 'data-i18n="c_share_h"' not in h: bad.append('シェアの見出し')
    if OFFICIAL_YOUTUBE not in h: bad.append('YouTubeアカウント')
    return bad
