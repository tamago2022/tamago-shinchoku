# -*- coding: utf-8 -*-
"""君は星勝を知っているか：10-18確定の型（怒れる人々 vol.1）にそろえる（120046番・2026-10-18）
- 章頭の一言を「小さくユーモアのある一言」に（10章）
- 吹き出し＝笑い（箸休め）と出典つき裏ネタを半々に（既存7を書き直し＋4つ追加）
- 出典で確かめられなかった事実を直す：埼玉県出身／14曲中8曲／キティ第1号『道草』1976-06-01／華語圏で最も多く改編／コメント欄の「Like Led Zeppelin」／TOWERの「名曲」
- 出典で確かめた事実を足す：170.3万枚・通算10週1位（悲しみは雪のように）／玉置「歌謡曲っぽくて売れそうな曲」／赤玉パンチ／鈴木幹治の縁／『愛的根源』(zh Wikipedia)
- 4言語（en/zh-Hans/es/ko）の訳を同じキーで更新。出典の一覧で訳が抜けていた8件も埋める
"""
import json, os, re, sys
from bs4 import BeautifulSoup
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(R, 'tools/magazine'))
import mag_build as MB
SRC = os.path.join(R, 'share/check/tokushu-hoshi-katsu.html')
h = open(SRC, encoding='utf-8').read()
if 'data-hk15="1"' in h:
    print('already'); sys.exit(0)
s = BeautifulSoup(h, 'html.parser')
TRP = os.path.join(R, 'tools/magazine/i18n_hoshikatsu.json'); tr = json.load(open(TRP, encoding='utf-8'))
L4 = ['en', 'zh-Hans', 'es', 'ko']

W = 'https://ja.wikipedia.org/wiki/'
HOSHI = W + '%E6%98%9F%E5%8B%9D'
WINE = W + '%E3%83%AF%E3%82%A4%E3%83%B3%E3%83%AC%E3%83%83%E3%83%89%E3%81%AE%E5%BF%83'
TAGA = W + '%E5%A4%9A%E8%B3%80%E8%8B%B1%E5%85%B8'
LGY = 'https://zh.wikipedia.org/wiki/%E6%84%9B%E7%9A%84%E6%A0%B9%E6%BA%90'
NOTE = 'https://note.com/60cloudviewroad/n/n13ff2836a473'
KANA = W + '%E6%82%B2%E3%81%97%E3%81%BF%E3%81%AF%E9%9B%AA%E3%81%AE%E3%82%88%E3%81%86%E3%81%AB'
GEND = 'https://gendai.media/articles/-/106129'
MCAL = 'http://music-calendar.jp/2015081901'
OGURA = W + '%E5%B0%8F%E6%A4%8B%E4%BD%B3'
KOKO = W + '%E5%BF%83%E3%82%82%E3%82%88%E3%81%86'

def a(u, lab):
    return f'<a class="cw-src" href="{u}" rel="noopener" target="_blank">{lab}</a>'

# key -> (ja with [[n]], {lang: text with [[n]]}, [anchors])
T = {}
def put(k, ja, en, zh, es, ko, anchors=()):
    T[k] = (ja, {'en': en, 'zh-Hans': zh, 'es': es, 'ko': ko}, list(anchors))

# ---- 導入 ----
put('k17', 'そのほとんどに、同じひとりの名前がクレジットされている。星勝（ほし かつ）。1948年8月19日生まれ、デビューしたての頃の芸名は「星まさる」だった[[1]]。19歳でギタリストとしてバンドでデビューし、解散してから編曲家に転じた人だ。',
    'On most of them, the same single name appears in the credits: Katz Hoshi. Born August 19, 1948; in his first days he went by the stage name "Hoshi Masaru"[[1]]. He debuted at 19 as a band guitarist, and after the band broke up he became an arranger.',
    '其中大多数，署着同一个人的名字：星胜。1948年8月19日生，刚出道时的艺名是“星まさる”[[1]]。19岁作为乐队吉他手出道，乐队解散后转为编曲家。',
    'En casi todas aparece el mismo nombre en los créditos: Katz Hoshi. Nacido el 19 de agosto de 1948; en sus primeros días usó el nombre artístico «Hoshi Masaru»[[1]]. Debutó a los 19 como guitarrista de una banda y, tras la separación, se hizo arreglista.',
    '그 대부분에 같은 한 사람의 이름이 크레디트되어 있다. 호시 카츠. 1948년 8월 19일생, 데뷔 직후의 예명은 ‘호시 마사루’였다[[1]]. 19세에 밴드의 기타리스트로 데뷔하고, 해산 뒤 편곡가로 돌아선 사람이다.', [a(HOSHI, 'Wikipedia')])

