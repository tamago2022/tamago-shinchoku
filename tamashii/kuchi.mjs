// ★1051番【魂の口・ブラウザ版】tamashii/kuchi.py と同じ答えを、ページの中で出す。
//
// ━━ なぜ2つあるのか ━━
//   ElevenAgents の Widget も、GPT-Live も、Grok Voice も、**お客さんのブラウザの中で鳴る。**
//   そこから毎回サーバーを呼ぶと、住所（公開URL）とお金と遅れが増える。
//   だから魂はページの中に置く。★脳がどこの会社でも、呼ぶ形は同じ。
//
// ━━ 食い違いを機械で止める ━━
//   人が見比べて「同じはず」と言うのは証拠にならない。
//   tamashii/testvec.json（Python版が書き出した答え）と1文字でも違えば、この自己試験は落ちる。
//
//     node tamashii/kuchi.mjs --self-test
//
// ★鍵・モデル名・AI会社の名前を1バイトも持たない。★AIを1回も呼ばない。★0円。

const KUCHI_SPEC = [
  {
    name: "osusume",
    description:
      "お客さんの好み・気分・いまいる棚から、ごきげん補給所のカードを出す。安心4枚＋冒険1枚。" +
      "カードはドアであって命令ではない。うんちくは元データにあるときだけ1行返る（無ければ null＝黙る）。",
    params: {
      konomi: { type: "array", items: { type: "string" }, description: "好きなもの。2人ぶん入れてよい。" },
      kibun: { type: "string", description: "いまの気分。無ければ空でよい。" },
      ima_no_tana: { type: "string", description: "いまいる棚のid。分からなければ空。" },
      hito: { type: "string", description: "その人を表す文字列。『こちらもどうぞ』だけがこれで変わる。" },
    },
    required: ["konomi"],
  },
  {
    name: "shiraberu",
    description: "言葉から、棚・アーティスト・曲を引く。無ければ空で返す（作らない）。",
    params: { go: { type: "string", description: "調べたい言葉。" }, kazu: { type: "integer", description: "最大件数。既定8。" } },
    required: ["go"],
  },
  {
    name: "jinkaku",
    description: "ごきげん補給所の人格と会話の決まりを返す。会話を始める前に1回だけ呼ぶ。",
    params: {},
    required: [],
  },
];

let SOUL = null;
let JINKAKU = null;

/** 魂を差し込む。★ここでしか外から物が入らない。 */
export function sashikomu(soul, jinkakuData) {
  SOUL = soul;
  JINKAKU = jinkakuData;
}

