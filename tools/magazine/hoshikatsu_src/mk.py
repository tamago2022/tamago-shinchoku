import sys,json,re
sys.path.insert(0,'/sessions/intelligent-practical-rubin/mnt/tamago/tamago-shinchoku/tools/magazine')
sys.path.insert(0,'/sessions/intelligent-practical-rubin/mnt/outputs')
import mag_build as MB
from tr1 import T; from tr2 import S,CAPS,PHOTO; from tr3 import Z
from bs4 import BeautifulSoup
h=open('/tmp/hk/out4.html',encoding='utf-8').read()
keys=MB.i18n_keys(h)
old=json.load(open('/tmp/hk/segs_ja.json',encoding='utf-8'))
assert keys==old, 'keymismatch'
LG=['en','zh-Hans','es','ko']
tr={l:{} for l in LG}; miss=[]
for k,ja in keys.items():
    plain=BeautifulSoup(ja,'html.parser').get_text().strip()
    if k in T or k in Z:
        en,ko=T[k]; zh,es=Z[k]
        v={'en':en,'ko':ko,'zh-Hans':zh,'es':es}
    elif ja in S or plain in S:
        a=S.get(ja) or S[plain]; v=dict(zip(['en','ko','zh-Hans','es'],a))
    elif 'data-i18n-cap' in ja:
        cap=re.search(r'<span data-i18n-cap="">(.*?)</span>',ja).group(1); anc=re.search(r'<a .*</a>',ja).group(0)
        c=CAPS[cap]; v={l:f'<span data-i18n-cap="">{c[i]}</span> {PHOTO[i]} {anc}' for i,l in enumerate(['en','ko','zh-Hans','es'])}
    elif '「' in plain and plain.index('「')>0 and plain[:plain.index('「')] in S and plain[plain.index('「'):] in S:
        a=S[plain[:plain.index('「')]]; b=S[plain[plain.index('「'):]]
        v={'en':a[0]+' '+b[0],'ko':a[1]+' '+b[1],'zh-Hans':a[2]+b[2],'es':a[3]+' '+b[3]}
    else:
        miss.append((k,plain)); continue
    for l in LG: tr[l][k]=v[l]
# placeholders count check
for k,ja in keys.items():
    n=len(re.findall(r'<a class="cw-src"',ja))
    for l in LG:
        if k in tr[l]:
            m=len(re.findall(r'\[\[\d+\]\]',tr[l][k]))
            if m!=n: print('PH',k,l,n,m)
tr['_title']={'ja':'君は星勝を知っているか 〜名前は知らなくても、音は知っている。日本のうたを支えた編曲家を辿る旅〜｜ごきげん補給所',
 'en':'Do You Know Katz Hoshi? — the arranger behind Japanese song｜Gokigen Hokyujo','zh-Hans':'你知道星胜吗——支撑日本歌谣的编曲家｜ごきげん補給所',
 'es':'¿Conoces a Katz Hoshi? — el arreglista detrás de la canción japonesa｜Gokigen Hokyujo','ko':'호시 카츠를 아십니까 — 일본의 노래를 떠받친 편곡가｜고키겐 보급소'}
print('miss',miss)
# stamp keys into html
soup=BeautifulSoup(h,'html.parser'); main=soup.find('main'); seen=set(); n=0
for q in MB.I18N_SEL:
    for el in main.select(q):
        if id(el) in seen or any(id(a) in seen for a in el.parents): continue
        if not re.search(r'[぀-ヿ一-鿿]',el.get_text()): continue
        n+=1; seen.add(id(el)); el['data-i18n']=f'k{n}'
h2=str(soup)
import re as _r
h2=_r.sub(r'<meta content="story" name="tamago-magazine"\s*/?>','<meta name="tamago-magazine" content="story"/>',h2)
h2=h2.replace('<div aria-hidden="true" class="cw-hero__bg">','<div class="cw-hero__bg" aria-hidden="true">')
h2=_r.sub(r'src="data:image/[^"]+"','src="assets/owner/x-avatar.jpg"',h2)
CL='<p data-i18n="k900">最後にもう一度、04章の、テレビ初出演の「氷の世界」を聴いてみてほしい。</p>'
k99='<p data-i18n="k99">'
i=h2.find(k99); assert i>0; h2=h2[:i]+CL+h2[i:]
h2=_r.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img alt="" decoding="async" src="([^"]+)"/>',r'\1<img src="\2" alt="" decoding="async"/>',h2)
for l,v in [('en','One last thing: go back to Chapter 04 and listen again to that first TV performance of "Koori no Sekai."'),('zh-Hans','最后，请再回到第04章，听一遍那段首次上电视的《冰的世界》。'),('es','Por último: vuelve al capítulo 04 y escucha otra vez aquella primera actuación televisiva de «Koori no Sekai».'),('ko','마지막으로 한 번 더, 04장의 첫 TV 출연 「얼음의 세계」를 들어 봐 주었으면 한다.')]: tr[l]['k900']=v
json.dump(tr,open('/sessions/intelligent-practical-rubin/mnt/tamago/tamago-shinchoku/tools/magazine/i18n_hoshikatsu.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
h2=MB.add_i18n(h2,tr)
open('/tmp/hk/out5.html','w',encoding='utf-8').write(h2)
print(n,len(h2),h2.count('cw-lang'))
