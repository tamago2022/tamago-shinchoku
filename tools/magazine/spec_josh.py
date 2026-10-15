import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mag_build import write, src, BASE

WKZ = 'https://ja.wikipedia.org/wiki/%E9%A2%A8%E3%82%92%E3%81%82%E3%81%A4%E3%82%81%E3%81%A6_(%E3%81%AF%E3%81%A3%E3%81%B4%E3%81%84%E3%81%88%E3%82%93%E3%81%A9%E3%81%AE%E6%9B%B2)'
REM = 'https://reminder.top/669882129/'
CREA = 'https://crea.bunshun.jp/articles/-/43121'
CINE = 'https://cinemore.jp/jp/erudition/52/article_54_p3.html'
GUA = 'https://www.theguardian.com/music/2024/mar/26/translation-changes-the-original-meaning-how-70s-psych-rockers-happy-end-ended-the-japanese-rock-controversy'
JLT = 'https://joshualeeturner.com/About'
WJLT = 'https://en.wikipedia.org/wiki/Joshua_Lee_Turner'
XM = 'https://x.com/takashi_mtmt/status/1266735609843863553'
CDJ = 'https://www.cdjournal.com/main/cdjpush/priscilla-ahn/1000000796'
BARKS_AHN = 'https://barks.jp/news/676370/'
WNC = 'https://ja.wikipedia.org/wiki/%E3%83%8A%E3%83%81%E3%83%A5%E3%83%A9%E3%83%AB%E3%83%BB%E3%82%AB%E3%83%A9%E3%83%BC%E3%82%BA'
NIEW = 'https://niewmedia.com/series/hosono_house/3_edymm_wrhra/'
CINRA_T = 'https://www.cinra.net/article/interview-201502-readaloudtahiti80'
T80 = 'https://tahiti80.com/facts'
TO = 'https://www.timeout.com/tokyo/music/tahiti-80'

