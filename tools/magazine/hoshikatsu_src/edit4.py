import re,sys,html as H
s=open('/tmp/hk/out3.html',encoding='utf-8').read()
def src(l,u): return f'<a class="cw-src" href="{u}" target="_blank" rel="noopener noreferrer">{l}</a>'
WEXPO='https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC%E4%B8%87%E5%9B%BD%E5%8D%9A%E8%A6%A7%E4%BC%9A'
WANAN='https://ja.wikipedia.org/wiki/An%E3%83%BBan'
WNONNO='https://ja.wikipedia.org/wiki/Non-no'
WOIL='https://ja.wikipedia.org/wiki/%E3%82%AA%E3%82%A4%E3%83%AB%E3%82%B7%E3%83%A7%E3%83%83%E3%82%AF'
T='https://thumb.wikimedia.org/wikipedia/commons/thumb/'
IL=[
 ('ch03', T+"8/86/United_Nations_Pavilion%2C_Osaka_Expo%2770_%28April_1970_by_Kingei_Marui%29.jpg/960px-United_Nations_Pavilion%2C_Osaka_Expo%2770_%28April_1970_by_Kingei_Marui%29.jpg",
  '1970年4月、大阪万博の国連館。', 'm-louis .® / CC BY-SA 2.0', "https://commons.wikimedia.org/wiki/File:United_Nations_Pavilion,_Osaka_Expo%2770_(April_1970_by_Kingei_Marui).jpg",
  f'1970年3月15日から183日間、大阪・千里丘陵で日本万国博覧会が開かれた。アジアで初めての万博で、総入場者数は6421万人を超えた{src("Wikipedia — 日本万国博覧会",WEXPO)}。モップスが「月光仮面」を歌っていた頃の日本は、こんな未来の形を見上げていた。'),
 ('ch04', "https://upload.wikimedia.org/wikipedia/commons/0/0d/Tokyo_1970-04-3.jpg",
  '1970年4月の東京。', 'Szilas / CC0', 'https://commons.wikimedia.org/wiki/File:Tokyo_1970-04-3.jpg',
  f'同じ1970年3月、『an・an』が創刊された{src("Wikipedia — an・an",WANAN)}。翌1971年5月には『non-no』{src("Wikipedia — non-no",WNONNO)}。若い女の子たちが、雑誌を片手に街へ出ていく時代が始まる。陽水の歌を聴いていたのは、この子たちだった。'),
 ('ch05', T+"2/26/Found_Photo_-_Japan_-_Tokyo_-_street_view_3.tif_%2834176177731%29.jpg/960px-Found_Photo_-_Japan_-_Tokyo_-_street_view_3.tif_%2834176177731%29.jpg",
  '1973年、東京の街かど。', 'David Pirmann / CC BY 2.0', 'https://commons.wikimedia.org/wiki/File:Found_Photo_-_Japan_-_Tokyo_-_street_view_3.tif_(34176177731).jpg',
  f'1973年10月、第四次中東戦争をきっかけに第1次オイルショックが始まった。翌1974年、消費者物価は23パーセント上がり、「狂乱物価」という言葉が生まれる。その年、日本は戦後初めてのマイナス成長を経験し、高度経済成長が終わった{src("Wikipedia — オイルショック",WOIL)}。'),
 ('ch08', T+"3/3c/Hot_dog_van_without_customers_in_street_of_Shinjuku%2C_circa_late-1970s_or_early-1980s_%28by_Jun_Shiraishi_%40Photozou_218980731%29.jpg/960px-Hot_dog_van_without_customers_in_street_of_Shinjuku%2C_circa_late-1970s_or_early-1980s_%28by_Jun_Shiraishi_%40Photozou_218980731%29.jpg",
  '1970年代の終わりごろ、新宿の路上。', '白石准（Jun Shiraishi） / CC BY-SA 2.5', 'https://commons.wikimedia.org/wiki/File:Hot_dog_van_without_customers_in_street_of_Shinjuku,_circa_late-1970s_or_early-1980s_(by_Jun_Shiraishi_@Photozou_218980731).jpg',
  f'第1次オイルショックは1977年3月まで続いた{src("Wikipedia — オイルショック",WOIL)}。長いトンネルを抜けた街に、80年代が来る。'),
]
CSS='.cw .cw-interlude{padding:56px 0}.cw .cw-interlude figure{margin:0 auto;max-width:760px}.cw .cw-interlude img{display:block;width:100%;height:auto;border-radius:4px;filter:sepia(.15)}.cw .cw-interlude figcaption{margin-top:10px;font-size:12.5px;line-height:1.6;color:var(--mute)}.cw .cw-interlude figcaption a{color:inherit;text-decoration:underline}.cw .cw-interlude p{max-width:640px;margin:22px auto 0;font-size:15.5px;line-height:1.95}'
s=s.replace('</style>\n<header class="cw-hero"',CSS+'</style>\n<header class="cw-hero"',1) if '</style>\n<header class="cw-hero"' in s else sys.exit('nocss')
for ch,img,cap,cred,page,text in IL:
    blk=(f'<section class="cw-interlude" aria-label="時代の空気"><div class="cw-wrap"><figure><img src="{img}" alt="{H.escape(cap)}" loading="lazy" decoding="async"/>'
         f'<figcaption><span data-i18n-cap>{cap}</span> 写真：<a href="{page}" target="_blank" rel="noopener noreferrer">{cred}（Wikimedia Commons）</a></figcaption></figure><p>{text}</p></div></section>')
    k=f'<section class="cw-chapter" id="{ch}">'
    k2=f'<section class="cw-chapter cw-chapter--paper" id="{ch}">'
    if k in s: s=s.replace(k,blk+k,1)
    elif k2 in s: s=s.replace(k2,blk+k2,1)
    else: sys.exit('nosec '+ch)
# sources
add=''.join(f'<li><a href="{u}" target="_blank" rel="noopener noreferrer">{l}</a></li>' for l,u in [('Wikipedia — 日本万国博覧会',WEXPO),('Wikipedia — an・an',WANAN),('Wikipedia — non-no',WNONNO),('Wikimedia Commons — 写真（各写真の下にクレジット）','https://commons.wikimedia.org/')])
s=s.replace('</ul><p class="cw-note">',add+'</ul><p class="cw-note">',1)
open('/tmp/hk/out4.html','w',encoding='utf-8').write(s)
print('ok', s.count('cw-interlude"'))
