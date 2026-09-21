# 案内人（アイリス）に名前を正しく読ませる ― 貼り方

`joy-relief-station` は非公開なのでここからは触れない。**貼るのは3か所だけ。**

---

## 1. 辞書を置く

`tools/yomi/out/yomiDictionary.ts` を、そのまま

```
src/lib/yomiDictionary.ts
```

として置く。**手で書き換えない**（入荷のたび `bash tools/yomi/run.sh` で作り直す）。

---

## 2. 検索結果に読みを足す（1行）

案内人へ返す直前に通すだけ。**元の `name` は壊さない。`yomi` を横に足すだけ。**

`src/lib/voiceConcierge.ts`（Grok版）と `src/lib/gptLiveConcierge.ts`（GPT版）の両方。
`searchSongs` の結果を `function_call_output` に詰めているところ：

```diff
+ import { withYomi, YOMI_INSTRUCTION } from "@/lib/yomiDictionary";
...
- out = await this.h.searchSongs(JSON.parse(ev.arguments ?? "{}"));
+ out = withYomi(await this.h.searchSongs(JSON.parse(ev.arguments ?? "{}")));
```

---

## 3. 指示文の末尾に1ブロック足す

セッションを作るところ（`instructions:` を組み立てている場所）：

```diff
- instructions: INSTRUCTIONS,
+ instructions: INSTRUCTIONS + "\n" + YOMI_INSTRUCTION,
```

`YOMI_INSTRUCTION` の中身は、

- 「yomi が付いているものは、必ずそのカタカナのとおりに発音する」
- 「英字のつづりを見て英語読みに直さない」
- 検索を通さずに口に出しやすい **235件の英字名の読み**（King Gnu=キングヌー ほか）

Edge Function 側（`supabase/functions/gptlive-session/index.ts`）で `instructions` を
組み立てている場合は、そちらにも同じ1行を足す。**片方だけだと直らない。**

---

## 4. 入荷のたび自動で読みが付くようにする

`package.json` に1行：

```json
"scripts": {
  "prebuild": "node scripts/yomi-check.mjs",
  ...
}
```

`scripts/yomi-check.mjs` は、`src/lib/coverGuide.ts` にあって
`src/lib/yomiDictionary.ts` に無い名前を数え、**0件でなければビルドを落とす**だけでよい。
落ちたら `tamago-shinchoku` 側で `bash tools/yomi/run.sh` を走らせて `yomiDictionary.ts` を貼り直す。

---

## なぜこの形か

使っている音声API（OpenAI Realtime / xAI realtime）は **speech-to-speech** で、
**SSML も発音記号のタグも持たない**。効くのは

1. 言葉での指示（＝3のブロック）
2. 渡す文字そのものを変える（＝2の `yomi`）

の2つだけ。だから読み仮名は**データとして渡す**。

## 元からあったもの

`coverGuide.ts` の `aliases` には、**King Gnu の「キングヌー」が最初から入っていた**。
足りなかったのはデータではなく、**案内人がそれを見る配線**だった。
