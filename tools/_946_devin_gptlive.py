#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPT Live版のコードを joy-relief-station に入れてPRを出すDevinセッションを立てる。

1セッション1目的。対象ファイルは名指し。src を丸ごと読ませない。
使い方: python3 tools/_946_devin_gptlive.py [--dry]
"""
import json
import os
import sys
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(REPO, "gptlive-ab")
ENV_PATH = os.path.join(REPO, ".env")


def load_key():
    if os.environ.get("DEVIN_API_KEY"):
        return os.environ["DEVIN_API_KEY"]
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if line.startswith("DEVIN_API_KEY="):
                return line.strip().split("=", 1)[1]
    return None


def read(rel):
    with open(os.path.join(KIT, rel), encoding="utf-8") as f:
        return f.read()


F1 = "supabase/functions/gptlive-session/index.ts"
F2 = "src/lib/gptLiveConcierge.ts"
F3 = "src/pages/LabGptLive.tsx"

PROMPT = """リポジトリ: tamago2022/joy-relief-station

【この作業の目的（これ1つだけ）】
新規ファイル3つを追加し、ルートを1行足し、型が通ることを確認して、PRを1本出す。
それ以外のことはしない。

【最重要：リポジトリの読み方】
★ src ディレクトリを丸ごと読まないでください。以前これで壊れています。
 開いてよいファイルは次の5つだけです：
  1. supabase/functions/voice-session/index.ts   （読むだけ）
  2. src/lib/voiceConcierge.ts                   （export を1個足すだけ）
  3. src/App.tsx （無ければルーター定義のファイル1つ。grep で "Route path=" を1回だけ検索して特定する）
  4. public/robots.txt                            （あれば1行足す）
  5. 下で新規作成する3ファイル
 これ以外のファイルは開かないでください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順1. 新しいブランチを切る
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
main から `lab/gptlive-ab` を切ってください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順2. 次の3ファイルを「新規作成」する
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
中身は下に全文を貼ってあります。1文字も変えずにそのまま作ってください。
既存ファイルの上書きは1つもありません（3つとも新規です）。
もし同名ファイルが既にあったら、上書きせずに止めて報告してください。

━━━ ファイルA: {f1} ━━━
```typescript
{c1}
```

━━━ ファイルB: {f2} ━━━
```typescript
{c2}
```