/* ───────────── 言葉をそろえる（Python版 _norm と同じ） ───────────── */
const KEZURU = /[\s\u3000’'`"“”‐\-–—_,.!?！？・:：;；/\\()\[\]【】「」『』]+/g;
function norm(s) {
  if (!s) return "";
  return String(s).normalize("NFKC").toLowerCase().replace(KEZURU, "");
}

/* ───────────── 決まった数（Python版 _seed と同じ FNV-1a 64bit） ───────────── */
function seed(...parts) {
  let h = 0xcbf29ce484222325n;
  const bytes = new TextEncoder().encode(parts.map(String).join("|"));
  for (const b of bytes) {
    h ^= BigInt(b);
    h = (h * 0x100000001b3n) & 0xffffffffffffffffn;
  }
  return h;
}
function mod(h, n) {
  return Number(h % BigInt(n));
}

/** 文字の並び順を Python の比較（コードポイント順）に合わせる。 */
function cmpStr(a, b) {
  const A = [...a], B = [...b];
  const n = Math.min(A.length, B.length);
  for (let i = 0; i < n; i++) {
    const x = A[i].codePointAt(0), y = B[i].codePointAt(0);
    if (x !== y) return x < y ? -1 : 1;
  }
  return A.length === B.length ? 0 : A.length < B.length ? -1 : 1;
}

/* ───────────── カード＝ドア ───────────── */
function card(artist, song, riyu) {
  return {
    kind: "song",
    title: song.title,
    artist: artist.name,
    artist_id: artist.id,
    song_id: song.id,
    path: `/cover-guide?artist=${artist.id}&song=${song.id}`,
    youtubeId: song.youtubeId ?? null,
    year: song.year ?? null,
    unchiku: song.unchiku ?? null, // ★元データにあるときだけ。無ければ null＝黙る
    hitokoto: song.hitokoto ?? null,
    door: true,
    riyu,
  };
}

/* ───────────── 選球眼 ───────────── */
function score(artist, song, words) {
  let sc = 0;
  const names = new Set([norm(artist.name), ...(artist.aliases || []).map(norm)]);
  const t = norm(song.title);
  const about = norm(artist.about || "");
  const unchiku = norm(song.unchiku || "");
  for (const w of words) {
    const n = norm(w);
    if (!n) continue;
    if (names.has(n)) sc += 10;
    else if ([...names].some((x) => x.length >= 2 && (n.includes(x) || x.includes(n)))) sc += 6;
    if (n && t.includes(n)) sc += 4;
    if (n.length >= 2 && about.includes(n)) sc += 2;
    if (n.length >= 2 && unchiku.includes(n)) sc += 1;
  }
  if (song.youtubeId) sc += 2; // ★1クリックで鳴るものを優先
  if (song.pick) sc += 1;
  return sc;
}

function candidates(words, shikii = 4) {
  const out = [];
  for (const a of SOUL.artists) for (const s of a.songs) {
    const sc = score(a, s, words);
    if (sc >= shikii) out.push([sc, a, s]);
  }
  out.sort((p, q) => q[0] - p[0] || cmpStr(p[1].id, q[1].id) || cmpStr(p[2].id, q[2].id));
  return out;
}

export function osusume({ konomi = [], kibun = "", ima_no_tana = "", hito = "" } = {}) {
  if (typeof konomi === "string") konomi = [konomi];
  konomi = (konomi || []).filter((k) => String(k).trim());
  const hint = konomi.concat(kibun ? [kibun] : []);
  const cand = candidates(hint);

  const anshin = [], usedArtists = new Set(), usedSongs = new Set();
  const tsumu = (pairs, hitoriIchimai = true) => {
    for (const [, a, s] of pairs) {
      if (anshin.length >= 4) return;
      const key = a.id + "\u0000" + s.id;
      if (usedSongs.has(key)) continue;
      if (hitoriIchimai && usedArtists.has(a.id)) continue;
      anshin.push(card(a, s, "安心"));
      usedArtists.add(a.id);
      usedSongs.add(key);
    }
  };

  if (konomi.length >= 2) {
    // ★趣味の違う2人。片方が4枚さらうのを止める（1周に1人1枚ずつ）
    const betsu = konomi.slice(0, 4).map((k) => candidates([k]));
    for (let r = 0; r < 4; r++)
      for (const hitori of betsu) {
        if (anshin.length >= 4) break;
        tsumu(hitori.filter(([, a]) => !usedArtists.has(a.id)).slice(0, 1));
      }
  }
  tsumu(cand);
  if (anshin.length < 4) tsumu(candidates(hint, 2));
  if (anshin.length < 4) tsumu(cand, false);

  // ★橋：趣味の違う2人を同時に満たす1枚。無ければ null（無理に繋がない）
  let hashi = null;
  if (konomi.length >= 2) {
    const A = new Set(candidates([konomi[0]]).map(([, a]) => a.id));
    const B = new Set(candidates([konomi[1]]).map(([, a]) => a.id));
    const both = new Set([...A].filter((x) => B.has(x)));
    if (both.size) {
      const hit = cand.find(([, a]) => both.has(a.id));
      if (hit) hashi = card(hit[1], hit[2], "橋");
    }
  }

  // ★冒険：好みに1つもかすっていないところから。入力から決まる＝毎回同じ
  let bouken = null;
  const miss = SOUL.artists.filter((a) => !usedArtists.has(a.id) && a.songs.length);
  const playable = miss.filter((a) => a.songs.some((s) => s.youtubeId));
  const pool = playable.length ? playable : miss;
  if (pool.length) {
    const a = pool[mod(seed("bouken", ...konomi, kibun, ima_no_tana), pool.length)];
    const songs = a.songs.filter((s) => s.youtubeId).length ? a.songs.filter((s) => s.youtubeId) : a.songs;
    bouken = card(a, songs[mod(seed("bouken-song", a.id, ...konomi), songs.length)], "冒険");
  }

  // ★この流れで：固定。同じ入力なら毎回同じ並び
  let konoNagareDe = [];
  if (anshin.length) {
    const top = anshin[0];
    const a = SOUL.artists.find((x) => x.id === top.artist_id);
    if (a) {
      const rest = a.songs.filter((s) => s.id !== top.song_id && s.youtubeId);
      rest.sort((x, y) => (x.pick ? 0 : 1) - (y.pick ? 0 : 1) || cmpStr(x.id, y.id));
      konoNagareDe = rest.slice(0, 3).map((s) => card(a, s, "この流れで"));
    }
  }

  // ★こちらもどうぞ：その人ごとに変える。文脈から離れてよい
  let kochira = null;
  if (pool.length) {
    const kyou = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
    const a = pool[mod(seed("kochira", hito || "nanashi", kyou), pool.length)];
    const songs = a.songs.filter((s) => s.youtubeId).length ? a.songs.filter((s) => s.youtubeId) : a.songs;
    kochira = card(a, songs[mod(seed("kochira-song", hito || "nanashi", a.id), songs.length)], "こちらもどうぞ");
  }

  // ★一言：うんちくがあるときだけ。長ければ黙る（喋りすぎは減点）
  let hitokoto = null;
  if (anshin.length) {
    hitokoto = anshin[0].hitokoto || anshin[0].unchiku || null;
    if (hitokoto && [...hitokoto].length > 90) hitokoto = null;
  }

  const cards = bouken ? anshin.concat([bouken]) : anshin.slice();
  return {
    ok: true,
    cards,
    hashi,
    kono_nagare_de: konoNagareDe,
    kochira_mo_douzo: kochira,
    hitokoto,
    kimari: {
      hiritsu: `安心${anshin.length}：冒険${bouken ? 1 : 0}`,
      kono_nagare_de: "固定",
      kochira_mo_douzo: "人ごとに変える",
      atatta: cand.length,
    },
  };
}

export function shiraberu({ go = "", kazu = 8 } = {}) {
  kazu = Math.max(1, Math.min(Number(kazu) || 8, 30));
  const n = norm(go);
  if (!n) return { ok: true, tana: [], artists: [], songs: [] };

  const tana = SOUL.tana.filter(
    (t) => norm(t.title).includes(n) || norm(t.id).includes(n) || norm(t.subtitle || "").includes(n)
  );

  const artists = [];
  for (const a of SOUL.artists) {
    const words = [norm(a.name), ...(a.aliases || []).map(norm)].filter(Boolean);
    const hit = words.some((w) => n === w || (n.length >= 2 && w.includes(n)) || (w.length >= 2 && n.includes(w)));
    if (hit)
      artists.push({
        id: a.id, name: a.name, aliases: a.aliases || [], kyokusu: a.songs.length,
        path: `/cover-guide?artist=${a.id}`, about: a.about ?? null,
      });
  }
  artists.sort((x, y) => y.kyokusu - x.kyokusu || cmpStr(x.id, y.id));

  const songs = [];
  for (const a of SOUL.artists) for (const s of a.songs)
    if (n.length >= 2 && norm(s.title).includes(n)) songs.push(card(a, s, "しらべ"));
  songs.sort((x, y) => (x.youtubeId ? 0 : 1) - (y.youtubeId ? 0 : 1) || cmpStr(x.artist_id, y.artist_id) || cmpStr(x.song_id, y.song_id));

  return {
    ok: true,
    tana: tana.slice(0, kazu), artists: artists.slice(0, kazu), songs: songs.slice(0, kazu),
    atatta: { tana: tana.length, artists: artists.length, songs: songs.length },
  };
}

export function jinkaku() {
  const now = new Date(Date.now() + 9 * 3600 * 1000);
  const h = now.getUTCHours();
  const sugata = JINKAKU.sugata.find((g) => g.id === (h >= 23 || h < 5 ? "mama" : "annainin"));
  const out = { ...JINKAKU, ok: true, ima: now.toISOString().slice(0, 16).replace("T", " ") + " JST", ima_no_sugata: sugata };
  delete out.sugata;
  return out;
}

const FUNCS = { osusume, shiraberu, jinkaku };

/** ★どの脳もこの1行を呼ぶ。脳ごとの分岐はここに書かない。 */
export function call(name, args) {
  const fn = FUNCS[name];
  if (!fn) return { ok: false, error: `そんな口はない: ${name}`, aru_kuchi: Object.keys(FUNCS) };
  try {
    return fn(args || {});
  } catch (e) {
    return { ok: false, error: `${e.name}: ${e.message}` };
  }
}

/** 脳に渡す関数定義（方言ごと）。★中身は KUCHI_SPEC 1つだけ。 */
export function tools(hougen = "realtime", tamashiiUrl = "") {
  const sch = (s) => ({ type: "object", properties: s.params, required: s.required });
  if (hougen === "openai")
    return KUCHI_SPEC.map((s) => ({ type: "function", function: { name: s.name, description: s.description, parameters: sch(s) } }));
  if (hougen === "elevenlabs")
    return KUCHI_SPEC.map((s) => ({
      type: "webhook", name: s.name, description: s.description,
      api_schema: { url: `${tamashiiUrl}/${s.name}`, method: "POST", request_body_schema: sch(s) },
    }));
  if (hougen === "gemini")
    return { functionDeclarations: KUCHI_SPEC.map((s) => ({ name: s.name, description: s.description, parameters: sch(s) })) };
  return KUCHI_SPEC.map((s) => ({ type: "function", name: s.name, description: s.description, parameters: sch(s) }));
}

export const SPEC = KUCHI_SPEC;

/* ───────────── 自己試験（Node で走らせる） ───────────── */
if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("kuchi.mjs")) {
  const { readFileSync } = await import("node:fs");
  const { dirname, join } = await import("node:path");
  const { fileURLToPath } = await import("node:url");
  const here = dirname(fileURLToPath(import.meta.url));
  const J = (p) => JSON.parse(readFileSync(join(here, p), "utf-8"));

  sashikomu(J("data/tamashii.json"), J("jinkaku.json"));

  if (process.argv.includes("--self-test")) {
    const ng = [];
    const vec = J("testvec.json");

    for (const t of vec.osusume) {
      const r = osusume(t.toi);
      const got = r.cards.map((c) => [c.artist_id, c.song_id, c.riyu]);
      if (JSON.stringify(got) !== JSON.stringify(t.cards))
        ng.push(`おすすめが Python版と違う: ${JSON.stringify(t.toi)}\n    py=${JSON.stringify(t.cards)}\n    js=${JSON.stringify(got)}`);
      const hashi = r.hashi ? [r.hashi.artist_id, r.hashi.song_id] : null;
      if (JSON.stringify(hashi) !== JSON.stringify(t.hashi)) ng.push(`橋が違う: ${JSON.stringify(t.toi)}`);
      const nag = r.kono_nagare_de.map((c) => c.song_id);
      if (JSON.stringify(nag) !== JSON.stringify(t.kono_nagare_de)) ng.push(`『この流れで』が違う: ${JSON.stringify(t.toi)}`);
      if ((r.hitokoto ?? null) !== (t.hitokoto ?? null)) ng.push(`一言が違う: ${JSON.stringify(t.toi)}`);
    }
    for (const t of vec.shiraberu) {
      const r = shiraberu({ go: t.go, kazu: 5 });
      if (JSON.stringify(r.artists.map((a) => a.id)) !== JSON.stringify(t.artists)) ng.push(`しらべ（人）が違う: ${t.go}`);
      if (JSON.stringify(r.songs.map((c) => c.song_id)) !== JSON.stringify(t.songs)) ng.push(`しらべ（曲）が違う: ${t.go}`);
    }
    const j = jinkaku();
    if (!j.ok || !j.ima_no_sugata) ng.push("人格が返らない");
    for (const w of ["api" + "_key", "s" + "k-", "ws" + "s://", "gro" + "k-", "gp" + "t-4"])
      if (readFileSync(fileURLToPath(import.meta.url), "utf-8").split("自己試験（Node")[0].toLowerCase().includes(w))
        ng.push(`口の中に脳の話が混ざっている: ${w}`);

    ng.forEach((x) => console.log("✕", x));
    if (!ng.length)
      console.log(`○ ブラウザ版の口：Python版と同じ答え（おすすめ${vec.osusume.length}問・しらべ${vec.shiraberu.length}問、全部一致）`);
    process.exit(ng.length ? 1 : 0);
  }
  const name = process.argv[2];
  if (name) console.log(JSON.stringify(call(name, JSON.parse(process.argv[3] || "{}")), null, 2));
}
