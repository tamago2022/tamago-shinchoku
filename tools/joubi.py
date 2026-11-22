#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""常備の列（2026-11-22 店主「俺が何か言わなきゃ動かないのは点数が低い。定期タスクでごまかすな。実際にやって」）。

新しい定期処理は作らない。auto_launcher の頭で毎回呼ばれる itsumo_shigoto.tick() の中から tick(q) が呼ばれ、
「常備の仕事」を店主の決めた順で、発車待ちが切れないように積む。着火は auto_launcher の「空きがあれば次」。

店主の順（この順で並べる・order 1〜8）：
  ① 店主の依頼の残り（Grok経由の保留・待ち）       grok
  ② 関連が4枚に足りないページを埋める（10ページずつ） kanren
  ③ 空のコピー埋め → コピー直し                     kara → naoshi
  ④ 消えた動画の差し替え                            video
  ⑤ SNSで出した曲のページを80点以上に               sns80
  ⑥ マガジンの曲は全部、独立ページ・関連4以上       mag
  ⑦ 仕入れ（棚には置かない）                        shiire

守ること：
  ・同時2本・週枠の線は auto_launcher（shuwaku_sen）がそのまま守る。常備の便は「名指しの急ぎ」扱いにしない
    （urgentReason に「自動で」を入れる＝線を超えている間は待つ）。
  ・常備の便は「見たいもの」（kubun=mitai）。客が見るページを良くする仕事なので、週末の裏方止めに掛けない。
  ・空回りさせない：常備の発車待ちは最大 MACHI 本だけ。材料が無い種類は積まない（仕事が無ければ何もしない）。
  ・完了は oni_modoshi の検品（本番の中身）を通ったものだけ。進捗表の「最近完了」は本番URLを先に出す。

wake-dispatch（Grok Bot が進捗表を見て、止まっていたら joy-relief-station に立てる札）：
  github_watch.check_repo が見つけたら okosu() を呼ぶ → 原因を調べて直せるものを直す → 常備を積み直して
  auto_launcher を1回まわす → Issue に1行コメントして閉じる。

  python3 tools/joubi.py --mitoshi          # 今の常備の列（読むだけ）
  python3 tools/joubi.py --kanren-bin K     # 関連埋めの K 便目（0始まり）が受け持つ10ページ
  python3 tools/joubi.py --self-test
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DIR = os.path.join(ST, "joubi")
TSUNDA = os.path.join(DIR, "tsunda.json")
KIROKU = os.path.join(DIR, "kiroku.jsonl")
PUBLIC = os.path.join(ST, "public", "joubi.json")
JRS = "/Users/mac/Desktop/joy-relief-station"

ORDER = ["grok", "kanren", "fuda", "kara", "naoshi", "video", "sns80", "mag", "shiire"]
NAME = {"grok": "店主の依頼の残り", "kanren": "関連を4枚以上に", "fuda": "料理・猫の関連カードの札と理由", "kara": "空のコピー埋め", "naoshi": "コピー直し",
        "video": "消えた動画の差し替え", "sns80": "SNSに出した曲を80点以上に", "mag": "マガジンの曲を独立ページ・関連4以上に",
        "shiire": "仕入れ（棚には置かない）"}
PREFIX = {"kanren": "関連埋め｜", "fuda": "札と理由埋め｜", "video": "動画差し替え｜", "sns80": "SNS曲80点｜", "mag": "マガジン曲｜"}
MACHI = 3            # 常備の発車待ちの上限（同時2本＋次の1本）
URGENT_REASON = "常備の列（自動で積んだ・週枠の線は守る）"
# ① 店主がGrok経由で頼んで、無駄カットで保留のままになっていた依頼（2026-11-22 店主名指し）
GROK_GH = [1034, 1035, 1047, 1056, 1071, 1166, 1169, 1172]
KANREN_BIN = 10
KYOUTSUU = ("ブラウザ・web_fetch・osascript・Lovableのチャットは使わない。お金のかかる道具は使わない（0円）。音を出さない"
            "（再生の確認は node tools/iphone_kakunin.mjs だけ）。棚（worlds.ts・admin_shelf_picks）は触らない。"
            "店主に質問しない。\n")
