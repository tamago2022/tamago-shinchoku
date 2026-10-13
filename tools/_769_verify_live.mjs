#!/usr/bin/env node
// 769番：本番(GitHub Pages)に実際に反映されたかを、公開URLへの実fetchで確認する。
const urls = [
  "https://tamago2022.github.io/tamago-shinchoku/share/check/769-peralino-usocchi-paste-sheet.html",
  "https://tamago2022.github.io/tamago-shinchoku/share/check/769-oniyome-chan-paste-sheet.html",
  "https://tamago2022.github.io/tamago-shinchoku/share/check/769-rashikoru-paste-sheet.html",
];
async function main() {
  for (const u of urls) {
    const res = await fetch(u, { cache: "no-store" });
    const text = await res.text();
    const hasHowto = text.includes("使い方（探さなくていいように");
    const oldPeraOnly = /ペラリーノ(?!・ウソッチ|ウソッチ)/.test(text.replace(/ペラリーノウソッチ\/LINEス/g, ""));
    console.log(u);
    console.log("  status:", res.status, "howto追加済み:", hasHowto, "「ペラリーノ」単独残り:", oldPeraOnly);
  }
}
main().catch((e) => { console.error("ERR:", e.message); process.exit(1); });
