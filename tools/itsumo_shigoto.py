#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""いつもの仕事（2026-11-05 たまごさん指示）。工場が空いているとき、列が空になる前に自分で次を積む。

たまごさん（2026-11-05）：
  「空振りしている見回りの代わりに、工場が空いているときの『いつもの仕事』を決めて入れて。
    新しい定期タスクや常駐は足さず、今ある自動発車（auto_launcher）の中で、列が空いたら次を自分で積む」
  「止めるのが最悪（何十回も言っている）。列が空になる、公開の鍵切れ、通信障害、利用上限、
    途中で外から止められる、のどれが起きても工場が止まらないように」
  「たまごさんが聞かないと止まったままになる仕事をゼロに。80点を超えて納品された便は、
    工場が自動で dispatch_outbox.jsonl に『完成：名前／Driveリンク』を書く」

いつもの仕事（この順）：
  ① 空コピー埋め（status/kara_card/README.md。tools/kara_card_tsumu.py の数え・割り方をそのまま使う）
  ② 既存のコピーの直し（水道水・事実の誤り・ポエム。sekisho-jijitsu-shutten と bonjovi-ojisan-kobun の基準）
  ③ 仕入れ＝たまごさんの Spotify のプレイリスト（季節→音楽のジャンル。音楽でないリストは飛ばす）。
     台帳に入れ、関連曲・カバー曲をつなぐ。棚には置かない（棚はたまごさんの名指しだけ）。

どこから呼ばれるか：auto_launcher._main_impl() の頭（queue_lock の中）から tick(q)。中で5分に1回に間引く。
  python3 tools/itsumo_shigoto.py --mitoshi    # 今の待ち・積んだ数を見る（読むだけ）
  python3 tools/itsumo_shigoto.py --self-test

止まらない作り（ここが受け持つ分）：
  ・列が空になる前に積む（種類ごとの「待ちの下限」を割ったら、次の便を積む）
  ・通信障害：auto_launcher の回収が tsuushin_shougai() で見分け、tsuushin_tateru() で旗を立てる。
    旗の間は tsuushin_matsu() が True＝新規発車を待つ。api.anthropic.com の名前が引けたら自動で外す。
  ・公開の鍵切れ：便の指示に「公開は飛ばして main に入れたら完了。koukai_machi.jsonl に1行」を書く。
    鍵が戻ったら（kagi_seimei.json で Lovable が死んでいない）まとめ公開の便を1本積む。
  ・詰まり：いつもの仕事の便は limitMin=90。90分で切られたら auto_launcher の既存の流れで列に戻り、続きから。
  ・利用上限：auto_launcher の既存の仕組み（weekly_limit.flag の resumeAt で自動再開）に任せる。
"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
DIR = os.path.join(ST, "itsumo")
GATE = os.path.join(DIR, ".tick_at")
TSUNDA = os.path.join(DIR, "tsunda.json")
TSUUSHIN = os.path.join(ST, "tsuushin_machi.json")
KOUKAI_MACHI = os.path.join(DIR, "koukai_machi.jsonl")
SPOTIFY_LISTS = os.path.join(DIR, "spotify_lists.json")
KIROKU = os.path.join(DIR, "kiroku.jsonl")
OUTBOX = os.path.join(ST, "dispatch_outbox.jsonl")
PUBLIC = os.path.join(ST, "public", "itsumo.json")
JRS = "/Users/mac/Desktop/joy-relief-station"

TICK_SEC = 300
LIMIT_MIN = 90
# 種類ごとの「待ちの下限」。これを割ったら積む。①が主役、②③は1本ずつ切らさない。
SHITA = {"kara": 4, "naoshi": 1, "shiire": 1}
TSUMU = {"kara": 6, "naoshi": 2, "shiire": 1}
PREFIX = {"kara": "空カード埋め｜", "naoshi": "コピー直し｜", "shiire": "仕入れ｜Spotify", "koukai": "まとめ公開｜"}
NET_RE = re.compile(r"(can't reach the api server|enotfound|econnrefused|econnreset|etimedout|eai_again|"
                    r"fetch failed|getaddrinfo|network error|socket hang up|connection error|overloaded_error)")
