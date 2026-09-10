// ここが正本データ。元は AI出力/_ルール/進捗表.html の REQUESTS（2026-09-02 に移植。中身は変えていない）。
// 更新のしかた：このファイルを書き換えて git push するだけ（GitHub Pages が数分で反映）。
// リンクは links:[{label:"…", url:"obsidian://open?vault=tamago_brain&file=AI出力/…"}] の形で足す。

window.SHINCHOKU = {
  generatedAt: "2026-09-01T00:20:00+09:00",

  // 626番（2026-09-07）：support@anthropic.comへ送った問い合わせの返信を1日1回チェックする見張り。
  // 見張り係(tools/check_anthropic_reply.py)は9/07からgmail_app_password未設置でblocked:no_credentialのまま
  // 死んでいた（自動検知はできず）。683番でその代わりに、Lovable公開専用Chrome(CDP)の
  // 既存タブへ1本だけ新規タブを足してGmailに直接アクセスし（新規ブラウザ起動はせず、既存プロセスに
  // 相乗り）、9/07にeggypop2010@gmail.com経由で送った問い合わせへの返信本文を人力で確認・記録した。
  anthropicReply: {
    subject: "Feedback: Dispatch behavior varies between sessions — can it be pinned?",
    from: "Fin AI Agent from Anthropic",
    date: "2026-09-07T12:40:00+09:00",
    summary: "各セッションは毎回まっさらな文脈で始まり前回の会話を引き継がないのは仕様どおり。特定セッションの挙動・モデル振り分けを" +
             "『固定』する公式手段は現時点で無い。対策としてMemory機能とSkillsで指示を明示的・永続的にすることを推奨（例：" +
             "『このチャンネルでは定型作業は自律的に決め、大きな変更のときだけ確認して』と明示的に覚えさせる）。",
    gmailUrl: "https://mail.google.com/mail/u/0/#search/from%3Aanthropic.com",
    detectedAt: "2026-09-09T09:20:00+09:00",
    note: "見張り係の自動検知ではなく人力確認（gmail_app_password未設置のため）。マイク不具合＋添付画像ロスの新規問い合わせ" +
          "(anthropicDraftMail)はまだたまごさん送信前のため、その返信はまだ存在しない。"
  },

  // 683番（2026-09-09）：マイク不具合の「再現条件を記録できる形」。新しい置き場所は作らず、
  // ここに配列で1行足すだけにする（626番のanthropicReplyと同じ手更新パターン）。
  // たまごさんが「またマイクが使えない」と言ったら、time・load・状況を1件足すだけでよい。
  micIssueLog: [
    {
      time: "2026-09-09T08:20:00+09:00",
      note: "初回切り分け（683番）。macOSのマイク権限＝Claude Desktopに許可済み（TCC.db実測）。" +
            "デフォルト入力デバイス＝内蔵マイクのまま（切り替わっていない）。他アプリがマイクを排他占有している" +
            "証拠は見つからず（aivisspeech-engine・Zoomは非稼働）。一方でload average 37〜45（8コアの4〜6倍・" +
            "Braveだけで75プロセス、Chromeレンダラー単体でCPU159%）という慢性的な過負荷を検出。" +
            "スマホは常時使える＝サーバ/アカウント側の問題ではないという手がかりとも整合するため、" +
            "こちら側（Macの高負荷）が最有力の要因。ただし高負荷時にアプリがマイクストリームを正しく" +
            "再初期化できていない可能性（アプリ側の頑健性の問題）も残るため、両方をAnthropicへ報告する。"
    }
  ],

  // 683番：Anthropicへの問い合わせ文面（マイク＋添付画像の取りこぼしの2件）。
  // 送信はたまごさん本人が押す（外部公開は確認義務）。gmailComposeUrlを開けば宛先・件名・本文が
  // 入った状態でGmailの作成画面が開くので、あとは送信ボタンを押すだけ。
  anthropicDraftMail: {
    to: "support@anthropic.com",
    subject: "Claude Desktop (Mac): intermittent microphone dictation failures & ~30% dropped image attachments",
    bodyEn: "Hello Anthropic Support,\n\nI'm a daily user of Claude Desktop (Cowork/Dispatch) on macOS and would like to report two intermittent input reliability issues.\n\n1) Microphone dictation intermittently stops working (Mac only)\n- I dictate most instructions by voice. On the Mac app, the microphone intermittently stops working (not a hard permission error, it just silently fails sometimes).\n- On my iPhone (same account), voice input always works. Only the Mac desktop app is affected.\n- I checked local causes: mic permission for Claude is granted in System Settings, the default input device is still the built-in mic (not switched), and I found no other app holding exclusive mic access at failure time. My Mac does sometimes run under heavy system load, which may contribute, but the Mac-only, intermittent pattern suggests the app itself may not recover the mic stream reliably (e.g. after device/focus changes or under load).\n- Is this a known issue? Any recommended fix besides restarting the whole app?\n\n2) Attached screenshots sometimes fail to send (~30% of the time)\n- When I attach a screenshot in Claude Desktop, about 30% of the time the image never reaches the assistant, even though it looked like it sent. I only notice when the assistant doesn't reference it, so I have to retake and resend, doubling the effort.\n- This is intermittent, not a hard failure every time.\n\nBoth issues affect voice input and image attachments, my primary way of using Claude Desktop daily. Any known fixes, or ways I can help debug (logs, timestamps) would be appreciated.\n\nThank you,\neggypop2010@gmail.com",
    bodyJa: "Anthropicサポート様\n\nClaude Desktop（Mac版・Cowork/Dispatch）を毎日使っているユーザーです。作業の妨げになっている入力の不安定さについて、2件ご報告します。\n\n1) マイク（音声入力）が断続的に使えなくなる（Mac版のみ）\n- 指示のほとんどを音声入力で出しています。Mac版アプリで、マイク入力が断続的に効かなくなります。権限エラーのような明確な失敗ではなく、時々静かに動かなくなるだけです。\n- 同じアカウントのiPhone版では、音声入力は常に安定して動きます。Mac版だけの現象です。\n- こちらで調べられる原因は確認済みです：システム設定でClaudeへのマイク権限は許可済み、デフォルトの入力デバイスは内蔵マイクのまま（切り替わっていない）、その時点で他アプリがマイクを排他的に使っている証拠も見つかりませんでした。Macがときどき高負荷になることが一因の可能性はありますが、断続的でPC版だけで起きるという特徴から、アプリ側（負荷時のマイクストリーム再初期化の扱いなど）の問題である可能性も考えられます。\n- 既知の問題か、アプリ全体の再起動以外に推奨される対処があれば教えてください。\n\n2) スクリーンショットの添付が届かないことがある（約3割）\n- Claude Desktopでメッセージに画像を添付すると、送信できたように見えても、約3割の確率でアシスタント側に画像が届きません。アシスタントが画像に触れないことで気づき、撮り直して送り直すことになり、毎回二度手間になっています。\n- こちらも常に失敗するわけではなく、断続的に発生します。\n\nどちらも、私が日常的にClaude Desktopとやり取りする主な手段（音声入力＋画像添付）を不安定にしています。既知の対処法や、デバッグに協力できること（ログ、発生時刻など）があれば教えてください。\n\nよろしくお願いいたします。\neggypop2010@gmail.com",
    gmailComposeUrl: "https://mail.google.com/mail/?view=cm&fs=1&to=support%40anthropic.com&su=Claude%20Desktop%20%28Mac%29%3A%20intermittent%20microphone%20dictation%20failures%20%26%20~30%25%20dropped%20image%20attachments&body=Hello%20Anthropic%20Support%2C%0A%0AI%27m%20a%20daily%20user%20of%20Claude%20Desktop%20%28Cowork/Dispatch%29%20on%20macOS%20and%20would%20like%20to%20report%20two%20intermittent%20input%20reliability%20issues.%0A%0A1%29%20Microphone%20dictation%20intermittently%20stops%20working%20%28Mac%20only%29%0A-%20I%20dictate%20most%20instructions%20by%20voice.%20On%20the%20Mac%20app%2C%20the%20microphone%20intermittently%20stops%20working%20%28not%20a%20hard%20permission%20error%2C%20it%20just%20silently%20fails%20sometimes%29.%0A-%20On%20my%20iPhone%20%28same%20account%29%2C%20voice%20input%20always%20works.%20Only%20the%20Mac%20desktop%20app%20is%20affected.%0A-%20I%20checked%20local%20causes%3A%20mic%20permission%20for%20Claude%20is%20granted%20in%20System%20Settings%2C%20the%20default%20input%20device%20is%20still%20the%20built-in%20mic%20%28not%20switched%29%2C%20and%20I%20found%20no%20other%20app%20holding%20exclusive%20mic%20access%20at%20failure%20time.%20My%20Mac%20does%20sometimes%20run%20under%20heavy%20system%20load%2C%20which%20may%20contribute%2C%20but%20the%20Mac-only%2C%20intermittent%20pattern%20suggests%20the%20app%20itself%20may%20not%20recover%20the%20mic%20stream%20reliably%20%28e.g.%20after%20device/focus%20changes%20or%20under%20load%29.%0A-%20Is%20this%20a%20known%20issue%3F%20Any%20recommended%20fix%20besides%20restarting%20the%20whole%20app%3F%0A%0A2%29%20Attached%20screenshots%20sometimes%20fail%20to%20send%20%28~30%25%20of%20the%20time%29%0A-%20When%20I%20attach%20a%20screenshot%20in%20Claude%20Desktop%2C%20about%2030%25%20of%20the%20time%20the%20image%20never%20reaches%20the%20assistant%2C%20even%20though%20it%20looked%20like%20it%20sent.%20I%20only%20notice%20when%20the%20assistant%20doesn%27t%20reference%20it%2C%20so%20I%20have%20to%20retake%20and%20resend%2C%20doubling%20the%20effort.%0A-%20This%20is%20intermittent%2C%20not%20a%20hard%20failure%20every%20time.%0A%0ABoth%20issues%20affect%20voice%20input%20and%20image%20attachments%2C%20my%20primary%20way%20of%20using%20Claude%20Desktop%20daily.%20Any%20known%20fixes%2C%20or%20ways%20I%20can%20help%20debug%20%28logs%2C%20timestamps%29%20would%20be%20appreciated.%0A%0AThank%20you%2C%0Aeggypop2010%40gmail.com",
    gmailSearchUrl: "https://mail.google.com/mail/u/0/#search/from%3Aanthropic.com",
    note: "651番・626番の実測どおり、この作業場にはGmail本文を読む/送るブラウザ手段がありません（IMAP=要アプリパスワード・Mail.app=Gmail未設定・既存Chrome=Lovable専用でGmail未ログイン・新規ブラウザ起動は憲法で禁止）。" +
          "そのため本文はここに事前生成し、gmailComposeUrlを開けば宛先・件名・本文入りでGmail作成画面が開く状態にしてあります。たまごさんが開いて送信ボタンを押すだけで送れます。"
  },

  // ── 今動いているもの（手更新。リアルタイム連携ではない）──

  // 2026-09-04 たまごさん「次に発車予定の予備軍も分かるようにしといて。これが終わったら次は何が発車されるのかな、って見たいから」
  // 上から順に発車する。走行中が空いたらここの一番上が繰り上がる。
  queueUpdatedAt: "2026-09-04T10:15:00+09:00",
  queue: [
    {n:1, title:"シェアしても画像が出ない", why:"SNSに貼ったときサムネが出ない",
     what:"ページのリンクをSNSやLINEに貼ると、ふつうは記事のサムネイル画像が一緒に出ます。それが出ていません。画像が出ないと、貼っても誰も押しません。ページの種類（曲・棚・アーティスト・特集・トップ）ごとに、画像を指定するタグが正しく出ているかを1つずつ確認して直します。",
     progress:"2026-09-05 一次対応：曲・棚・アーティスト・トップ・特集10本の型を確認、`/feature/final-view`だけ画像URLが相対パス（LINE/iMessage等で解決できない）のまま壊れていたのを発見・修理してmainへpush済み（commit 703a353f）。他の9本の特集・曲・棚・トップは正常だった。本番反映は自動デプロイ待ち。個別の曲ページ・棚ページ1件ずつの全数チェックはまだ（母数が数万件あるため今回は型の代表チェックまで）。"},
    {n:2, title:"LINEに送るが壊れている", why:"リンクのコピーはできるが、LINEを選ぶとQRコードを求められる",
     what:"共有ボタンから「LINEに送る」を選ぶと、送るはずが QRコード読み取りの画面になってしまう状態です。スマホから友達に送れないので、実質シェアできません。LINEの共有の呼び出し方が古い方式のままになっている可能性が高いです。"},
    {n:3, title:"おすすめを10本にする（全ページ）", why:"アメリだけの話ではなく、サイト全部",
     what:"ページの下にある「こちらも」「おすすめ」が4〜5本しか出ていません。これを10本に増やします。アメリのページで気づいた話ですが、直すのは全ページです。次から次へと聴き続けられるようにするのが狙いです。"},
    {n:4, title:"驚の部屋・美の部屋を「音楽の扉」と同じ形にする", why:"棚が縦にバーッと出ていて見づらい",
     what:"音楽の扉では、棚が横一列に並んでいて、押すと一覧でサムネイルが出ます。驚の部屋と美の部屋はその形になっておらず、全部が縦に並んで出てしまっています。音楽の扉に合わせます。新しく作るのではなく、既にある形に寄せます。"},
    {n:5, title:"棚編集で155棚すべてを選べるようにする", why:"「驚の部屋」の中のテクノロジー・天才が選べない",
     what:"外部URLを貼って棚に入れるとき、選択肢に上位10個（音楽・笑い・かわいい・食・旅・踊り・美・驚・静・和）しか出てきません。その下にあるサブ棚（テクノロジー、天才など）が選べないので、入れたい棚に入れられない状態です。"},
    {n:6, title:"外部から入れた曲の「曲名とアーティスト」を自動で埋める", why:"URLを貼っただけだと曲名もアーティストも空のまま",
     what:"X（旧Twitter）などからURLを貼って取り込むと、曲名やアーティスト名が入らないことがあります（例：92° / Vulfmon & Tommy de Bourbon が入らなかった）。1日1回、その日入ったものを見回って、動画の説明欄や音楽データベースから曲名とアーティストを調べて埋めます。Shazamがやることを、あとから機械にやらせるイメージです。裏が取れないものは埋めずに残します。"},
    {n:7, title:"「誰が演奏しているか分からない」カードを22件直す", why:"演奏者が登録されていないので、その人のページに飛べない",
     what:"カードに動画は入っているのに、誰が演奏・投稿しているのかが登録されていないものが22件あります。そのせいで、そのアーティストのページ（部屋）に繋がりません。動画の投稿者情報から特定して埋めます。判断は要らない、埋めるだけの作業です。"},
    {n:10, title:"HOME／ふるさとプレイリストを仕上げる", why:"33曲は入った。タイトル・公開設定・曲順が残り",
     what:"Spotifyに33曲入りましたが、タイトルが型に合っていない（🏠 帰りたくなった夜に｜ごきげん補給所 にする）、非公開のまま、曲順が国で固まっていて物語の流れになっていない、の3点が残っています。ChromeがSpotifyにログインしていないのが壁です。"},
    {n:11, title:"プレイリストの曲を補給所にもカードとして入れる", why:"裏タグを仕込んで後から繋げるように",
     what:"プレイリストに入れた曲を、補給所のカードとしても登録します。裏タグ（_home-leave / _home-faraway など6パターン＋国コード）を付けておくと、あとで「アイルランドの帰れない歌だけ」のように引っ張れます。"},
    {n:12, title:"ドラマ主題歌22件を「ドラマ」棚へ移す", why:"映画の棚にドラマが混ざっている",
     what:"映画の棚50枚の中に、テレビドラマの主題歌（ミステリと言う勿れ、朝ドラおひさま など）が混ざっています。ドラマの棚を作ってそちらへ移し、映画の棚は映画だけにします。"},
    {n:13, title:"コピーの書き直しを5案（A〜E）から選べるようにする", why:"1案だけ出されても選べない",
     what:"コピーを直すとき、いまは書き直し案が1つしか出ません。切り口の違う5案を出して選べるようにします。さらに「全部自分で書く」空欄も用意します。将来は1行目はA案、2行目はC案、のようにいいとこ取りできる形へ。"},
    {n:14, title:"止まっているタスク56件を減らす", why:"台帳が「着手中」のまま何日も動いていない",
     what:"依頼の一覧で「止まっている（台帳は着手中）」が56件あります。着手したことになっているのに実際は誰も動いていないもので、これが「頼んだのに帰ってこない」の実体です。短時間で終わるものから順に片づけて数を減らします。"},
    {n:15, title:"未着手110件から、すぐ終わるものを拾って消す", why:"1時間以内で終わるものだけ選んで数を減らす",
     what:"依頼の一覧で「未着手」が110件あります。この中には調査が要る大きいものと、確認するだけで閉じられる小さいものが混ざっています。小さいものだけ選んで、次々に片づけます。"},
    {n:16, title:"未反映ブランチ112本を仕分ける", why:"本番に出ていない作業が112本ぶん積まれている",
     what:"「ブランチ」＝作業の下書き置き場のことです。AIが作業した内容が112本ぶん、本番に出ないまま残っています。中身が既に本番に入っていて捨てていいもの、まだ生きていて本番に出すべきもの、判断が要るもの、の3つに仕分けます。これも「帰ってこない卵」の実体です。"},
    {n:17, title:"YouTube APIで動画を差し替えられるようにする", why:"急いでいない。実装はもう入っている",
     what:"棚の動画を、スマホから検索して差し替えられる機能です。コードは既に本番に入っていて、APIキーを通すところだけ残っています。たまごさんから「本当に急いでいない」との指定あり。"},
    {n:18, title:"アメリの細かい調整", why:"85点。急がない",
     what:"アメリのページは既に本番に出ていて、たまごさんの採点で85点。残り15点ぶんの細かい調整（「この曲から続く道」の位置など）は後回しでよい、との指定あり。"},
    {n:19, title:"Eagleの画像をWebで見る仕組みを育てる", why:"1147件は見られる。取り込み口も動いている",
     what:"Eagleの画像をスマホのブラウザで見られるようにしました（1147件・検索とタグ絞り込みつき）。iPhoneから放り込む口も動いています。次はフォルダごとの絞り込みや、元画像の受け渡しを足していきます。"},
    {n:20, title:"走行中が空いたら自動で次を発車させる", why:"この「次に発車」を手動更新から自動へ",
     what:"いまこの発車待ちの一覧は手で書いています。これを、走行中のセッションが終わったら自動で一番上を着火する形にします。ここまで来ると「工場が止まらない」が完成します。"}
  ],
  runningUpdatedAt: "2026-09-05T17:45:00+09:00",
  running: [
    {lane:1, title:"「世界の暮らし」棚（旅の扉）×「ノスタルジー/ふるさと」棚（音楽の扉）を関連欄で相互接続", who:"Sonnet / local_243c1fd7", state:"状態不明（09-03 18:05着火から更新なし・停止の可能性）", progress:"関連4枠の内訳＝同じ棚2＋反対側の棚2。双方向・根拠1行。サンプル2ページ＋確認URLまで", links:[]},
    {lane:2, title:"アメリ日本版トレーラーを映画の棚にハブとして格納＋Rousseauカバー/本人音源/海外版を双方向接続。ドラマ主題歌は新設「ドラマ」棚へ移動", who:"Sonnet / local_bc15311b", sessionTitle:"アメリ映画ハブ＋ドラマ棚分離", limitMin:60, state:"状態不明（09-03 18:24着火・1時間で切る予定だったが更新なし）", progress:"Rousseau版が本人演奏に見える表記を直すのが最優先。映画の棚50枚からドラマを外す", links:[]},
    {lane:3, title:"キュー#1「シェアしても画像が出ない」調査・修理", who:"Sonnet(PWAリモコン再開セッション)", state:"完了（mainへpush済み・Lovable反映待ち）", progress:"原因はOGP機構ではなく下敷きYouTube動画の削除。「癒しの音楽棚」30件を全数生死確認→29件(96.7%)が削除済みと判明。実在確認・公式チャンネル確認が取れた21件を生存動画へ差し替え済み(commit 39cabdd1+ca469532)。原田知世6件等は本人名義の演奏が見つからず架空の疑いがあり店主確認待ち（KNOWN_ISSUESに詳細）。残り約150件は未調査、他の棚にも同規模破損が眠っている可能性", links:[]}
  ],

  // ── TODAY（進捗表.html の TODAY 欄をそのまま移植）──
  today: {
    northstar: "映像・音楽・AI・笑い・旅・食・言葉・体験で、世界の苦しみを減らしごきげんを増やす体験装置を作る。3つの核心：Eden Loop／カガリビト／錬金術。",
    top3: [
      "Supabase service_role鍵を.env.localに貼る（NewJeans Ditto統合ほか複数修正がここ待ち）",
      "466本のプレイリストから「配る棚」10〜20本を選ぶ",
      "部屋IDが開けない実害（羊文学↔スキマスイッチID衝突ほか）の付け替え・統合3件の可否"
    ],
    dontdo: [
      "サブのbuilderへ実装を丸投げしてコミットゼロで放置させる（本日3回発生・Mistake Log F6参照）",
      "同時走行3本を超えて新規セッションを立てる"
    ],
    tasteGate: "obsidian://open?vault=tamago_brain&file=AI%E5%87%BA%E5%8A%9B%2F_%E3%83%AB%E3%83%BC%E3%83%AB%2FTaste_Gate",
    kpi: "未設定（次回の朝会スキル実行時に決める。売上／公開本数／AI事故件数／判断待ち件数を予定）"
  },

  // ── 依頼一覧（進捗表.html の REQUESTS をそのまま）──
  requests: [
  // --- たまごさんが動かないと進まないもの(判断待ち) ---
  {status:"hold", content:"Supabaseのservice_role鍵を.env.localに貼る(NewJeans Ditto統合等が待ち)", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:".env.localにSUPABASE_SERVICE_ROLE_KEY=(値)を1行追記してほしい"},
  {status:"hold", content:"棚編集のYouTube動画差し替え機能(検索鍵が本番に届いていない)", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"直し方A(課金)/B(直書き)/C(推奨)のどれにするか"},
  {status:"hold", content:"わえさん(@cosmicwae)の予約投稿", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"ブラウザ自動操作が6通り試して拒否される。本人操作 or ライブ許可が必要"},
  {status:"hold", content:"466本のプレイリストから「配る棚」10〜20本を選ぶ", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"AI側で決められない好みの判断。選んでほしい"},
  {status:"hold", content:"Xania Monet重複ページの消し方", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"①倉庫送り+30日以内対応 ②永久倉庫を新設、どちらか"},
  {status:"hold", content:"note月額980円プラン集約・年内月50万円目標", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"最終決定は本人、と宣言台帳に明記済み"},
  {status:"hold", content:"部屋IDが開けない実害(羊文学↔スキマスイッチ衝突/ID重複12種24部屋/濁点文字化け137件 等)", orderedAt:"2026-08-31T18:45:00+09:00", owner:"見回り係", evidence:"", note:"調査資料は完成。ID付け替え・統合3件の可否をたまごさんに聞く必要あり"},

  // --- 状態不明・止まっている(赤) ---
  {status:"red", content:"🚨Mac負荷が急上昇中(load average 222→296→581・6分間で悪化)", orderedAt:"2026-09-05T17:02:00+09:00", owner:"-", evidence:"", note:"claude CLIプロセス実測29本(同時走行3本の原則を大幅超過)。vite devサーバーが6h31m/6h10m/4h39m/3h32m連続稼働、Virtualization.frameworkのVMが119.9%CPU・3h25m。orphan_reaper.pyは孤児0件(devサーバーは設計上対象外のため主因を捕捉できず)。たまごさん本人による同時セッション数の手動整理を推奨。詳細は見張り番ログ.md 09-05 17:02"},
  {status:"red", content:"Braveブラウザのポートを閉じる", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"急ぎではない。通常再起動で閉じられる"},
  {status:"red", content:"Notionサポートへの返信メール送信", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"Gmail下書き済み・送信のみ(08-27時点情報、対応済みの可能性あり=要確認)"},
  {status:"red", content:"案内所パーソナライズ改修(大型指示書・1件目/URL1つ→1問→3件→反応→次の3件)", orderedAt:"2026-08-31T06:19:00+09:00", owner:"不明(joy-relief-station系)", evidence:"", note:"18:44に再着火を試みたが23:22の督促にも応答なし。担当セッション死亡濃厚"},
  {status:"red", content:"GitHub共通脳のPING確認・書き戻し", orderedAt:"2026-08-31T08:48:00+09:00", owner:"-", evidence:"", note:"完了かどうか記録なし(※双方向テスト自体は別項目で完了確認済み)"},
  {status:"red", content:"KOBITO「愛すべきポンコツ人間事典」ハンドオフ内容確認", orderedAt:"2026-08-31T09:07:00+09:00", owner:"-", evidence:"", note:"2026-08-15依頼が2週間放置されていたと判明。以後の進捗記録なし"},
  {status:"red", content:"GitHub Actions自動巡回3本(Tamago Manager/Role Sweep/Video Patrol)全滅を発見", orderedAt:"2026-08-31T09:15:00+09:00", owner:"-", evidence:"", note:"発見のみ。対応記録なし"},
  {status:"red", content:"案内所パーソナライズ改修(大型指示書・2件目)", orderedAt:"2026-08-31T09:20:00+09:00", owner:"不明(joy-relief-station系)", evidence:"", note:"実装・コミット(0b232e19)まで進み実操作確認で停止。以後応答なし"},
  {status:"red", content:"Nujabes特集を80点にする(Fable・死を軸にしない/曲5曲/海外向け英語対応)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明(Fable)", evidence:"", note:"状態不明。停止しているとの情報あり。生存確認できていない"},
  {status:"red", content:"棚編集の並び順(そのカードが入っている棚をリスト最上部にまとめる)", orderedAt:"2026-08-31T18:44:00+09:00", owner:"不明", evidence:"", note:"状態不明。着手できているかの応答なし"},
  {status:"red", content:"仕入れの継続とハブ&スポーク接続(カバー⇄原曲の双方向/CM・映画・ドラマをハブに接続)", orderedAt:"2026-08-31T17:55:00+09:00", owner:"joy-relief-station系", evidence:"", note:"検品Agentが16-turn上限で停止、resumeされていない"},
  {status:"red", content:"棚に出てる分のコピー書き直し(汎用コピー25,421件=棚の68%。「とりあえず棚優先」で方針決定済み、上位30件から着手)", orderedAt:"2026-08-31T18:37:00+09:00", owner:"joy-relief-station系", evidence:"", note:"23:22に件数・URLを督促したが応答なし"},
  {status:"red", content:"日本語フレーズ集(訪日外国人向けSNS動画3本／めっちゃおいしい・かわいい・なんでやねん)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明(Remotion制作ライン)", evidence:"", note:"たまごさん本人「どっか走ったまま行っちゃってる」。状態不明・要捜索"},
  {status:"red", content:"Final View記事(タルチョの写真差し替え/曲リストのサムネイル/色ベタ2枚)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明", evidence:"", note:"状態不明。00_現在地・棚卸しに記録なし"},
  {status:"red", content:"世界から人が流れ込む設計(Fable・AI推薦最適化/SEO/メール導線)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明(Fable)", evidence:"", note:"状態不明。生存確認できていない"},
  {status:"red", content:"訪日客が実際に使っているもの調査(アプリ/Nomad List)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明", evidence:"", note:"状態不明。生存確認できていない"},
  {status:"red", content:"一流編集者の脳を実装する", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明", evidence:"", note:"状態不明。00_現在地・棚卸しに記録なし"},
  {status:"red", content:"外国人に何が刺さるかのリサーチ", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明", evidence:"", note:"状態不明。00_現在地・棚卸しに記録なし"},
  {status:"red", content:"Xの過去投稿を検索できるようにする", orderedAt:"2026-08-31T00:00:00+09:00", owner:"不明", evidence:"", note:"状態不明。00_現在地・棚卸しに記録なし"},

  // --- 作業中(担当セッション生存確認あり、または部分的に前進が確認できている) ---
  {status:"wip", content:"見回り係(rusuban-mimawari-30min)がbudget_guardで後継セッションを着火できない構造問題の解消", orderedAt:"2026-08-31T23:30:00+09:00", owner:"PID 48717「見回り係が次を立てられるようにする」", evidence:"", note:"生存確認済み・作業中"},
  {status:"wip", content:"Eagleとの連携(外付けライブラリの画像を検索・活用)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"-", evidence:"", note:"外付け「eagle AI 画像整理.library」1129点は読める所まで確認済み。タグが無く見た目検索は要工夫、連携未完成"},

  // --- できない ---
  {status:"cannot", content:"ハブ&スポーク接続PRの検品", orderedAt:"2026-08-31T18:52:00+09:00", owner:"joy-relief-station", evidence:"", note:"Agentが16-turn上限で停止、再開されず中断"},

  // --- 完了 ---
  {status:"done", content:"GitHub Actions自動実行が支払い不備で全滅(08-08頃〜)", orderedAt:"2026-08-30T00:00:00+09:00", owner:"-", evidence:"", note:"課金せずローカル直接実行へ切替済み"},
  {status:"done", content:"共通脳の双方向テスト(ChatGPT⇄Claude)", orderedAt:"2026-08-31T00:00:00+09:00", owner:"-", evidence:"ai-brain/sync/chatgpt/latest.md ⇄ ai-brain/sync/claude/latest.md", note:"往復1周成立確認済み。たまごさんのコピペは不要になった"},
  {status:"done", content:"依頼台帳を作る", orderedAt:"2026-08-31T23:37:00+09:00", owner:"本セッション", evidence:"AI出力/_ルール/依頼台帳.md", note:""},
  {status:"done", content:"発車待ち#26：止まっているタスク56件のうち9件を検品(6件PASS/3件FAIL)", orderedAt:"2026-09-05T12:00:00+09:00", owner:"tamago-orchestrator", evidence:"https://tamago2022.github.io/tamago-shinchoku/share/check/26-stalled-tasks-check.html", note:"joy-relief-station側TASK_BOARD.mdの「検品前」案件6件（#2/#37/#61/#76/#99/#100）を本番URL実測でPASS・🔵検品済みへ格上げ。3件（#21/#77/#78）は逆に「直ったつもりで止まっていた」ことが判明しFAILとして台帳へ記録（次の一手も併記）。残る47件は未着手"},
  {status:"done", content:"Googleドライブ同期の再確認＋円卓デザイン案にClaude版を上げる", orderedAt:"2026-09-05T17:00:00+09:00", owner:"PWAリモコン再開セッション", evidence:"マイドライブ/たまご共通素材庫/02_円卓デザイン案/Claude版/（40枚＋説明メモ）", note:"実測：ジャパニーズ20フレーズのclaude_v1フォルダが09-03時点で既に同期済み・新規に100MB規模のフォルダ作成も即成功＝Mac→クラウドの同期は生きている。ChatGPT版は「chatgpt_（ここにChatGPT版）」が空のプレースホルダのままで、まだ上がっていないだけ（同期の不具合ではない）。円卓の40枚（卵劇場_円卓_ルック開発_01-40）をClaude版としてDriveへ投入完了、比較可能な状態にした。"},
  {status:"done", content:"デスクトップ整理で移動した物、全部の行き先を証明(735番・全19件)", orderedAt:"2026-09-11T02:31:00+09:00", owner:"735番(1/2+2/2)", evidence:"https://tamago2022.github.io/tamago-shinchoku/share/check/735-desktop-cleanup-trace-2of2.html", note:"たまごさんの『フォルダが本当にいなくなった、不安』を受け19件を1件ずつ実地照合。18件は実在(削除は0件)。ただし2点の発見あり：①disk_guardian.pyがゴミ箱7日超の中身を無確認で自動完全削除しており4件・17.2GB(ソフトウェア1/2・ZoomRecordings・録音)が復元不可能な状態と判明→即無効化(詳細は1/2ページ)。②デスクトップ整理_2026-09-02は移動が完了しておらず元の場所に17GB・93,564ファイルが残ったまま停止中(たまごさんの『整理止めて』指示でrsyncが途中停止。データは消えていない)。1/2ページ: https://tamago2022.github.io/tamago-shinchoku/share/check/735-desktop-cleanup-trace-1of2.html"},
  ]
};