# ---- 章頭の一言 ----
put('k21', '目隠しで弾いた19歳。客は昼も夜も、同じ5人', 'Nineteen, playing blindfolded. Same five people in the audience, noon and night', '19岁蒙着眼演奏。白天晚上，台下都是同样的5个人', 'Diecinueve años, tocando con los ojos vendados. El mismo público de cinco, tarde y noche', '눈을 가리고 연주한 19세. 손님은 낮에도 밤에도 같은 5명')
put('k28', '初めて書いた譜面は、ブーイングから始まった', 'His first full score began with boos', '第一次写的总谱，从嘘声开始', 'Su primera partitura completa empezó con abucheos', '처음 쓴 악보는 야유로 시작됐다')
put('k36', '譜面が読めない男が、譜面を書き込んだ', 'The man who couldn\'t read music wrote out every part', '不识谱的男人，把谱子写满了', 'El hombre que no leía partituras las escribió nota a nota', '악보를 못 읽던 남자가, 악보를 빼곡히 써 넣었다')
put('k43', 'シャッターの下から売れた、日本初の100万枚', 'Sold from under a shop shutter: Japan\'s first million-selling LP', '从卷帘门下卖出去的，日本第一张百万唱片', 'Vendido por debajo de la persiana: el primer LP millonario de Japón', '셔터 아래로 팔려 나간, 일본 최초의 100만 장')
put('k51', 'ゴーストバスターズの男と、ロサンゼルスで', 'In Los Angeles, with the Ghostbusters guy', '和“捉鬼敢死队”那个人，在洛杉矶', 'En Los Ángeles, con el tipo de Cazafantasmas', '고스트버스터즈의 그 남자와, 로스앤젤레스에서')
put('k57', '「何でオレが…」から始まった、シクラメン', 'A cyclamen that began with "Why me?"', '从“为什么是我…”开始的仙客来', 'Un ciclamen que empezó con «¿Por qué yo?»', '“왜 내가…”에서 시작된 시클라멘')
put('k64', '清志郎、ご不満。でも半世紀、歌い継がれた', 'Kiyoshiro wasn\'t happy. It\'s been sung for half a century anyway', '清志郎不满意。但它被传唱了半个世纪', 'Kiyoshiro no quedó contento. Se ha cantado medio siglo igualmente', '기요시로는 불만. 그래도 반세기 동안 불려 왔다')
put('k71', '同じメロディが、11日違いで2回ヒットした', 'The same melody hit twice, eleven days apart', '同一段旋律，相隔11天红了两次', 'La misma melodía triunfó dos veces, con once días de diferencia', '같은 멜로디가, 11일 차이로 두 번 히트했다')
put('k84', '「歌謡曲っぽくて売れそうな曲」を、本気で狙った', 'They set out, in earnest, to write "a pop-ish song that would sell"', '认真瞄准了“像歌谣曲、好卖的歌”', 'Fueron a por «una canción pop que se venda», y muy en serio', '“가요곡 같고 팔릴 것 같은 노래”를 진심으로 노렸다')
put('k91', '11年後に降り直した雪、170万枚', 'Snow that fell again eleven years later: 1.7 million copies', '11年后重新落下的雪，170万张', 'Nieve que volvió a caer once años después: 1,7 millones de copias', '11년 뒤 다시 내린 눈, 170만 장')

# ---- 吹き出し ----
put('k2007', 'この「月光仮面」、歌っているのは星勝さん本人。ネットでは「さすがヒロミツの声！」と褒められることが多いそうで（ShimaQ の 今日この頃）、本人の歌が、別人の名前で褒められる。裏方人生、ここからもう始まっていた説。',
    'That\'s Katz Hoshi himself singing "Gekko Kamen." Online, people keep praising it as "classic Hiromitsu vocals!" (ShimaQ blog). His own singing, complimented under someone else\'s name. The backstage life had already begun.',
    '这首《月光仮面》，唱的是星胜本人。网上常有人夸“不愧是ヒロミツ的嗓音！”（ShimaQ博客）。自己的歌，被按别人的名字夸奖。幕后人生，从这里就开始了。',
    'En «Gekko Kamen» el que canta es el propio Katz Hoshi. En internet lo elogian como «¡la voz de Hiromitsu, sin duda!» (blog ShimaQ). Su canto, alabado con el nombre de otro. La vida entre bastidores ya había empezado.',
    '이 「月光仮面」, 노래하는 건 호시 카츠 본인. 인터넷에선 “역시 히로미츠의 목소리!”라는 칭찬이 많다고 한다(ShimaQ 블로그). 본인의 노래가 남의 이름으로 칭찬받는다. 뒷방 인생, 여기서 이미 시작됐다는 설.')
put('k2008', 'プロの楽団にいきなりブーイングされて、その場で書き直して、グランプリ。僕なら会場のトイレで膝を抱えてます。原因は音域表の「限界音」をフルに使ったこと（music-calendar.jp）。つまり全楽器に全力疾走を命じていた。新人、元気。',
    'Booed by a professional band on the spot, he rewrote the charts right there and took the grand prize. I\'d have been hugging my knees in the venue bathroom. The cause: he had used the "limit notes" on the range chart to the full (music-calendar.jp). He had ordered every instrument to sprint flat out. Rookies have energy.',
    '被专业乐团当场嘘，当场改谱，然后拿了大奖。换成我，早就蹲在会场厕所抱膝了。原因是把音域表上的“极限音”用到了满（music-calendar.jp）。等于命令所有乐器全力冲刺。新人，有劲。',
    'Abucheado por músicos profesionales, reescribió las partituras allí mismo y ganó el gran premio. Yo habría acabado abrazado a mis rodillas en el baño. La causa: usó al máximo las «notas límite» de la tabla de registros (music-calendar.jp). Es decir, ordenó a todos los instrumentos correr a tope. Los novatos tienen energía.',
    '프로 악단에게 다짜고짜 야유를 받고, 그 자리에서 고쳐 써서, 그랑프리. 나라면 화장실에서 무릎을 끌어안고 있었을 거다. 원인은 음역표의 ‘한계음’을 꽉 채워 쓴 것(music-calendar.jp). 즉 모든 악기에 전력 질주를 명령한 셈. 신인, 기운차다.')
