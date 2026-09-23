#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【受付台帳の種】いま埋もれているものを、機械で数えて台帳に流し込む。

★「言われた回数」の定義（これ以外の数え方をしない。数字を手で書かない）:
   回数 = この件に触れている **別々の仕事票（status/queue.json）の本数**
        + この件に触れている **別々の引き継ぎメモ（status/*.md）の本数**
   どちらも「また言われた／また落ちた」から増えるもの。**機械で数えられる。**
   内訳は台帳の moto に残るので、後から誰でも数え直せる。

★「最初に言われた日」:
   status/dispatch_outbox.jsonl の実測 ts から n→日付のアンカーを作り、
   アンカーが無い n は前後から埋める（その行は hatsuKind="推定" と印を付ける）。
   ★推定を実測のように書かない。

使い方:  python3 tools/daicho_tane.py          # 数えて台帳に入れる（既にある行は回数を更新）
        python3 tools/daicho_tane.py --dry    # 数えるだけ
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import daicho  # noqa: E402

# (id, 依頼1行, 拾う言葉, 今なぜ治っていないか（1語）, 潰す手, 1人目の選手)
TANE = [
    ("honban", "補給所の本番が古い（pushしても本番に出ない。Lovableの公開が別操作）",
     ["Lovable", "公開が", "本番に出", "反映されていな", "deploy_project", "本番が古"],
     "別操作", "Lovable公式MCPの deploy_project を心臓に相乗りさせ、push後に必ず1回走らせる",
     "claude-ko"),
    ("kanshi", "自動検知（発車・Lovable公開・鬼監督）が動いていない",
     ["自動検知", "動いていません", "見張り"],
     "止まる", "止まった見張りを台帳の行にして、3時間で選手交代させる",
     "claude-ko"),
    ("jules", "Jules/Devin/外部担当の返事が溜まって処理されない",
     ["Jules", "jules", "Devin", "devin", "GH4"],
     "溜まる", "返事を仕事票にせず、台帳の同じ行の「今どこまで」に上書きする",
     "claude-ko"),
    ("betsujin", "棚に別人の曲が混ざっている 2230件",
     ["別人", "同定", "名前の部分一致", "2230"],
     "人手不足", "Jevに yes/no だけ判定させる（★2230件×1万トークン＝約147円。yosan.pyの栓を先に通す）",
     "jev"),
    ("annai", "案内人（コンシェルジュ）のトンチンカン",
     ["コンシェル", "案内人", "案内所"],
     "作り直し中", "「その場で再生＋なぜ出したか1行」だけに絞って1本通す",
     "claude-ko"),
    ("e", "絵を1枚も出せていない",
     ["絵の門", "画像生成", "絵を出", "イラスト生成", "nano banana"],
     "予算0", "1枚いくらを円で出して yosan.py の栓を開ける→1枚だけ出す",
     "claude-ko"),
    ("kakuninmachi", "「確認待ち」の一覧が無い",
     ["確認待ち"],
     "散らばり", "台帳の「たまごさんの1手」だけを集めた画面にする（この台帳がそれ）",
     "claude-ko"),
    ("shinchoku", "進捗表がごちゃごちゃ（スマホ1画面になっていない）",
     ["進捗表", "スマホ1画面", "見づら", "sumaho_gate"],
     "盛りすぎ", "1画面＝1つの問いにする。sumaho_gate.py を通らないページは出さない",
     "claude-ko"),
    ("shiire", "仕入れが止まる（プレイリスト起点で何千曲）",
     ["仕入れ", "入荷"],
     "関所待ち", "同定の関所をJevのyes/noにして、人の判断を棚出しだけに残す",
     "jules"),
    ("omosa", "重い（Mac・ディスク・ページ）",
     ["重い", "重く", "容量", "ディスク"],
     "原因未特定", "1日20GB減る出どころを実測で1つに絞る",
     "claude-ko"),
    ("kane", "金額が円で出ない／予算の栓で全部止まる",
     ["予算の栓", "yosan", "円で", "課金"],
     "栓が0円", "使う前に「◯件で◯円」を出す形を daicho から呼べるようにする",
     "claude-ko"),
    ("koe", "声で会話できるようにする（たまごさんの1番）",
     ["声で", "マイク", "Realtime Voice"],
     "統合待ち", "マイク1往復だけを先に通す。残りは後",
     "claude-ko"),
    ("houkoku", "報告が長い／URLが無いのに完了になっている",
     ["報告を短く", "URLが無い", "3行"],
     "型が無い", "台帳に url が無い行は「潰した」にできない（tsubushita で機械が拒否）",
     "claude-ko"),
    ("spotify", "Spotifyのプレイリストに入れる（毎回ログインさせられる）",
     ["Spotify", "spotify", "プレイリスト"],
     "毎回ログイン", "refresh_token＋PKCEで一度の同意だけにする。同意のURLを1つ出す",
     "claude-ko"),
    ("gaibuai", "外部AIの判定役が全滅（鍵なし・予算0・claude不在）",
     ["判定役", "外部AI", "検品の門", "採点"],
     "鍵なし", "金の出ない口（codex＝ChatGPTログイン／Jev）だけに寄せる",
     "claude-ko"),
    ("supabase", "Supabaseのservice role鍵が無くて棚に0行も入らない",
     ["service role", "Supabase", "supabase", "サービスロール"],
     "鍵なし", "★鍵はたまごさんしか出せない。入れる入り口のURLを1つ出す",
     "tamago"),
    ("claudeauth", "Claudeのログイン切れ（更新用の鍵が空）",
     ["auth-expired", "ログイン切れ", "認証が切れ", "再ログイン"],
     "鍵が空", "工場は claude CLI に頼らない形へ替える（codex/Jev）。残りは再ログインの1手",
     "claude-ko"),
    ("nagekomi", "投げ込み箱が本番に出ていない",
     ["投げ込", "nagekomi"],
     "未反映", "Lovableの deploy_project を1回走らせてURLで開く",
     "claude-ko"),
    ("domain", "独自ドメインを取ってCloudflareに置く",
     ["独自ドメイン", "Cloudflare"],
     "要支払い", "★ドメイン代はたまごさんしか押せない。金額を円で出して入り口1つ",
     "tamago"),
    ("souzoku", "相続税のページ",
     ["相続"],
     "手つかず", "何を出すページなのかを1行に決めてから着火する",
     "claude-ko"),
]


def anchors():
    a = {}
    for f in ("status/dispatch_outbox.jsonl", "status/ai_daicho.jsonl",
              "status/dispatch_reported.jsonl"):
        p = os.path.join(REPO, f)
        if not os.path.exists(p):
            continue
        for l in io.open(p, encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(l)
            except Exception:
                continue
            n, ts = r.get("n"), (r.get("ts") or r.get("at"))
            if isinstance(n, int) and ts and n < 100000:
                d = str(ts)[:10]
                if n not in a or d < a[n]:
                    a[n] = d
    return a


def kazoeru():
    q = json.load(io.open(os.path.join(REPO, "status", "queue.json"), encoding="utf-8"))["items"]
    mds = glob.glob(os.path.join(REPO, "status", "*.md")) + \
        glob.glob(os.path.join(REPO, "status", "*", "*.md"))
    md = {}
    for p in mds:
        try:
            md[p] = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            pass
    a = anchors()
    ks = sorted(a)
    out = []
    for rid, irai, ws, naze, te, sen in TANE:
        qn = [x for x in q if any(
            w in ((x.get("title") or "") + (x.get("why") or "") + (x.get("what") or "")[:600])
            for w in ws)]
        mn = [p for p, t in md.items() if any(w in t for w in ws)]
        ns = sorted(x.get("n") for x in qn if isinstance(x.get("n"), int))
        # ★「遅くともこの日には存在した」を取る（＝日数は必ず控えめ・盛らない）。
        #   n は増える順に作られるので、n以上の仕事票が動いた日のうち一番早い日が上限。
        if ns:
            n0 = ns[0]
            if n0 in a:
                hatsu, kind = a[n0], "実測"
            else:
                ue = [a[k] for k in ks if k >= n0]
                hatsu = min(ue) if ue else (a[max(ks)] if ks else "2026-09-06")
                kind = "推定"
        else:
            # 仕事票が1本も無い＝引き継ぎメモにしか居ない。メモの最初の日付を使う。
            yuka = min(a.values()) if a else "2026-09-06"   # ★これより前は引用文の日付なので採らない
            hi = sorted(set(x for p in mn for x in
                            __import__("re").findall(r"2026-\d\d-\d\d", md[p]) if x >= yuka))
            hatsu, kind = (hi[0] if hi else yuka), "推定"
        out.append({
            "id": rid, "irai": irai, "naze": naze, "te": te, "senshu": sen,
            "kaisu": len(qn) + len(mn), "q": len(qn), "md": len(mn),
            "hatsu": hatsu, "hatsuKind": kind,
            "ns": ns[:10],
        })
    return sorted(out, key=lambda r: -r["kaisu"])


def main():
    rows = kazoeru()
    dry = "--dry" in sys.argv
    for r in rows:
        print("%3d回 (仕事票%d+引継%d) %s  ← %s" % (r["kaisu"], r["q"], r["md"],
                                                r["irai"][:40], r["hatsu"]))
    if dry:
        return 0
    have = {x["id"] for x in daicho.yomu()["rows"]}
    for r in rows:
        if r["id"] in have:
            continue
        daicho.ireru(
            r["irai"], hatsu=r["hatsu"], kaisu=r["kaisu"],
            hatsu_kind=r["hatsuKind"], rid=r["id"], senshu=r["senshu"],
            koko="（まだ誰も手を付けていない）",
            tsugi=r["te"],
            jotai="たまごさんの1手" if r["senshu"] == "tamago" else "順番待ち")
    # ★回数と内訳は毎回この1か所で上書きする（数を手で書かない）
    d = daicho.yomu()
    naze = {t[0]: t[3] for t in TANE}
    for r in rows:
        for x in d["rows"]:
            if x["id"] == r["id"]:
                x["kaisu"] = r["kaisu"]
                x["naze"] = naze.get(r["id"], "")
                x["moto"] = ["仕事票 %d本（n=%s）" % (r["q"], ",".join(map(str, r["ns"])) or "—"),
                             "引き継ぎメモ %d本" % r["md"]]
    daicho.kaku(d)
    daicho.hi_koushin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