SEASON = ("春", "夏", "秋", "冬", "spring", "summer", "autumn", "fall", "winter")
GENRE = ("rock", "ロック", "r&b", "rnb", "r＆b", "soul", "ソウル", "electro", "エレクトロ", "pop", "ポップ",
         "city", "シティ", "chill", "チル", "jazz", "ジャズ", "funk", "ファンク", "hip", "ヒップ", "rap", "ラップ",
         "indie", "インディ", "lofi", "lo-fi", "disco", "ディスコ", "house", "ハウス", "techno", "ambient",
         "アンビエント", "folk", "フォーク", "acoustic", "アコースティック", "ballad", "バラード", "歌謡",
         "anime", "アニソン", "k-pop", "kpop", "j-pop", "jpop", "邦楽", "洋楽", "曲", "song", "music", "音楽",
         "night", "夜", "drive", "ドライブ", "love", "dance", "ダンス", "cover", "カバー", "mix")
HIMUSIC = ("business", "ビジネス", "podcast", "ポッドキャスト", "勉強", "study english", "英会話", "自己啓発",
           "audiobook", "オーディオブック", "瞑想ガイド", "news", "ニュース", "講座", "セミナー", "language",
           "テクノロジー", "経営", "コテンラジオ", "神回", "社会", "起業", "マーケ", "川邊", "伊藤穰一", "ソロプレナー", "エージェント")
HIMUSIC_RE = re.compile(r"(^|[^a-z])(ai|sns)([^a-z]|$)")


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


# ---------------------------------------------------------------- 通信障害
def tsuushin_shougai(txt, urls=None):
    """回収した便の出力が「APIに届かなかっただけ」か。証拠URLがあれば仕事はしているので数えない。"""
    t = (txt or "").lower()
    if urls:
        return False
    if not NET_RE.search(t):
        return False
    # 長い報告の途中にたまたま出てきた単語では判定しない（失敗の出力は短い）
    return ("api error" in t) or len(t) < 1500


def tsuushin_tateru(n=None, sec=180):
    o = _load(TSUUSHIN, {}) or {}
    o.setdefault("since", now())
    o["until"] = time.time() + sec
    o["untilJ"] = time.strftime("%F %T", time.localtime(o["until"]))
    o["last_n"] = n
    o["kaisuu"] = int(o.get("kaisuu") or 0) + 1
    _save(TSUUSHIN, o)


def _api_ni_todoku(host="api.anthropic.com"):
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(4)
        socket.getaddrinfo(host, 443)
        return True
    except Exception:
        return False
    finally:
        socket.setdefaulttimeout(old)


def tsuushin_matsu():
    """True＝通信障害の旗の間なので、新規発車を待つ。戻っていれば旗を外して False。"""
    o = _load(TSUUSHIN, None)
    if not o:
        return False
    if time.time() < float(o.get("until") or 0):
        return True
    if _api_ni_todoku():
        try:
            os.remove(TSUUSHIN)
        except Exception:
            pass
        _append(KIROKU, {"at": now(), "shita": "通信が戻ったので発車を再開", "since": o.get("since"),
                         "kaisuu": o.get("kaisuu")})
        return False
    tsuushin_tateru(o.get("last_n"), 180)
    return True


# ---------------------------------------------------------------- 種類の見分け
def shurui(it):
    t = it.get("title") or ""
    for k, p in PREFIX.items():
        if t.startswith(p):
            return k
    return it.get("itsumo")


def _machi(q):
    c = {k: 0 for k in PREFIX}
    for it in q.get("items", []):
        k = shurui(it)
        if k and it.get("status") in ("waiting", "running"):
            c[k] += 1
    return c


# ---------------------------------------------------------------- 文面
KOUKAI_GYOU = ("【公開の鍵が切れていたら】公開（98403_lovable_publish_mcp.py）が通らなくても止まらない。"
               "書く・関所・main に入れるところまでやって完了にし、status/itsumo/koukai_machi.jsonl に "
               "{\"at\":時刻,\"n\":この便の番号,\"url\":本番URL,\"commit\":main のコミット} を1行。"
               "Dispatch が自分の Lovable コネクタ（deploy_project）でまとめて本番に出し、中身で確かめる"
               "（2026-11-13・鍵の再発行は頼まない）。たまごさんに鍵を頼まない。\n")
