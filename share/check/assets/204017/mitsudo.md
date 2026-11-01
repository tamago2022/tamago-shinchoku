# 映像の密度の調べ物（廃墟モールFPV・Blender前の準備資料）

調べ日：2026-11-01。動画は見ていない。記事・インタビューの文章だけから拾った。「【抜粋】」は検索結果の抜粋のみ（本文未確認）。「【手】」は出典のない一般的なBlenderの手で、Blender側で実測して決める目安。

## 1. 結論：密度は何から生まれるか
1. 密度は「物の数」より、時間が刻んだ跡（汚れ・苔・割れ・水）が、場所ごとに理由を持って偏って乗ることから生まれる。Alex Romanは「建物は最初の1か月で時の跡が出る。ぴかぴかで見せるのは間違い」と語る。
2. 全部を見せない。影・反射・光の筋・ボケで「示す」ほうが、全部描くより濃く見える（Romanの「smoke and mirrors」）。
3. 小さな物の反復（椅子・子柱・タイル目地）が、スケール感と「長い時間そこにあった」感じを一度に出す。
4. カメラの癖（ボケ・歪み・ビネット・色収差・粒子）と、緩急・間のある動きで「撮られた映像」に見せる。FPVは計画した振り付け＋何度もの撮り直しで成立している。
5. 白黒基調では、色を残す場所を決めて視線を誘導する。色数でなく、色を残す理由で密度を作る。

