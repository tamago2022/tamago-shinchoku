#!/usr/bin/env node
const u = "https://tamago2022.github.io/tamago-shinchoku/share/check/769-name-howto-fix.html";
fetch(u, { cache: "no-store" }).then(async (res) => {
  const text = await res.text();
  console.log("status:", res.status, "len:", text.length, "has_img:", text.includes("<img"));
}).catch((e) => console.log("ERR:", e.message));