M = dict(
    key='josh', file='hikigatari-josh-turner-b.html', title='弾き語り・ジョシュ・ターナー編 ― 終わりの季節から、寄り道して',
    desc='はっぴいえんど「風をあつめて」を起点に、ブルックリンのJosh Turner、Priscilla Ahn、レイ・ハラカミ、Tahiti 80へ。日本語のまま海を渡った一曲を、ページの中で聴きながら辿る。',
    hero='QeWtMZYjnCE', eyebrow='Hikigatari — Josh Turner edition · 5 songs',
    h1='弾き語り・ジョシュ・ターナー編',
    lead='終わりの季節から、寄り道して。<br/>「風をあつめて」を一本の糸にして、ブルックリン、ロサンゼルス、ルーアンへ。5曲。',
    big='渋谷の喫茶店のトイレの落書きから、<br/>ブルックリンの部屋まで。',
    open=['1971年の東京で生まれた日本語の歌が、日本語のまま、海の向こうで歌われている。その道を、寄り道しながらたどってみる。'],
    door='最後は、フランスのバンドで軽く締める。',
    paper=[],
    chapters=[
        dict(no='01', en='すべての起点', title='はっぴいえんど - 風をあつめて', year='1971',
             main=dict(id='kTPw8tJLdtw', role='Live 1985', artist='はっぴいえんど', song='風をあつめて', cap='一般の方の投稿（1985年のライブ「All Together Now」）。12年で69万回以上再生されている'),
             body=[f'アルバム『風街ろまん』の一曲。詞は松本隆、曲は細野晴臣{src("Wikipedia", WKZ)}。',
                   f'詞のきっかけは、渋谷の喫茶店「マックスロード」のトイレの壁に書かれていた一行、「てふてふが一匹韃靼海峡を渡って行った」だった{src("CREA", CREA)}。',
                   f'録音はドタバタだった。大瀧詠一と鈴木茂はスタジオに呼ばれず、松本のドラム以外は全部、細野がひとりで演奏。ギター、ドラム、ベース、オルガンを重ねても、まだメロディができない。スタジオの廊下でやっとできて、すぐに歌った。だから「起きぬけの」のところは、歌い間違えたまま残っている{src("Re:minder", REM)}。',
                   f'2003年、映画『ロスト・イン・トランスレーション』で使われる。音楽プロデューサーが小山田圭吾に「この映画に合う日本の曲はないか」と尋ね、渡された音源の中から、ソフィア・コッポラと二人で選んだのがこの曲だった{src("CINEMORE", CINE)}。松本隆は2024年にこう話している。「母国語は日本語。翻訳するのはフィルターをかけるようなもの。元の意味が変わってしまう」{src("The Guardian", GUA)}。'],
             say='メロディが完成したのは、スタジオの廊下（Re:minder）。名曲、意外と立ち話で生まれてる。',
             bridge='そして2020年。この日本語の歌を、ブルックリンの若者が、日本語のまま歌った。'),
        dict(no='02', en='僕が彼を知ったのは、このツイートだった', title='Josh Turner - 風をあつめて', year='2020',
             main=dict(id='QeWtMZYjnCE', role='Cover 2020', artist='Josh Turner', song='風をあつめて (Gather the wind) - Happy End Cover', cap='Josh Turner Guitar 公式チャンネル'),
             body=['送りバントの高山さんが「これ最高だから聴いてください」と投げていた。高山さんは、めっちゃ面白い人だ。その人が「最高」と言うんだから、押すしかない。押したら、本当に最高だった。……と書きつつ、正直に言うと、Priscilla Ahn の版を聴いていたのが先だったかもしれない。どっちが先でもいい。たどり着いた先が、この人だった。',
                   f'ブルックリンを拠点にする、ギターも歌も鍵盤もやるミュージシャン。15歳だった2007年にYouTubeチャンネルを始めた。2014年、ポール・サイモン「Graceland」のカバーで『Good Morning America』に出ている{src("公式サイト", JLT)}{src("Wikipedia", WJLT)}。',
                   f'決めごとがある。口パクも、ごまかしも一切なし。聴こえている音を、そのまま弾いて見せる。カバーする曲はアルゴリズムではなく、自分の好奇心で選ぶ{src("公式サイト", JLT)}。',
                   f'この動画を、作詞した松本隆本人が紹介している。「ドラムのフィルまで感じつかんでる」{src("松本隆のX", XM)}。'],
             say='細野さんは先に知っていて、松本さんに「最近アメリカ人が日本語のままカバーしてるよ」と教えていた（松本隆のX）。はっぴいえんど、まだ連絡網が生きてる。',
             bridge='日本語の意味が分からなくても、この歌に惹かれた人は、ほかにもいる。'),
        dict(no='03', en='カバーつながりで、ひとつ寄り道', title='Priscilla Ahn - 風をあつめて', year='2012',
             main=dict(id='SWBVVgLBWvA', role='Cover 2012', artist='Priscilla Ahn', song='Kaze Wo Atsumete', cap='Priscilla Ahn 公式アーティストチャンネル'),
             body=[f'アメリカのシンガー・ソングライター。J-POPのカバー集『ナチュラル・カラーズ』に「風をあつめて」が入っていて、ほとんどの曲を日本語の詞のまま歌っている{src("BARKS", BARKS_AHN)}{src("Wikipedia", WNC)}。',
                   f'選んだのは本人だった。「〈風をあつめて〉は、私からやりたいとリクエストした曲です。映画『ロスト・イン・トランスレーション』のサントラを聴いて、歌詞の内容はまったくわかりませんでしたが、すごく好きになりました。私もバンドの一員として部屋の中にいるような感覚になるんです」{src("CDJournal", CDJ)}。'],
             bridge='寄り道のつもりが、ここで足が止まる。細野晴臣のもう一曲を、自分の声で歌った人がいる。'),
        dict(no='04', en='寄り道の、さらに寄り道', title='rei harakami - owari no kisetsu', year='2005',
             main=dict(id='wC1z9sNSaXo', role='lust 2005', artist='rei harakami', song='owari no kisetsu', cap='rei harakami - Topic（公式の音源配信）'),
             body=[f'細野晴臣が1973年の『HOSONO HOUSE』に入れた「終りの季節」を、レイ・ハラカミが本人の声でカバーした{src("NiEW", NIEW)}。',
                   f'この人の話は長くなるので、特集「<a href="{BASE}rei-harakami.html">君はレイ・ハラカミを知っているか</a>」にまとめた。'],
             bridge='最後は、フランスから。日本と縁の深いバンドで締める。'),
        dict(no='05', en='最後に、これをどうぞ', title='Tahiti 80 - Heartbeat', year='1999',
             main=dict(id='K3SezDMPpVM', role='Official MV', artist='Tahiti 80', song='Heartbeat', cap='Tahiti 80 公式アーティストチャンネル'),
             body=[f'フランス・ルーアンの大学で結成されたバンド{src("公式サイト", T80)}。1999年、当時のマネージャーがフランスでコーネリアスのマネジメントも担当していて、デモを小山田圭吾に渡せた。小山田はそのデモ版「Heartbeat」を自分のコンピレーションに入れた{src("CINRA", CINRA_T)}{src("Time Out Tokyo", TO)}。メンバーいわく「本当に幸運だった」{src("CINRA", CINRA_T)}。',
                   f'デビュー・アルバム『Puzzle』は日本でゴールドディスクになり、その中でいちばん成功したシングルが「Heartbeat」だった{src("公式サイト", T80)}。',
                   '実は Tahiti 80 も「風をあつめて」をカバーしている。それも良かった。でも最後はこっち。これだけは絶対に紹介したかった。'],
             more_label='関連動画 — Tahiti 80 の「風をあつめて」',
             more=[dict(id='lp6rkCyAaFc', role='Cover', artist='Tahiti 80', song='風をあつめて', cap='Tahiti 80 公式アーティストチャンネル')],
             say='バンド名は、ボーカルの父親が1980年にもらったお土産のTシャツから（公式サイト）。Tシャツ1枚で、バンドの名前が決まった事件。',
        ),
    ],
    close=['一曲のカバーを追いかけたら、知らない人に会えた。', 'トイレの落書きから始まった歌は、まだ旅の途中だ。', '次回の弾き語りもお楽しみに。'],
    sources=[('Wikipedia — 風をあつめて', WKZ), ('CREA — 松本隆と「風街」', CREA), ('Re:minder — 「風をあつめて」誕生', REM), ('CINEMORE — ロスト・イン・トランスレーション', CINE), ('The Guardian — Happy End', GUA),
             ('Joshua Lee Turner 公式サイト', JLT), ('Wikipedia — Joshua Lee Turner', WJLT), ('松本隆（X）', XM), ('CDJournal — Priscilla Ahn インタビュー', CDJ), ('BARKS — ナチュラル・カラーズ', BARKS_AHN), ('Wikipedia — ナチュラル・カラーズ', WNC),
             ('NiEW — 『HOSONO HOUSE』再訪', NIEW), ('CINRA — Tahiti 80', CINRA_T), ('Tahiti 80 公式サイト', T80), ('Time Out Tokyo — Tahiti 80', TO)],
    note='はっぴいえんどの映像は公式が見つからなかったため、長く残って再生回数の多い一般の方の投稿を使っています。高山さんの投稿は工場の記録から見つからなかったため、文章だけで触れています。事実は上の出典で確認できた範囲だけを書いています。',
)

if __name__ == '__main__':
    print(write(M))