## 2. 要素ごとの表
| 要素 | 参照作でどう使われているか（出典） | この作品での入れ方（Blender/EEVEE） |
|---|---|---|
| 汚れ・雨だれ | Romanは時間の跡を意図して素材に入れた（[Filmnosis p4](https://filmnosis.com/interviews/alex-roman-on-the-making-of-the-third-the-seventh/4)）。Maarten Hofのモールは汚れ・埃・水たまりを塗れるマスター素材（[80.lv](https://80.lv/articles/an-abandoned-shopping-mall-made-in-blender-substance-3d-unreal-engine)） | 【手】天窓の下・壁の継ぎ目・手すりの下から縦に垂れる筋。Noise を縦に伸ばして ColorRamp → Mix（Overlay）で Base Color と Roughness に。Pointiness/AO で隅に溜める。 |
| 苔・植物 | Beau Chapmanの廃墟モールは植物と水生生物を入れ、細部への気配りが評された（[Blender Artists](https://blenderartists.org/t/abandoned-mall-scene/1302408)）。Hofは「ほぼ全小物に苔を塗れる」（80.lv）。Romanも自然を「呼吸する登場人物」とした（Filmnosis p4） | 【手】白黒基調なので苔は暗い塊で。Geometry Nodes の Distribute Points on Faces → Instance on Points、法線の向き（水平度）で割合を決める。苔マスクはNoise＋AO。蔦は天窓の下に集中。 |
| ほこり（空中の粒） | 出典で直接の記述は見つからず。Hofは「ワールド空間の埃素材で小物を環境になじませる」（80.lv） | 【手】光の筋の中だけに浮く小さな粒。Geometry Nodes で体積内にポイント散布→小さな平面/ico球インスタンス、Emission弱め。粒は動かさず、カメラ移動で視差を見せる。床には World 座標の埃マスク。 |
| 割れたガラス | Rolling Acresは「割れたガラスとがれきが床に散乱」（[Weather.com](https://weather.com/travel/news/abandoned-malls-seph-lawless-photos-20140408)） | 【手】ガラスは Principled（Transmission 1、Roughness 0.05）に、割れ部分はアルファ抜き＋白い縁の線。床のガラス片は小さな板を散布。EEVEEは屈折が弱いので、割れ板は簡易のアルファ＋反射で足りる。 |
| 看板の残骸 | 実物写真記事に看板の記述は無し。Hofの素材セットは店舗が空洞（80.lv） | 【手】文字の欠けたサイン（Text→Mesh＋Boolean）、斜めに垂れた案内板、色が残る1点（後述）。文字は架空語にする。 |
| 配線・ケーブル | 出典なし（天井の鎖はBlender Artistsのコメントで「良い仕掛け」と評価） | 【手】天井開口から垂れるケーブルは Curve＋Bevel、Simple Deform でたるみ。本数と長さはGeometry Nodesでばらす。 |
| 水たまりの反射 | Chapmanの作は水の見た目が評価された（Blender Artists） | 【手】床の凹みに Roughness 0.02 の領域（Noise の閾値）を作り、EEVEE Legacy なら Screen Space Reflections を ON（Nextは Raytracing）。反射が主役の光源を映す配置にする。 |
| 光の筋（ボリューム） | Romanは光の動き（タイムラプス）を、レンダラーの限界試験にした（[Filmnosis p2](https://filmnosis.com/interviews/alex-roman-on-the-making-of-the-third-the-seventh/2)）。EEVEEのボリュームは版で挙動が変わる点に注意（[Blender issue #80425](https://projects.blender.org/blender/blender/issues/80425)） | 【手】天窓に Sun/Area ライト。World に Principled Volume（Density 0.005〜0.02、Anisotropy 0.3〜0.5）。EEVEE Legacy は Volumetrics の Samples 64、Volumetric Shadows ON。 |
| ボケ（被写界深度） | Romanは映画の言語を持ち込んだと語る（Filmnosis p2）。具体値の記事は未確認 | 【手】カメラのDOFをON、F値 2.8〜4（FPVは広角なので浅すぎない）、フォーカス対象は Empty。奥の吹き抜けはボケで「奥行きの霞」に。 |
| レンズの癖 | 具体値の記事は未確認。実機FPVは小型広角（Digital Trends：cinewhoop） | 【手】コンポジットで Lens Distortion（歪み＋分散）、Glare（Bloom）、Vignette（Ellipse mask）、Film Grain（Noise）、軽いモーションブラー。魚眼にしすぎない。 |
| ゆっくりした間 | Romanは「示す・隠す」をカメラ運びにも使う（Filmnosis p2）。Right Up Our Alleyは各ポイントで振り付けされた間（[Digital Trends](https://digitaltrends.com/news/makers-of-that-bowling-alley-drone-video-reveal-hardest-move)） | 【手】Fカーブで、速→ほぼ停止（1.5〜2秒のホバー）→再加速。ホバー中は小さな揺れだけ。見せ場の前で一度止まる。 |
| スケール感（反復する小物） | 手すり・エスカレーターは実物写真で必ず出る（Weather.com）。Hofの素材は「モジュール式」（80.lv） | 【手】Array/Instances で椅子・子柱・タイル目地を等間隔に。均一にせず、10〜20%を倒す・欠く・ずらす。目地は Bump＋AO。 |
| 落ちた天井パネル・がれき | 「崩れる壁のがれき」（Weather.com）。Hofのセット | 【手】Rigid Body で落として確定→ベイク。天井の穴の真下に集中。パネルの端は曲げ、配線を引っ張らせる。 |
| AO／接触影 | 出典は一般論 | 【手】EEVEE Legacy は Ambient Occlusion と Contact Shadows（ライト側）で補う。壁と床の境、椅子の下を暗く。 |
| 色の設計 | Romanは「色は感情を伝える強い道具」と語る（Filmnosis p2）。Lawlessの雪のモールは白一色に近い（[PetaPixel 抜粋](https://petapixel.com/2015/02/09/winter-wonderland-photos-abandoned-indoor-mall-covered-snow/)） | 【手】白黒基調に、色を1〜2か所だけ残す：①割れた看板の1色②水たまりに映る空の青み。残す理由＝視線誘導とモールらしさ。Color Balance で影を冷たく、光を僅かに暖かく。 |

## 3. 一目で「モールの廃墟」と分かる要素（実物写真の記事から）
出典：[Weather.com（Seph Lawless）](https://weather.com/travel/news/abandoned-malls-seph-lawless-photos-20140408)、[PetaPixel 抜粋](https://petapixel.com/2015/02/09/winter-wonderland-photos-abandoned-indoor-mall-covered-snow/)、[80.lv](https://80.lv/articles/an-abandoned-shopping-mall-made-in-blender-substance-3d-unreal-engine)。Lawless本人は「エスカレーターの下の綿菓子」「噴水の水音」を記憶として語っている（Weather.com）。
- [ ] 吹き抜け（アトリウム）と複数階の通路 — 【抜粋】で確認
- [ ] エスカレーター（止まって、植物や瓦礫がある）— Weather.com／【抜粋】
- [ ] 噴水（枯れた池・水が溜まる）— Weather.com（記憶の語りとして）
- [ ] 手すり（ガラス/金属）の連続 — 一般的特徴、Hofのモジュール群
- [ ] 閉じたシャッターと空洞の店舗 — Hof（店舗に入れない設定）
- [ ] 天窓と落ちる光 — 【手】今回読んだ記事に明記なし
- [ ] フードコートの椅子とテーブル — 【手】明記なし
- [ ] 案内板・看板・サイン — 【手】明記なし
- [ ] 床のガラス片・がれき・崩れた壁 — Weather.comで確認
- [ ] 水たまり・苔・植物 — Hof、Chapmanの作品で確認
- [ ] 天井パネルの落下と配線 — 【手】明記なし

## 4. FPVワンテイクの動きの型（5項目）
出典：[Digital Trends](https://digitaltrends.com/news/makers-of-that-bowling-alley-drone-video-reveal-hardest-move)、[ProVideo Coalition](https://www.provideocoalition.com/jay-christensen-a-top-gun-drone-pilot-and-videographer/)。
1. 入りが一番難しい：Right Up Our Alleyは、高所から降りて入口へ飛び込む冒頭が最難関だった。本作も「入口突入」を最初の見せ場に。
2. くぐり抜けを見せ場にする：客の脚の間、レーンからピンの奥へ。本作は、エスカレーターの下・崩れた天井の隙間・手すりの間をくぐる。
3. 偶然に見えるよう振り付ける：5回の練習と約10テイクで人の動きと合わせた。本作は、物の落下・水滴をタイムラインで飛行に合わせて置く。
4. 終わり方を決める：実作は最後にドローンがピンへ突入。本作は、光の筋の中での急停止、または暗がりへ消える終わりを。
5. 緩急と間：実作は音を後付け。本作は「沈める寺」に合わせ、速い区間は少なく、ホバーを増やす。【手】ゆっくり：速い＝3：1を目安。揺れは基本なめらかに、微小なロール揺れを重ねる。

## 5. 調べで分からなかったこと
- Alex Romanの被写界深度・露出・レンズ設定の具体値：読めたインタビューには無し（Filmnosis p1・p3は取得できず、書籍『From Bits To The Lens』に詳しい可能性）。Chaos Groupの長いインタビューは本文を取れていない。
- 廃墟モールを飛ぶFPVのメイキング記事：見つからず。代わりにRight Up Our Alleyで型を取った。
- Blenderの設定値は【手】の目安で、出典付きの数字ではない。EEVEE Legacy／Next で項目名が違う。

## 6. 出典一覧
- [Filmnosis Alex Roman p2](https://filmnosis.com/interviews/alex-roman-on-the-making-of-the-third-the-seventh/2)／[p4](https://filmnosis.com/interviews/alex-roman-on-the-making-of-the-third-the-seventh/4)
- [CG Channel（Chaos Groupインタビュー紹介のみ）](https://www.cgchannel.com/?p=22773)
- [Visualizing Architecture](https://visualizingarchitecture.com/?p=907)
- [80.lv 廃墟モール](https://80.lv/articles/an-abandoned-shopping-mall-made-in-blender-substance-3d-unreal-engine)
- [Blender Artists Abandoned Mall Scene](https://blenderartists.org/t/abandoned-mall-scene/1302408)
- [Blender issue #80425](https://projects.blender.org/blender/blender/issues/80425)
- [Digital Trends](https://digitaltrends.com/news/makers-of-that-bowling-alley-drone-video-reveal-hardest-move)
- [ProVideo Coalition](https://www.provideocoalition.com/jay-christensen-a-top-gun-drone-pilot-and-videographer/)
- [Weather.com Seph Lawless](https://weather.com/travel/news/abandoned-malls-seph-lawless-photos-20140408)
- [PetaPixel 雪のモール（検索抜粋のみ）](https://petapixel.com/2015/02/09/winter-wonderland-photos-abandoned-indoor-mall-covered-snow/)
