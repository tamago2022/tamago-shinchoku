// 在庫一覧（zaiko）の素：joy-relief-station の本番データを「実際に動かした後の姿」で吐き出す。
// tools/zaiko_build.py が origin/main を一時フォルダに展開し、ここを esbuild で束ねて node で1回走らせる。
// ★正規表現でTSを読まない：倉庫下ろし・再生できない曲の隠し・アーティスト統合が全部済んだ artists を読む。
import { artists } from "./src/lib/coverGuide";
import { worlds, getCanonicalCardTo } from "./src/lib/worlds";
import { worldOrder, worldMeta } from "./src/lib/worldMeta";
import { magazineFeatureInfosFor, MAGAZINE_INDEX } from "./src/lib/magazineFeatures";
import { KANSEI_HIDDEN_REASONS } from "./src/lib/kanseiHidden.generated";
import { KANSEI_GATE } from "./src/lib/kansei";

const shelvesBySong: Record<string, { w: string; wl: string; s: string; st: string }[]> = {};
for (const wid of worldOrder) {
  const w = (worlds as any)[wid];
  if (!w) continue;
  for (const s of w.shelves ?? []) {
    for (const c of s.cards ?? []) {
      const to = getCanonicalCardTo(c) ?? "";
      const m = to.match(/^\/cover-guide\?artist=([^&]+)&song=([^&#]+)/);
      if (!m) continue;
      const key = `${decodeURIComponent(m[1])}/${decodeURIComponent(m[2])}`;
      const list = (shelvesBySong[key] ??= []);
      if (!list.some((x) => x.s === s.id)) {
        list.push({ w: wid, wl: (worldMeta as any)[wid]?.label ?? w.label ?? wid, s: s.id, st: s.title ?? s.id });
      }
    }
  }
}

const out = {
  artists: artists.map((a: any) => ({
    id: a.id,
    name: a.name,
    aliases: a.aliases ?? [],
    songs: (a.songs ?? []).map((s: any) => {
      const key = `${a.id}/${s.id}`;
      return {
        id: s.id,
        title: s.title,
        yt: s.youtubeId ?? (s.altYoutubeIds ?? [])[0] ?? "",
        hidden: KANSEI_GATE && KANSEI_HIDDEN_REASONS[key] ? KANSEI_HIDDEN_REASONS[key] : "",
        shelves: shelvesBySong[key] ?? [],
        features: magazineFeatureInfosFor(a.id, s.id).map((f) => ({ path: f.path, title: f.title })),
      };
    }),
  })),
  magazines: MAGAZINE_INDEX.map((m) => ({ path: m.path, title: m.title, kicker: m.kicker })),
};
process.stdout.write(JSON.stringify(out));