put('h_q03', 'シングルの裏面、陽水さんが本当はA面にしたかったのは「帰れない二人」のほう。多賀さんが「心もよう」を推して題名まで付け、A面を取った。負けた「帰れない二人」は、忌野清志郎との共作です（Wikipedia — 心もよう）。その清志郎が、4章あとで星勝と組みます。',
    'The song Yosui actually wanted as the A-side was "Kaerenai Futari," the B-side. Taga pushed "Kokoro Moyo," even named it, and won the A-side. The losing song was co-written with Kiyoshiro Imawano (Wikipedia — Kokoro Moyo). Four chapters from now, that Kiyoshiro teams up with Katz Hoshi.',
    '单曲的B面——阳水真正想放A面的是《帰れない二人》。多贺力推《心もよう》，连标题都是他起的，拿下了A面。落选的《帰れない二人》是和忌野清志郎合写的（Wikipedia — 心もよう）。四章之后，这位清志郎会和星胜搭档。',
    'La que Yosui quería de verdad como cara A era «Kaerenai Futari», la cara B. Taga empujó «Kokoro Moyo», hasta le puso el título, y se quedó con la cara A. La perdedora está coescrita con Kiyoshiro Imawano (Wikipedia — Kokoro Moyo). Cuatro capítulos más adelante, ese Kiyoshiro trabaja con Katz Hoshi.',
    '싱글의 뒷면, 요스이가 정말 A면으로 삼고 싶었던 건 「帰れない二人」 쪽. 타가가 「心もよう」를 밀고 제목까지 붙여 A면을 차지했다. 밀려난 「帰れない二人」는 이마와노 기요시로와의 공작(Wikipedia — 心もよう). 그 기요시로가 4장 뒤에 호시 카츠와 손을 잡는다.')
put('h_q04b', 'ジャケットのあの白っぽい写真、狙いではなく、ネガを現像液に長く浸けすぎた結果だそうです（Wikipedia）。失敗が、日本でいちばん売れたLPの顔になった。僕の失敗は、だいたい失敗のまま棚に並んでいます。',
    'That washed-out white look on the cover wasn\'t intentional: the negative was left in the developer too long (Wikipedia). A mistake became the face of Japan\'s best-selling LP. My mistakes mostly stay mistakes, lined up on the shelf.',
    '封套上那张发白的照片不是故意的，是底片在显影液里泡太久的结果（Wikipedia）。一个失误，成了日本最畅销LP的脸。我的失误，大多还是以失误的样子摆在架子上。',
    'Ese aire blanquecino de la portada no fue buscado: el negativo se quedó demasiado tiempo en el revelador (Wikipedia). Un error se convirtió en la cara del LP más vendido de Japón. Mis errores, en general, siguen siendo errores en la estantería.',
    '재킷의 그 허옇게 뜬 사진, 의도가 아니라 네거티브를 현상액에 너무 오래 담근 결과라고 한다(Wikipedia). 실수가 일본에서 가장 많이 팔린 LP의 얼굴이 됐다. 내 실수는 대체로 실수인 채로 선반에 놓여 있다.')
put('k2009', '物価が1年で23パーセント上がった年に、当時いちばん高い買い物のひとつだったLPが、日本で初めて100万枚。僕はスーパーの卵が30円上がっただけで、棚の前で5分固まります。あの頃の若者、強い。',
    'In a year when prices rose 23 percent, an LP, one of the priciest things you could buy, sold a million for the first time in Japan. I freeze for five minutes in front of the shelf when eggs go up 30 yen. Young people back then were tough.',
    '物价一年涨23%的年份，当时最贵的消费品之一LP，在日本第一次卖到100万张。超市鸡蛋涨30日元，我就能在货架前僵五分钟。那个年代的年轻人，真强。',
    'En un año en que los precios subieron un 23 por ciento, un LP, de lo más caro que se podía comprar, vendió un millón por primera vez en Japón. Yo me quedo cinco minutos congelado frente al estante cuando los huevos suben 30 yenes. Qué fuertes eran los jóvenes de entonces.',
    '물가가 1년에 23퍼센트 오른 해에, 당시 가장 비싼 쇼핑 중 하나였던 LP가 일본 최초로 100만 장. 나는 마트 달걀이 30엔 오르면 선반 앞에서 5분 굳는다. 그 시절 젊은이들, 강하다.')
put('k2010', 'この録音、ギターにはレイ・パーカー・ジュニア（Wikipedia — 二色の独楽）。10年後に映画『ゴーストバスターズ』の主題歌で世界を踊らせる人です。1974年のロサンゼルスで彼を呼んでいたのは、日本から来た編曲家でした。',
    'On guitar for these sessions: Ray Parker Jr. (Wikipedia — Nishoku no Koma). Ten years later he\'d have the world dancing to the Ghostbusters theme. In 1974 Los Angeles, the one calling him in was an arranger from Japan.',
    '这次录音的吉他手是雷·帕克（Wikipedia — 二色の独楽）。十年后，他会用电影《捉鬼敢死队》的主题曲让全世界跳舞。而1974年在洛杉矶召唤他的，是一位来自日本的编曲家。',
    'A la guitarra en estas sesiones: Ray Parker Jr. (Wikipedia — Nishoku no Koma). Diez años después pondría al mundo a bailar con el tema de Cazafantasmas. En el Los Ángeles de 1974, quien lo llamaba era un arreglista llegado de Japón.',
    '이 녹음의 기타는 레이 파커 주니어(Wikipedia — 二色の独楽). 10년 뒤 영화 『고스트버스터즈』 주제가로 세계를 춤추게 할 사람이다. 1974년 로스앤젤레스에서 그를 부른 건, 일본에서 온 편곡가였다.')