KYOUTSUU = ("ブラウザ・web_fetch・Lovableのチャットとエージェントは使わない。有料APIは使わない（0円）。"
            "棚（worlds.ts・admin_shelf_picks）は触らない。たまごさんに質問しない。\n")


def what_naoshi(aid, name, songs):
    return ("【コピー直し】%s の曲カードに今入っているコピー（coverGuide.ts の note・src/lib/tabiCopy.ts）を点検して直す。\n"
            "対象の曲ID：%s\n"
            "見る3点：①水道水コピー（「代表曲のひとつ。」「〜を歌う。」の類）②事実の誤り（出典 src と食い違う・出典なしの断定）"
            "③ポエム（雰囲気だけで中身が無い）。スキル sekisho-jijitsu-shutten と bonjovi-ojisan-kobun を必ず読んでから直す。"
            "問題のない曲は触らない。事実は2本の独立した出典で確かめる（tools/wiki_lookup.py・tools/mac_fetch.py）。\n"
            "関所：joy-relief-station の check-song-shutten・check-cover-truth --strict・detect-generic-copy --fail-hard・"
            "check-note-video-match・check-i18n-parity、工場の tools/sekisho/gate_fact_source.py --strict を通して main へ。\n"
            "%s%s"
            "【記録】status/itsumo/naoshi.jsonl に {\"at\",\"artist\":\"%s\",\"mita\":点検した曲数,\"naoshita\":直した曲数,"
            "\"rei\":[直す前→後を2つまで]} を1行。\n"
            "【報告】点検した曲数／直した曲数と直した理由の内訳／本番URL https://joy-relief-station.lovable.app/cover-guide?artist=%s の3行。"
            % (name, ", ".join(songs), KOUKAI_GYOU, KYOUTSUU, aid, aid))


def what_shiire(pl):
    rng = ""
    if pl.get("kara") is not None:
        rng = "（このリストの %d〜%d 曲目だけ）" % (pl["kara"] + 1, pl["made"])
    else:
        rng = ("（1便で30曲まで。31曲目以降が残ったら status/itsumo/shiire_tsuzuki.jsonl に "
               "{\"id\":\"%s\",\"name\":リスト名,\"kara\":次に始める曲の番号(0始まり),\"total\":全曲数} を1行。工場が続きを積む）" % pl["id"])
    return ("【仕入れ｜Spotify】たまごさんの Spotify のプレイリスト「%s」（id %s・%s曲）%s を仕入れる。\n"
            "1) 曲を読む：`python3 tools/spotify_yomu.py zenkyoku \"%s\"`（GETだけ・鍵の値をログに書かない）。"
            "読めなければ `python3 tools/spotify_kokai_yomu.py --ids %s`（鍵なしの公開読み）。\n"
            "2) 1曲ずつ：曲ページ（coverGuide.ts）にもうあるか確かめる（同定は名前の一致で済ませず、動画の oEmbed の題名・投稿者や ISRC で裏を取る）。"
            "無ければ曲ページとアーティストページを一緒に作る（sekisho-artist-song の関所。公式か生きている動画だけ・素人カバーは入れない）。\n"
            "3) その曲に、関連曲（bridgeRelated・理由の言えるもの4本以上・bridgeReasons に理由）とカバー曲（originalRef／covered-by）を見つけてつなぐ。"
            "取り違え禁止（名前が同じ別人をつながない）。カバーは原曲の作者・年を出典で確かめる。\n"
            "4) コピーは bonjovi-ojisan-kobun、事実は sekisho-jijitsu-shutten（出典 src つき）。検品（tools/shiire_zaiko_kanmon.py ほか prebuild の関所）を通して main へ。\n"
            "★棚には置かない（棚に置くのはたまごさんが名指しした曲だけ）。\n"
            "%s%s"
            "【記録】仕入れ台帳 status/itsumo/shiire_daicho.jsonl に1曲1行 {\"at\",\"list\":\"%s\",\"track\":曲名,\"artist\":アーティスト,"
            "\"kekka\":\"足した|もうあった|飛ばした\",\"naze\":飛ばした理由,\"kanren\":つないだ関連の数,\"cover\":つないだカバーの数,\"url\":曲ページ}。\n"
            "【報告】仕入れた曲数／つないだ関連・カバーの数／飛ばした曲と理由 の3行。"
            % (pl["name"], pl["id"], pl.get("total", "?"), rng, pl["name"], pl["id"], KOUKAI_GYOU, KYOUTSUU, pl["name"]))


