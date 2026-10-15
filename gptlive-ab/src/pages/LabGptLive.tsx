// src/pages/LabGptLive.tsx
//
// 非公開ページ /lab/gptlive
// どこからもリンクを張らない。メニュー・トップ・sitemap・検索に出さない。
// URLを知っている人だけが入れる。
//
// 中身は Grok版と条件を揃える：人格も search_songs も同じ。違うのは声のエンジンだけ。

import { useEffect, useRef, useState } from "react";
import { GptLiveConcierge, type GptLiveStatus } from "@/lib/gptLiveConcierge";

// ★ Grok版と「同じ検索」を使う。ここを別実装にしたら聴き比べにならない。
//   voiceConcierge.ts 側の検索関数に export を1個付けて、それをそのまま import する。
//   （関数名が違う場合はここだけ直す）
import { searchSongs } from "@/lib/voiceConcierge";

// 聴き比べ用の固定台本。両方に同じ順で同じ文言を流す。
const SCRIPT = [
  "今日何がおすすめ？",
  "雨だから、雨の日に合う曲ある？",
  "もう少し昔の曲ない？",
  "アップテンポがいい",
  "アジアのアーティストで何かない？",
];

export default function LabGptLive() {
  const [status, setStatus] = useState<GptLiveStatus>("idle");
  const [log, setLog] = useState<string[]>([]);
  const [assistant, setAssistant] = useState("");
  const [toolCalls, setToolCalls] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const ref = useRef<GptLiveConcierge | null>(null);

  // 検索避け（noindex）。ページ単体で効かせる。
  useEffect(() => {
    const m = document.createElement("meta");
    m.name = "robots";
    m.content = "noindex, nofollow, noarchive";
    document.head.appendChild(m);
    const prevTitle = document.title;
    document.title = "lab / gptlive";
    return () => {
      m.remove();
      document.title = prevTitle;
    };
  }, []);

  // 経過時間＝お金。1分あたり約7.5円。
  useEffect(() => {
    if (startedAt === null) return;
    const t = setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 500);
    return () => clearInterval(t);
  }, [startedAt]);

  const push = (s: string) => setLog((l) => [...l.slice(-60), s]);

  const start = async () => {
    const c = new GptLiveConcierge({
      onStatus: setStatus,
      onAssistantText: (t, done) => {
        setAssistant(t);
        if (done) push(`アイリス: ${t}`);
      },
      onUserText: (t) => push(`あなた: ${t}`),
      onError: (m) => push(`⚠️ ${m}`),
      searchSongs: async (args) => {
        setToolCalls((n) => n + 1);
        push(`🔎 search_songs ${JSON.stringify(args)}`);
        return await searchSongs(args as any);
      },
    });
    ref.current = c;
    setStartedAt(Date.now());
    await c.connect();
  };

  const stop = () => {
    ref.current?.close();
    ref.current = null;
    setStartedAt(null);
    setStatus("closed");
  };

  useEffect(() => () => ref.current?.close(), []);

  const yen = (elapsed / 60) * 7.5;

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <p style={{ fontSize: 12, opacity: 0.6, letterSpacing: ".08em" }}>
        LAB / 非公開 / GPT Live（OpenAI Realtime）
      </p>
      <h1 style={{ fontSize: 22, margin: "8px 0 16px" }}>アイリス — 声のエンジン比較</h1>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
        <button onClick={start} disabled={status === "connecting" || status === "listening" || status === "speaking"}>
          つなぐ
        </button>
        <button onClick={stop} disabled={status === "idle" || status === "closed"}>
          切る
        </button>
        <span style={{ fontSize: 13 }}>状態: {status}</span>
      </div>

      <div style={{ fontSize: 13, marginBottom: 16 }}>
        経過 {elapsed.toFixed(0)}秒 ／ 概算 <b>{yen.toFixed(1)}円</b>（音声1分＝約7.5円）
        ／ search_songs 呼び出し <b>{toolCalls}</b>回
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, opacity: 0.6, marginBottom: 6 }}>聴き比べ台本（同じ文言を両方に流す）</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {SCRIPT.map((s) => (
            <button
              key={s}
              onClick={() => ref.current?.say(s)}
              disabled={status !== "listening" && status !== "speaking"}
              style={{ fontSize: 12 }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div style={{ minHeight: 48, padding: 12, background: "#faf5ec", borderRadius: 8, marginBottom: 16 }}>
        {assistant || "（ここにアイリスの話した内容が出ます）"}
      </div>

      <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", opacity: 0.8 }}>{log.join("\n")}</pre>
    </div>
  );
}