put('k2011', '小椋佳さん、本人いわく「楽譜を書き起こせないし、楽器演奏も苦手」（Wikipedia — 小椋佳）。ギターのコードを鳴らしながら口ずさんでカセットに録り、誰かに譜面にしてもらい、編曲家に渡す。この「スタンド・スティル」では、その編曲家が隣で歌っています。現役の銀行員と元サイケ・ロッカーのデュエット。',
    'Kei Ogura, in his own words: "I can\'t write out a score, and I\'m bad at playing instruments" (Wikipedia — Kei Ogura). He\'d strum chords, hum into a cassette, have someone notate it, then hand it to an arranger. On "Stand Still," that arranger is singing next to him. A working banker and an ex-psychedelic rocker, in duet.',
    '小椋佳本人说：“我不会写谱，也不擅长演奏乐器”（Wikipedia — 小椋佳）。弹着吉他和弦哼唱录进卡带，请人记谱，再交给编曲家。这首《スタンド・スティル》里，那位编曲家就在旁边一起唱。在职银行员和前迷幻摇滚手的二重唱。',
    'Kei Ogura, en sus palabras: «no sé escribir partituras y se me da mal tocar instrumentos» (Wikipedia — Kei Ogura). Rasgueaba acordes, tarareaba en una casete, alguien lo pasaba a partitura y se lo daba a un arreglista. En «Stand Still», ese arreglista canta a su lado. Un banquero en activo y un exrockero psicodélico, a dúo.',
    '오구라 케이, 본인 말로는 “악보를 쓸 줄 모르고 악기 연주도 서툴다”(Wikipedia — 小椋佳). 기타 코드를 치며 흥얼거려 카세트에 담고, 누군가에게 악보로 옮기게 하고, 편곡가에게 넘긴다. 이 「スタンド・スティル」에선 그 편곡가가 옆에서 노래한다. 현직 은행원과 전직 사이키델릭 로커의 듀엣.')
put('h_q07', 'ピアノは深町純、と長く言われてきました。星勝さんはそれを否定しています（Wikipedia — スローバラード）。半世紀たっても「誰が弾いたか」で話が続く。それだけ、隅々まで聴き込まれてきた1曲です。',
    'For years people said the piano was Jun Fukamachi. Katz Hoshi denies it (Wikipedia — Slow Ballad). Half a century on, people still argue over who played. That\'s how closely this song has been listened to.',
    '长期以来都说钢琴是深町纯弹的。星胜否认了（Wikipedia — スローバラード）。过了半个世纪，“是谁弹的”还在被讨论。这首歌，就是被听得这么细。',
    'Durante años se dijo que el piano era de Jun Fukamachi. Katz Hoshi lo niega (Wikipedia — Slow Ballad). Medio siglo después, aún se discute quién lo tocó. Así de a fondo se ha escuchado esta canción.',
    '피아노는 후카마치 준이라고 오래 이야기돼 왔다. 호시 카츠는 그걸 부정한다(Wikipedia — スローバラード). 반세기가 지나도 ‘누가 쳤는가’로 이야기가 이어진다. 그만큼 구석구석 들려 온 한 곡이다.')
put('k2012', '来生さんの「夢の途中」が11月10日、薬師丸さんの「セーラー服と機関銃」が11月21日。来生さんは薬師丸さんの予約枚数を聞いて「大差をつけられたら」と不安になり、2曲ともベストテンに入って安心したそうです（Wikipedia）。自分の曲に、自分が負けるかもしれない恐怖。僕は自分で立てた月の目標に、毎月負けています。',
    'Kisugi\'s "Yume no Tochu" came out November 10; Yakushimaru\'s "Sailor-fuku to Kikanju" on the 21st. Hearing her pre-order numbers, Kisugi worried about being left far behind, then relaxed when both made the top ten (Wikipedia). The fear of losing to your own song. I lose to my own monthly goals every month.',
    '来生的《夢の途中》11月10日发行，药师丸的《セーラー服と機関銃》11月21日。来生听说药师丸的预订量后担心“会不会被甩开一大截”，两首都进了前十才放心（Wikipedia）。输给自己写的歌的恐惧。我每个月都输给自己定的目标。',
    '«Yume no Tochu» de Kisugi salió el 10 de noviembre; «Sailor-fuku to Kikanju» de Yakushimaru, el 21. Al oír las reservas de ella, Kisugi temió quedarse muy atrás, y respiró cuando las dos entraron en el top ten (Wikipedia). El miedo a perder contra tu propia canción. Yo pierdo cada mes contra las metas que me pongo.',
    '키스기의 「夢の途中」가 11월 10일, 야쿠시마루의 「セーラー服と機関銃」가 11월 21일. 키스기는 야쿠시마루의 예약 수량을 듣고 “크게 벌어지면” 하고 불안해하다, 두 곡 다 베스트 텐에 들어 안심했다고 한다(Wikipedia). 자기 노래에 자기가 질지도 모른다는 공포. 나는 내가 세운 이달 목표에 매달 진다.')
put('k2013', 'この曲、サントリー「赤玉パンチ」のCMソングでした。採用の条件が「作詞は井上陽水で」。だから詞は陽水さん、しかもCMに使われると知っていて書いた（Wikipedia — ワインレッドの心）。ワインの名前の入った歌が先か、赤い飲み物が先か。答えは、飲み物。',
    'This was the jingle for Suntory\'s "Akadama Punch." The condition for getting the ad: lyrics by Yosui Inoue. So Yosui wrote the words, knowing they\'d run in a commercial (Wikipedia — Wine Red no Kokoro). Which came first, the song with wine in its name or the red drink? The drink.',
    '这首歌是三得利“赤玉パンチ”的广告曲。被采用的条件是“作词要井上阳水”。所以词是阳水写的，而且写的时候就知道要用在广告里（Wikipedia — ワインレッドの心）。先有带酒名的歌，还是先有红色饮料？答案：饮料。',
    'Fue la canción del anuncio de «Akadama Punch» de Suntory. La condición para conseguirlo: letra de Yosui Inoue. Así que Yosui la escribió sabiendo que iría en un anuncio (Wikipedia — Wine Red no Kokoro). ¿Qué fue antes, la canción con vino en el título o la bebida roja? La bebida.',
    '이 곡은 산토리 ‘아카다마 펀치’의 CM송이었다. 채택 조건이 ‘작사는 이노우에 요스이로’. 그래서 가사는 요스이, 게다가 CM에 쓰일 걸 알고 썼다(Wikipedia — ワインレッドの心). 와인 이름이 든 노래가 먼저냐, 빨간 음료가 먼저냐. 답은, 음료.')