def what_koukai(rows):
    return ("【まとめ公開】公開の鍵が切れていた間に main へ入った変更を、まとめて本番に出す（%d便分）。\n"
            "1) `python3 tools/koukai_kakunin.py --id` で本番のIDを控える → `python3 tools/98403_lovable_publish_mcp.py` で公開 → "
            "`python3 tools/koukai_kakunin.py --before <ID> --wait 12`。\n"
            "2) 落ちたら `--kanmon` で落ちた関所の名前を出し、その関所を直してもう一度。\n"
            "3) 本番で次のページに文が出ているか確かめる：%s\n"
            "4) 出たら status/itsumo/koukai_sumi.jsonl に {\"at\",\"n\":[便の番号],\"id\":本番ID} を1行。\n"
            "%s【報告】本番ID／確かめたURL／出なかったページ の3行。"
            % (len(rows), " ".join(sorted(set(r.get("url", "") for r in rows if r.get("url")))[:12]), KYOUTSUU))


# ---------------------------------------------------------------- 積む
def _queue_add(text, label, kind):
    sys.path.insert(0, HERE)
    import command_ingest
    st, msg = command_ingest.queue_add(text, priority=1, label=label, origin="factory", urgent=True)
    _append(KIROKU, {"at": now(), "shita": "積んだ", "kind": kind, "label": label, "st": st, "msg": str(msg)[:160]})
    return st


