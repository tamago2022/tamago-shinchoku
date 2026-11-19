# -*- coding: utf-8 -*-
"""君は星勝を知っているか：写真の塩梅（2026-10-17 たまごさん「写真は直前・直後の文を強めるものを」）
- 04章の後：ただの「1973年の街かど」→ 石油危機で消灯した看板（1973年10月 オレゴン州・NARA/EPA DOCUMERICA、パブリックドメイン）。
  導入にもオイルショックの説明があるので、ここの文は「100万枚の年の暮れ＝オイルショックのただ中」の一行に縮める。
- 05章の後：全曲ロサンゼルス録音の年 → 1974年11月 ハリウッドのチャイニーズ・シアター（Chas Smith, CC BY 3.0）。
"""
import json, os, re, sys
from bs4 import BeautifulSoup
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
SRC = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
h = open(SRC, encoding='utf-8').read()
if 'data-hk14="1"' in h:
    print('already'); sys.exit(0)
s = BeautifulSoup(h, 'html.parser')
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'); tr = json.load(open(TRP, encoding='utf-8'))
L4 = ['en', 'zh-Hans', 'es', 'ko']
def settr(k, d):
    for l in L4: tr[l][k] = d[l]
sel = json.load(open(os.path.join(R, 'status/hsk_audit/commons/sel3.json'), encoding='utf-8'))
neon = [o for o in sel if 'OREGON' in o['title']][0]
chin = [o for o in sel if 'Chinese Theater' in o['title']][0]
OIL = 'https://ja.wikipedia.org/wiki/%E3%82%AA%E3%82%A4%E3%83%AB%E3%82%B7%E3%83%A7%E3%83%83%E3%82%AF'
CR = {'en': 'Photo: ', 'zh-Hans': '照片：', 'es': 'Foto: ', 'ko': '사진: '}

# 04章の後
il = [x for x in s.select('section.cw-interlude') if 'Pirmann' in str(x)][0]
il['data-hk14'] = '1'
img = il.select_one('img'); img['src'] = neon['thumb'].split('?')[0]; img['alt'] = '石油危機で明かりを消した看板（1973年、オレゴン州）'
img['width'] = str(neon['tw']); img['height'] = str(neon['th'])
cap = il.select_one('figcaption'); ck = cap['data-i18n']
cja = '1973年10月、アメリカ・オレゴン州。ネオンと広告の明かりが禁止され、消えた看板に「明かりを消して節約しています」。'
cap.clear(); cap.append(BeautifulSoup(f'<span data-i18n-cap="">{cja}</span> 写真：<a href="{neon["page"]}" rel="noopener" target="_blank">David Falconer（NARA）/ パブリックドメイン（Wikimedia Commons）</a>', 'html.parser'))
cd = {'en': 'October 1973, Oregon. With neon and advertising lights banned, an unlit sign reads "Our lights are off to save energy."', 'zh-Hans': '1973年10月，美国俄勒冈州。霓虹灯和广告灯被禁止，熄灭的招牌上写着“我们关灯节约能源”。',
      'es': 'Octubre de 1973, Oregón. Con el neón y la luz publicitaria prohibidos, un cartel apagado dice «Apagamos las luces para ahorrar energía».', 'ko': '1973년 10월, 미국 오리건주. 네온과 광고 조명이 금지되고, 꺼진 간판에 “불을 끄고 에너지를 아끼고 있습니다”.'}
settr(ck, {l: cd[l] + f' {CR[l]}<a href="{neon["page"]}" rel="noopener" target="_blank">David Falconer (NARA) / Public domain (Wikimedia Commons)</a>' for l in L4})
p = il.select_one('p[data-i18n]'); pk = p['data-i18n']
pja = f'100万枚の『氷の世界』が出た1973年12月。日本も世界も、オイルショックのただ中にいた<a class="cw-src" href="{OIL}" rel="noopener" target="_blank">Wikipedia — オイルショック</a>。'
p.clear(); p.append(BeautifulSoup(pja, 'html.parser'))
settr(pk, {'en': 'December 1973, when the million-selling "Koori no Sekai" came out. Japan and the world were in the middle of the oil shock[[1]].',
           'zh-Hans': '卖出百万张的《冰的世界》发行的1973年12月，日本和世界都正处在石油危机之中[[1]]。',
           'es': 'Diciembre de 1973, cuando salió el millonario «Koori no Sekai». Japón y el mundo estaban en plena crisis del petróleo[[1]].',
           'ko': '100만 장의 『얼음의 세계』가 나온 1973년 12월. 일본도 세계도 오일쇼크 한복판에 있었다[[1]].'})

# 05章の後：ロサンゼルス 1974
ch05 = s.select_one('#ch05')
cja2 = '1974年11月、ロサンゼルス・ハリウッドのチャイニーズ・シアター。映画『大地震』を観る人の列。'
cd2 = {'en': 'November 1974: the Chinese Theatre in Hollywood, Los Angeles, with a line for the film Earthquake.', 'zh-Hans': '1974年11月，洛杉矶好莱坞的中国剧院。排队观看电影《大地震》的人们。',
       'es': 'Noviembre de 1974: el Teatro Chino de Hollywood, Los Ángeles, con la fila para ver la película Terremoto.', 'ko': '1974년 11월, 로스앤젤레스 할리우드의 차이니즈 시어터. 영화 『대지진』을 보려는 사람들의 줄.'}
cred = f'<a href="{chin["page"]}" rel="noopener" target="_blank">Chas Smith / CC BY 3.0（Wikimedia Commons）</a>'
la = BeautifulSoup(f'<section aria-label="時代の空気" class="cw-interlude"><div class="cw-wrap"><figure><img alt="1974年、ハリウッドのチャイニーズ・シアター" loading="lazy" decoding="async" src="{chin["thumb"].split("?")[0]}" width="{chin["tw"]}" height="{chin["th"]}"/>'
                   f'<figcaption data-i18n="h_la74"><span data-i18n-cap="">{cja2}</span> 写真：{cred}</figcaption></figure></div></section>', 'html.parser').section
settr('h_la74', {l: cd2[l] + f' {CR[l]}<a href="{chin["page"]}" rel="noopener" target="_blank">Chas Smith / CC BY 3.0 (Wikimedia Commons)</a>' for l in L4})
nxt = ch05.find_next_sibling()
if nxt is not None and 'cw-interlude' in (nxt.get('class') or []):
    nxt.select_one('.cw-wrap').insert(0, la.select_one('figure'))
else:
    ch05.insert_after(la)

out = str(s)
out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
out = MB.unify_look(out)
for q in (SRC, os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')):
    open(q, 'w', encoding='utf-8').write(out)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
print('ok', MB.look_check(out))
