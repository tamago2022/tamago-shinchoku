# -*- coding: utf-8 -*-
# 2026-10-16：07章「スローバラード」を、出典で確かめた事実（Wikipedia「スローバラード」）で書き直す＋終わりの共通部品を入れ直す
import sys, os, re, json
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
from bs4 import BeautifulSoup

SRC, OUT = sys.argv[1], sys.argv[2]
h = open(SRC, encoding='utf-8').read()
h = re.sub(r'<script>\(function\(\)\{var L=.*?</script>', '', h, flags=re.S)
TR = json.load(open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), encoding='utf-8'))
LG = ['en', 'zh-Hans', 'es', 'ko']
soup = BeautifulSoup(h, 'html.parser')
main = soup.find('main')
W_SB = 'https://ja.wikipedia.org/wiki/%E3%82%B9%E3%83%AD%E3%83%BC%E3%83%90%E3%83%A9%E3%83%BC%E3%83%89'
def src(l, u): return f'<a class="cw-src" href="{u}" target="_blank" rel="noopener noreferrer">{l}</a>'

def setk(k, ja, en, zh, es, ko):
    e = main.find(attrs={'data-i18n': k})
    if e is None: sys.exit('no ' + k)
    e.clear(); e.append(BeautifulSoup(ja, 'html.parser'))
    for l, v in zip(LG, [en, zh, es, ko]): TR.setdefault(l, {})[k] = v

setk('k64', '歌い継がれる、ふたりのバラード', 'A ballad for two, still being passed on', '被一代代传唱的，两个人的情歌', 'Una balada para dos que se sigue cantando', '계속 불려 내려오는, 두 사람의 발라드')
setk('k65', f'1976年1月21日、RCサクセションにとって4年ぶりのシングルとして出た。編曲は星勝とRCサクセション。ちょうど日本公演中だったタワー・オブ・パワーのホーン・セクションが録音に加わっている{src("Wikipedia — スローバラード", W_SB)}。',
     'Released January 21, 1976 — RC Succession\'s first single in four years. Arranged by Katz Hoshi and RC Succession. Tower of Power\'s horn section, in Japan on tour at the time, joined the session[[1]].',
     '1976年1月21日发行，是RC Succession时隔4年的单曲。编曲是星胜与RC Succession。正在日本巡演的Tower of Power的铜管组也参与了录音[[1]]。',
     'Salió el 21 de enero de 1976: el primer sencillo de RC Succession en cuatro años. Arreglo de Katz Hoshi y RC Succession. La sección de vientos de Tower of Power, de gira por Japón en ese momento, se sumó a la grabación[[1]].',
     '1976년 1월 21일, RC 석세션에게 4년 만의 싱글로 나왔다. 편곡은 호시 카츠와 RC 석세션. 마침 일본 공연 중이던 타워 오브 파워의 혼 섹션이 녹음에 참여했다[[1]].')
setk('k68', f'それでも、この曲は残った。1991年の『!［ai-ou］』、2015年の『ラブ&ピース』と、2本の映画の主題歌になった{src("Wikipedia — スローバラード", W_SB)}。ゴスペラーズ、和田アキ子、Bank Band、槇原敬之、Superfly、渋谷すばる、鈴木雅之……と、歌い継ぐ人の列は今も続いている{src("Wikipedia — スローバラード", W_SB)}。',
     'And yet the song stayed. It became the theme for two films — <i>!［ai-ou］</i> in 1991 and <i>Love &amp; Peace</i> in 2015[[1]]. The Gospellers, Akiko Wada, Bank Band, Noriyuki Makihara, Superfly, Subaru Shibutani, Masayuki Suzuki… the line of people singing it keeps going[[2]].',
     '即便如此，这首歌还是留了下来。它成了1991年的《!［ai-ou］》和2015年的《Love &amp; Peace》两部电影的主题曲[[1]]。Gospellers、和田秋子、Bank Band、槙原敬之、Superfly、涩谷昴、铃木雅之……传唱它的人至今络绎不绝[[2]]。',
     'Y aun así, la canción se quedó. Fue el tema de dos películas: <i>!［ai-ou］</i> en 1991 y <i>Love &amp; Peace</i> en 2015[[1]]. The Gospellers, Akiko Wada, Bank Band, Noriyuki Makihara, Superfly, Subaru Shibutani, Masayuki Suzuki… la fila de quienes la cantan no se detiene[[2]].',
     '그래도 이 곡은 남았다. 1991년 『!［ai-ou］』, 2015년 『러브 앤 피스』, 두 편의 영화 주제가가 되었다[[1]]. 고스펠러즈, 와다 아키코, Bank Band, 마키하라 노리유키, Superfly, 시부타니 스바루, 스즈키 마사유키…… 이어 부르는 사람들의 줄은 지금도 이어지고 있다[[2]].')
setk('k104', '清志郎が不満を口にした録音が、今も歌い継がれている。', 'The recording Kiyoshiro grumbled about is still being sung today.', '清志郎曾抱怨过的那次录音，至今仍被传唱。', 'La grabación de la que se quejó Kiyoshiro se sigue cantando hoy.', '기요시로가 불만을 말했던 그 녹음이, 지금도 불리고 있다.')
ul = main.select_one('.cw-sources ul')
if W_SB not in str(ul):
    ul.append(BeautifulSoup(f'<li><a data-i18n="h_src_sb" href="{W_SB}" rel="noopener noreferrer" target="_blank">Wikipedia — スローバラード</a></li>', 'html.parser'))
    for l, v in zip(LG, ['Wikipedia (ja) — Slow Ballad', 'Wikipedia（日文）— Slow Ballad', 'Wikipedia (ja) — Slow Ballad', 'Wikipedia(일본어) — 슬로 발라드']): TR[l]['h_src_sb'] = v
for l, d in MB.common_i18n().items():
    TR.setdefault(l, {}).update(d)
h2 = str(soup)
h2 = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', h2)
h2 = h2.replace('<div aria-hidden="true" class="cw-hero__bg">', '<div class="cw-hero__bg" aria-hidden="true">')
h2 = re.sub(r'(<div class="cw-hero__bg" aria-hidden="true">)<img alt="" decoding="async" src="([^"]+)"/>', r'\1<img src="\2" alt="" decoding="async"/>', h2)
h2 = MB.unify_tail(h2, 'hoshikatsu')
JN = 'kimi-wa-hoshi-katsu.i18n.json'
json.dump(TR, open(os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, JN), 'w', encoding='utf-8').write(json.dumps(TR, ensure_ascii=False, separators=(',', ':')))
h2 = h2.replace('</body>', MB.i18n_script(TR, JN) + '</body>', 1)
open(OUT, 'w', encoding='utf-8').write(h2)
print('ok', len(h2))
