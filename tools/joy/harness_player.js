// 961番の確認ページの中身を、ブラウザを開かずに動かして筋を確かめる簡易ハーネス。
// 目的：「ページを移っても cutCount が増えないか」「曲送りで誤カウントしないか」。
const fs = require("fs");

function mkEl(tag) {
  const listeners = {};
  const el = {
    tagName: tag, children: [], dataset: {}, style: {}, attributes: {},
    hidden: false, textContent: "", _html: "",
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; this.children = []; },
    appendChild(c) { this.children.push(c); return c; },
    setAttribute(k, v) { this.attributes[k] = v; },
    getAttribute(k) { return this.attributes[k]; },
    addEventListener(t, fn) { (listeners[t] = listeners[t] || []).push(fn); },
    dispatch(t, ev) { (listeners[t] || []).forEach((f) => f(ev || {})); },
    querySelector() { return mkEl("x"); },
    getContext() {
      return { fillRect() {}, beginPath() {}, arc() {}, fill() {}, fillText() {}, set fillStyle(v) {}, set font(v) {} };
    },
    toDataURL() { return "data:image/png;base64,AAA"; },
    click() { this.dispatch("click"); },
  };
  return el;
}

const byId = {};
["player","pArt","pTitle","pArtist","pPlay","pPrev","pNext","nav","stage",
 "mNav","mCut","mSec","verdict","raw"].forEach((id) => (byId[id] = mkEl("div")));

global.document = {
  getElementById: (id) => byId[id],
  createElement: (t) => mkEl(t),
};
global.URL = { createObjectURL: () => "blob:fake" };
global.Blob = class { constructor() {} };
global.MediaMetadata = class { constructor(o) { Object.assign(this, o); } };

const msCalls = {};
const fakeNavigator = {
  mediaSession: {
    playbackState: "none",
    setActionHandler(a, fn) { msCalls[a] = fn; },
    setPositionState(s) { this._pos = s; },
  },
};
// Node 22 の navigator は読み取り専用なので上書きし直す
Object.defineProperty(globalThis, "navigator", {
  value: fakeNavigator, writable: true, configurable: true,
});
global.location = { hash: "" };
const historyStack = [];
global.history = { pushState(s, t, u) { historyStack.push(u); } };
global.window = { addEventListener() {} };

let audioRef = null;
global.Audio = class {
  constructor() {
    audioRef = this;
    this._l = {};
    this.paused = true; this.currentTime = 0; this.duration = 12; this.playbackRate = 1;
    this._src = "";
  }
  get src() { return this._src; }
  set src(v) {
    // 本物の <audio> と同じ：src を入れ替えると load アルゴリズムが走り
    // 再生中なら pause と emptied が飛ぶ
    const wasPlaying = !this.paused;
    this._src = v; this.currentTime = 0;
    if (wasPlaying) { this.paused = true; this.dispatch("pause"); }
    this.dispatch("emptied");
  }
  setAttribute() {}
  addEventListener(t, fn) { (this._l[t] = this._l[t] || []).push(fn); }
  dispatch(t, e) { (this._l[t] || []).forEach((f) => f(e || {})); }
  play() { this.paused = false; this.dispatch("play"); return Promise.resolve(); }
  pause() { if (!this.paused) { this.paused = true; this.dispatch("pause"); } }
};

const html = fs.readFileSync(process.argv[2], "utf8");
const js = html.match(/<script>([\s\S]*?)<\/script>/)[1];
eval(js);

function count(id) { return parseInt(byId[id].textContent, 10); }

// 1) 再生する
byId.pPlay.dispatch("click");
console.log("再生後            : paused=" + audioRef.paused);

// 2) ページを4回移る
byId.nav.children.forEach((b) => b.dispatch("click"));
byId.nav.children.forEach((b) => b.dispatch("click"));

console.log("ページを移った回数 : " + count("mNav"));
console.log("音が途切れた回数   : " + count("mCut"));
console.log("移動後 paused      : " + audioRef.paused);

// 3) 次の曲へ（emptied が出るが、途切れとして数えてはいけない）
byId.pNext.dispatch("click");
console.log("曲送り後の途切れ   : " + count("mCut"));

// 4) ロック画面のボタンが登録されているか
const want = ["play","pause","stop","seekbackward","seekforward","seekto","previoustrack","nexttrack"];
const missing = want.filter((a) => typeof msCalls[a] !== "function");
console.log("ロック画面の操作   : " + (missing.length ? "不足 " + missing.join(",") : want.length + "種すべて登録"));

// 5) ロック画面の表示（曲名・アーティスト・絵）
const md = fakeNavigator.mediaSession.metadata;
console.log("ロック画面の表示   : " + (md ? md.title + " / " + md.artist + " / 絵" + md.artwork.length + "枚" : "なし"));

// 6) 一時停止は「途切れ」に数えない
const before = count("mCut");
byId.pPlay.dispatch("click");
console.log("自分で止めた時     : 途切れ " + before + " → " + count("mCut"));

const ok = count("mNav") === 8 && count("mCut") === 0 && !missing.length && md;
console.log(ok ? "\n判定: OK（8回移って途切れ0・ロック画面の配線あり）" : "\n判定: NG");
process.exit(ok ? 0 : 1);