━━━ ファイルC: {f3} ━━━
```tsx
{c3}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順3. ★ここが一番大事★ アイリスの人格と search_songs を「1文字も変えずに」移す
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ファイルA（{f1}）の中に `__PASTE_FROM_voice-session/index.ts__` と書いた
差し込み口が2か所あります。コピー元は **supabase/functions/voice-session/index.ts** です。

(1) アイリスの人格の instructions 文字列
    → voice-session/index.ts の instructions に渡している文字列を、
      **1文字も変えず**そのまま `IRIS_INSTRUCTIONS` に入れる。
      要約・整形・改行の詰め直し・敬語の統一など一切しないでください。

(2) search_songs（3万曲レコメンド）の関数定義
    → voice-session/index.ts の tools 配列を、**1文字も変えず**そのまま `TOOLS` に入れる。
      ⚠ 形だけ注意：Realtime GA の tools は
        {{ type:"function", name, description, parameters }} の**平置き**です。
      コピー元が {{ type:"function", function:{{...}} }} の入れ子形なら、
      **入れ子を1段外すだけ**にしてください。
      name / description / parameters の中身は1文字も変えない。

ここを変えると、比べているのが「声」ではなく「別のAI」になります。それだけは絶対に避けてください。
声のエンジン以外は完全に同条件にするのが、この作業の唯一の目的です。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順4. ★絶対に位置を変えないこと★
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ファイルAの中の
  - `session.audio.output.voice`
  - `session.audio.input.turn_detection`
この2つの**置き場所を動かさないでください。**
`session.voice` / `session.turn_detection` の直下に移すと、OpenAI 側に黙って無視されます
（エラーも出ません）。旧 preview のサンプルはその形なので、参考にしないでください。
ここで過去に3日溶かしています。

同じ理由で、エンドポイントも変えないでください：
  発行 POST https://api.openai.com/v1/realtime/client_secrets
  接続 POST https://api.openai.com/v1/realtime/calls
旧 /v1/realtime/sessions には戻さないでください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順5. 検索関数をつなぐ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ファイルC（{f3}）の冒頭に
  import {{ searchSongs }} from "@/lib/voiceConcierge";
という行があります。

src/lib/voiceConcierge.ts の中の、search_songs の実体になっている検索関数に
**`export` を1個付けるだけ**にしてください。関数の中身は1文字も触らない。
関数名が `searchSongs` でなければ、ファイルCのその import 行1行だけを実際の名前に直してください。
（ファイルCの他の行は変えない）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順6. ルートを1行だけ足す
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ルーター（src/App.tsx など、"Route path=" を grep して特定した1ファイル）に、
他のルートと同じ書き方で1行だけ足してください：

  <Route path="/lab/gptlive" element={{<LabGptLive />}} />

import も1行足してください（既存の import の並びに合わせる）。

★★★ やらないこと（これを破ったらこのPRは不合格です）★★★
 - メニュー・ヘッダー・フッター・トップページ・一覧・カード・検索結果、
   どこからも `/lab/gptlive` へのリンクを張らない。
 - sitemap.xml に載せない。
 - ページ側の noindex を消さない（ファイルCが自前で入れています。そのまま残す）。
 - public/robots.txt があれば `Disallow: /lab/` を1行だけ足す。無ければ何もしない。
URLを知っている人だけが入れる状態にしてください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順7. 型が通ることを確認してから PR を出す
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  npx tsc --noEmit
を実行して、**エラーが0件になってから** PR を出してください。
型が通らない場合は、通らない箇所を報告してください。勝手に人格文字列や
search_songs の定義をいじって辻褄を合わせるのは禁止です。

PRのタイトル: lab: GPT Live 版アイリス（非公開 /lab/gptlive）
PR本文には、次の3点が守られていることを1行ずつ書いてください：
  - instructions と search_songs は voice-session からそのまま（変更なし）
  - voice / turn_detection の位置は audio.output / audio.input のまま
  - /lab/gptlive はどこからもリンクなし・noindex 維持

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
手順8. やらないこと
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 - main には直接 push しない（必ずPR）。
 - API キーをコードにもコミットにもログにも書かない。
   OPENAI_API_KEY は Supabase の Secrets 側で入れます。こちらでは触らない。
 - 既存の Grok版（voice-session / voiceConcierge / cover-guide）の挙動を変えない。
   voiceConcierge.ts に付ける変更は `export` の1語だけです。
 - リファクタ・整形・lint 自動修正・依存の更新はしない。
 - 迷ったら止めて質問してください。勝手に判断して広げないでください。

終わったら PR の URL を教えてください。
""".format(f1=F1, f2=F2, f3=F3, c1=read(F1), c2=read(F2), c3=read(F3))


def main():
    if "--dry" in sys.argv:
        sys.stdout.write(PROMPT)
        sys.stderr.write("\n--- %d chars ---\n" % len(PROMPT))
        return 0

    key = load_key()
    if not key:
        print("DEVIN_API_KEYが見つかりません。")
        return 1

    body = json.dumps({
        "prompt": PROMPT,
        "title": "GPT Live版アイリス /lab/gptlive を joy-relief-station へ",
        "idempotent": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.devin.ai/v1/sessions",
        data=body, method="POST",
        headers={"Authorization": "Bearer %s" % key,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        print("Devin APIエラー %s: %s" % (e.code, e.read().decode("utf-8", "ignore")[:500]))
        return 1
    except Exception as e:
        print("繋がりませんでした: %s" % e)
        return 1

    print(json.dumps(data, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
