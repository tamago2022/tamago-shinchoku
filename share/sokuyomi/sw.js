/* 948番（2026-09-19）たまごさん「以前のやつが残ってる。追いかけで読むんじゃなくて。」

   前の作りは「キャッシュにあればそれを返す（cache-first）」だった。
   index.html までこの扱いだったので、直したものを公開しても、この画面だけは
   一度入ったキャッシュを永久に返し続けていた＝古い画面が出たまま戻らない。

   直し方：中身（HTMLとJSON）は必ず先にネットへ取りに行く（network-first）。
   取れたらそれを出しつつ控えを更新し、取れなかったときだけ控えを出す（圏外でも開ける）。
   アイコン・画像・CSS・JS といった見た目の部品はこれまでどおり控えを先に使う
   ＝軽さは壊さない。
*/
const CACHE = "sokuyomi-v2";
const ASSETS = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

// 中身＝画面そのものと、数字の入ったファイル。古いものを出してはいけないもの。
function isContent(req) {
  if (req.mode === "navigate") return true;
  const accept = req.headers.get("accept") || "";
  if (accept.indexOf("text/html") !== -1) return true;
  const path = new URL(req.url).pathname;
  return /\.(html|json|webmanifest|txt)$/i.test(path);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  if (isContent(req)) {
    // 新しいものを取ってから出す。取れないときだけ控え。
    e.respondWith(
      fetch(req, { cache: "no-store" })
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || Promise.reject(new Error("offline"))))
    );
    return;
  }

  // 見た目の部品は控えを先に使う（軽さのため）。無ければ取りに行って控える。
  e.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      });
    })
  );
});