put('h_q10', '通算10週1位。ただし途中の1週だけ、とんねるずの「ガラガラヘビがやってくる」に首位を奪われています（Wikipedia）。雪の悲しみが、ヘビに1回だけ負けた。人生、そういう週もある。',
    'Ten weeks at No. 1 in total. But for one week in the middle, the top spot went to Tunnels\' "Garagara-hebi ga Yattekuru" (Wikipedia). Snow-like sorrow lost to a rattlesnake, once. Some weeks are like that.',
    '累计10周冠军。不过中间有一周，第一名被“とんねるず”的《ガラガラヘビがやってくる》抢走了（Wikipedia）。如雪的悲伤，只输给过蛇一次。人生，总有那么一周。',
    'Diez semanas en el número uno en total. Pero una semana, en medio, el primer puesto se lo llevó «Garagara-hebi ga Yattekuru» de Tunnels (Wikipedia). La tristeza como nieve perdió una vez contra una serpiente de cascabel. Hay semanas así.',
    '통산 10주 1위. 다만 중간 한 주만, 툰네루즈의 「ガラガラヘビがやってくる」에 1위를 빼앗겼다(Wikipedia). 눈 같은 슬픔이 뱀에게 딱 한 번 졌다. 인생, 그런 주도 있다.')

# ---- 本文の直し ----
put('k32', 'この「御意見無用」は、その年の勢いがそのまま入った曲だ。', 'This "Iijanaika" has that year\'s momentum poured straight into it.', '这首《御意見無用》，把那一年的势头原封不动地装了进去。', 'Este «Iijanaika» lleva dentro, tal cual, el impulso de aquel año.', '이 「御意見無用」는 그 해의 기세가 그대로 담긴 곡이다.')
put('k54', '星勝はこのアルバムの編曲を手がけた。当時、一緒に仕事をしていた人物は「このレコーディングでの星のアレンジに対して、スタジオ・ミュージシャンや他のアレンジャーからの評価は、一緒に仕事をしてきた僕が誇らしく思えるほど絶賛された」と書いている[[1]]。',
    'Katz Hoshi arranged this album. A colleague from those days wrote: "The studio musicians and the other arrangers praised Hoshi\'s arrangements so highly that I, who had worked alongside him, felt proud"[[1]].',
    '星胜为这张专辑编曲。当时与他共事的人写道：“录音棚乐手和其他编曲家对星的编曲赞不绝口，连一直和他共事的我都感到自豪”[[1]]。',
    'Katz Hoshi arregló este álbum. Alguien que trabajaba con él entonces escribió: «los músicos de estudio y los demás arreglistas elogiaron tanto los arreglos de Hoshi que yo, que llevaba tiempo trabajando con él, me sentí orgulloso»[[1]].',
    '호시 카츠는 이 앨범의 편곡을 맡았다. 당시 함께 일하던 사람은 “이 레코딩에서 호시의 편곡에 대한 스튜디오 뮤지션과 다른 편곡가들의 평가는, 함께 일해 온 내가 자랑스러울 만큼 절찬이었다”고 썼다[[1]].', [a(MCAL, 'music-calendar.jp')])
put('k86', '作詞は井上陽水、作曲は玉置浩二、編曲は安全地帯と星勝、プロデュースも星勝[[1]]。ヒット曲が出ない安全地帯に、スタッフは陽水への作曲依頼を考えたが、玉置が断った。玉置いわく「歌謡曲っぽくて売れそうな感じの曲」を狙って作った[[2]]。オリコン週間1位、1984年度の年間2位[[3]]。',
    'Lyrics by Yosui Inoue, music by Koji Tamaki, arranged by Anzen Chitai and Katz Hoshi, produced by Hoshi[[1]]. With no hit yet, the staff considered asking Yosui to write the music; Tamaki refused. In his words, they aimed for "a pop-ish song that feels like it would sell"[[2]]. No. 1 on the Oricon weekly chart, No. 2 for the year 1984[[3]].',
    '作词井上阳水，作曲玉置浩二，编曲安全地带与星胜，制作也是星胜[[1]]。安全地带迟迟没有热门曲，工作人员曾考虑请阳水作曲，被玉置拒绝。玉置说，他们瞄准的是“像歌谣曲、感觉好卖的歌”[[2]]。Oricon周榜第1，1984年度年榜第2[[3]]。',
    'Letra de Yosui Inoue, música de Koji Tamaki, arreglos de Anzen Chitai y Katz Hoshi, producción de Hoshi[[1]]. Sin un éxito a la vista, el equipo pensó en pedirle la música a Yosui; Tamaki se negó. Según él, fueron a por «una canción con aire de pop que parezca que se va a vender»[[2]]. Número uno semanal en Oricon y segundo del año 1984[[3]].',
    '작사 이노우에 요스이, 작곡 타마키 코지, 편곡 안전지대와 호시 카츠, 프로듀스도 호시[[1]]. 히트곡이 없던 안전지대에 스태프는 요스이에게 작곡을 부탁할 생각이었지만 타마키가 거절했다. 타마키 말로는 “가요곡 같고 팔릴 것 같은 노래”를 노려 만들었다[[2]]. 오리콘 주간 1위, 1984년도 연간 2위[[3]].', [a(WINE, 'Wikipedia — ワインレッドの心')] * 3)
