// joy-relief-station の src/lib/mediaSession.ts としてそのまま置く。
//
// これは「画面を消してもロック画面に曲名・絵・再生ボタンが出る」ための配線。
// 961番（2026-09-19）。
//
// 前提（ここを外すと必ず止まる）:
//   - 音は <audio> 要素で鳴らす。AudioContext（Web Audio API）で鳴らすと
//     iPhoneは画面を消した瞬間に止める。鳴っている <audio> だけが
//     バックグラウンドでも音の権利を持ち続ける。
//   - その <audio> は __root.tsx の <Outlet /> の外（AudioEngine）に置き、
//     ページ遷移で作り直さない。作り直した瞬間に音の権利も消える。
//
// 出典:
//   Media Session API — https://developer.mozilla.org/en-US/docs/Web/API/Media_Session_API

export type NowPlaying = {
  title: string;
  artist: string;
  album?: string;
  /** 正方形のPNG/JPGのURL。無ければロック画面に絵は出ない */
  artwork?: string;
};

type Handlers = {
  next?: () => void;
  prev?: () => void;
};

/**
 * <audio> と「いま流している曲」をロック画面へつなぐ。
 * 曲が変わるたびに呼んでよい（同じ audio に何度呼んでも二重登録にならないよう
 * リスナーは1回だけ張る）。
 */
export function attachMediaSession(
  audio: HTMLAudioElement,
  track: NowPlaying,
  handlers: Handlers = {},
): void {
  if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;
  const ms = navigator.mediaSession;

  try {
    ms.metadata = new MediaMetadata({
      title: track.title,
      artist: track.artist,
      album: track.album ?? "ごきげん補給所",
      artwork: track.artwork
        ? [96, 128, 192, 256, 384, 512].map((s) => ({
            src: track.artwork as string,
            sizes: `${s}x${s}`,
            type: "image/png",
          }))
        : [],
    });
  } catch {
    /* 端末が MediaMetadata を持たないときは表示だけ諦める */
  }

  const set = (action: MediaSessionAction, fn: ((details: never) => void) | null) => {
    try {
      ms.setActionHandler(action, fn as never);
    } catch {
      /* その端末が対応していない操作は黙って飛ばす（例外で全部落とさない） */
    }
  };

  set("play", () => {
    void audio.play();
  });
  set("pause", () => audio.pause());
  set("stop", () => {
    audio.pause();
    audio.currentTime = 0;
  });
  set("seekbackward", () => {
    audio.currentTime = Math.max(0, audio.currentTime - 10);
  });
  set("seekforward", () => {
    audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10);
  });
  set("seekto", ((d: { seekTime?: number }) => {
    if (typeof d?.seekTime === "number") audio.currentTime = d.seekTime;
  }) as never);
  set("previoustrack", (handlers.prev ?? null) as never);
  set("nexttrack", (handlers.next ?? null) as never);

  if (!(audio as HTMLAudioElement & { __msBound?: boolean }).__msBound) {
    (audio as HTMLAudioElement & { __msBound?: boolean }).__msBound = true;
    const sync = () => syncMediaSession(audio);
    audio.addEventListener("play", sync);
    audio.addEventListener("pause", sync);
    audio.addEventListener("timeupdate", sync);
    audio.addEventListener("loadedmetadata", sync);
  }
  syncMediaSession(audio);
}

/** 再生位置とシークバーをロック画面へ反映する。 */
export function syncMediaSession(audio: HTMLAudioElement): void {
  if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;
  const ms = navigator.mediaSession;
  ms.playbackState = audio.paused ? "paused" : "playing";
  if (
    Number.isFinite(audio.duration) &&
    audio.duration > 0 &&
    typeof ms.setPositionState === "function"
  ) {
    try {
      ms.setPositionState({
        duration: audio.duration,
        playbackRate: audio.playbackRate,
        position: Math.min(audio.currentTime, audio.duration),
      });
    } catch {
      /* duration と position が一瞬揃わないときがある。無視してよい */
    }
  }
}

/** 曲を止めたあと、ロック画面から表示を消す。 */
export function clearMediaSession(): void {
  if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;
  try {
    navigator.mediaSession.metadata = null;
    navigator.mediaSession.playbackState = "none";
  } catch {
    /* noop */
  }
}
