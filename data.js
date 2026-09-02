// ここが正本データ。元は AI出力/_ルール/進捗表.html の REQUESTS（2026-09-02 に移植。中身は変えていない）。
// 更新のしかた：このファイルを書き換えて git push するだけ（GitHub Pages が数分で反映）。
// リンクは links:[{label:"…", url:"obsidian://open?vault=tamago_brain&file=AI出力/…"}] の形で足す。

window.SHINCHOKU = {
  generatedAt: "2026-09-01T00:20:00+09:00",

  // ── 今動いているもの（手更新。リアルタイム連携ではない）──
  runningUpdatedAt: "2026-09-02T09:30:00+09:00",
  running: [
    {lane:1, title:"iMacの音楽ライブラリ841フォルダをGoogleドライブへ転送（完走まで）", who:"転送セッション", state:"走行中", progress:"進捗ログ gdrive_music_progress.log の行数＝完了数", links:[
      {label:"作業キュー", url:"obsidian://open?vault=tamago_brain&file=AI%E5%87%BA%E5%8A%9B%2F_%E3%83%AB%E3%83%BC%E3%83%AB%2F%E4%BD%9C%E6%A5%AD%E3%82%AD%E3%83%A5%E3%83%BC"}
    ]},
    {lane:2, title:"溜まっている案件から「今すぐ着火できる10本」を出す（優先順位はたまごさん）", who:"Dispatch子セッション", state:"走行中", progress:"受付台帳・カンバン・引き継ぎを洗い出し中", links:[
      {label:"受付台帳（自動記録）", url:"obsidian://open?vault=tamago_brain&file=AI%E5%87%BA%E5%8A%9B%2F_%E3%83%AB%E3%83%BC%E3%83%AB%2F%E5%8F%97%E4%BB%98%E5%8F%B0%E5%B8%B3_%E8%87%AA%E5%8B%95%E8%A8%98%E9%8C%B2"},
      {label:"引き継ぎ", url:"obsidian://open?vault=tamago_brain&file=AI%E5%87%BA%E5%8A%9B%2F_%E3%83%AB%E3%83%BC%E3%83%AB%2F%E5%BC%95%E3%81%8D%E7%B6%99%E3%81%8E"}
    ]},
    {lane:3, title:"この進捗表をスマホのアイコンから開けるアプリにする", who:"スマホ化セッション", state:"完了（この画面）", progress:"公開URLを渡した時点で完了", links:[
      {label:"元の進捗表（Vault）", url:"obsidian://open?vault=tamago_brain&file=AI%E5%87%BA%E5%8A%9B%2F_%E3%83%AB%E3%83%BC%E3%83%AB%2F%E9%80%B2%E6%8D%97%E8%A1%A8.html"}
    ]}
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
  ]
};