put('k87', 'ここが、多賀英典のキティ・レコードが最大の果実を取った場所である。多賀がポリドールから独立したのは1972年[[1]]。そこから11年。',
    'This is where Hidenori Taga\'s Kitty Records reaped its biggest harvest. Taga had left Polydor to go independent in 1972[[1]]. Eleven years on.',
    '这里，是多贺英典的Kitty Records收获最大果实的地方。多贺1972年从宝丽多独立[[1]]。从那时起，11年。',
    'Aquí es donde Kitty Records, de Hidenori Taga, recogió su mayor cosecha. Taga había dejado Polydor para independizarse en 1972[[1]]. Once años después.',
    '여기가 타가 히데노리의 키티 레코드가 가장 큰 열매를 거둔 자리다. 타가가 폴리도르에서 독립한 건 1972년[[1]]. 그로부터 11년.', [a(TAGA, 'Wikipedia — 多賀英典')])
put('k88', 'この曲は海を渡った。香港の譚詠麟（アラン・タム）が「酒紅色的心」として広東語でカバーし、1984年のアルバム『愛的根源』に収めている[[1]][[2]]。',
    'The song crossed the sea. Hong Kong\'s Alan Tam covered it in Cantonese as "酒紅色的心," on his 1984 album 愛的根源[[1]][[2]].',
    '这首歌漂洋过海。香港的谭咏麟以粤语翻唱为《酒紅色的心》，收录在1984年的专辑《愛的根源》[[1]][[2]]。',
    'La canción cruzó el mar. Alan Tam, de Hong Kong, la versionó en cantonés como «酒紅色的心», en su álbum de 1984 愛的根源[[1]][[2]].',
    '이 곡은 바다를 건넜다. 홍콩의 탐영린(앨런 탐)이 「酒紅色的心」으로 광둥어 커버해 1984년 앨범 『愛的根源』에 실었다[[1]][[2]].', [a(LGY, 'Wikipedia（中文） — 愛的根源'), a(NOTE, '広東語カバーソング事典')])
put('k93', 'イントロはポリスの「見つめていたい」に似ていると言われる。でも浜田省吾の頭にあったのは、ジュード・コールというアーティストの曲だった。その曲を星勝に聴かせて「こういう感じにしたい」と頼んだ。結果は、累計170.3万枚、通算10週1位。浜田のシングルで過去最大のヒットになった[[1]]。',
    'The intro is often compared to The Police\'s "Every Breath You Take." But what Shogo Hamada had in mind was a song by an artist named Jude Cole. He played it for Katz Hoshi and said, "I want this kind of feel." The result: 1.703 million copies, ten weeks at No. 1, the biggest single of Hamada\'s career[[1]].',
    '前奏常被说像The Police的《Every Breath You Take》。但滨田省吾脑子里的是一位叫Jude Cole的歌手的曲子。他放给星胜听，说“想要这种感觉”。结果：累计170.3万张，累计10周冠军，成了滨田单曲史上最大的热门[[1]]。',
    'Dicen que la intro recuerda a «Every Breath You Take» de The Police. Pero lo que Shogo Hamada tenía en la cabeza era una canción de un artista llamado Jude Cole. Se la puso a Katz Hoshi y le dijo: «quiero algo así». El resultado: 1.703.000 copias, diez semanas en el número uno, el mayor éxito en sencillo de Hamada[[1]].',
    '인트로는 폴리스의 「Every Breath You Take」와 닮았다는 말을 듣는다. 하지만 하마다 쇼고의 머릿속에 있던 건 주드 콜이라는 아티스트의 곡이었다. 그 곡을 호시 카츠에게 들려주고 “이런 느낌으로”라고 부탁했다. 결과는 누계 170.3만 장, 통산 10주 1위. 하마다의 싱글 중 최대 히트가 됐다[[1]].', [a(KANA, 'Wikipedia — 悲しみは雪のように')])
put('k94', '星勝は1991年、スタジオジブリ『おもひでぽろぽろ』の音楽を担当している。2013年の映画『ペコロスの母に会いに行く』では音楽監督を務めた。1990年には尾崎豊のアルバム『誕生』全20曲を編曲した。浜田省吾とは1977年の「木枯しの季節」から。縁をつないだのは、モップスのドラマーだった鈴木幹治。浜田のプロデューサーになっていた彼が、星を呼んだ[[1]]。「悲しみは雪のように」の依頼も、いつもと変わらず「カッコ良いサウンドにして下さい」だったと本人が振り返っている[[2]]。',
    'In 1991 Katz Hoshi scored Studio Ghibli\'s Only Yesterday, and in 2013 he was music director on the film Pecoross\' Mother and Her Days. In 1990 he arranged all 20 tracks of Yutaka Ozaki\'s album Tanjo. His work with Shogo Hamada goes back to "Kogarashi no Kisetsu" in 1977. The link was Mikiharu Suzuki, once the drummer of The Mops, who had become Hamada\'s producer and called Hoshi in[[1]]. The brief for "Kanashimi wa Yuki no Yoni," Hoshi recalls, was the usual: "Make it sound cool"[[2]].',
    '1991年，星胜负责了吉卜力《岁月的童话》的音乐；2013年的电影《去见佩克罗斯的母亲》担任音乐监督。1990年为尾崎丰专辑《誕生》全20曲编曲。与滨田省吾的合作始于1977年的《木枯しの季節》。牵线的是曾任The Mops鼓手的铃木干治——他成了滨田的制作人，把星叫了来[[1]]。《悲しみは雪のように》的委托，据本人回忆，也一如既往：“请做成帅气的声音”[[2]]。',
    'En 1991 Katz Hoshi compuso la música de Recuerdos del ayer, de Studio Ghibli, y en 2013 fue director musical de la película Pecoross\' Mother and Her Days. En 1990 arregló las 20 canciones del álbum Tanjo de Yutaka Ozaki. Con Shogo Hamada trabaja desde «Kogarashi no Kisetsu», de 1977. El enlace fue Mikiharu Suzuki, antiguo batería de The Mops, convertido en productor de Hamada, que llamó a Hoshi[[1]]. El encargo para «Kanashimi wa Yuki no Yoni», recuerda Hoshi, fue el de siempre: «que suene con estilo»[[2]].',
    '호시 카츠는 1991년 스튜디오 지브리 『추억은 방울방울』의 음악을 맡았다. 2013년 영화 『페코로스, 어머니 만나러 갑니다』에선 음악감독. 1990년엔 오자키 유타카의 앨범 『誕生』 전 20곡을 편곡했다. 하마다 쇼고와는 1977년 「木枯しの季節」부터. 인연을 이어 준 건 몹스의 드러머였던 스즈키 미키하루. 하마다의 프로듀서가 돼 있던 그가 호시를 불렀다[[1]]. 「悲しみは雪のように」의 의뢰도 여느 때처럼 “멋진 사운드로 해 주세요”였다고 본인은 돌아본다[[2]].', [a(HOSHI, 'Wikipedia — 星勝'), a(GEND, '週刊現代')])
