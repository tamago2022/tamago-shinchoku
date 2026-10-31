# -*- coding: utf-8 -*-
"""君は星勝を知っているか：ch06（小椋佳の流れ）に「思い込み」（作詞・歌 小椋佳／作曲 星勝）を軽く1曲分差し込む（2026-10-22 たまごさん）
入れる場所：k61「小椋佳の曲として知られている曲が、実は星勝の作曲」の直後、聴きくらべ「スタンド・スティル」の前。
動画 28x7Wirobjw＝Kei Ogura - Topic（UMG提供・埋め込み可）。事実の出典＝Wikipedia「遠ざかる風景」。本文には出さず、最後の出典欄の ch06（h4 k7）に1行足し、対応を tools/magazine/shutten/kimi-wa-hoshi-katsu.json に1件足す。
※shutten.py を出典移し済みのページにもう一度通すと出典欄と対応表が消える（2026-10-22 実測）ので通さない。
使い方：python3 edit16_omoikomi.py <ページ.html> <ページ.i18n.json>   何度通しても同じ（data-omk="1" で判定）
"""
import json, sys
VID = '28x7Wirobjw'
WIKI = 'https://ja.wikipedia.org/wiki/%E9%81%A0%E3%81%96%E3%81%8B%E3%82%8B%E9%A2%A8%E6%99%AF'
PAGE = 'https://joy-relief-station.lovable.app/cover-guide?artist=ogura-kei&amp;song=omoikomi'
ANCHOR = '<p class="cw-more__label" data-i18n="k62">'
BLOCK = (
    '<p class="cw-more__label" data-i18n="h_omk_lb" data-omk="1">たとえば — 「思い込み」</p>'
    '<div class="cw-more__grid"><figure class="cw-video cw-video--small"><div class="cw-video__frame">'
    f'<button aria-label="ここで再生：小椋佳「思い込み」" class="cw-video__cover" data-yt-cover="{VID}">'
    f'<img alt="" decoding="async" loading="lazy" src="https://i.ytimg.com/vi/{VID}/hqdefault.jpg"/>'
    '<span class="cw-video__role">1976</span><span aria-hidden="true" class="cw-video__play"></span></button></div>'
    '<figcaption><span class="cw-video__name"><b data-i18n="k145">小椋佳</b><i data-i18n="h_omk_ti">「思い込み」</i></span>'
    '<span class="cw-video__cap" data-i18n="h_omk_cap">作詞・歌：小椋佳／作曲：星勝</span>'
    f'<a class="cw-video__page" data-i18n="c_songpage" href="{PAGE}">この曲のページへ →</a></figcaption></figure></div>'
    '<div class="cw-body" style="margin-top:18px"><p data-i18n="h_omk_p">1976年10月7日、NHKホール。小椋佳は午前中まで銀行で働き、午後に早退してステージに立った。'
    'このコンサートを収めたライブ盤『遠ざかる風景』で、「スタンド・スティル」のひとつ前に入っているのが「思い込み」。作詞と歌は小椋佳、作曲は星勝だ。</p></div>'
)
TR = {
    'h_omk_lb': ('For example — 「思い込み」 (Omoikomi)', '比如——《思い込み》', 'Por ejemplo — «思い込み» (Omoikomi)', '예를 들면 — 「思い込み」(오모이코미)'),
    'h_omk_ti': ('「思い込み」 (Omoikomi)', '《思い込み》', '«思い込み» (Omoikomi)', '「思い込み」(오모이코미)'),
    'h_omk_cap': ('Lyrics & vocals: Kei Ogura / Music: Katz Hoshi', '作词・演唱：小椋佳／作曲：星胜', 'Letra y voz: Kei Ogura / Música: Katz Hoshi', '작사・노래: 오구라 케이 / 작곡: 호시 카츠'),
    'h_omk_p': ('October 7, 1976, NHK Hall. Kei Ogura worked at the bank through the morning, left early in the afternoon, and walked on stage. The concert became the live album 『遠ざかる風景』 (Tozakaru Fukei), and the track right before "Stand Still" is 「思い込み」. Lyrics and vocals by Ogura, music by Katz Hoshi.',
                '1976年10月7日，NHK礼堂。小椋佳上午还在银行上班，下午早退登台。这场音乐会被收录成现场专辑《遠ざかる風景》，排在《Stand Still》前一首的，就是《思い込み》。作词和演唱是小椋佳，作曲是星胜。',
                '7 de octubre de 1976, NHK Hall. Kei Ogura trabajó en el banco toda la mañana, salió antes por la tarde y subió al escenario. Aquel concierto quedó en el disco en vivo 『遠ざかる風景』 (Tozakaru Fukei), y justo antes de «Stand Still» suena «思い込み». Letra y voz de Ogura, música de Katz Hoshi.',
                '1976년 10월 7일, NHK홀. 오구라 케이는 오전까지 은행에서 일하고 오후에 조퇴해 무대에 섰다. 이 콘서트를 담은 라이브 앨범 『遠ざかる風景』에서 「스탠드 스틸」 바로 앞에 실린 곡이 「思い込み」다. 작사와 노래는 오구라 케이, 작곡은 호시 카츠.'),
}
L4 = ['en', 'zh-Hans', 'es', 'ko']
if __name__ == '__main__':
    hp, ip = sys.argv[1], sys.argv[2]
    h = open(hp, encoding='utf-8').read()
    if 'data-omk="1"' not in h:
        assert h.count(ANCHOR) == 1, 'k62 の場所が1つでない'
        h = h.replace(ANCHOR, BLOCK + ANCHOR)
        open(hp, 'w', encoding='utf-8').write(h)
        print('inserted')
    SH = '<h4 data-i18n="k7">'
    LI = f'<li data-omk="1"><a href="{WIKI}" rel="noopener" target="_blank">Wikipedia — 遠ざかる風景</a></li>'
    if 'data-omk="1"><a' not in h:
        if SH in h:
            i = h.index(SH); j = h.index('</ul>', i)
            h = h[:j] + LI + h[j:]
        else:  # ch06 の出典は前の章と重なって見出しごと無い → k6 と k8 の間に見出しを作る
            nx = '<h4 data-i18n="k8">'
            assert h.count(nx) == 1
            h = h.replace(nx, SH + '小椋佳 - シクラメンのかほり</h4><ul>' + LI + '</ul>' + nx)
        open(hp, 'w', encoding='utf-8').write(h)
        print('source added')
    import os
    jp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shutten', 'kimi-wa-hoshi-katsu.json')
    rows = json.load(open(jp, encoding='utf-8'))
    if not any(r.get('url') == WIKI for r in rows):
        rows.append({'ch': 'ch06', 'chName': '小椋佳 - シクラメンのかほり', 'url': WIKI, 'label': 'Wikipedia — 遠ざかる風景',
                     'fact': '1976年10月7日NHKホールの小椋佳のコンサートを収めたライブ盤『遠ざかる風景』。小椋は午前中まで銀行で働き午後に早退。「思い込み」（作詞 小椋佳・作曲 星勝）は「スタンド・スティル」のひとつ前'})
        json.dump(rows, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('shutten row added')
    d = json.load(open(ip, encoding='utf-8'))
    for k, v in TR.items():
        for L, t in zip(L4, v):
            d[L][k] = t
    json.dump(d, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('i18n ok')
