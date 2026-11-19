#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
わえ（@cosmicwae）Instagram 自動投稿スクリプト
- 判断はしない。決まった時刻に、決まった文面と画像を投げるだけ。
- AIは動かない。ネタはたまごさん、文章はqueue.jsonに確定済み。

使い方:
  python3 post.py --show        全部見せる（投稿しない）※投稿前に必ずこれ
  python3 post.py --check       鍵が生きているか確認（投稿しない）
  python3 post.py --post        次の1本を実際に投稿する
停止:
  wae_autopost/.stop という空ファイルを置くだけで即停止
"""
import os, sys, json, time, argparse, urllib.request, urllib.parse, mimetypes, uuid, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
QUEUE = os.path.join(BASE, "queue.json")
LOG   = os.path.join(BASE, "log.json")
STOP  = os.path.join(BASE, ".stop")
STATUS= os.path.join(ROOT, "status", "wae_autopost_status.json")
GRAPH = "https://graph.facebook.com/v21.0"
# 1031番の関所：たまごさんがOKを出した id しか外に出せない。
# 「見せてから出す」を、思い出したセッションだけが守る約束ではなく、
# 投稿の一本道の上に置く（oni_gate.py と同じ考え方）。
GATE  = os.path.join(ROOT, "status", "sns_gate", "approved.json")

RED = "\033[31m"; GRN = "\033[32m"; OFF = "\033[0m"

def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("META_", "IG_", "FB_"))})
    return env

def jst_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))

def http(url, data=None, files=None, method=None):
    if files:
        b = uuid.uuid4().hex
        body = b""
        for k, v in (data or {}).items():
            body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
        for k, path in files.items():
            fn = os.path.basename(path)
            ct = mimetypes.guess_type(fn)[0] or "application/octet-stream"
            body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\n"
                     f"Content-Type: {ct}\r\n\r\n").encode()
            body += open(path, "rb").read() + b"\r\n"
        body += f"--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    elif data is not None:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    else:
        req = urllib.request.Request(url)
    if method:
        req.get_method = lambda: method
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:600]}")

def load_queue():
    return json.load(open(QUEUE, encoding="utf-8"))

def load_log():
    return json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []

def next_item(q, log):
    done = {e["id"] for e in log if e.get("result") == "ok"}
    for it in q["items"]:
        if it["id"] not in done:
            return it
    return None

def write_status(ok, msg, extra=None):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    s = {"updated": jst_now().isoformat(), "ok": ok,
         "color": "green" if ok else "red", "message": msg}
    if extra: s.update(extra)
    json.dump(s, open(STATUS, "w"), ensure_ascii=False, indent=2)

def cmd_show(q, log):
    nxt = next_item(q, log)
    print(f"■ わえ自動投稿キュー（{q['account']}） 全{len(q['items'])}本 / 投稿枠 {', '.join(q['slots_jst'])} JST")
    done = {e["id"] for e in log if e.get("result") == "ok"}
    for it in q["items"]:
        mark = "済" if it["id"] in done else ("次→" if nxt and it["id"] == nxt["id"] else "  ")
        cl = it.get("collaborators") or q.get("collaborators") or []
        print(f"\n{'='*70}\n[{mark}] {it['id']}  画像: {os.path.basename(it['image'])}"
              f"  (実在: {'○' if os.path.exists(it['image']) else RED+'×'+OFF})"
              f"  共同投稿: {'＋'.join('@'+u for u in cl) if cl else RED+'なし'+OFF}\n{'-'*70}")
        print(it["caption"])
    print(f"\n{'='*70}")

def load_gate():
    """OKが出ている id の集合を返す。ファイルが無ければ空＝1本も出せない。"""
    try:
        with open(GATE, encoding="utf-8") as f:
            return set(json.load(f).get("approved") or [])
    except Exception:
        return set()


def cmd_ok(q):
    """関所を開ける。11本の文面を全部見せてから、y を押したぶんだけOKにする。"""
    cmd_show(q, load_log())
    print("\n★ここから外に出ます。出したら取り消せません。")
    print("  上に出ている文面と画像で、この%d本を出していいですか。" % len(q["items"]))
    try:
        ans = input("  出してよければ y、やめるなら何か別のキー → ").strip().lower()
    except EOFError:
        ans = ""
    if ans != "y":
        print("やめました。1本も出しません。"); return 1
    os.makedirs(os.path.dirname(GATE), exist_ok=True)
    body = {"approved": [it["id"] for it in q["items"]],
            "at": jst_now().strftime("%Y-%m-%d %H:%M:%S"),
            "how": "post.py --ok（たまごさんが文面を見てyを押した）"}
    with open(GATE, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=1)
    print(GRN + "○ %d本にOKを出しました。9:00と19:00に、上から順に1本ずつ出ます。" % len(body["approved"]) + OFF)
    print("  止めたいときは『4_とめる.command』。OKを取り消すなら status/sns_gate/approved.json を消すだけ。")
    return 0


def cmd_check(env):
    tok = env.get("META_ACCESS_TOKEN"); ig = env.get("IG_USER_ID")
    if not tok:
        print(RED + "× META_ACCESS_TOKEN が .env にありません（鍵がまだ無い）" + OFF); return 1
    if not ig:
        print(RED + "× IG_USER_ID が .env にありません" + OFF); return 1
    r = http(f"{GRAPH}/{ig}?fields=username,followers_count,media_count&access_token={urllib.parse.quote(tok)}")
    print(GRN + f"○ 鍵OK: @{r.get('username')} 投稿数{r.get('media_count')} フォロワー{r.get('followers_count')}" + OFF)
    return 0

def cmd_collabtest(env, q):
    """Collabs（共同投稿）が本当に通るかを、公開せずに実際に叩いて確かめる。
    コンテナを1個作るだけ。公開しない。24時間で自動的に消える。"""
    tok = env.get("META_ACCESS_TOKEN"); ig = env.get("IG_USER_ID"); page = env.get("FB_PAGE_ID")
    if not (tok and ig and page):
        print(RED + "× 鍵がまだ無いので叩けません。README_鍵の取り方.md の5手順を1回だけ" + OFF); return 1
    collabs = q.get("collaborators") or []
    if not collabs:
        print(RED + "× queue.json に collaborators が入っていません" + OFF); return 1
    it = q["items"][0]
    print(f"… @{collabs[0]} を共同投稿者にしてコンテナを1個だけ作ります（公開はしません）")
    up = http(f"{GRAPH}/{page}/photos", data={"published": "false", "access_token": tok}, files={"source": it["image"]})
    ph = http(f"{GRAPH}/{up['id']}?fields=images&access_token={urllib.parse.quote(tok)}")
    img_url = sorted(ph["images"], key=lambda x: -x["width"])[0]["source"]
    base = {"image_url": img_url, "caption": "collab test (not published)", "access_token": tok}
    try:
        c = http(f"{GRAPH}/{ig}/media", data={**base, "collaborators": json.dumps(collabs[:3])})
        print(GRN + f"○ Collabs 通った。コンテナID={c['id']}（公開していません）" + OFF)
        print(GRN + f"  → {', '.join('@'+u for u in collabs[:3])} に招待が飛ぶ形で投稿できます" + OFF)
        return 0
    except Exception as e:
        print(RED + f"× Collabs 拒否された。返ってきたもの↓\n{e}" + OFF)
        try:
            http(f"{GRAPH}/{ig}/media", data=base)
            print("  ※ collaborators を外すと同じリクエストは通る＝原因はCollabsの指定だけ")
        except Exception as e2:
            print(f"  ※ collaborators を外しても通らない＝原因は別: {str(e2)[:300]}")
        return 1

def cmd_post(env, q, log, dry=False):
    if os.path.exists(STOP):
        print("停止ファイル(.stop)があるので何もしません"); return 0
    tok = env.get("META_ACCESS_TOKEN"); ig = env.get("IG_USER_ID"); page = env.get("FB_PAGE_ID")
    it = next_item(q, log)
    if not it:
        write_status(False, "在庫ゼロ：投稿できる原稿が残っていない")
        print(RED + "× 在庫ゼロ。queue.json に原稿を足してください" + OFF); return 2
    ok_ids = load_gate()
    if it["id"] not in ok_ids:
        write_status(False, "関所で止めた：この文面にはまだOKが出ていません（%s）" % it["id"],
                     {"next_id": it["id"], "gate": "status/sns_gate/approved.json"})
        print(RED + "× 関所で止めました。まだOKが出ていない文面です: " + it["id"] + OFF)
        print("  たまごさんが『0_この11本にOKを出す.command』を1回押すと開きます。")
        print("  ★OKの無いものは、鍵があっても絶対に出しません。")
        return 5
    if not (tok and ig and page):
        write_status(False, "鍵なし：META_ACCESS_TOKEN / IG_USER_ID / FB_PAGE_ID が .env に無い", {"next_id": it["id"]})
        print(RED + "× 鍵がないので投稿できません。README_鍵の取り方.md の5手順を1回だけ" + OFF); return 1
    if not os.path.exists(it["image"]):
        write_status(False, f"画像が見つからない: {it['image']}", {"next_id": it["id"]})
        print(RED + f"× 画像なし: {it['image']}" + OFF); return 3
    try:
        # 1) 画像をFacebookページに「未公開写真」として上げ、公開URLをもらう
        up = http(f"{GRAPH}/{page}/photos", data={"published": "false", "access_token": tok}, files={"source": it["image"]})
        ph = http(f"{GRAPH}/{up['id']}?fields=images&access_token={urllib.parse.quote(tok)}")
        img_url = sorted(ph["images"], key=lambda x: -x["width"])[0]["source"]
        # 2) Instagramコンテナを作る（Collabs＝共同投稿つき）
        params = {"image_url": img_url, "caption": it["caption"], "access_token": tok}
        collabs = it.get("collaborators") or q.get("collaborators") or []
        if collabs:
            # 公式仕様: フィード画像・リール・カルーセルのみ。最大3人。ストーリーズは非対応。
            # developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/
            params["collaborators"] = json.dumps(collabs[:3])
        try:
            c = http(f"{GRAPH}/{ig}/media", data=params)
        except RuntimeError as e:
            if collabs and "collaborator" in str(e).lower():
                # Collabsだけが原因なら、投稿自体は落とさずCollabs抜きで出す（理由はログに残す）
                print(RED + f"※ Collabs拒否({collabs})。Collabs抜きで投稿します: {str(e)[:200]}" + OFF)
                params.pop("collaborators")
                c = http(f"{GRAPH}/{ig}/media", data=params)
                collabs = []
            else:
                raise
        # 3) 公開
        for _ in range(12):
            st = http(f"{GRAPH}/{c['id']}?fields=status_code&access_token={urllib.parse.quote(tok)}")
            if st.get("status_code") == "FINISHED": break
            time.sleep(5)
        pub = http(f"{GRAPH}/{ig}/media_publish", data={"creation_id": c["id"], "access_token": tok})
        perm = http(f"{GRAPH}/{pub['id']}?fields=permalink&access_token={urllib.parse.quote(tok)}").get("permalink", "")
        log.append({"id": it["id"], "result": "ok", "at": jst_now().isoformat(), "media_id": pub["id"],
                    "permalink": perm, "collaborators": collabs})
        json.dump(log, open(LOG, "w"), ensure_ascii=False, indent=2)
        write_status(True, f"投稿できた: {it['id']}", {"permalink": perm, "remaining": len(q['items']) - len([e for e in log if e.get('result')=='ok'])})
        print(GRN + f"○ 投稿完了 {it['id']}  {perm}" + OFF)
        return 0
    except Exception as e:
        log.append({"id": it["id"], "result": "ng", "at": jst_now().isoformat(), "error": str(e)[:500]})
        json.dump(log, open(LOG, "w"), ensure_ascii=False, indent=2)
        write_status(False, f"投稿失敗: {it['id']} / {str(e)[:200]}", {"next_id": it["id"]})
        print(RED + f"× 投稿失敗 {it['id']}: {e}" + OFF)
        return 4

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--collabtest", action="store_true")
    ap.add_argument("--ok", action="store_true", help="関所を開ける（文面を全部見てからOKを出す）")
    a = ap.parse_args()
    env = load_env(); q = load_queue(); log = load_log()
    if a.ok:    return cmd_ok(q)
    if a.show:  return cmd_show(q, log) or 0
    if a.check: return cmd_check(env)
    if a.collabtest: return cmd_collabtest(env, q)
    if a.post:  return cmd_post(env, q, log)
    ap.print_help(); return 0

if __name__ == "__main__":
    sys.exit(main())
