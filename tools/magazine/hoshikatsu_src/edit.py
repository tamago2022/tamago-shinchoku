import re,sys
s=open('/tmp/k.html',encoding='utf-8').read()
def R(a,b,n=None):
    global s
    c=s.count(a)
    if c==0 or (n and c!=n): sys.exit(f'NG {c} {a[:60]}')
    s=s.replace(a,b)
FULL='君は星勝を知っているか 〜名前は知らなくても、音は知っている。日本のうたを支えた編曲家を辿る旅〜'
R('<title>君は星勝を知っているか｜',f'<title>{FULL}｜')
R('content="君は星勝を知っているか"',f'content="{FULL}"')
R('<h1 class="cw-hero__title">君は星勝を知っているか</h1>','<h1 class="cw-hero__title">君は星勝を知っているか<span style="display:block;font-size:.4em;line-height:1.7;margin-top:.7em;font-weight:500;letter-spacing:.02em">〜名前は知らなくても、音は知っている。<br/>日本のうたを支えた編曲家を辿る旅〜</span></h1>')
R('<p class="cw-hero__lead">モップスのギタリストで、井上陽水「氷の世界」を編曲した人。<br/>名前を知らなくても、あなたはこの人の音を聴いている。ここから11曲。</p>',
  '<p class="cw-hero__lead">若い世代は、もう名前を知らないかもしれない。それでも、日本の音楽史に刻まれている人がいる。<br/>モップスのギタリストで、井上陽水「氷の世界」を編曲した、星勝。その仕事と足跡を、11曲で一緒に辿る旅。</p>')
# hero = young Yosui (TV debut)
R('lDrtcWkQsMU/maxresdefault.jpg','PGkM8FDFsJI/hqdefault.jpg',4)
R('<meta property="og:image:width" content="1280"/><meta property="og:image:height" content="720"/>','<meta property="og:image:width" content="480"/><meta property="og:image:height" content="360"/>')
# 03 心もよう -> young Yosui live
R('9TWH8nj7dFM/maxresdefault.jpg','mqlqEb22EUA/hqdefault.jpg')
R('9TWH8nj7dFM','mqlqEb22EUA')
R('<span class="cw-video__role">Live 2014</span>','<span class="cw-video__role">Live</span>')
R('UNIVERSAL MUSIC JAPAN（公式）','若いころの陽水の歌唱映像（一般投稿・11万回）')
# 06 シクラメン -> 1975 original single sound
R('vzTsWRhunVY/maxresdefault.jpg','42vMJqDngVg/hqdefault.jpg')
R('vzTsWRhunVY','42vMJqDngVg')
R('中山エミ（一般投稿・163万回）','1975年のシングル音源（編曲：小野崎孝輔、星勝）')
# 07 スローバラード -> TVK 1980
R('-mQElMb3R5c','e6oHTWcA4YA')
R('MrDenijac（一般投稿・265万回）','TVK「ファイティング80」1980年の放送より（一般投稿・262万回）')
# 08 remove wrong-shelf link
s=re.sub(r'<a href="https://joy-relief-station\.lovable\.app/cover-guide\?artist=rufus-gumede[^"]*" class="cw-video__page">この曲のページへ →</a>','',s)
s=re.sub(r'href="https://joy-relief-station\.lovable\.app/cover-guide\?artist=rufus-gumede[^"]*"','href="#ch08"',s)
R('徳永英明さんのカバーは在庫にあるので、そちらから曲ページにも入れます。','徳永英明さんのカバーからは、曲ページにも入れます。')
# sources: drop zaiko line, replace work note
s=re.sub(r'<li><a [^>]*>ごきげん補給所 — 曲の在庫一覧[^<]*</a></li>','',s)
s=re.sub(r'<p class="cw-note">.*?</p>','<p class="cw-note">動画は公式の配信元と、長く残っている一般投稿から選んでいます。事実は上の出典で確認できた範囲だけを書いています。</p>',s,flags=re.S)
s=re.sub(r'<script[^>]*cloudflareinsights[^>]*></script>','',s)
open('/tmp/hk/out.html','w',encoding='utf-8').write(s)
body=re.sub(r'<style>.*?</style>|<script.*?</script>','',s[s.find('<body'):],flags=re.S)
for w in ['じゃないけど','突き合わせ','在庫','新規入荷','oEmbed','叩き','Genspark','zaiko','候補','rufus','申し送り','NHKホール 2014','MrDenijac','中山エミ']:
    print(w, body.count(w))
print(len(s))