def _ichiran():
    """空カードの一覧（kara_card_tsumu --kazoe の最新）。6時間より古ければ裏で数え直しを起こす（待たない）。"""
    p = os.path.join(ST, "kara_card", "ichiran_saishin.json")
    try:
        age = time.time() - os.path.getmtime(p)
    except Exception:
        age = 1e9
    if age > 6 * 3600:
        lock = os.path.join(DIR, ".kazoe_at")
        if not os.path.exists(lock) or time.time() - os.path.getmtime(lock) > 3600:
            os.makedirs(DIR, exist_ok=True)
            io.open(lock, "w").write(now())
            try:
                subprocess.Popen(["python3", os.path.join(HERE, "kara_card_tsumu.py"), "--kazoe", JRS],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    return _load(p, None)


def tsumu_kara(n, t):
    sys.path.insert(0, HERE)
    import kara_card_tsumu as k
    data = _ichiran()
    if not data or not data.get("artists"):
        return 0
    kt = k.load_tsunda()
    done = set(kt.get("keys", []))
    added = 0
    for b in k.bin_list(data, k.sns_artists()):
        if added >= n:
            break
        if b["key"] in done or b["artist"] == "hyukoh":
            continue
        bu = "（%d/%d）" % (b["bu"], b["busu"]) if b["busu"] > 1 else ""
        st = _queue_add(k.what_of(b).replace("【完了条件】", KOUKAI_GYOU + "【完了条件】"),
                        "空カード埋め｜%s%s" % (b["name"], bu), "kara")
        kt.setdefault("keys", []).append(b["key"])
        kt.setdefault("log", []).append({"at": time.strftime("%F %T"), "key": b["key"], "st": st, "by": "itsumo"})
        if st != "failed":
            added += 1
    _save(k.TSUNDA, kt)
    return added


def tsumu_naoshi(n, t):
    """コピーが入っている曲のアーティストを、埋め終わった順（hanei.jsonl）→ 元から入っていた順で点検に回す。"""
    done = set(t.setdefault("naoshi", []))
    order = []
    try:
        for ln in io.open(os.path.join(ST, "kara_card", "hanei.jsonl"), encoding="utf-8"):
            try:
                a = json.loads(ln).get("artist")
            except Exception:
                continue
            # 記録の artist が「id + id（説明）」のような文になっている行がある。曲ページのidの形のものだけ拾う
            for a2 in re.findall(r"[a-z0-9][a-z0-9\-]+", a or "") if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*", a or "") else [a]:
                if a2 not in order and len(a2) > 2:
                    order.append(a2)
    except Exception:
        pass
    # そのあとは SNS に出した曲のアーティスト（たまごさん優先順位1位の曲ページ）
    try:
        sys.path.insert(0, HERE)
        import kara_card_tsumu as _k
        order += [a for a in _k.sns_artists() if a not in order]
    except Exception:
        pass
    data = _ichiran() or {}
    names = {a["id"]: a["name"] for a in data.get("artists", [])}
    added = 0
    for aid in order:
        if added >= n:
            break
        if aid in done:
            continue
        name = names.get(aid, aid)
        st = _queue_add(what_naoshi(aid, name, ["（このアーティストのコピーが入っている曲すべて・20曲まで）"]),
                        "コピー直し｜%s" % name, "naoshi")
        done.add(aid)
        t["naoshi"].append(aid)
        if st != "failed":
            added += 1
    return added


def _lists():
    """Spotify のプレイリスト一覧（spotify_yomu.py ichiran の控え）を、季節→ジャンルの順に並べる。音楽でないものは飛ばす。"""
    raw = _load(SPOTIFY_LISTS, None)
    if raw is None:
        return []
    pls = raw.get("playlists") if isinstance(raw, dict) else raw
    out = []
    for p in pls or []:
        name = (p.get("name") or "").strip()
        low = name.lower()
        if not name or any(w in low for w in HIMUSIC) or HIMUSIC_RE.search(low):
            continue
        total = int(p.get("total") or p.get("tracks") or 0)
        if any(w in low for w in SEASON):
            rank = 0
        elif any(w in low for w in GENRE):
            rank = 1
        else:
            rank = 2   # 名前で分からないものは最後（音楽の可能性があるので飛ばさない）
        out.append({"id": p.get("id"), "name": name, "total": total, "rank": rank})
    out.sort(key=lambda x: (x["rank"], -x["total"]))
    return out


def _tsuzuki():
    out = []
    try:
        for ln in io.open(os.path.join(DIR, "shiire_tsuzuki.jsonl"), encoding="utf-8"):
            try:
                r = json.loads(ln)
                out.append({"id": r["id"], "name": r.get("name") or r["id"], "total": int(r.get("total") or 0),
                            "kara": int(r["kara"]), "rank": -1})
            except Exception:
                pass
    except Exception:
        pass
    return out


def tsumu_shiire(n, t):
    done = set(t.setdefault("shiire", []))
    added = 0
    # 続き（30曲を超えたリストの残り）を先に積む＝1つのリストを最後まで終わらせてから次へ
    for pl in _tsuzuki():
        if added >= n:
            return added
        key = "%s#%s" % (pl["id"], pl["kara"])
        if key in done:
            continue
        made = pl["kara"] + 30 if not pl["total"] else min(pl["kara"] + 30, pl["total"])
        p2 = dict(pl, made=made)
        st = _queue_add(what_shiire(p2).replace("【記録】", "（30曲を超えて残ったら、同じ形で shiire_tsuzuki.jsonl に次の番号を1行）\n【記録】"),
                        "仕入れ｜Spotify「%s」（%d〜%d曲目）" % (pl["name"], pl["kara"] + 1, made), "shiire")
        t["shiire"].append(key)
        done.add(key)
        if st != "failed":
            added += 1
    for pl in _lists():
        # 40曲を超えるリストは30曲ずつ（1便15〜60分に収める）
        parts = [None] if pl["total"] <= 40 else list(range(0, pl["total"], 30))
        for kara in parts:
            if added >= n:
                return added
            key = "%s#%s" % (pl["id"], kara)
            if key in done:
                continue
            p2 = dict(pl)
            if kara is not None:
                p2["kara"], p2["made"] = kara, min(kara + 30, pl["total"])
            bu = "" if kara is None else "（%d〜%d曲目）" % (kara + 1, p2["made"])
            st = _queue_add(what_shiire(p2), "仕入れ｜Spotify「%s」%s" % (pl["name"], bu), "shiire")
            t["shiire"].append(key)
            done.add(key)
            if st != "failed":
                added += 1
    return added


def tsumu_koukai(q, t):
    """鍵が戻っていて、公開待ちが溜まっていれば、まとめ公開の便を1本だけ積む。"""
    if _machi(q).get("koukai"):
        return 0
    rows = []
    sumi = set(t.setdefault("koukai_sumi_line", []))
    try:
        for i, ln in enumerate(io.open(KOUKAI_MACHI, encoding="utf-8")):
            if str(i) in sumi:
                continue
            try:
                r = json.loads(ln)
                r["_i"] = str(i)
                rows.append(r)
            except Exception:
                pass
    except Exception:
        return 0
    if not rows:
        return 0
    ks = _load(os.path.join(ST, "kagi_seimei.json"), {}) or {}
    if "Lovable" in (ks.get("broken_now") or []):
        return 0      # 鍵がまだ死んでいる。書く・mainに入れるは止めずに、公開だけ待つ
    st = _queue_add(what_koukai(rows), "まとめ公開｜鍵切れの間に溜まった%d便" % len(rows), "koukai")
    if st != "failed":
        t["koukai_sumi_line"] += [r["_i"] for r in rows]
        return 1
    return 0


# ---------------------------------------------------------------- 宙に浮いた便を列に戻す
def fukki(q):
    """たまごさんの返事待ちで止まったままの「いつもの仕事」を、返事なしで流れるように直す（同じものは二度触らない）。
    ・お金がかからないのに「金額を確認して」で止まっている（costsMoney の機械の誤判定）→ 0円なので通す
    ・通信障害で何もできずに確認待ちへ落ちた → 失敗に数えず列へ戻す
    ・途中で外から止められて確認待ちへ落ちた → 続きから列へ戻す
    ・いつもの仕事の便には limitMin=90 を付ける（詰まっても90分で次へ）"""
    ch = 0
    for it in q.get("items", []):
        k = shurui(it) or ("chuu" if it.get("chuuKey") else None)
        if not k:
            continue
        if k != "chuu" and not it.get("itsumo"):
            it["itsumo"] = k
            ch += 1
        if it.get("status") in ("waiting", "running") and k not in ("koukai", "chuu") and int(it.get("limitMin") or 180) > LIMIT_MIN:
            it["limitMin"] = LIMIT_MIN
            ch += 1
        # いつもの仕事・制作便は作りが0円（有料APIを使わないと指示に書いてある）。「金額を確認」で止めない
        if not it.get("costApproved") and it.get("status") in ("waiting", "hold"):
            it["costApproved"] = True
            it["costApprovedWhy"] = "itsumo_shigoto：0円の仕事（有料APIなし）。金額の自動抽出ができなかっただけの誤判定（2026-11-05）"
            ch += 1
        if k != "chuu" and it.get("status") == "awaiting_check" and not it.get("itsumoFukki"):
            r = (it.get("result") or "") + " " + " ".join(map(str, it.get("failReasons") or []))
            naze = None
            if NET_RE.search(r.lower()) and "API Error" in r:
                naze = "通信障害で何もできずに終わっていた"
            elif "途中で切られました" in r or "外から止められて" in r:
                naze = "途中で外から止められていた（続きから）"
            elif it.get("stuckAt") and "完了・途中" in r:
                naze = "途中までで止まっていた（続きから）"
            if naze:
                it["statusBefore"] = it.get("status")
                it["status"] = "waiting"
                it["itsumoFukki"] = now()
                it["itsumoFukkiWhy"] = naze
                it["redoCount"] = 0
                it["what"] = ("【続きから・%s】終わっている曲はやり直さず、まだ空・未完の曲だけやる。\n" % naze) + (it.get("what") or "")
                for kk in ("finishedAt", "result", "urls", "sessionId", "startedAt", "pid", "stuckAt"):
                    it.pop(kk, None)
                ch += 1
                _append(KIROKU, {"at": now(), "shita": "列に戻した", "n": it.get("n"), "naze": naze})
    return ch


# ---------------------------------------------------------------- 80点以上の完成を知らせる
TEN_RE = re.compile(r"(?:自己採点|採点|点数|スコア)[^0-9]{0,8}(\d{2,3})\s*点|(\d{2,3})\s*点(?:以上)?(?:で|・|）|\)|／|。)")
DRIVE_RE = re.compile(r"https://drive\.google\.com/[^\s\"'（）)、。`　]+")


def kansei_tsuuchi(q):
    ch = 0
    for it in q.get("items", []):
        if not it.get("kanseiTsuuchi") or it.get("kanseiTsuuchiAt"):
            continue
        if it.get("status") not in ("awaiting_check", "done", "merged", "verifying"):
            continue
        r = it.get("result") or ""
        ten = [int(a or b) for a, b in TEN_RE.findall(r) if (a or b)]
        ten = [x for x in ten if x <= 100]
        drive = DRIVE_RE.findall(r) + [u for u in (it.get("urls") or []) if "drive.google.com" in u]
        if not ten or max(ten) < 80 or not drive:
            continue
        name = it.get("kanseiMei") or it.get("hyoudai") or it.get("title")
        _append(OUTBOX, {"at": time.strftime("%F %T"), "from": "itsumo_shigoto", "type": "kansei",
                         "n": it.get("n"), "what": "完成：%s／%s（%d点）" % (name, drive[0], max(ten))})
        it["kanseiTsuuchiAt"] = now()
        ch += 1
    return ch


# ---------------------------------------------------------------- クリエイティブは1便ずつ
def hitotsuzutsu(q):
    """chuuKey の付いた制作便（Fable）は1便ずつ流す。先頭が走行中・待ちの間、残りは hold（順番待ち）。
    先頭が確認待ち・完了・取り消し・固まりになったら、次の便の hold を外す。たまごさんの操作は要らない。"""
    items = [it for it in q.get("items", []) if it.get("chuuKey")]
    if not items:
        return 0
    items.sort(key=lambda it: int(it.get("n") or 0))
    ch = 0
    katsudou = [it for it in items if it.get("status") in ("waiting", "running", "verifying")
                and not it.get("chuuJunban")]
    for it in items:
        if it.get("status") == "hold" and it.get("chuuJunban"):
            if not katsudou:
                it["status"] = "waiting"
                it.pop("chuuJunban", None)
                it.pop("holdNote", None)
                katsudou.append(it)
                ch += 1
                _append(KIROKU, {"at": now(), "shita": "制作便の順番が来た", "n": it.get("n")})
            continue
        if it.get("status") == "waiting" and katsudou and it is not katsudou[0] and it not in katsudou[:1]:
            it["status"] = "hold"
            it["chuuJunban"] = True
            it["holdNote"] = "順番待ち（制作便は1便ずつ・Macを重くしない）。前の便が終わったら工場が自動で外す"
            ch += 1
    return ch


# ---------------------------------------------------------------- 心臓から
def tick(q, force=False):
    """auto_launcher の queue_lock の中から呼ばれる。q を直したら True（呼び出し側が保存する）。"""
    os.makedirs(DIR, exist_ok=True)
    try:
        if not force and time.time() - os.path.getmtime(GATE) < TICK_SEC:
            return False
    except Exception:
        pass
    io.open(GATE, "w").write(now())
    ch = fukki(q) + kansei_tsuuchi(q) + hitotsuzutsu(q)
    t = _load(TSUNDA, {})
    m = _machi(q)
    tsunda = {}
    try:
        try:
            import mudacut as _mc
            _kara_ok = not _mc.kara_teishi()  # 2026-11-08 無駄カット：空カードの自動補充を止める
        except Exception:
            _kara_ok = True
        if _kara_ok and m["kara"] < SHITA["kara"]:
            tsunda["kara"] = tsumu_kara(TSUMU["kara"], t)
        if m["naoshi"] < SHITA["naoshi"]:
            tsunda["naoshi"] = tsumu_naoshi(TSUMU["naoshi"], t)
        if m["shiire"] < SHITA["shiire"]:
            tsunda["shiire"] = tsumu_shiire(TSUMU["shiire"], t)
        tsunda["koukai"] = tsumu_koukai(q, t)
    finally:
        _save(TSUNDA, t)
    if not t.get("hajimari") and any(tsunda.values()):
        t["hajimari"] = now()
        _save(TSUNDA, t)
    _save(PUBLIC, {"at": now(), "machi": m, "tsunda_kondo": tsunda, "hajimari": t.get("hajimari"),
                   "tsuushin_machi": bool(_load(TSUUSHIN, None)),
                   "spotify_lists": len(_lists()), "shiire_tsunda": len(t.get("shiire", [])),
                   "naoshi_tsunda": len(t.get("naoshi", [])),
                   "saisho_1jikan": ichijikan(t.get("hajimari"))})
    return ch > 0


def ichijikan(hajimari):
    """回り始めてから最初の1時間に書けた曲数・仕入れた曲数・つないだ関連とカバー（記録の行から数える。推定はしない）。"""
    if not hajimari:
        return {}
    t0 = hajimari[:19].replace("T", " ")
    t1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.mktime(time.strptime(t0, "%Y-%m-%d %H:%M:%S")) + 3600))
    out = {"kara": t0, "made": t1, "kaita_kyoku": 0, "shiire_kyoku": 0, "kanren": 0, "cover": 0, "list": 0}
    def rows(p):
        try:
            for ln in io.open(p, encoding="utf-8"):
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                at = str(r.get("at") or "")[:19].replace("T", " ")
                if t0 <= at <= t1:
                    yield r
        except Exception:
            return
    for r in rows(os.path.join(ST, "kara_card", "hanei.jsonl")):
        if "反映確認" in str(r.get("text") or "") or "反映済み" in str(r.get("text") or ""):
            continue      # 前に書いた分の本番確認は「書けた曲」に数えない
        try:
            out["kaita_kyoku"] += int(r.get("kyoku") or 0)
        except Exception:
            pass
    ls = set()
    for r in rows(os.path.join(DIR, "shiire_daicho.jsonl")):
        if r.get("kekka") == "足した":
            out["shiire_kyoku"] += 1
        out["kanren"] += int(r.get("kanren") or 0)
        out["cover"] += int(r.get("cover") or 0)
        ls.add(r.get("list"))
    out["list"] = len(ls)
    return out


