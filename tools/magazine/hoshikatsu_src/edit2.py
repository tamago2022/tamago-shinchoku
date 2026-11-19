import re,sys,html as H
s=open('/tmp/hk/out.html',encoding='utf-8').read()
PLAY='<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5.5v13l11-6.5z"></path></svg>'
def e(t): return H.escape(t,quote=True)
def fig(id,role,artist,song,cap,size='small',page=None,q=None):
    q=q or ('maxresdefault' if size=='main' else 'hqdefault')
    return (f'<figure class="cw-video cw-video--{size}"><div class="cw-video__frame"><button type="button" class="cw-video__cover" data-yt-cover="{id}" aria-label="ここで再生：{e(artist)}「{e(song)}」"><img src="https://i.ytimg.com/vi/{id}/{q}.jpg" alt="" decoding="async"/><span class="cw-video__role">{e(role)}</span><span class="cw-video__play" aria-hidden="true">{PLAY}</span></button></div>'
            f'<figcaption><span class="cw-video__name"><b>{e(artist)}</b><i>「{e(song)}」</i></span><span class="cw-video__cap">{e(cap)}</span>'+(f'<a href="{e(page)}" class="cw-video__page">この曲のページへ →</a>' if page else '')+'</figcaption></figure>')
def li(id,role,artist,song,cap,href):
    return (f'<li><a href="{e(href)}"><span class="cw-map__img"><img src="https://i.ytimg.com/vi/{id}/mqdefault.jpg" alt="" decoding="async"/><em>00</em></span><span class="cw-map__txt" data-card-face="" data-card-music="1"><small data-card-genre="">{e(role)}</small><b data-card-heading="">{e(artist)}「{e(song)}」</b><i data-card-desc="">{e(cap)}</i></span></a></li>')
def figre(id): return re.compile(r'<figure class="cw-video cw-video--(main|small)"><div class="cw-video__frame"><button type="button" class="cw-video__cover" data-yt-cover="'+re.escape(id)+r'".*?</figure>',re.S)
def lire(id): return re.compile(r'<li><a href="[^"]*"><span class="cw-map__img"><img src="https://i.ytimg.com/vi/'+re.escape(id)+r'/mqdefault.jpg".*?</li>',re.S)
def swap(old,id,role,artist,song,cap,ch,page=None):
    global s
    m=figre(old).search(s); 
    if not m: sys.exit('nofig '+old)
    size=m.group(1); q='hqdefault'
    s=s[:m.start()]+fig(id,role,artist,song,cap,size,page,q)+s[m.end():]
    m=lire(old).search(s)
    if not m: sys.exit('noli '+old)
    s=s[:m.start()]+li(id,role,artist,song,cap,page or '#ch'+ch)+s[m.end():]
    s=s.replace(f'/vi/{old}/','/vi/{id}/'.replace('{id}',id))  # toc thumbs
# 05
swap('suR-AU4wxLs','4YM9lH_82vU','二色の独楽 1974','井上陽水','旅から旅','アルバム『二色の独楽』（1974年）の音源','05')
# 08 main
swap('W6TGQe2uWgc','CKBmWgihrnM','1980','来生たかお','スローモーション','No Brain（一般投稿）','08')
# 08 related yakushimaru
swap('8J-ov6-qlUw','w2UzVC9fYhQ','1981','薬師丸ひろ子','セーラー服と機関銃','Hiroko Yakushimaru - Topic（1981年のオリジナル音源・公式配信）','08')
# 10 related
swap('NvjoS1N453w','dgT4nU34uOE','1984 広東語版','譚詠麟（アラン・タム）','酒紅色的心','1984年の広東語版（一般投稿）','10')
swap('a0-2BHvk6QM','VKQQruBxWMM','1982','上田正樹','悲しい色やね -OSAKA BAY BLUES-','ichiropractor（一般投稿）','10')
# 11 related
swap('4YcAG6G4Pz0','cAVnxFszvKo','2019','King Gnu','飾りじゃないのよ涙は','King Gnu - Topic（『井上陽水トリビュート』収録・公式配信）','11')
swap('Oy7fhdAWvpk','tGzS70EnrEE','1992','浜田省吾','悲しみは雪のように','1992年のシングル版（公式配信）','11','https://joy-relief-station.lovable.app/cover-guide?artist=hamada&song=kanashimi-wa-yuki-no-youni')
# 04: remove 40-years-later comparison
a=s.find('id="ch04"'); b=s.find('id="ch05"'); seg=s[a:b]
seg2=re.sub(r'<p class="cw-more__label">聴きくらべ — 40年後の、同じ曲</p><div class="cw-more__grid">.*?</figure></div>','',seg,flags=re.S)
if seg2==seg: sys.exit('no04')
s=s[:a]+seg2+s[b:]
s=lire('lDrtcWkQsMU').sub('',s,1)
# 09: add Kisugi self version
a=s.find('id="ch09"'); b=s.find('id="ch10"'); seg=s[a:b]
seg=seg.replace('聴きくらべ — デビュー曲のほう','聴きくらべ — デビュー曲と、作った本人の声')
m=figre('HAh_Z4Uq0UM').search(seg)
K='https://joy-relief-station.lovable.app/cover-guide?artist=kisugi-takao&song=second-love'
seg=seg[:m.end()]+fig('hEyxari6i-g','1983 セルフカバー','来生たかお','セカンド・ラブ','Takao Kisugi - Topic（公式配信）','small',K)+seg[m.end():]
s=s[:a]+seg+s[b:]
m=lire('HAh_Z4Uq0UM').search(s)
s=s[:m.end()]+li('hEyxari6i-g','1983 セルフカバー','来生たかお','セカンド・ラブ','Takao Kisugi - Topic（公式配信）',K)+s[m.end():]
# renumber map
n=[0]
def ren(m):
    n[0]+=1; return f'<em>{n[0]:02d}</em>'
i=s.find('class="cw-map"'); j=s.find('</ol>',i)
s=s[:i]+re.sub(r'<em>\d+</em>',ren,s[i:j])+s[j:]
s=re.sub(r'THE MAP — \d+ SONGS',f'THE MAP — {n[0]} SONGS',s)
# hamada source
GEN='https://gendai.media/articles/-/106129'
s=s.replace('1977年からは浜田省吾の作品を延々と手がけてきた。',f'1977年からは浜田省吾の作品を延々と手がけてきた。「悲しみは雪のように」の依頼も、いつもと変わらず「カッコ良いサウンドにして下さい」だったと本人が振り返っている<a class="cw-src" href="{GEN}" target="_blank" rel="noopener noreferrer">週刊現代</a>。',1) if '1977年からは浜田省吾の作品を延々と手がけてきた。' in s else sys.exit('nohamada')
s=s.replace('</ul><p class="cw-note">',f'<li><a href="{GEN}" target="_blank" rel="noopener noreferrer">週刊現代（現代ビジネス） — 浜田省吾『悲しみは雪のように』を星勝さんらが語る（2023）</a></li></ul><p class="cw-note">',1)
open('/tmp/hk/out2.html','w',encoding='utf-8').write(s)
ids=re.findall(r'data-yt-cover="([^"]+)"',s); print(len(ids),sorted(set(ids)))
print(n[0])