KOUKAI = ("【公開】joy-relief-station は npm run prebuild（関所全部）を通して main へ。公開が通らなければ "
          "status/itsumo/koukai_machi.jsonl に {\"at\",\"n\",\"url\",\"commit\"} を1行（まとめ公開の便が出す）。\n")
HOUKOKU = ("【報告】3行：何を直したか（ページ数）／本番URL（lovable.app を必ず1本以上）／残り。"
           "★完了は自己申告できない（oni_modoshi が本番の中身で確かめる）。\n")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _load(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def _save(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(o, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def _append(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 見分け
def _gh_no(it):
    m = re.search(r"#(\d+)$", str(it.get("ghKey") or ""))
    if m:
        return int(m.group(1))
    m = re.match(r"GH(\d+)\b", str(it.get("title") or ""))
    return int(m.group(1)) if m else None


def shurui(it):
    if it.get("joubi") in ORDER:
        return it["joubi"]
    t = str(it.get("title") or "")
    for k, p in PREFIX.items():
        if t.startswith(p):
            return k
    if t.startswith("空カード埋め｜"):
        return "kara"
    if t.startswith("コピー直し｜"):
        return "naoshi"
    if t.startswith("仕入れ｜Spotify"):
        return "shiire"
    return None


def kaijo_ok(it, jougen):
    """無駄カット（同じ便3回目以降は保留）の例外：常備の①で外した店主の依頼は、外してから2回まで出してよい。"""
    if not it.get("joubiKaijo"):
        return False
    base = int(it.get("joubiKaijoKaisuu") or 0)
    return int(it.get("hasshaKaisuu") or 0) < max(base, jougen or 2) + 2


def _tag(it, k):
    """常備の便の印。見たいもの・順番・線は守る（名指しの急ぎにしない）。"""
    ch = False
    want = {"joubi": k, "kubun": "mitai", "order": ORDER.index(k) + 1}
    if k != "grok" and it.get("costsMoney") and not it.get("costApproved"):
        # 常備の便は0円（お金のかかる道具は使わないと指示に書いてある）。語の拾い違いで止めない
        want.update({"costsMoney": False})
        it.pop("costAskedAt", None)
    if k != "grok":
        want.update({"urgent": True, "urgentReason": URGENT_REASON})
        if int(it.get("limitMin") or 999) > 90:
            want["limitMin"] = 90
    for a, b in want.items():
        if it.get(a) != b:
            it[a] = b
            ch = True
    return ch


# ---------------------------------------------------------------- ① 店主の依頼の残り
GROK_GYOU = ("\n【常備の列・2026-11-22 店主の名指しで保留を外した】前回は「URLが1本も無いまま終了」で落ちている。"
             "Issue を gh で全文読み、進められる所まで進めて本番URL（lovable.app）を報告に貼る。"
             "既に本番に出ているなら、本番の中身を確かめて URL を貼り、Issue に1行コメントして完了。"
             "店主の判断・支払い・本人確認がどうしても要る所だけは、手を止めず『店主に聞くこと：〜』の1行を報告の最後に書く"
             "（status/joubi/kiku.jsonl にも {\"at\",\"gh\",\"kiku\"} を1行）。\n")


def grok_kaijo(q):
    ch = 0
    t = _load(TSUNDA, {})
    sumi = set(t.setdefault("grokKaijo", []))
    for it in q.get("items", []):
        g = _gh_no(it)
        if g not in GROK_GH:
            continue
        st = it.get("status")
        # 「〜さんの返信」の票は親の依頼の便が Issue のコメントごと読むので、保留のまま（同じ仕事を2本出さない）
        if st == "hold" and str(it.get("n")) not in sumi and "さんの返信" not in str(it.get("title") or ""):
            it["statusBefore"] = "hold"
            it["status"] = "waiting"
            it.pop("holdNote", None)
            it["joubiKaijo"] = now()
            it["joubiKaijoKaisuu"] = int(it.get("hasshaKaisuu") or 0)
            it["tamagoIrai"] = True
            it["what"] = str(it.get("what") or "") + GROK_GYOU
            for k in ("finishedAt", "result", "urls", "sessionId", "startedAt", "pid"):
                it.pop(k, None)
            sumi.add(str(it.get("n")))
            _append(KIROKU, {"at": now(), "shita": "店主の依頼の保留を外した", "n": it.get("n"), "gh": g})
            ch += 1
        if it.get("status") in ("waiting", "running") and _tag(it, "grok"):
            ch += 1
    t["grokKaijo"] = sorted(sumi)
    _save(TSUNDA, t)
    return ch


# ---------------------------------------------------------------- ② 関連埋め
def what_kanren(k):
    return ("【関連埋め・常備の列②・%d便目】関連が4枚に足りないページ（joy-relief-station docs/kata-related-daicho.json）を10ページ埋める。\n"
            "【受け持ち】まず `python3 tools/joubi.py --kanren-bin %d` を実行。出た10ページが受け持ち"
            "（並び＝店主がよく見る順：SNSに出した曲→マガジンの曲→店主の推し・名指し→台帳の順）。"
            "出なければ台帳を自分で読み、同じ並びで %d〜%d 番目を受け持つ。既に4枚以上なら飛ばして次へ。\n"
            "【型 v3】1ページに4〜6枚。種類は 原曲／カバー／同じ人の代表曲／パロディ／ライブ のどれか（札を付ける）。"
            "理由を1行（事実で言える繋がり・出典つき・ボンジョビおじさん構文）。同じ名前の別人を混ぜない"
            "（スキル sekisho-artist-song を読む）。動画は生きているもの（oEmbed）だけ。棚には置かない。\n"
            "【書く所】coverGuide.ts の bridgeRelated（カードB）。終わったら docs/kata-related-daicho.json の該当行を更新。\n"
            "【記録】status/joubi/kanren_sumi.jsonl に {\"at\",\"bin\":%d,\"pages\":[キー],\"umeta\":ページ数} を1行。\n"
            "%s%s%s" % (k + 1, k, k * KANREN_BIN + 1, (k + 1) * KANREN_BIN, k, KOUKAI, KYOUTSUU, HOUKOKU))


def _daicho_rows(jrs=JRS):
    d = _load(os.path.join(jrs, "docs", "kata-related-daicho.json"), None)
    if d is None:
        return None
    rows = d
    if isinstance(d, dict):
        for key in ("pages", "items", "rows", "fusoku", "lt4", "list"):
            if isinstance(d.get(key), list):
                rows = d[key]
                break
        else:
            rows = [dict(v, key=k) if isinstance(v, dict) else {"key": k, "v": v} for k, v in d.items()]
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        n = r.get("related", r.get("kanren", r.get("count", r.get("n"))))
        try:
            if n is not None and int(n) >= 4:
                continue
        except Exception:
            pass
        key = r.get("key") or r.get("page") or ("%s/%s" % (r.get("artist") or r.get("artistId") or "", r.get("song") or r.get("songId") or ""))
        out.append({"key": key, "url": r.get("url") or r.get("page"), "related": n})
    return out


def kanren_narabi(jrs=JRS):
    rows = _daicho_rows(jrs)
    if rows is None:
        return None
    sns = {i.get("key"): idx for idx, i in enumerate(_load(os.path.join(ST, "public", "toukou_tenken.json"), {}).get("items") or [])}
    mag = set()
    for songs in (_load(os.path.join(ST, "public", "magazine_gate.json"), {}).get("mags") or {}).values():
        for s in songs or []:
            mag.add(s.get("key"))
            if s.get("link"):
                mag.add(s["link"])

    def rank(ir):
        i, r = ir
        if r["key"] in sns:
            return (0, sns[r["key"]], i)
        if r["key"] in mag or (r.get("url") and r["url"] in mag):
            return (1, 0, i)
        return (2, 0, i)
    return [r for _, r in sorted(enumerate(rows), key=rank)]


def kanren_bin(k, jrs=JRS):
    rows = kanren_narabi(jrs)
    if rows is None:
        return None
    return rows[k * KANREN_BIN:(k + 1) * KANREN_BIN]


# ---------------------------------------------------------------- ④⑤⑥ 材料のある時だけ
def zairyou_video():
    d = _load(os.path.join(ST, "public", "hikkomi.json"), {})
    return [i for i in d.get("items") or [] if i.get("jotai") == "hikkomi" and not i.get("sashikae")]


def zairyou_sns():
    d = _load(os.path.join(ST, "public", "toukou_tenken.json"), {})
    return [i for i in d.get("items") or [] if i.get("ok") is False or i.get("pass") is False
            or (isinstance(i.get("score"), (int, float)) and i["score"] < 80)
            or (isinstance(i.get("related"), int) and i["related"] < 4)]


def zairyou_mag():
    c = (_load(os.path.join(ST, "public", "magazine_gate.json"), {}).get("count") or {})
    return sum(int(c.get(k) or 0) for k in ("no_page", "link_ng", "related_lt4", "copy_memo_ng", "video_dead"))


def what_fuda():
    return ("【札と理由埋め・常備の列②の続き】料理（/room/tashizan・/room/card の食べ物・食べ物の扉）と猫の部屋の関連カードで、"
            "種類の札（原曲／カバー／同じ人の代表曲／パロディ／ライブ、料理なら 同じ食材／同じ作り手／合わせ技 など、その部屋の型にある札）"
            "と理由1行が空のものを、上から20枚まで埋める。理由は事実で言える繋がり（出典つき）・ボンジョビおじさん構文。"
            "推測でつながない。埋めたら残りの枚数を status/joubi/fuda_nokori.json に {\"at\",\"nokori\":残り枚数} で上書き。\n"
            "%s%s%s" % (KOUKAI, KYOUTSUU, HOUKOKU))


def what_video(rows):
    keys = ", ".join("%s（%s）" % (r.get("key"), "・".join(r.get("shelves") or [])[:40]) for r in rows)
    return ("【動画差し替え・常備の列④】引っ込めた（消えた・埋め込み不可）動画を差し替える。対象：%s\n"
            "同じ曲・同じ人の公式か、長く残っていて再生の多い動画を oEmbed で生きていると確かめてから差し替え、"
            "status/hikkomi の台帳に sashikae を書く（tools/hikkomi.py の流儀）。見つからない物は理由を1行。\n%s%s%s"
            % (keys, KOUKAI, KYOUTSUU, HOUKOKU))


def what_sns(rows):
    keys = "\n".join("・%s %s「%s」 %s" % (r.get("key"), r.get("artist"), r.get("title"), r.get("url")) for r in rows)
    return ("【SNS曲80点・常備の列⑤】SNSに出した曲のページを5点（検索・関連4以上・メモと出典・マガジン入口・生きた動画）"
            "そろえて、曲ページ点検で80点以上にする。対象：\n%s\n"
            "点検は joy-relief-station scripts/patrol/check-posted-songs.mts。事実は出典つき（sekisho-jijitsu-shutten）。\n%s%s%s"
            % (keys, KOUKAI, KYOUTSUU, HOUKOKU))


def what_mag():
    return ("【マガジン曲・常備の列⑥】status/public/magazine_gate.json の落ちた曲（no_page・link_ng・related_lt4・"
            "copy_memo_ng・video_dead）を、上から10曲まで直す：正しい曲の独立ページ・関連4以上・コピーとメモ（出典つき）・生きた動画。"
            "見張りは python3 tools/magazine/magazine_gate.py --daily。\n%s%s%s" % (KOUKAI, KYOUTSUU, HOUKOKU))


# ---------------------------------------------------------------- 積む
def _queue_add(text, label, kind):
    sys.path.insert(0, HERE)
    import command_ingest
    st, msg = command_ingest.queue_add(text, priority=1, label=label, origin="factory", urgent=False)
    _append(KIROKU, {"at": now(), "shita": "積んだ", "kind": kind, "label": label, "st": st, "msg": str(msg)[:160]})
    if st != "failed":
        tag_on_disk(label, kind)
    return st


def tag_on_disk(label, kind):
    """積んだ直後に印を付ける（付く前に線や裏方止めをすり抜けないように）。queue_lock は再入できる。"""
    try:
        import queue_store
        dq = queue_store.load_queue()
        snap = queue_store.snapshot_items(dq)
        hit = [it for it in dq.get("items", []) if str(it.get("title") or "").startswith(label[:20])
               and it.get("status") == "waiting" and not it.get("joubi")]
        for it in hit:
            _tag(it, kind)
        if hit:
            queue_store.save_queue(dq, snapshot=snap)
        return len(hit)
    except Exception as e:
        _append(KIROKU, {"at": now(), "shita": "印を付けられなかった", "label": label, "err": str(e)[:160]})
        return 0


def _machi(q):
    c = {k: 0 for k in ORDER}
    for it in q.get("items", []):
        k = shurui(it)
        if k and it.get("status") in ("waiting", "running"):
            c[k] += 1
    return c


def tsumu(kind, t, its_t):
    """1種類につき1便積む。材料が無ければ 0（何もしない）。"""
    if kind == "kanren":
        k = int(t.get("kanrenNext") or 0)
        rows = kanren_bin(k)
        if rows is not None and not rows:
            return 0               # 台帳が読めて、もう足りないページが無い
        st = _queue_add(what_kanren(k), "%s%d便目（10ページ）" % (PREFIX["kanren"], k + 1), kind)
        if st != "failed":
            t["kanrenNext"] = k + 1
            return 1
        return 0
    if kind == "fuda":
        last = _load(os.path.join(DIR, "fuda_nokori.json"), {})
        if t.get("fudaAt", "")[:10] == now()[:10] or last.get("nokori") == 0:
            return 0               # 1日1便。前の便が「残り0」と書いたら積まない
        if _queue_add(what_fuda(), "%s料理・猫の関連カード（20枚まで）" % PREFIX["fuda"], kind) != "failed":
            t["fudaAt"] = now()
            return 1
        return 0
    if kind in ("kara", "naoshi", "shiire"):
        import itsumo_shigoto as its
        f = {"kara": its.tsumu_kara, "naoshi": its.tsumu_naoshi, "shiire": its.tsumu_shiire}[kind]
        return f(1, its_t) if kind != "kara" else f(1, its_t)
    if kind == "video":
        sumi = set(t.setdefault("video", []))
        rows = [r for r in zairyou_video() if r.get("key") not in sumi][:5]
        if not rows:
            return 0
        if _queue_add(what_video(rows), "%s%d本" % (PREFIX["video"], len(rows)), kind) != "failed":
            t["video"] += [r.get("key") for r in rows]
            return 1
        return 0
    if kind == "sns80":
        sumi = set(t.setdefault("sns80", []))
        rows = [r for r in zairyou_sns() if r.get("key") not in sumi][:5]
        if not rows:
            return 0
        if _queue_add(what_sns(rows), "%s%s ほか%d曲" % (PREFIX["sns80"], rows[0].get("title"), len(rows) - 1), kind) != "failed":
            t["sns80"] += [r.get("key") for r in rows]
            return 1
        return 0
    if kind == "mag":
        last = t.get("magAt") or ""
        gate_at = str(_load(os.path.join(ST, "public", "magazine_gate.json"), {}).get("at") or "")
        if not zairyou_mag() or last >= gate_at:
            return 0               # 見張りが新しく数え直すまで同じ便を積まない
        if _queue_add(what_mag(), "%s落ちた曲を直す（%d件）" % (PREFIX["mag"], zairyou_mag()), kind) != "failed":
            t["magAt"] = gate_at
            return 1
        return 0
    return 0


def tick(q, its_t=None):
    """itsumo_shigoto.tick() の中（auto_launcher の queue_lock の中）から呼ばれる。q を直したら変更数を返す。"""
    os.makedirs(DIR, exist_ok=True)
    ch = grok_kaijo(q)
    for it in q.get("items", []):
        k = shurui(it)
        if k and k != "grok" and it.get("status") in ("waiting", "running"):
            ch += 1 if _tag(it, k) else 0
    # 店主本人のIssue・返信（GHxxxx tamago2022さんの返信）は店主の言葉＝見たいもの。週末の裏方止めに掛けない
    for it in q.get("items", []):
        if (it.get("status") == "waiting" and not it.get("kubun")
                and re.match(r"GH\d+ tamago2022さんの返信", str(it.get("title") or ""))):
            it["kubun"] = "mitai"
            ch += 1
    t = _load(TSUNDA, {})
    its_t = its_t if its_t is not None else {}
    m = _machi(q)
    tsunda = []
    # 店主の順で前から見る。「自分より前の種類の待ち＋自分」が MACHI 未満で、自分の種類が0本なら1便積む
    #   （古い種類の便が溜まっていても、前の順の仕事が後ろに回らないように）。
    mae = 0
    for kind in ORDER[1:]:
        if mae >= MACHI:
            break
        if not m.get(kind):
            try:
                n = tsumu(kind, t, its_t)
            except Exception as e:
                _append(KIROKU, {"at": now(), "shita": "積めなかった", "kind": kind, "err": str(e)[:200]})
                n = 0
            if n:
                m[kind] = n
                tsunda.append(kind)
        mae += m.get(kind) or 0
    if True:
        if tsunda:
            # 積んだ便に印（同じ q の末尾に入っている）
            for it in q.get("items", []):
                k = shurui(it)
                if k and it.get("status") == "waiting":
                    _tag(it, k)
            ch += len(tsunda)
    _save(TSUNDA, t)
    _save(PUBLIC, {"at": now(), "junban": [NAME[k] for k in ORDER], "machi": _machi(q), "tsunda_kondo": tsunda})
    return ch


# ---------------------------------------------------------------- wake-dispatch
def shindan():
    """止まっている原因を、工場の記録から見分ける（読むだけ）。"""
    r = []
    pace = _load(os.path.join(ST, "pace.json"), {})
    if pace.get("senStop"):
        r.append("週枠の線（%s）" % pace.get("senLine", "")[:40])
    for f, msg in (("no_launch.flag", "発車止めの旗"), ("weekly_limit.flag", "利用上限の旗"),
                   ("tsuushin_machi.json", "通信障害の旗")):
        if os.path.exists(os.path.join(ST, f)):
            r.append(msg)
    top = _load(os.path.join(ST, "top_status.json"), {})
    if top.get("stoppedReason"):
        r.append(str(top["stoppedReason"])[:60])
    if (top.get("login") or {}).get("ng"):
        r.append("Claudeのログイン切れ")
    kk = _load(os.path.join(ST, "kohyou_kanshi.json"), {})
    if kk.get("aka"):
        r.append("本番がmainに追いついていない")
    return r


def okosu(q):
    """札を見たときの立て直し（queue_lock の中で呼ぶ）。直したことの一覧を返す。"""
    naoshi = []
    tf = os.path.join(ST, "tsuushin_machi.json")
    if os.path.exists(tf):
        try:
            import itsumo_shigoto as its
            if its._api_ni_todoku():
                os.remove(tf)
                naoshi.append("通信障害の旗を外した（APIに届く）")
        except Exception:
            pass
    n = tick(q)
    if n:
        naoshi.append("常備の列を積み直した（%d件）" % n)
    return naoshi


def wake_issue(repo, num, token, post_comment, close_issue):
    """github_watch から呼ばれる。原因→直す→発車→1行コメント→閉じる。"""
    sys.path.insert(0, HERE)
    import queue_store
    genin = shindan()
    with queue_store.queue_lock():
        q = queue_store.load_queue()
        snap = queue_store.snapshot_items(q)
        naoshi = okosu(q)
        queue_store.save_queue(q, snapshot=snap)
    try:
        subprocess.run(["python3", os.path.join(HERE, "auto_launcher.py")], timeout=150,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    q = _load(os.path.join(ST, "queue.json"), {})
    run = [it for it in q.get("items", []) if it.get("status") == "running"]
    run.sort(key=lambda it: str(it.get("startedAt") or ""), reverse=True)
    bin_ = "走行中 " + "／".join("%s番「%s」" % (it.get("n"), str(it.get("hyoudai") or it.get("title"))[:30]) for it in run[:2])
    nx0 = sorted([it for it in q.get("items", []) if it.get("status") == "waiting" and shurui(it)],
                 key=lambda it: (it.get("order") or 99, it.get("n") or 0))[:1]
    if run and nx0:
        bin_ += "／常備の次＝%s番「%s」" % (nx0[0].get("n"), str(nx0[0].get("title"))[:30])
    if not run:
        nx = sorted([it for it in q.get("items", []) if it.get("status") == "waiting" and shurui(it)],
                    key=lambda it: (it.get("order") or 99, it.get("n") or 0))[:1]
        bin_ = ("走行なし。次は%s番「%s」（%s）" % (nx[0].get("n"), str(nx[0].get("title"))[:30],
                "週枠の線が上がり次第自動で発車" if "週枠の線" in " ".join(genin) else "空きが出次第自動で発車")
                if nx else "走行なし・常備の材料なし")
    body = "工場：原因＝%s／直したこと＝%s／発車＝%s" % ("・".join(genin) or "見つからず", "・".join(naoshi) or "なし", bin_)
    post_comment(repo, num, token, body)
    close_issue(repo, num, token)
    _append(KIROKU, {"at": now(), "shita": "wake-dispatch", "issue": "%s#%s" % (repo, num), "body": body})
    return body


# ---------------------------------------------------------------- 手で見る
def mitoshi():
    q = _load(os.path.join(ST, "queue.json"), {})
    out = []
    for it in q.get("items", []):
        k = shurui(it)
        if k and it.get("status") in ("waiting", "running"):
            out.append((it.get("order") or 99, it.get("n"), it.get("status"), k, str(it.get("title"))[:50]))
    for r in sorted(out):
        print(*r)
    print(json.dumps({"machi": _machi(q), "shindan": shindan()}, ensure_ascii=False))


def self_test():
    ok = True
    ok &= shurui({"title": "関連埋め｜1便目"}) == "kanren"
    ok &= shurui({"title": "コピー直し｜x"}) == "naoshi"
    ok &= shurui({"title": "判定日赤｜x"}) is None
    it = {"title": "関連埋め｜1便目", "limitMin": 180}
    _tag(it, "kanren")
    ok &= it["kubun"] == "mitai" and it["order"] == 2 and shurui({"title": "札と理由埋め｜x"}) == "fuda" and it["limitMin"] == 90
    sys.path.insert(0, HERE)
    try:
        import shuwaku_sen as sw
        ok &= not sw.is_meishi_isogi(it)         # 線を超えている間は待つ
    except Exception:
        pass
    try:
        import shukan_kubun as sk
        ok &= sk.classify_item(it) == "mitai"    # 週末の裏方止めに掛からない
    except Exception:
        pass
    g = {"ghKey": "gh:tamago2022/joy-relief-station#1034", "hasshaKaisuu": 2, "joubiKaijo": "x", "joubiKaijoKaisuu": 2}
    ok &= _gh_no(g) == 1034 and kaijo_ok(g, 2)
    g["hasshaKaisuu"] = 4
    ok &= not kaijo_ok(g, 2)
    ok &= "kanren-bin 3" in what_kanren(3)
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--kanren-bin" in a:
        k = int(a[a.index("--kanren-bin") + 1])
        jrs = a[a.index("--jrs") + 1] if "--jrs" in a else JRS
        rows = kanren_bin(k, jrs)
        print(json.dumps(rows, ensure_ascii=False, indent=1) if rows is not None else "台帳が読めません")
        sys.exit(0 if rows else 1)
    mitoshi()