put('k123', '編曲：安全地帯、星勝／プロデュース：星勝', 'Arranged by Anzen Chitai and Katz Hoshi / Produced by Katz Hoshi', '编曲：安全地带、星胜／制作：星胜', 'Arreglos: Anzen Chitai y Katz Hoshi / Producción: Katz Hoshi', '편곡: 안전지대, 호시 카츠／프로듀스: 호시 카츠')
put('h_sb_end', '清志郎が「思っていた音と違う」と感じた録音が、半世紀たったいま、2本の映画の主題歌になり、歌い継がれている。編曲という仕事の不思議が、この1曲に詰まっている。',
    'A recording Kiyoshiro felt "didn\'t sound the way I imagined" has, half a century on, become the theme of two films and is still being sung. The strangeness of the arranger\'s job is packed into this one song.',
    '清志郎觉得“和想象中的声音不一样”的录音，半个世纪后成了两部电影的主题曲，被人传唱。编曲这份工作的不可思议，都装在这一首里。',
    'Una grabación que a Kiyoshiro le pareció «distinta de lo que imaginaba» es, medio siglo después, tema de dos películas y se sigue cantando. Lo extraño del oficio de arreglista cabe en esta sola canción.',
    '기요시로가 “생각했던 소리와 다르다”고 느낀 녹음이, 반세기가 지난 지금 영화 두 편의 주제가가 되어 계속 불리고 있다. 편곡이라는 일의 불가사의가 이 한 곡에 담겨 있다.')
put('k104', '思いどおりにならなかった録音が、半世紀残った。', 'The recording that didn\'t go his way lasted half a century.', '不如意的录音，留了半个世纪。', 'La grabación que no salió como quería duró medio siglo.', '뜻대로 되지 않은 녹음이 반세기를 남았다.')

# ---- 出典一覧（訳が抜けていた8件＋新規3件）----
SRCS = {
 'k279': ('music-calendar.jp — 星勝がアレンジャーとして行ったモップス以外の初仕事は井上陽水（2015）', 'music-calendar.jp — Hoshi\'s first arranging job outside The Mops was Yosui Inoue (2015)', 'music-calendar.jp — 星胜在The Mops之外的首个编曲工作是井上阳水（2015）', 'music-calendar.jp — El primer arreglo de Hoshi fuera de The Mops fue para Yosui Inoue (2015)', 'music-calendar.jp — 호시가 몹스 밖에서 처음 맡은 편곡은 이노우에 요스이 (2015)'),
 'k280': ('昭和歌謡の編曲家 代表作一覧 — 星勝', 'Arrangers of Showa kayokyoku, list of works — Katz Hoshi', '昭和歌谣编曲家 代表作一览 — 星胜', 'Arreglistas del kayokyoku Showa, lista de obras — Katz Hoshi', '쇼와 가요 편곡가 대표작 일람 — 호시 카츠'),
 'k281': ('ShimaQ の 今日この頃 — 星勝さん（2020）', 'ShimaQ blog — On Katz Hoshi (2020)', 'ShimaQ博客 — 星胜（2020）', 'Blog ShimaQ — Sobre Katz Hoshi (2020)', 'ShimaQ 블로그 — 호시 카츠 (2020)'),
 'k282': ('zakzak — 昭和歌謡の職人たち 編曲家・星勝（2019）', 'zakzak — Craftsmen of Showa kayokyoku: arranger Katz Hoshi (2019)', 'zakzak — 昭和歌谣的匠人们 编曲家·星胜（2019）', 'zakzak — Artesanos del kayokyoku Showa: el arreglista Katz Hoshi (2019)', 'zakzak — 쇼와 가요의 장인들 편곡가 호시 카츠 (2019)'),
 'k283': ('マイナビウーマン — 70年代ファッションの特徴（2019）', 'Mynavi Woman — Features of 1970s fashion (2019)', 'Mynavi Woman — 70年代时尚的特征（2019）', 'Mynavi Woman — Rasgos de la moda de los 70 (2019)', '마이나비 우먼 — 70년대 패션의 특징 (2019)'),
 'k286': ('note — 広東語カバーソング事典 譚詠麟編', 'note — Encyclopedia of Cantonese cover songs: Alan Tam', 'note — 粤语翻唱歌曲事典 谭咏麟篇', 'note — Enciclopedia de versiones en cantonés: Alan Tam', 'note — 광둥어 커버송 사전 탐영린 편'),
 'k287': ('YouTube — 星勝さん 宮城・村田町の親善アンバサダーに就任', 'YouTube (khb) — Katz Hoshi named goodwill ambassador of Murata, Miyagi', 'YouTube（khb） — 星胜就任宫城县村田町亲善大使', 'YouTube (khb) — Katz Hoshi, embajador de buena voluntad de Murata, Miyagi', 'YouTube (khb) — 호시 카츠, 미야기현 무라타마치 친선 앰배서더 취임'),
 'k288': ('週刊現代（現代ビジネス） — 浜田省吾『悲しみは雪のように』を星勝さんらが語る（2023）', 'Shukan Gendai — Katz Hoshi and others on Shogo Hamada\'s "Kanashimi wa Yuki no Yoni" (2023)', '周刊现代 — 星胜等谈滨田省吾《悲しみは雪のように》（2023）', 'Shukan Gendai — Katz Hoshi y otros sobre «Kanashimi wa Yuki no Yoni» de Shogo Hamada (2023)', '슈칸겐다이 — 호시 카츠 등이 말하는 하마다 쇼고 「悲しみは雪のように」 (2023)'),
 'h_src_lgy': ('Wikipedia（中文） — 愛的根源（譚詠麟・1984）', 'Wikipedia (zh) — 愛的根源 (Alan Tam, 1984)', '维基百科（中文） — 愛的根源（谭咏麟·1984）', 'Wikipedia (zh) — 愛的根源 (Alan Tam, 1984)', 'Wikipedia(중문) — 愛的根源 (탐영린·1984)'),
 'h_src_ogura': ('Wikipedia — 小椋佳', 'Wikipedia — Kei Ogura', '维基百科 — 小椋佳', 'Wikipedia — Kei Ogura', 'Wikipedia — 오구라 케이'),
 'h_src_koko': ('Wikipedia — 心もよう', 'Wikipedia — Kokoro Moyo', '维基百科 — 心もよう', 'Wikipedia — Kokoro Moyo', 'Wikipedia — 心もよう'),
}

