// src/lib/gptLiveConcierge.ts
//
// GPT Live（OpenAI Realtime GA / WebRTC）版のアイリス。
// Grok版 voiceConcierge.ts と「違うのは声のエンジンだけ」にするための薄い層。
//
// 鍵はここに一切出てこない。Edge Function `gptlive-session` から ephemeral token をもらう。
//
// つなぎ方（GA）:
//   1. Edge Function → ek_... をもらう（有効1分）
//   2. RTCPeerConnection を作り、マイクの track を addTrack
//   3. createDataChannel("oai-events")
//   4. offer.sdp を POST https://api.openai.com/v1/realtime/calls?model=gpt-realtime
//      Authorization: Bearer ek_...  /  Content-Type: application/sdp
//   5. 返ってきた SDP を setRemoteDescription
//
// ★ ドラクエの道具屋ルール：3秒で開かなかったら失敗扱いにして切る。
//   「つないでいます…」で固まらせない。

import { supabase } from "@/integrations/supabase/client";

export type GptLiveStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "error"
  | "closed";

export interface GptLiveHandlers {
  onStatus?: (s: GptLiveStatus) => void;
  /** 相手（アイリス）の発話テキスト。字幕・ログ用 */
  onAssistantText?: (text: string, done: boolean) => void;
  /** こちらの発話の書き起こし */
  onUserText?: (text: string) => void;
  /** search_songs の実体。Grok版と同じ検索を渡すこと（下の注意書き参照） */
  searchSongs: (args: Record<string, unknown>) => Promise<unknown>;
  onError?: (message: string) => void;
  /** デバッグ用。全サーバーイベント */
  onEvent?: (e: any) => void;
}

const CONNECT_TIMEOUT_MS = 3000;

export class GptLiveConcierge {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private mic: MediaStream | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private h: GptLiveHandlers;
  private assistantBuf = "";

  constructor(handlers: GptLiveHandlers) {
    this.h = handlers;
  }

  private status(s: GptLiveStatus) {
    this.h.onStatus?.(s);
  }

  async connect(): Promise<void> {
    this.status("connecting");

    // 1. ephemeral token
    const { data, error } = await supabase.functions.invoke("gptlive-session", {
      body: {},
    });
    if (error || !data?.client_secret) {
      this.fail(`token: ${error?.message ?? JSON.stringify(data)}`);
      return;
    }
    const ek: string = data.client_secret;
    const model: string = data.model ?? "gpt-realtime";

    // 2. PeerConnection + 再生先
    const pc = new RTCPeerConnection();
    this.pc = pc;

    const audioEl = document.createElement("audio");
    audioEl.autoplay = true;
    audioEl.style.display = "none";
    document.body.appendChild(audioEl);
    this.audioEl = audioEl;

    pc.ontrack = (ev) => {
      if (ev.streams[0]) audioEl.srcObject = ev.streams[0];
    };

    // 3. マイク
    try {
      this.mic = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      pc.addTrack(this.mic.getAudioTracks()[0], this.mic);
    } catch (e) {
      this.fail(`mic: ${String(e)}`);
      return;
    }

    // 4. データチャンネル（先に作ってから offer）
    const dc = pc.createDataChannel("oai-events");
    this.dc = dc;
    dc.addEventListener("message", (ev) => this.onServerEvent(ev.data));
    dc.addEventListener("close", () => this.status("closed"));

    const opened = new Promise<boolean>((resolve) => {
      const t = setTimeout(() => resolve(false), CONNECT_TIMEOUT_MS);
      dc.addEventListener("open", () => {
        clearTimeout(t);
        resolve(true);
      });
    });

    // 5. SDP 交換
    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpRes = await fetch(
        `https://api.openai.com/v1/realtime/calls?model=${encodeURIComponent(model)}`,
        {
          method: "POST",
          body: offer.sdp,
          headers: {
            Authorization: `Bearer ${ek}`,
            "Content-Type": "application/sdp",
          },
        },
      );
      if (!sdpRes.ok) {
        this.fail(`sdp ${sdpRes.status}: ${await sdpRes.text()}`);
        return;
      }
      await pc.setRemoteDescription({
        type: "answer",
        sdp: await sdpRes.text(),
      });
    } catch (e) {
      this.fail(`sdp: ${String(e)}`);
      return;
    }

    if (!(await opened)) {
      this.fail("3秒でつながりませんでした");
      return;
    }
    this.status("listening");
  }

  private async onServerEvent(raw: string) {
    let ev: any;
    try {
      ev = JSON.parse(raw);
    } catch {
      return;
    }
    this.h.onEvent?.(ev);

    switch (ev.type) {
      case "error":
        this.h.onError?.(ev.error?.message ?? "unknown");
        break;

      case "input_audio_buffer.speech_started":
        this.status("listening");
        break;

      case "output_audio_buffer.started":
      case "response.output_audio.delta":
        this.status("speaking");
        break;

      case "response.output_audio_transcript.delta":
        this.assistantBuf += ev.delta ?? "";
        this.h.onAssistantText?.(this.assistantBuf, false);
        break;

      case "response.output_audio_transcript.done":
        this.h.onAssistantText?.(ev.transcript ?? this.assistantBuf, true);
        this.assistantBuf = "";
        break;

      case "conversation.item.input_audio_transcription.completed":
        this.h.onUserText?.(ev.transcript ?? "");
        break;

      // ★ 3万曲レコメンド。ここが来なければ Today's Pick しか見ていない＝不合格。
      case "response.function_call_arguments.done": {
        if (ev.name !== "search_songs") break;
        let out: unknown;
        try {
          out = await this.h.searchSongs(JSON.parse(ev.arguments ?? "{}"));
        } catch (e) {
          out = { error: String(e) };
        }
        this.send({
          type: "conversation.item.create",
          item: {
            type: "function_call_output",
            call_id: ev.call_id,
            output: JSON.stringify(out),
          },
        });
        this.send({ type: "response.create" });
        break;
      }

      case "response.done":
        this.status("listening");
        break;
    }
  }

  /** テキストで話しかける（聴き比べ台本を毎回同じ文言で流したいとき用） */
  say(text: string) {
    this.send({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    });
    this.send({ type: "response.create" });
  }

  private send(obj: unknown) {
    if (this.dc?.readyState === "open") this.dc.send(JSON.stringify(obj));
  }

  private fail(msg: string) {
    this.h.onError?.(msg);
    this.status("error");
    this.close();
  }

  close() {
    try {
      this.dc?.close();
    } catch {}
    try {
      this.pc?.close();
    } catch {}
    this.mic?.getTracks().forEach((t) => t.stop());
    this.audioEl?.remove();
    this.dc = null;
    this.pc = null;
    this.mic = null;
    this.audioEl = null;
  }
}
