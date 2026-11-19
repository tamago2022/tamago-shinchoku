#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1464番【打開関所】「できません」「この方法しかない」を、機械が裏取りする門。

たまごさん（2026-09-19 20:23・原文）:
  「鬼監督システムもそうなんだけど…あなたは思い込みが強くて…自分の思い込みですぐ諦めたり、
   自分独自のやり方でやろうとしたりする…『直し方が一つしかなくて』っていうのは俺は信用してないよ…
   他にももっと良い方法があるのに、実はあなたが知らないやり方を調べてないみたいな」

━━ なぜ文章のお願い（第二条「できないと言うのは最終手段」／19条）では足りなかったか ━━
  既存憲法には「複数の打開策を試してから諦める」というルールは既にあった。
  それでも同じ苦言が出た＝**プロンプトに書くだけでは信用されない**ということ。
  oni_modoshi.py と同じ考え方に合わせる：
    「プロンプトの遵守ではなく、実際に走るコマンドの exit code をゲートにする」

━━ この関所が見るもの ━━
  「できない」「この方法しかない」と結論づける前に、
  **経路の異なる打開策を2種類以上、実際に試した記録**があるか。
  1種類だけ・同じ経路を言い方だけ変えて繰り返した・内容や結果を書いていない
  （＝試したふり）は、理由を問わず弾く。

  経路（shudan）の種類：
    browser … 実ブラウザでの操作
    cli     … コマンドライン（curl・スクリプト実行等）
    api     … 公式APIを直接叩く
    agent   … 別のサブエージェント・別セッションへの委任
    doc     … 公式ドキュメント・一次資料を読んで手順を変えた
    config  … 設定ファイル・権限・環境変数を変えて試した
    other   … 上のどれにも当たらないが経路として別物

━━ 通ったら ━━
  status/1464_dakai_daicho.jsonl に追記。次に同じ詰まりが来た時、
  `--search` で過去の打開策を検索できる＝「あなたが知らないやり方」を
  ゼロから調べ直させない（同じ苦言の再発防止）。

━━ 使い方 ━━
  単発申請：
    python3 tools/1464_dakai_kanmon.py --shinsei '{"komatta":"...", "kokoromi":[...], "ketsuron":"できない"}'
  ファイルから複数件（jsonl、1行1件）：
    python3 tools/1464_dakai_kanmon.py --shinsei-file status/xxx.jsonl
  過去の打開策を検索：
    python3 tools/1464_dakai_kanmon.py --search "キーワード"
  弾いた数・通した数の集計：
    python3 tools/1464_dakai_kanmon.py --show
  自己試験：
    python3 tools/1464_dakai_kanmon.py --self-test

━━ 守っていること ━━
  - 台帳は追記のみ・消さない（弾いた記録も残す＝弾き0が続いたら「門が効いていない」と分かるように）
  - ブラウザを使わない・ネットワークに出ない（ローカルのjsonlだけで完結）
  - 深いディレクトリ探索をしない（status/直下1ファイルのみ）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DAICHO = os.path.join(ST, "1464_dakai_daicho.jsonl")

SHUDAN = {
    "browser": "実ブラウザでの操作",
    "cli": "コマンドライン（curl・スクリプト実行等）",
    "api": "公式APIを直接叩く",
    "agent": "別のサブエージェント・別セッションへの委任",
    "doc": "公式ドキュメント・一次資料を読んで手順を変えた",
    "config": "設定ファイル・権限・環境変数を変えて試した",
    "other": "上のどれにも当たらないが経路として別物",
}

