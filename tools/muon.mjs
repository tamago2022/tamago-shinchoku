// 無音の道具（Node 版）。中身は tools/muon.py と同じ。確認道具は音を鳴らさない。確認はデータで行う。
// 2026-10-10：status/_v1oc/v2.mjs が WebKit(iPhone) で YouTube を音ありで鳴らした事故から。
//
//   import { MUON_ARGS, MUON_FIREFOX, MUON_INIT, muonContext, muonLaunch } from "<repo>/tools/muon.mjs";
//   const b = await muonLaunch(chromium, { headless: true });   // どのエンジンでも無音で起動
//   const ctx = await muonContext(await b.newContext({...}));     // 中のページも音量0に固定
//
// WebKit は起動引数で消音できないので、ページ内で実際の音量(volume)だけを0に固定する。
// muted はページの意図のまま残す（「音ありで再生できたか」の確認をデータで続けるため）。
export const MUON_ARGS = ["--mute-audio", "--autoplay-policy=user-gesture-required"];
export const MUON_FIREFOX = { "media.volume_scale": "0.0", "media.autoplay.default": 5 };
export const MUON_INIT = `(() => {
  try {
    if (window.__muon) return; window.__muon = 1;
    const P = HTMLMediaElement.prototype;
    const vd = Object.getOwnPropertyDescriptor(P, "volume");
    const zero = (el) => { try { vd.set.call(el, 0); } catch (e) {} };
    Object.defineProperty(P, "volume", { configurable: true,
      get() { return this.__muonV === undefined ? 1 : this.__muonV; },
      set(v) { this.__muonV = v; zero(this); } });
    const op = P.play;
    P.play = function () { zero(this); return op.apply(this, arguments); };
    for (const ev of ["play", "playing", "loadedmetadata", "volumechange"]) {
      document.addEventListener(ev, (e) => { if (e.target instanceof HTMLMediaElement) zero(e.target); }, true);
    }
    setInterval(() => { for (const el of document.querySelectorAll("video,audio")) zero(el); }, 200);
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC && window.AudioNode) {
      const oc = AudioNode.prototype.connect;
      AudioNode.prototype.connect = function (d, ...a) {
        if (window.AudioDestinationNode && d instanceof AudioDestinationNode) {
          const c = d.context;
          if (!c.__muonG) { c.__muonG = c.createGain(); c.__muonG.gain.value = 0; oc.call(c.__muonG, d); }
          return oc.call(this, c.__muonG, ...a);
        }
        return oc.call(this, d, ...a);
      };
    }
    if (window.speechSynthesis) { window.speechSynthesis.speak = () => {}; }
  } catch (e) {}
})();`;

export async function muonContext(ctx) {
  await ctx.addInitScript(MUON_INIT);
  return ctx;
}

// browserType = chromium / webkit / firefox（Playwright）。起動設定に無音を必ず混ぜる。
export async function muonLaunch(browserType, opts = {}) {
  const name = typeof browserType.name === "function" ? browserType.name() : "";
  const o = { ...opts };
  if (name === "chromium") o.args = [...(o.args || []), ...MUON_ARGS];
  if (name === "firefox") o.firefoxUserPrefs = { ...(o.firefoxUserPrefs || {}), ...MUON_FIREFOX };
  const b = await browserType.launch(o);
  const nc = b.newContext.bind(b);
  b.newContext = async (...a) => muonContext(await nc(...a));
  const np = b.newPage.bind(b);
  b.newPage = async (...a) => { const p = await np(...a); await p.addInitScript(MUON_INIT); return p; };
  return b;
}