def mitoshi():
    q = _load(os.path.join(ST, "queue.json"), {})
    print(json.dumps({"machi": _machi(q), "lists": len(_lists()), "tsuushin": _load(TSUUSHIN, None),
                      "public": _load(PUBLIC, {})}, ensure_ascii=False, indent=1))


def self_test():
    ok = True
    ok &= tsuushin_shougai("API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)", [])
    ok &= not tsuushin_shougai("API Error: Can't reach the API server (ENOTFOUND)", ["https://x.example/a"])
    ok &= not tsuushin_shougai("完了しました。" * 400 + " ENOTFOUND", [])
    ok &= shurui({"title": "空カード埋め｜HYUKOH（1/2）"}) == "kara"
    ok &= shurui({"title": "仕入れ｜Spotify「秋」"}) == "shiire"
    q = {"items": [{"n": 1, "title": "空カード埋め｜X", "status": "awaiting_check",
                    "result": "API Error: Can't reach the API server (ENOTFOUND)"},
                   {"n": 2, "title": "空カード埋め｜Y", "status": "waiting", "costsMoney": True,
                    "costEstimate": "金額はタスク文面から自動抽出できません。"},
                   {"n": 3, "title": "Fable｜宇宙うんこ", "status": "awaiting_check", "kanseiTsuuchi": True,
                    "result": "自己採点82点。https://drive.google.com/file/d/abc/view"}]}
    global OUTBOX, KIROKU
    o1, o2 = OUTBOX, KIROKU
    OUTBOX = KIROKU = "/tmp/itsumo_selftest.jsonl"
    try:
        fukki(q)
        kansei_tsuuchi(q)
    finally:
        OUTBOX, KIROKU = o1, o2
        try:
            os.remove("/tmp/itsumo_selftest.jsonl")
        except Exception:
            pass
    ok &= q["items"][0]["status"] == "waiting"
    ok &= q["items"][1].get("costApproved") is True
    ok &= bool(q["items"][2].get("kanseiTsuuchiAt"))
    print("ITSUMO_SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        sys.exit(self_test())
    if "--mitoshi" in a:
        mitoshi()
