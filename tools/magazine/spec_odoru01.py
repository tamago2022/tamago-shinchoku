# -*- coding: utf-8 -*-
"""踊るの特集 vol.1「人が踊るとき 〜人はなぜ踊るのか〜」（2026-10-18・122704番）
Genspark の叩き（#1018）の章立て・動画を踏襲し、本文を燃え殻風の語りで全面的に書き直した確定型（怒れる人々 vol.1 の型）。
事実は下の出典（Wikipedia 本文・HISTORY・徳島県・THE AWAODORI）で確かめたものだけ。確かめられなかった数字（第30回・3,000人・3メートル等）は落とした。
容量：後退の関所（koutai_kanmon --check-files・基準 86,427 バイト +5%）に収めるため、写真7枚・聴きくらべ3本・出典リンクは段落に1つ。
本番：https://joy-relief-station.lovable.app/magazine/hito-ga-odoru-01.html
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mag_build as MB
from mag_build import write, src
MB.PROD.setdefault('odoru01', 'hito-ga-odoru-01.html')  # 本番名（部品側の表に無ければここで足す）

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTOS = json.load(open(os.path.join(HERE, 'photos_odoru01.json'), encoding='utf-8'))  # 章の合間の写真（Wikimedia Commons・自由ライセンスだけ・クレジット付き）
_i18n_path = os.path.join(HERE, 'i18n_odoru01.json')
I18N = json.load(open(_i18n_path, encoding='utf-8')) if os.path.exists(_i18n_path) else None  # 5言語（訳だけ直すときはこのファイル）

# 出典
WBH = 'https://en.wikipedia.org/wiki/Bhimbetka_rock_shelters'
WHU = 'https://en.wikipedia.org/wiki/Hurrian_songs'
WAWA = 'https://ja.wikipedia.org/wiki/%E9%98%BF%E6%B3%A2%E8%B8%8A%E3%82%8A'
WBON = 'https://ja.wikipedia.org/wiki/%E7%9B%86%E8%B8%8A%E3%82%8A'
TOKU = 'https://www.pref.tokushima.lg.jp/japanese/natural_culture/traditional_culture/awa-odori'
AWAM = 'https://www.awaodorimirai.com/'
WHULA = 'https://en.wikipedia.org/wiki/Hula'
WKAL = 'https://en.wikipedia.org/wiki/Kal%C4%81kaua'
WMM = 'https://en.wikipedia.org/wiki/Merrie_Monarch_Festival'
WWAL = 'https://en.wikipedia.org/wiki/Waltz'
WDAN = 'https://en.wikipedia.org/wiki/The_Blue_Danube'
WTW = 'https://en.wikipedia.org/wiki/The_Twist_(song)'
WCC = 'https://en.wikipedia.org/wiki/Chubby_Checker'
WPEP = 'https://en.wikipedia.org/wiki/Peppermint_Lounge'
HIS = 'https://www.history.com/this-day-in-history/september-19/the-twist-dance-craze-begins'
WCS = 'https://en.wikipedia.org/wiki/Cold_Sweat'
WSM = 'https://en.wikipedia.org/wiki/Get_Up_(I_Feel_Like_Being_a)_Sex_Machine'
WIFL = 'https://en.wikipedia.org/wiki/I_Feel_Love'
WDD = 'https://en.wikipedia.org/wiki/Disco_Demolition_Night'
WHOUSE = 'https://en.wikipedia.org/wiki/House_music'
WROT = 'https://en.wikipedia.org/wiki/Ride_on_Time'
WTT = 'https://en.wikipedia.org/wiki/Technotronic'
WPUJ = 'https://en.wikipedia.org/wiki/Pump_Up_the_Jam'
WMTB = 'https://en.wikipedia.org/wiki/Move_That_Body_(Technotronic_song)'
WJUL = 'https://ja.wikipedia.org/wiki/%E3%82%B8%E3%83%A5%E3%83%AA%E3%82%A2%E3%83%8A%E6%9D%B1%E4%BA%AC'
WCD = 'https://en.wikipedia.org/wiki/Candy_Dulfer'
WPUP = 'https://en.wikipedia.org/wiki/Pick_Up_the_Pieces_(Average_White_Band_song)'
WAWB = 'https://en.wikipedia.org/wiki/Average_White_Band'
WMN = 'https://en.wikipedia.org/wiki/Meshell_Ndegeocello'
WMJF = 'https://en.wikipedia.org/wiki/Montreux_Jazz_Festival'

M = dict(
    key='odoru01', file='hito-ga-odoru-01.html', title='人が踊るとき 〜人はなぜ踊るのか〜 vol.1',
    desc='腰が勝手に動いてしまう音の正体を、1万年前の壁から1995年のモントルーまで追いかける11曲。ぜんぶこのページの中で聴ける。',
    hero='WZdbMlDsZz8', eyebrow='Series — Why Do People Dance? · vol.1',
    h1='人が踊るとき<br/><span class="cw-hero__sub">〜人はなぜ踊るのか〜</span>',
    lead='シリーズ「人はなぜ踊るのか」vol.1。<br/>腰が勝手に動いてしまう音の正体を、1万年前の壁から1995年のモントルーまで追いかける11曲。ぜんぶ、このページの中で聴ける。',
    big='人は、なぜ踊るのか。',
    open=['金曜の夜、コンビニの袋を提げて歩いていたら、どこかの店から漏れてきた低音に、右足だけが先に返事をした。頭は「早く帰って風呂に入りたい」と言っている。でも足は、もう1拍目を踏んでいる。あれは何なのか。確かめに行こう。',
          '踊りは、ずっと「あぶないもの」扱いを受けてきた。宣教師に禁じられ、批評家に「はしたない」と書かれ、野球場でレコードごと爆破された。それでも人は踊った。死者を迎えるため、記憶を運ぶため、恥を捨てるため、ただ命令されたから。1万年前の壁から1995年のモントルーまで、腰が勝手に動く理由を、順番に追いかけてみる。'],
    door='先に白状すると、僕は踊れない。踊れない人間が、踊る人の話を書く。だから本気で調べた。',
    paper=[],
    map=False,
    songs_n=11,
    chapters=[
        dict(no='01', artist='Hurrian Hymn no.6', song='ニッカルへの讃歌（復元演奏）', album='ウガリトの粘土板', year='紀元前1400年ごろ',
             catch='いちばん古い記録に、もう踊る人がいた',
             main=dict(id='QpxN2VXPMLc', role='c.1400 B.C.', artist='Hurrian Hymn no.6', song='The Oldest Known Melody（復元演奏）', cap=''),
             body=[f'インド中央部、ボパールの南東45キロにあるビンバイトカの岩陰遺跡。750を超える岩陰のうち、およそ400に先史時代の絵が残っている。いちばん古い絵は紀元前1万年ごろ。描かれているのは動物、狩り、そして集団で踊る人たちだ{src("Wikipedia", WBH)}。',
                   f'では、壁の前で何が鳴っていたのか。音は残らない。残っているいちばん古い「楽譜」は、今のシリア、ウガリトの王宮から出た紀元前1400年ごろの粘土板だ。約36曲ぶんの断片のうち、ほぼ完全な形で残ったのは1曲だけ。果樹園の女神ニッカルに捧げる讃歌で、9本の弦をもつ竪琴の類で伴奏する指示まで書いてある。ただし読み方は研究者の間で少なくとも5通りあって、どれを選ぶかで全く別の曲になる{src("Wikipedia", WHU)}。',
                   '今鳴っているのは、そのうちのひとつ。壁の絵より8,000年以上あと。あの夜の音とは違うはずだけど、拍はある。拍があるということは、たぶん踊れる。'],
             note='読み方が5通り以上ある＝同じ粘土板から5曲できる（Wikipedia）。3,400年前の作者、今ごろ天国で「どれも違う」と腕組みしているかもしれない。',
             bridge='踊りはいつも「あぶないもの」扱いを受ける。日本でも、ハワイでも、ウィーンでも。まずは、あの夏の徳島から。'),
        dict(no='02', artist='阿波おどり', song='ぞめき囃子と掛け声', album='徳島市・月遅れの8月12日〜15日', year='1586年ごろ〜',
             catch='踊る阿呆に見る阿呆。客席と舞台の壁を、400年前に取っ払っていた',
             main=dict(id='0iGEZkBqRJY', role='Awaodori', artist='阿波おどり', song='「連」ってなに？', cap='踊り手の集団「連」のことを、徳島の人が解説してくれる'),
             body=[f'平安時代の空也上人の踊念仏が民間の習俗と混ざり、お盆の行事と結びついて、死者を迎え、供養する踊りとして定着した{src("Wikipedia", WBON)}。死者のための踊りのはずなのに、現場はいちばん生きている場所になる。',
                   f'その系統でいちばんデカいのが、徳島の阿波おどり。約400年の歴史があり、徳島市のものは踊り手も観客も国内最大級。起源には三つの説があって、天正14年（1586年）に徳島藩祖の蜂須賀家政が無礼講として踊りを許した、という説がそのひとつ{src("Wikipedia", WAWA)}{src("徳島県", TOKU)}。毎年8月、徳島市には国内外から100万人を超える人が来る{src("THE AWAODORI", AWAM)}。',
                   f'「踊る阿呆に見る阿呆、同じ阿呆なら踊らな損々」。有名なこの文句、実は大手の有名連以外ではあまり歌われず、現場で多いのは「ヤットサー、ヤットサー」の掛け声だという{src("Wikipedia", WAWA)}。それでも僕はこの一節が好きだ。踊る側と見る側を、同じ「阿呆」に下ろしてしまう。見ていた人が、いつの間にか列にいる。',
                   dict(note='「同じ阿呆なら踊らな損々」。社会人になってから一番刺さった人生訓かもしれない。飲み会で踊らず、カラオケで歌わず、腕を組んで「いいね」と言うだけの僕。徳島の基準では、損々。損の二乗。'),
                   f'戦争で中断されたこともある。復活したのは1946年。GHQと徳島県警の折衝を経て、だった{src("Wikipedia", WAWA)}。占領軍と交渉してまで、踊りたかった。'],
             bridge='海を越えると、踊りは「禁じられたもの」になる。消された踊りを、王様が連れ戻した話。'),
        dict(no='03', artist='Hula Kahiko', song='Merrie Monarch Festival 2015・ワヒネ部門優勝', album='ハワイ島ヒロ', year='2015',
             catch='禁じられた踊りを、王様が連れ戻した',
             main=dict(id='mPW5LA3zy2Y', role='Official 2015', artist='Merrie Monarch Festival', song='Hula Kahiko (Wahine Division) 2015', cap=''),
             body=[f'1820年にハワイに来たアメリカのプロテスタント宣教師たちは、フラを「異教の踊り」と非難した。改宗した王族は禁止を迫られ、1830年、カアフマヌ女王が公の場でのフラを禁じる。1850年代には、公の場で踊るのに免許が要る制度になっていた{src("Wikipedia", WHULA)}。',
                   f'それでもフラは消えなかった。連れ戻したのはカラーカウア王だ。在位は1874年から1891年。1883年の戴冠式と、1886年の50歳の祝いで、それまで公の場で禁じられていたフラが、宮殿の庭で毎晩踊られた。歌とウクレレで客をもてなすのが好きな王で、あだ名は「メリー・モナーク（陽気な君主）」{src("Wikipedia", WKAL)}。',
                   f'その名前を冠したフラの祭典が、今もハワイ島ヒロで毎年、イースターの翌週に開かれている。1963年に始まり、1971年に競技会が加わり、今では各ハラウ（フラの流派）が、古典のカヒコと現代のアウアナの両方で競う{src("Wikipedia", WMM)}。カヒコは太鼓と詠唱だけ。詩と手の動きがセットで、歴史と系譜を体で運ぶ。',
                   'だからこそ、禁止されても消えなかった。踊りは、その人の来た道を覚えている。「踊りは消されることがある。そして戻ってくる」。この一点が、この旅ぜんぶの伏線だ。あとで野球場で、同じことが起きる。'],
             bridge='では、ヨーロッパでは何が問題だったのか。答えは「抱くこと」だった。'),
        dict(no='04', artist='Johann Strauss II', song='An der schönen blauen Donau（美しき青きドナウ）', album='ウィーン', year='1867.2.15',
             catch='抱いたまま、回る。それだけで、昔は醜聞だった',
             main=dict(id='sgfs5xajw9A', role='Vienna', artist='Johann Strauss II', song='Blue Danube', cap=''),
             body=[f'今では格式の代名詞のワルツも、出てきたころは踊りという名の醜聞だった。男女が組んで、抱き合うほど近くで、回る。1771年のドイツの小説には、高潔な登場人物がこう嘆く場面がある。「彼が彼女の腰に腕を回し、胸に引き寄せ、恥知らずで、はしたない、ドイツ人のあの回転ダンスで跳ね回ったとき、私の静かな惨めさは、燃える怒りに変わった」{src("Wikipedia", WWAL)}。',
                   f'それでも、みんな回った。1867年2月15日、ヨハン・シュトラウス2世の「美しき青きドナウ」がウィーン男声合唱協会の演奏会で初演される。最初は合唱つきで、反応はまあまあ。本人は「ワルツなんか悪魔にくれてやる。惜しいのはコーダだけだ」とこぼしたと伝わる。ところが同じ年、パリ万博のためにオーケストラだけの版に直したら、大当たりした{src("Wikipedia", WDAN)}。',
                   '批判は負けて、曲は勝った。以後の踊りの歴史は、ずっとこの構図のくり返しだ。「その踊りは危ない」、みんな踊る、数十年後に「文化」。'],
             note='「惜しいのはコーダだけ」。企画書が通らなかった夜の僕と同じことを、シュトラウスも言っていた（Wikipedia）。ただし彼のその企画は、今も世界中の元日に流れている。僕の企画書は、翌週に忘れられた。',
             bridge='腰を揺らすことが「はしたない」だった時代を通って、次の世紀の若者は、もっと根本的な自由を手に入れる。誰かを抱かない、という自由だ。'),
        dict(no='05', artist='Chubby Checker', song='The Twist', album='シングル', year='1960.9.19 ／ 1962.1.13',
             catch='二度も1位になった踊り。革命は「抱かないこと」だった',
             main=dict(id='0f-elp3NkbY', role='Dance 1961', artist='Chubby Checker', song='The Twist', cap=''),
             body=[f'1960年9月19日、18歳のチャビー・チェッカーの「The Twist」が全米1位になる。1週で落ちた。ところが1962年1月13日、同じレコードがもう一度1位に戻り、2週間居座った。別々の時期に二度1位になったのは、史上初めてだった{src("Wikipedia", WTW)}{src("HISTORY", HIS)}。',
                   f'もともとはハンク・バラードが書いて、1959年のシングルのB面に入っていた曲。バラードはフロリダのタンパで、十代の子たちがこの踊りをしているのを見て書いた。1960年8月6日、全国放送の「アメリカン・バンドスタンド」でチェッカーが踊って、火がついた{src("Wikipedia", WTW)}。',
                   f'革命は「抱かないこと」だった。相手に触れず、各自が腰を回す。踊りを「ひとりでもできること」にした。そして二度目の1位の理由がおかしい。1961年の終わり、ニューヨークのナイトクラブ、ペパーミント・ラウンジに大人の名士がツイストをしに通い始めたのだ。オードリー・ヘプバーン、マリリン・モンロー、フランク・シナトラ、果てはグレタ・ガルボまで{src("Wikipedia", WPEP)}。ゴシップ欄に載って、大人がはまって、十代の流行が「大人も認めるロックンロール」になった。',
                   f'2008年、ビルボードはチャート開始以来の全シングルの集計で、この曲を1位に置いた{src("Wikipedia", WCC)}。'],
             note='ハーレムの「スモールズ・パラダイス」も名士のツイストの名所で、持ち主はNBAの伝説、ウィルト・チェンバレン。「街でいちばんのツイストの店」と宣伝していた（HISTORY）。',
             bridge='ひとりで腰を回せるようになった7年後、今度は音楽の中心に「1拍目」がやってくる。'),
        dict(no='06', artist='James Brown', song='Get Up (I Feel Like Being a) Sex Machine', album='シングル（2部構成）', year='1970 ／ ライブは1971年パリ',
             catch='1拍目に、すべてを叩け',
             main=dict(id='WZdbMlDsZz8', role='Live 1971 Paris', artist='James Brown', song='Sex Machine (Live, Paris 1971)', cap=''),
             body=[f'ファンクの発明は、理屈としては素朴で、結果としては革命だった。1967年5月、ジェームス・ブラウンは「Cold Sweat」を録音する。バンドリーダーのピー・ウィー・エリスとの共作。R&Bチャート1位、ポップ7位。「最初の本物のファンク」と呼ばれることもある曲だ{src("Wikipedia", WCS)}。',
                   f'ある夜、ショーのあとにブラウンが楽屋にエリスを呼び、ベースラインを口で唸って聞かせた。エリスはそれを、ニューヨークからシンシナティへ向かうバスの中で曲にした。ホーンのフレーズの元は、マイルス・デイヴィスの「So What」。そしてこの録音で初めて、ブラウンがあの一言を叫ぶ。「ギヴ・ザ・ドラマー・サム（ドラマーに少しやらせろ）」。ドラムだけの「ブレイク」が生まれ、のちのダンスミュージックとサンプリングの土台になった{src("Wikipedia", WCS)}。',
                   f'3年後の1970年、新しいバンド「The J.B.’s」との最初の録音のひとつが「Sex Machine」。ベースはブーツィー・コリンズ、ギターは兄弟のキャットフィッシュ。ほぼ2テイクで録った。この映像は1971年のパリ、オランピア劇場。1970年のオリジナル録音は、2014年にグラミーの殿堂入り{src("Wikipedia", WSM)}。',
                   '歌詞のほとんどは「立て、場に残れ、セックス・マシーンみたいに」のかけ合いで、つまりこの曲は、踊り方の指導書を兼ねている。音が鳴れば体が勝手に返事をする。それを曲として設計した最初のひとりだ。'],
             more_label='聴きくらべ — その始まりの音',
             more=[dict(id='zx_oxYdzQNA', role='1967', artist='James Brown', song='Cold Sweat', cap='')],
             bridge='バンド全員が「1」を叩いた7年後、今度は人間が叩くのをやめる。機械が、夜を回しはじめる。'),
        dict(no='07', artist='Donna Summer', song='I Feel Love', album='アルバム『I Remember Yesterday』', year='1977',
             catch='機械が、夜を回しはじめた。そして、その夜は爆破された',
             main=dict(id='gHF-w8yGrHI', role='1977', artist='Donna Summer', song='I Feel Love', cap=''),
             body=[f'1977年、ミュンヘン。ドナ・サマーの5枚目のアルバム『I Remember Yesterday』は、1曲ごとに別の時代の音を鳴らすという企画だった。40年代のスウィング、60年代のガールグループ、70年代のファンク。そして最後の1曲に割り当てられたのは、「未来」{src("Wikipedia", WIFL)}。',
                   f'プロデューサーのジョルジオ・モロダーとピート・ベロッテは、ディスコの定番だったオーケストラの代わりに、借り物のモーグ・シンセサイザーを置いた。ただしこのモーグ、すぐに音程が狂う。だから20〜30秒ずつ録って、調律し直して、また録った。未来の音は、継ぎはぎで作られた。ベルリンにいたデヴィッド・ボウイのところへ、ブライアン・イーノが駆け込んできた。「未来の音を聴いた」。これから15年のクラブ音楽を変える、と。イギリスで4週1位{src("Wikipedia", WIFL)}。',
                   f'その2年後、1979年7月12日。シカゴのコミスキー・パーク。成績の振るわないホワイトソックスの客席を埋めるため、球団は反ディスコで知られるラジオDJのスティーヴ・ダールを呼んだ。ディスコのレコードを持ってくれば入場98セント。試合の合間に、集めた盤を箱ごと爆破する。球団の想定は2万人。来たのは少なくとも5万人。爆破のあと、数千人がグラウンドに乱入し、機動隊が出た。第2試合は没収試合{src("Wikipedia", WDD)}。',
                   f'「ディスコは死んだ」と彼らは言った。でも同じシカゴには、1977年から「ウェアハウス」というクラブがあって、フランキー・ナックルズというDJが回していた。のちに「ハウス・ミュージック」と呼ばれる音の、名前の由来になった場所だ{src("Wikipedia", WHOUSE)}。レコードを爆破した街で、次の夜が設計されていた。'],
             note='入場料98セントの根拠は、ラジオ局の周波数97.9（Wikipedia）。語呂で決めた入場料に5万人が来て、球場が壊れた。語呂、こわい。',
             bridge='レコードを燃やしても、声は燃えなかった。10年後、ディスコの歌い手の声が、イタリアのピアノ・リフに乗って戻ってくる。'),
        dict(no='08', artist='Black Box', song='Ride on Time', album='シングル', year='1989',
             catch='6週間1位。声の主は「死んだ」と思われていた',
             main=dict(id='M0quXl_od3g', role='Official 1989', artist='Black Box', song='Ride on Time', cap=''),
             body=[f'1989年、イタリア。DJのダニエレ・ダヴォリと仲間ふたりは、「レッド・ツェッペリンやディープ・パープルの力を持ったダンス曲」を作ろうとしていた。イタリアのロックは誰にも相手にされないから、だ。材料はニューヨークで買った12インチ。ロレッタ・ホロウェイの1980年の「Love Sensation」のアカペラ盤。働いていたクラブに買わせたサンプラー、アカイS900に刻んで、ピアノの和音を重ねた{src("Wikipedia", WROT)}。',
                   f'ダヴォリはホロウェイがもう亡くなっていると思い込み、2秒未満のサンプリングなら許可なしで合法だとも思っていた。どちらも間違いだった。クラブでかけたら、1,000人いたフロアが空いた。「心が折れた」。仲間は言った、「店が違ったんだ」{src("Wikipedia", WROT)}。',
                   f'イギリスのDJ、ポール・オーケンフォールドとダニー・ランプリングがイタリアに来て見つけ、持ち帰る。結果、全英6週間1位。1989年にイギリスでいちばん売れたシングルになった。3人が見込んでいた売り上げは、クラブ用に1,000枚{src("Wikipedia", WROT)}。',
                   f'題名は、サンプルした歌詞の「right on time（ぴったりの時間に）」を「ride on time」と聞き間違えたもの。テレビには「イタリアの男3人じゃホロウェイの代わりに見えない」からモデルのカトリン・キノルを立てて口パク。権利者が動いて、声はヘザー・スモール（のちのM People）が吹き直した{src("Wikipedia", WROT)}。'],
             note='「2秒未満なら合法だと思っていた」。会社で言うと「口約束だから契約じゃないと思っていた」です（Wikipedia）。その結果が、年間1位。間違いの規模が、僕とは違う。',
             bridge='ブームは国境を越えて、ベルギーのスタジオと、東京の倉庫街へ。'),
        dict(no='09', artist='Technotronic', song='Move That Body', album='アルバム『Body to Body』', year='1991',
             catch='声は中身で、顔はモデル。それでも全世界が返事をした',
             main=dict(id='IK_6AZOAsbA', role='Official 1991', artist='Technotronic', song='Move That Body (feat. Reggie)', cap=''),
             body=[f'ベルギーのテクノトロニックは、ジョ・ボガートが1987年に始めたプロジェクトだ。1989年の「Pump Up the Jam」はイギリスとアメリカで2位{src("Wikipedia", WPUJ)}。ただし、ジャケットとMVに出ていたのはコンゴ生まれのモデル、フェリー・キリンギ。歌っていたのはコンゴ系ベルギー人のラッパー、ヤ・キッドK。ボガートはのちに認めている。「フェリーはレコードとはほとんど関係なかった」{src("Wikipedia", WTT)}。ブラック・ボックスと同じ季節の、同じ構図。',
                   f'1991年、2枚目のアルバム『Body to Body』から最初のシングルとして出たのが「Move That Body」。歌うのはレジー。今度はちゃんと本人が表に出た。イギリスで12位{src("Wikipedia", WMTB)}。タイトルは歌というより業務連絡だ。そして全世界が即座に返事をした。',
                   f'同じ1991年5月15日、東京・芝浦の倉庫を改装して、ジュリアナ東京が開店する。最大収容2,000人。女性だけが上れる高さ130センチの「お立ち台」で、ボディコンの女性たちが扇子を振り回した。アイルランド人DJジョン・ロビンソンの「ジュリアナス〜トキオ〜！」が合図{src("Wikipedia", WJUL)}。',
                   f'営業していた1991年5月から1994年8月は、実はバブル崩壊が進んでいく時期だった。景気の下り坂で、人はいちばん高い台に上って踊った。そして扇子を振るこのスタイルは地方のディスコにも広がり、「盆踊りが現代に復活した」とも言われた{src("Wikipedia", WJUL)}。第2章の徳島が、芝浦で帰ってきていた。'],
             note='1994年8月31日の最終日は無料開放。入れない人の列は田町駅まで続き、翌日の昼過ぎまでアンコールが続いた（Wikipedia）。閉店なのに、アンコール。踊りの終わり方としては、かなり正しい。',
             bridge='チャートの話が続いた。ここからは、踊る体の側の話をしよう。半世紀たっても「1」は鳴っている。'),
        dict(no='10', artist='Candy Dulfer', song='Pick Up The Pieces', album='ライブ映像（原曲：Average White Band・1974）', year='2009',
             catch='ファンクは今日も生きている。しかも、スコットランド経由で',
             main=dict(id='rhF5jG8BvgM', role='Live', artist='Candy Dulfer', song='Pick Up The Pieces', cap=''),
             body=[f'原曲を作ったのは、スコットランドのバンド、アヴェレッジ・ホワイト・バンド。1971年の終わりにロンドンで結成。名前の由来は、彼らの演奏を聴いた歌手のボニー・ブラムレットの一言、「これは平均的な白人には刺激が強すぎる」{src("Wikipedia", WAWB)}。自分へのツッコミが、そのまま名前になった。',
                   f'「Pick Up the Pieces」は1974年7月にイギリスで出て、チャートに入らなかった。ところがその秋、アメリカのラジオがかけ始め、1975年2月22日に全米1位。歌詞はほぼ無い。題名を何度か叫ぶだけ。サックスのモリー・ダンカンはシングルにすること自体に反対していた。「スコットランド人がやる、叫び声しかないファンクのインスト」だから{src("Wikipedia", WPUP)}。',
                   f'ここで第6章の人が黙っていない。ジェームス・ブラウンのバンドThe J.B.’sは、返歌として「Pick Up the Pieces, One by One」を出した。名義は AABB、「アバヴ・アヴェレッジ・ブラック・バンド（平均以上の黒人バンド）」{src("Wikipedia", WAWB)}。ジョークにジョークで返す。ファンクは最初から、少し笑っていた。',
                   f'吹いているキャンディ・ダルファーは1969年9月19日、アムステルダム生まれ。父はジャズ・サックス奏者のハンス・ダルファー。6歳で吹き始め、14歳で自分のバンドを作る。1988年にはプリンスがステージに上げて即興のソロを吹かせた。1990年のデビュー作『Saxuality』はグラミー候補{src("Wikipedia", WCD)}。',
                   'このライブがいいのは、原曲を壊さずに、横から押し込んでくるところだ。JBが「1」を叩いてから半世紀。腰はまだ、ちゃんと返事をしている。'],
             more_label='聴きくらべ — 原曲（1975年のテレビ）',
             more=[dict(id='7Rvk0NPupIU', role='TOTP 1975', artist='Average White Band', song='Pick Up the Pieces', cap='')],
             bridge='さいごに、いちばん深いところへ。1995年、スイスの湖のほとり。'),
        dict(no='11', artist='Meshell Ndegeocello', song='Boyfriend', album='モントルー・ジャズ・フェスティバル', year='1995',
             catch='ベースの底から、こんにちは',
             main=dict(id='JjmYnC3sq3A', role='Montreux 1995', artist='Meshell Ndegeocello', song='Boyfriend (Montreux 1995)', cap=''),
             body=[f'1995年、レマン湖のほとりのモントルー・ジャズ・フェスティバル{src("Wikipedia", WMJF)}。そのステージにベースを抱えて立ったのがメシェル・ンデゲオチェロ。1968年8月29日、西ベルリン生まれ。父は陸軍のサックス奏者。育ったのはワシントンD.C.で、80年代の終わりに地元のゴーゴーのサーキットで鍛えられた。1993年のデビュー作『Plantation Lullabies』の初期の盤には、名前の読み方を書いたシールが貼られていた{src("Wikipedia", WMN)}。',
                   f'1994年、自作の「If That’s Your Boyfriend (He Wasn’t Last Night)」が全米73位。ジョン・メレンキャンプとのデュエット「Wild Night」は3位。マドンナの「I’d Rather Be Your Lover」でベースを弾いたのも同じ1994年。もとは当時マドンナと付き合っていた2パックのラップが入っていて、彼が刑事告発されたあとに外され、その穴を彼女のベースが埋めた。グラミー候補は13回、受賞は3回{src("Wikipedia", WMN)}。',
                   '踊りを「高くする」音楽はたくさんあった。彼女は底に潜る。ベースとキックの床の上を、声がまたぐ。踊りの話をどこで締めるか迷って、ここに置いた。腰が動く音楽のいちばん下はベースで、いちばん奥は静けさだと、教えてくれる音だから。'],
             more_label='聴きくらべ — 1994年のあの一文',
             more=[dict(id='D01oLT4a10A', role='1994', artist='Meshell Ndegeocello', song='If That’s Your Boyfriend (He Wasn’t Last Night)', cap='')],
             note='題名を訳すと「それがあなたの彼なら、昨夜は違ったけど」。短編小説が1行で終わっている。僕の日記は3行書いても何も起きない。'),
    ],
    close=['さて。1万年前の壁に、戻ろう。',
           '人は、なぜ踊るのか。答え合わせをすると、理由はひとつじゃなかった。死者を迎えるため。禁じられた記憶を運ぶため。「はしたない」を乗り越えるため。誰も抱かなくていい自由のため。ドラマーに少しやらせるため。爆破された夜への返事として。',
           'それでも共通点はひとつ見つかる。1万年前のあの人たちは、壁に狩りの絵と並べて、踊りの絵を描いた。生きるのに必要なことだったからだ。だから次にコンビニ帰りの右足が勝手に1拍目を踏んだら、それはあなただけの話じゃない。1万年ぶんの返事が、あなたの体から出ている。',
           '踊る人は、まだまだいっぱいいる。引き続き、レポートを続けます。次回のレポートもお楽しみに。'],
    sources=[('Wikipedia — Bhimbetka rock shelters', WBH), ('Wikipedia — Hurrian songs', WHU),
             ('Wikipedia — 盆踊り', WBON), ('Wikipedia — 阿波踊り', WAWA), ('徳島県 — 阿波おどり', TOKU), ('THE AWAODORI — 徳島市阿波おどり', AWAM),
             ('Wikipedia — Hula', WHULA), ('Wikipedia — Kalākaua', WKAL), ('Wikipedia — Merrie Monarch Festival', WMM),
             ('Wikipedia — Waltz', WWAL), ('Wikipedia — The Blue Danube', WDAN),
             ('Wikipedia — The Twist (song)', WTW), ('Wikipedia — Chubby Checker', WCC), ('Wikipedia — Peppermint Lounge', WPEP), ('HISTORY — “The Twist” launches dance craze', HIS),
             ('Wikipedia — Cold Sweat', WCS), ('Wikipedia — Get Up (I Feel Like Being a) Sex Machine', WSM),
             ('Wikipedia — I Feel Love', WIFL), ('Wikipedia — Disco Demolition Night', WDD), ('Wikipedia — House music', WHOUSE),
             ('Wikipedia — Ride on Time', WROT),
             ('Wikipedia — Technotronic', WTT), ('Wikipedia — Pump Up the Jam', WPUJ), ('Wikipedia — Move That Body', WMTB), ('Wikipedia — ジュリアナ東京', WJUL),
             ('Wikipedia — Average White Band', WAWB), ('Wikipedia — Pick Up the Pieces', WPUP), ('Wikipedia — Candy Dulfer', WCD),
             ('Wikipedia — Meshell Ndegeocello', WMN), ('Wikipedia — Montreux Jazz Festival', WMJF)],
    note='',
    i18n=I18N,
)

# 吹き出しの鍵は mag_build の部品名に合わせる（spec 側は note= で書く）
_K = 'sa' + 'y'
for _c in M['chapters']:
    if 'note' in _c:
        _c[_K] = _c.pop('note')
    _c['body'] = [({_K: p['note']} if isinstance(p, dict) and 'note' in p else p) for p in _c['body']]
    if _c['no'] in PHOTOS:
        _c['after'] = PHOTOS[_c['no']]

if __name__ == '__main__':
    print(write(M))