SAITEI_SHUDAN_SHU = 2  # ★経路の異なる打開策、最低これだけ試していないと弾く


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def tooru(sh: dict) -> dict:
    """1件の申請を見る。通れば ok=True、弾けば ok=False と理由。"""
    riyuu = []

    komatta = (sh.get("komatta") or "").strip()
    if not komatta:
        riyuu.append("komatta（詰まった内容）が空")

    ketsuron = (sh.get("ketsuron") or "").strip()
    if ketsuron not in ("できない", "できた"):
        riyuu.append("ketsuron は「できない」か「できた」のどちらか必須（%s）" % (ketsuron or "空"))

    kokoromi = sh.get("kokoromi") or []
    if not isinstance(kokoromi, list) or not kokoromi:
        riyuu.append("kokoromi（試した打開策）が無い＝★思い込みで諦めた疑い")
    else:
        shurui = set()
        yoi = []
        for k in kokoromi:
            if not isinstance(k, dict):
                continue
            sd = (k.get("shudan") or "").strip()
            naiyou = (k.get("naiyou") or "").strip()
            kekka = (k.get("kekka") or "").strip()
            if sd not in SHUDAN:
                continue
            if not naiyou or not kekka:
                # 内容か結果のどちらか欠落＝「試したふり」とみなし数えない
                continue
            shurui.add(sd)
            yoi.append({"shudan": sd, "naiyou": naiyou, "kekka": kekka})
        if len(yoi) < len(kokoromi):
            riyuu.append("内容(naiyou)か結果(kekka)が書かれていない項目がある＝試したふりは数えない")
        # ★「できた」で通した場合は経路数を問わない（結果的に打開できているため）
        if ketsuron == "できない" and len(shurui) < SAITEI_SHUDAN_SHU:
            riyuu.append(
                "経路の異なる打開策が%d種類しかない（最低%d種類必要・同じ経路の言い換えは数えない）: %s"
                % (len(shurui), SAITEI_SHUDAN_SHU, sorted(shurui))
            )

    ok = not riyuu
    return {
        "ok": ok,
        "komatta": komatta,
        "ketsuron": ketsuron,
        "kokoromi": kokoromi,
        "n": sh.get("n"),
        "riyuu": riyuu,
        "at": _now(),
    }


def kazoeru(kekka: list, nani: str = "") -> dict:
    tooshita = [r for r in kekka if r["ok"]]
    hajita = [r for r in kekka if not r["ok"]]
    rec = {
        "at": _now(),
        "nani": nani,
        "申請": len(kekka),
        "通した": len(tooshita),
        "弾いた": len(hajita),
    }
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    with io.open(DAICHO, "a", encoding="utf-8") as fp:
        for r in kekka:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rec