def settr(k, d):
    for l in L4: tr[l][k] = d[l]

def render(ja, anchors):
    return re.sub(r'\[\[(\d+)\]\]', lambda m: anchors[int(m.group(1)) - 1], ja)

def set_el(el, k):
    ja, d, anchors = T[k]
    assert ja.count('[[') == len(anchors), k
    for l in L4: assert d[l].count('[[') == len(anchors), (k, l)
    el.clear(); el.append(BeautifulSoup(render(ja, anchors), 'html.parser'))
    settr(k, d)

main = s.find('main')
def byk(k):
    el = main.select_one(f'[data-i18n="{k}"]'); assert el is not None, k; return el

for k in T:
    if main.select_one(f'[data-i18n="{k}"]') is not None:
        set_el(byk(k), k)

def say_div(k):
    ja, d, anchors = T[k]
    settr(k, d)
    return BeautifulSoup(f'<div class="say"><div class="say__ic"><img alt="" src="assets/owner/x-avatar.jpg"/></div><div class="say__bub" data-i18n="{k}">{render(ja, anchors)}</div></div>', 'html.parser').div

# 新しい吹き出し：03章（出典つき裏ネタ）→ つなぎの前／04章の本文の中（箸休め）／07章（裏ネタ）→ つなぎの前／10章（箸休め）→ 引用句の前
main.select_one('#ch03 p.bridge').insert_before(say_div('h_q03'))
byk('k47').insert_after(say_div('h_q04b'))
main.select_one('#ch07 p.bridge').insert_before(say_div('h_q07'))
byk('k106').insert_before(say_div('h_q10'))

# 消す：TOWERの「名曲」の段落／04章の重複した引用句（本文と同じ一文）
for k in ('h_sb_tower', 'k103'):
    el = main.select_one(f'[data-i18n="{k}"]')
    if el is not None: el.decompose()
    for l in L4: tr[l].pop(k, None)

# 出典一覧：TOWER・道草を外し、愛的根源・小椋佳・心もようを足す。訳の抜け8件を埋める
srcul = main.select_one('section.cw-sources ul')
for k in ('h_src9_0', 'k276'):
    el = main.select_one(f'[data-i18n="{k}"]')
    if el is not None: el.find_parent('li').decompose()
    for l in L4: tr[l].pop(k, None)
for k, u in (('h_src_lgy', LGY), ('h_src_ogura', OGURA), ('h_src_koko', KOKO)):
    srcul.append(BeautifulSoup(f'<li><a data-i18n="{k}" href="{u}" rel="noopener" target="_blank">{SRCS[k][0]}</a></li>', 'html.parser').li)
for k, v in SRCS.items():
    settr(k, dict(zip(L4, v[1:])))

main['data-hk15'] = '1'
out = str(s)
out = re.sub(r'<meta content="story" name="tamago-magazine"\s*/?>', '<meta name="tamago-magazine" content="story"/>', out)
out = MB.unify_look(out)
for q in (SRC, os.path.join(R, 'status/magazine_prod/kimi-wa-hoshi-katsu.html')):
    os.makedirs(os.path.dirname(q), exist_ok=True)
    open(q, 'w', encoding='utf-8').write(out)
json.dump(tr, open(TRP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
t = json.dumps(dict(tr, **{l: dict(tr[l], **MB.common_i18n()[l]) for l in L4}), ensure_ascii=False, separators=(',', ':'))
for d in ('share/check', 'status/magazine_prod'):
    open(os.path.join(R, d, 'kimi-wa-hoshi-katsu.i18n.json'), 'w', encoding='utf-8').write(t)
print('ok bytes=%d look=%s' % (len(out.encode('utf-8')), MB.look_check(out)))
