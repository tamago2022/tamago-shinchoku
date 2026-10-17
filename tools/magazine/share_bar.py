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
 'line': 'M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314',
 'wa': 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z',
 'yt': 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
 'x': 'M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z',
 'fb': 'M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z',
 'th': 'M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.75-1.757-.513-.586-1.308-.883-2.359-.89h-.029c-.844 0-1.992.232-2.721 1.32L7.734 7.847c.98-1.454 2.568-2.256 4.478-2.256h.044c3.194.02 5.097 1.975 5.287 5.388.108.046.216.094.321.142 1.49.7 2.58 1.761 3.154 3.07.797 1.82.871 4.79-1.548 7.158-1.85 1.81-4.094 2.628-7.277 2.65Zm1.003-11.69c-.242 0-.487.007-.739.021-1.836.103-2.98.946-2.916 2.143.067 1.256 1.452 1.839 2.784 1.767 1.224-.065 2.818-.543 3.086-3.71a10.5 10.5 0 0 0-2.215-.221z',
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
       '.cw .cw-share .cw-share__sep{flex:1}'
       '.cw .cw-share--top{margin:0 0 8px}'
       '.cw .cw-sharebox{margin:36px 0 8px;padding:18px 0 4px;border-top:1px solid var(--line)}'
       '.cw .cw-sharebox__h{margin:0;font-size:13px;letter-spacing:.14em;font-weight:700}'
       '.cw .cw-sharebox .cw-share{margin:12px 0 0}')


def symbols():
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
            + ''.join(f'<symbol id="i-{k}" viewBox="0 0 24 24"><path d="{v}"/></symbol>' for k, v in P.items()) + '</svg>')


def ic(k):
    return f'<svg aria-hidden="true"><use href="#i-{k}"/></svg>'


def bar(pos):
    btn = ''.join(f'<a href="#" data-sh="{k}" aria-label="{LABEL[k]}" rel="noopener">{ic(k)}</a>' for k in ('line', 'wa', 'x', 'fb', 'th'))
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


SCRIPT = ('<script>(function(){var c=document.querySelector("link[rel=canonical]"),U=function(){return (c&&c.href)||location.href.split("#")[0].split("?")[0]},'
          'T=function(){return document.title.split("｜")[0].trim()},E=encodeURIComponent,'
          # 下書き（言語ごと）：p＝友だち1人に送る一言（LINE・WhatsApp）、s＝みんなに向けた一言（X・Threads）
          'D={ja:{o:"「",c:"」",p:"これ、ちょっと読んでみて。おもしろかった。",s:"読み終えて、だれかに渡したくなった。"},en:{o:"“",c:"”",p:"Have a read of this — I enjoyed it.",s:"Finished this and wanted to pass it on. "},'
          '"zh-Hans":{o:"《",c:"》",p:"这篇你读读看，挺有意思的。",s:"读完了，想转给别人看看。"},es:{o:"«",c:"»",p:"Échale un ojo a esto, me ha gustado.",s:"Lo terminé y me dieron ganas de pasarlo. "},ko:{o:"「",c:"」",p:"이거 한번 읽어 봐. 재밌더라.",s:"다 읽고 나니 누군가에게 건네고 싶어졌다. "}},'
          'W=function(){return D[document.documentElement.lang]||D.ja};'
          'document.querySelectorAll("[data-share]").forEach(function(b){if(navigator.share)b.classList.add("can-sh");'
          'b.addEventListener("click",function(ev){var a=ev.target.closest("[data-sh]");if(!a)return;var k=a.getAttribute("data-sh"),u=U(),t=T(),h=null;'
          'var cpy=function(str,done){if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(str).then(done,function(){})}else{var x=document.createElement("textarea");x.value=str;document.body.appendChild(x);x.select();try{document.execCommand("copy");done()}catch(e){}x.remove()}};'
          'var flash=function(id){var y=a.querySelector("use");if(!y)return;y.setAttribute("href","#i-ok");setTimeout(function(){y.setAttribute("href",id)},1800)};'
          # LINE（2026-10-17 店主指示）：スマホ＝line.me/R/share（アプリの送り先選択）、PC＝共有シート→無ければコピー＋line://。ログイン画面には飛ばさない
          'var w=W(),q=w.o+t+w.c,pt=w.p+"\\n"+q+"\\n"+u,st=w.s+q;'
          'if(k==="line"){ev.preventDefault();var lt=pt;if(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)){location.href="https://line.me/R/share?text="+E(lt);return}'
          'var fb=function(){cpy(lt,function(){flash("#i-line")});var l=document.createElement("a");l.href="line://msg/text/"+E(lt);l.style.display="none";document.body.appendChild(l);try{l.click()}catch(e){}l.remove()};'
          'if(navigator.share){navigator.share({title:t,text:w.p+q,url:u}).catch(function(e){if(!e||e.name!=="AbortError")fb()})}else fb();return}'
          'if(k==="wa")h="https://wa.me/?text="+E(pt);else if(k==="x")h="https://x.com/intent/tweet?text="+E(st)+"&url="+E(u);'
          'else if(k==="fb")h="https://www.facebook.com/sharer/sharer.php?u="+E(u);else if(k==="th")h="https://www.threads.com/intent/post?text="+E(st)+"&url="+E(u);'
          'if(h){ev.preventDefault();window.open(h,"_blank","noopener");return}'
          'if(k==="sh"){navigator.share({title:t,text:t,url:u}).catch(function(){});return}'
          'if(k==="cp"){var s=t+" "+u,ok=function(){var y=a.querySelector("use");y.setAttribute("href","#i-ok");setTimeout(function(){y.setAttribute("href","#i-cp")},1600)};'
          'if(navigator.clipboard)navigator.clipboard.writeText(s).then(ok,function(){});else{var x=document.createElement("textarea");x.value=s;document.body.appendChild(x);x.select();try{document.execCommand("copy");ok()}catch(e){}x.remove()}}'
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
    h = R.sub(r'<section class="cw-sharebox".*?</section>', '', h, flags=R.S)
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