def kensaku(kw: str, limit: int = 10):
    """過去の打開策から、似た詰まりを検索する。★ここが「あなたが知らないやり方」対策の実体。"""
    if not os.path.exists(DAICHO):
        return []
    hit = []
    with io.open(DAICHO, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if kw in (r.get("komatta") or "") and r.get("ok"):
                hit.append(r)
    return hit[-limit:]


def shuukei():
    if not os.path.exists(DAICHO):
        return {"申請": 0, "通した": 0, "弾いた": 0}
    tot, ok, ng = 0, 0, 0
    with io.open(DAICHO, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            tot += 1
            if r.get("ok"):
                ok += 1
            else:
                ng += 1
    return {"申請": tot, "通した": ok, "弾いた": ng}


def self_test() -> bool:
    zenbu_ok = True

    # ケース1：kokoromiが空 → 弾かれる
    r1 = tooru({"komatta": "テスト用の詰まりA", "ketsuron": "できない", "kokoromi": []})
    if r1["ok"]:
        print("NG: ケース1（kokoromi空）が通ってしまった")
        zenbu_ok = False
    else:
        print("OK: ケース1（kokoromi空）は弾かれた")

    # ケース2：経路1種類だけ → 弾かれる
    r2 = tooru({
        "komatta": "テスト用の詰まりB",
        "ketsuron": "できない",
        "kokoromi": [
            {"shudan": "cli", "naiyou": "curlで叩いた", "kekka": "403"},
            {"shudan": "cli", "naiyou": "別のcurlオプションで叩いた", "kekka": "403"},
        ],
    })
    if r2["ok"]:
        print("NG: ケース2（同一経路2回）が通ってしまった")
        zenbu_ok = False
    else:
        print("OK: ケース2（同一経路2回）は弾かれた")

    # ケース3：経路2種類・内容/結果あり → 通る
    r3 = tooru({
        "komatta": "テスト用の詰まりC",
        "ketsuron": "できない",
        "kokoromi": [
            {"shudan": "cli", "naiyou": "curlで叩いた", "kekka": "403で拒否された"},
            {"shudan": "browser", "naiyou": "ブラウザで開いた", "kekka": "ログイン画面で止まった"},
        ],
    })
    if not r3["ok"]:
        print("NG: ケース3（経路2種類）が弾かれてしまった: %s" % r3["riyuu"])
        zenbu_ok = False
    else:
        print("OK: ケース3（経路2種類）は通った")

    # ケース4：内容だけあって結果が無い → 弾かれる（試したふり対策）
    r4 = tooru({
        "komatta": "テスト用の詰まりD",
        "ketsuron": "できない",
        "kokoromi": [
            {"shudan": "cli", "naiyou": "curlで叩いた", "kekka": ""},
            {"shudan": "browser", "naiyou": "", "kekka": "ログイン画面で止まった"},
        ],
    })
    if r4["ok"]:
        print("NG: ケース4（結果/内容欠落）が通ってしまった")
        zenbu_ok = False
    else:
        print("OK: ケース4（結果/内容欠落）は弾かれた")

    # ケース5：ketsuron=できた は経路数を問わない
    r5 = tooru({
        "komatta": "テスト用の詰まりE",
        "ketsuron": "できた",
        "kokoromi": [
            {"shudan": "api", "naiyou": "公式APIで叩いた", "kekka": "成功した"},
        ],
    })
    if not r5["ok"]:
        print("NG: ケース5（できた・1経路でも通るはず）が弾かれてしまった: %s" % r5["riyuu"])
        zenbu_ok = False
    else:
        print("OK: ケース5（できた・1経路）は通った")

    # ケース6：検索が動く（自己試験用の一時レコードは台帳を汚さないよう書き込まない）
    hit = kensaku("テスト用の詰まりC不存在キーワード")
    if hit:
        print("NG: 存在しないはずのキーワードで検索がヒットした")
        zenbu_ok = False
    else:
        print("OK: 検索の空振りは空振りのまま返る")

    return zenbu_ok


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0

    if "--self-test" in argv:
        ok = self_test()
        print("SELF_TEST_RESULT: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    if "--show" in argv:
        s = shuukei()
        print("申請 %d ／ 通した %d ／ 弾いた %d" % (s["申請"], s["通した"], s["弾いた"]))
        if s["申請"] > 0 and s["弾いた"] == 0:
            print("★注意：弾き0。門が効いていない可能性があります。")
        return 0

    if "--search" in argv:
        i = argv.index("--search")
        kw = argv[i + 1] if i + 1 < len(argv) else ""
        hit = kensaku(kw)
        if not hit:
            print("該当なし（過去にこの詰まりを打開した記録はまだありません）")
            return 0
        print("過去の打開策 %d 件:" % len(hit))
        for r in hit:
            print("  [%s] %s → %s" % (r["at"], r["komatta"], r["ketsuron"]))
            for k in r.get("kokoromi", []):
                if isinstance(k, dict) and k.get("naiyou"):
                    print("      - %s: %s → %s" % (k.get("shudan"), k.get("naiyou"), k.get("kekka")))
        return 0

    if "--shinsei" in argv:
        i = argv.index("--shinsei")
        raw = argv[i + 1] if i + 1 < len(argv) else "{}"
        sh = json.loads(raw)
        r = tooru(sh)
        rec = kazoeru([r], nani="shinsei-single")
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if r["ok"]:
            print("DAKAI_KANMON_RESULT: PASS")
            return 0
        else:
            print("DAKAI_KANMON_RESULT: FAIL")
            for x in r["riyuu"]:
                print("  弾いた理由: %s" % x)
            return 2

    if "--shinsei-file" in argv:
        i = argv.index("--shinsei-file")
        path = argv[i + 1] if i + 1 < len(argv) else ""
        if not os.path.exists(path):
            print("申請ファイルがありません: %s" % path)
            return 1
        kekka = []
        with io.open(path, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                kekka.append(tooru(json.loads(line)))
        rec = kazoeru(kekka, nani=os.path.basename(path))
        print("申請 %d ／ 通した %d ／ 弾いた %d" % (rec["申請"], rec["通した"], rec["弾いた"]))
        return 0 if rec["弾いた"] == 0 else 2

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
