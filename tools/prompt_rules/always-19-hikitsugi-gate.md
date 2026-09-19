## 引き継ぎを「読ませる」関所（924番・2026-09-17）— 読んだかを機械で確かめる

たまごさんの言葉（そのまま）：
「次の人が読むかどうかは保証できません、ってさぁ、それも仕組みでクリアできないの」
「あなたも最初の1日2日『聞いてません』って状態だったじゃん」
「俺は次引き継いだら、どれだけ引き継がれてるか質問から入るから」

**会話の最初、返事をする前に、この2つを実際に読む（プロンプトの「読んでください」だけに頼らない）：**
- `status/public/genzaichi.md`（今の状態1枚）
- `ai-brain/kettei.json`（決定台帳）

**そのあと、以下を1回実行して「読んだ証拠」を機械に残す：**
```
python3 tools/hikitsugi_gate.py --generate
```
出た7問（genzaichi.md/kettei.jsonから機械生成・毎回内容に追従する）に、実際に読んだ内容で
自分で答え、回答ファイル（例 `/tmp/hikitsugi_ans.json`、形は `{"q1_honban": "...", ...}`）を作って：
```
python3 tools/hikitsugi_gate.py --answer-file /tmp/hikitsugi_ans.json
```
`HIKITSUGI_RESULT: PASS`（7問中5問以上正解）が出るまで、適当に埋めて先へ進まない。

### 報告する前は止まる（呼び忘れても素通りしない）

`tools/kenpin_gate.py --n <号番号> --can-deliver` は、外部検品PASS・自己検品・実機能テストに加えて
**本日この関所に合格しているか**も自動でチェックする（`hikitsugi_gate.py --check`を内部で呼ぶ）。
未合格なら`KENPIN_DELIVER: NG`の理由の1つとして出るので、**最終提出（9章）は自動的に止まる**。
個別に`--check`だけ呼びたい時：
```
python3 tools/hikitsugi_gate.py --check   # 0=本日合格済み／1=未合格
```

### なぜ性善説に頼らないか（世界の事例・status/WORLD_CASES_924.md）

Anthropic公式のsub-agentsドキュメント（docs.claude.com）でも「Ask the subagent to consult its
memory」——読ませる責任は呼び出し側にあり、書けば自動で読まれる保証はどこにも書いていない。
だから「引き継ぎ書を置いた」で終わらせず、読んだという事実を機械のテストで残す。
