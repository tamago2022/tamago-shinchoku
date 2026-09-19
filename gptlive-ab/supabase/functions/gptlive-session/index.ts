// supabase/functions/gptlive-session/index.ts
//
// GPT Live（OpenAI Realtime GA）用の ephemeral token 発行。
// Grok版 voice-session と同じ構造：鍵はここだけ。フロントには1秒も出さない。
//
// ★ 2026-09 時点の GA プロトコル
//    発行:  POST https://api.openai.com/v1/realtime/client_secrets
//    接続:  POST https://api.openai.com/v1/realtime/calls  (Bearer ek_..., Content-Type: application/sdp)
//    旧 /v1/realtime/sessions は preview。使わない。
//
// ★ 既定値の罠（Grok版で3日溶かしたやつ）
//    指定しなかった項目は勝手に埋まる。だから下は全部「明示」する：
//      - audio.output.voice           → 指定しないと別人の声になる
//      - audio.input.turn_detection   → 指定しないと返事が返らなくなる
//    GA では voice は session.audio.output.voice、
//    turn_detection は session.audio.input.turn_detection の下にある（旧 preview と場所が違う）。

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// ───────────────────────────────────────────────────────────────
// ▼▼▼ ここから下の2ブロックは Grok版から「1文字も変えずに」貼る ▼▼▼
//
//   コピー元: supabase/functions/voice-session/index.ts
//   ここが1文字でも違うと、比べているのが「声」ではなく「別のAI」になる。
//
// ───────────────────────────────────────────────────────────────

// ===== [貼り付け1/2] アイリスの人格・指示文 =====
// voice-session/index.ts の instructions 文字列をそのままここへ。
const IRIS_INSTRUCTIONS = `__PASTE_FROM_voice-session/index.ts__`;

// ===== [貼り付け2/2] search_songs（3万曲レコメンド）の関数定義 =====
// voice-session/index.ts の tools 配列をそのままここへ。
// 注意：GA の tools は { type:"function", name, description, parameters } の平置き。
//       Chat Completions 風の { type:"function", function:{...} } ではない。
const TOOLS: Record<string, unknown>[] = [
  // {
  //   type: "function",
  //   name: "search_songs",
  //   description: "...",
  //   parameters: { type: "object", properties: { ... }, required: [...] },
  // },
];

// ───────────────────────────────────────────────────────────────
// ▲▲▲ 貼り付けここまで ▲▲▲
// ───────────────────────────────────────────────────────────────

const MODEL = "gpt-realtime";

// Grok版と「声の系統」を揃える。marin / cedar が GA の新しい2種。
// 聴き比べの主役はここ。変えるならこの1行だけ変える。
const VOICE = "marin";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const apiKey = Deno.env.get("OPENAI_API_KEY");
    if (!apiKey) {
      return new Response(
        JSON.stringify({ error: "OPENAI_API_KEY_MISSING" }),
        { status: 500, headers: { ...CORS, "Content-Type": "application/json" } },
      );
    }

    const res = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        session: {
          type: "realtime",
          model: MODEL,
          instructions: IRIS_INSTRUCTIONS,
          tools: TOOLS,
          tool_choice: "auto",
          audio: {
            input: {
              // ★ 明示必須。書かないと type:null になって8割返事が返らない。
              turn_detection: {
                type: "server_vad",
                threshold: 0.5,
                prefix_padding_ms: 300,
                silence_duration_ms: 600,
                create_response: true,
                interrupt_response: true,
              },
              transcription: { model: "whisper-1" },
            },
            output: {
              // ★ 明示必須。書かないと別人の声になる。
              voice: VOICE,
            },
          },
        },
      }),
    });

    const text = await res.text();
    if (!res.ok) {
      // 鍵は絶対に返さない。OpenAI の生エラー文だけ返す。
      return new Response(
        JSON.stringify({ error: "OPENAI_CLIENT_SECRET_FAILED", status: res.status, detail: text }),
        { status: 502, headers: { ...CORS, "Content-Type": "application/json" } },
      );
    }

    const data = JSON.parse(text);
    // GA レスポンス: { value: "ek_...", expires_at: ..., session: {...} }
    return new Response(
      JSON.stringify({
        client_secret: data.value,
        expires_at: data.expires_at,
        model: MODEL,
        voice: VOICE,
      }),
      { headers: { ...CORS, "Content-Type": "application/json" } },
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: "UNEXPECTED", detail: String(e) }),
      { status: 500, headers: { ...CORS, "Content-Type": "application/json" } },
    );
  }
});
