// 回帰テスト用の見本。たまごさんが実際に見た事故をそのまま再現したもの。
// 「ジャズシンガーakikoの棚に、矢野顕子の曲が入っている」状態。
// 関門がこれを落とせなくなったら、同じ事故がまた出る。
export const artists = [
  { id: "akiko", name: "akiko", aliases: ["あきこ", "アキコ"], eras: ["00s"], about: "埼玉県出身のジャズシンガー。", songs: [
    { id: "i-miss-you", title: "I Miss You", note: "静かな夜に沁み入るスタンダード。", year: 2006, youtubeId: "iDcyqN3HWV0" },
    { id: "rydeen-akiko-yano-trio", title: "Rydeen - AKIKO YANO TRIO featuring Will Lee & Chris Parker Live at Blue Note Tokyo 2025", note: "代表曲のひとつ。", youtubeId: "W0_ndu4L3Mw" },
    { id: "ramen-tabetai-akiko-yano-trio", title: "ラーメンたべたい - AKIKO YANO TRIO featuring Will Lee & Chris Parker Live at Blue Note Tokyo 2025", note: "代表曲のひとつ。", youtubeId: "BK5Kb0zvWHc" },
    { id: "coffee-or-tea-prod-silverstrike", title: "Coffee or tea (Prod. SILVERSTRIKE)", note: "", youtubeId: "FKIVSFDmmAs" },
    { id: "lupin-the-third-feat-akiko", title: "ルパン三世のテーマ (feat. akiko)", note: "大野雄二作曲のテレビアニメ主題歌を、ジャズ・ボッサでカバー。", year: 2001, youtubeId: "SyoEIjB6Jy0", originalRef: { artistId: "yuji-ohno", songId: "lupin-the-third-theme" } }
  ]},
  { id: "akiko-yano", name: "矢野顕子", aliases: ["Akiko Yano"], eras: ["70s", "80s"], about: "青森育ちのシンガーソングライター。", songs: [
    { id: "gohan-ga-dekita-yo", title: "ごはんができたよ", note: "1980年発表。", year: 1980, youtubeId: "PENDING" }
  ]}
];
