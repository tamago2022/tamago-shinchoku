# 1047 引き継ぎ（2026-09-24 01:50）

## やったこと
こちら止まりの186件を「かかる時間」で分け、Aから1件ずつ片づけた。
一覧：https://tamago2022.github.io/tamago-shinchoku/share/check/1047-katazuke.html （200・12行）
台帳：status/1047_kata.jsonl（1件1行）

A 終わった10件／A 途中1件（#937）／B 7件／C 168件。

## この便で分かった構造（次の便が同じ穴に落ちないように）
1. **joy-relief-station は非公開でこの口からcloneできない**（$ git clone → could not read Username）。
   → ごきげん補給所の本体（曲ページ6/6停止・棚編集28秒・URL貼りで落ちる）は**この口ではC**。
     たまごさんが優先したい場所なのに触れない。ここを開けるなら、鍵かミラーが要る。
2. **ブラウザが入らない**（$ python3 -m playwright install chromium → Download failure）。
   → 渡す門（tools/watashi_gate.py）を通せない。share/check/ は WATASHI_GATE_SKIP=1 でしか出せない。
     375pxの画も撮れない。工場側に「門を通す」job kind が無いのが原因。作れば直る。
3. **main への push はできない**（認証が無い）。commit はできる。公開は tools/kohyou.py（putfile）だけ。
   → kohyou は**テキスト1ファイルずつ**。mp4/png などバイナリは出せない。
4. **本番反映まで約1〜2分**。putfile直後に叩くと404が返る。1回待ってから測ること。
5. **渡し済みURLの404の正体**（#936の答え）：
   - status/disk_trend_report.json / health.json / split/509-list.json … .gitignore の `status/*` で追跡外＝永久に出ない
   - status/public/queue.json … tools/pages_publish.sh:155「1MB超は載せない」で除外（1.83MB）
   → **この4本はURLを渡してはいけない。** 渡すなら先に1MB未満にするか追跡に戻すこと。

## 次の便が最初にやるべきA 3件
1. **status/public/queue.json を1MB未満にして404を止める**（#936の残り）。
   いま1.83MB。pages_publish.sh が1MB超を落としている。列の要らない項目を削った軽量版を
   status/public/queue.json として書き出すだけでよい。直後に工場から叩いて200を確認する。
2. **工場に「渡す門を通す」job kind を1本足す**（tools/gaibu_runner.py）。
   payload に path をもらって Mac側で `python3 tools/watashi_gate.py --check <path>` を走らせ、
   結果を返すだけ。これが通れば share/check/ を SKIP 無しで出せるようになり、375pxも撮れる。
3. **#937 の残り3本を決着させる**。x-search/data.json（12MB・データ）は公開から外すか分割するか決める。
   share/check/img/906-image-quality/ の原本2枚は「画質比較の原本」なので縮めない＝除外リストに入れる。
   どちらも「縮める」ではなく「どう扱うか決める」仕事。決めれば憲法点検の赤が1つ消える。

## 触っていないC（主なもの）
ごきげん補給所の本体3件、鍵待ち（Supabase service_role／Gmail／X・Instagram／Claude setup-token）、
お金待ち（OpenAI残高・Grokチーム鍵・1日の上限0円）、GH###の返事読み込み約60件、毎朝の入荷見回り（過去日付）11件。
