#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MP4 を渡すと YouTube（@joy-relief-station）に「限定公開（unlisted）」で上げて URL を返す係（2026-10-31）

なぜ要るか：チャットに貼った MP4 は PC で再生できない（たまごさん 10-31）。限定公開の YouTube なら PC でもスマホでも見られる。

  python3 tools/yt_gentei.py put <a.mp4> [--title 題] [--desc 説明]   … 上げて URL を1行で返す（同じ中身は二度上げない）
  python3 tools/yt_gentei.py --signin     … 許可URLを status/yt_gentei/jotai.json と Dispatch に出し、受け皿で待つ（URL_HOURS 時間）
  python3 tools/yt_gentei.py --jotai      … 今の状態（鍵・許可・上げた本数）
  python3 tools/yt_gentei.py --self-test

public には絶対にしない（道具の中で強制）：
  - 送る公開設定は定数 KOUKAI="unlisted" だけ。引数で変えられない。_body() は unlisted 以外を作ると例外。
  - 上げた後に videos.list で確かめ、万一 public なら即 private に倒し、Dispatch へ1行。
  - 再生リスト「試作（限定公開）」も unlisted で作る。

鍵：Google には動的クライアント登録が無いので、OAuth クライアント（種類＝デスクトップ アプリ）の JSON が
  ~/.tamago/keys/google_oauth_client.json に要る。トークンは ~/.tamago/yt_gentei_token.json（0600・中身はどこにも書かない）。
台帳：限定公開URLは「見る人を選ぶ」ものなので公開リポには置かない → ~/.tamago/yt_gentei/daicho.json。
  status/yt_gentei/jotai.json（公開リポ）には本数と状態だけ。

注意（YouTube 公式の決まり）：2020-07-28 以降に作った「未審査」の API プロジェクトから videos.insert した動画は
  「非公開（private）」に固定される。審査（YouTube API Services の監査）を通るまで unlisted にならない。
  その間も、チャンネルの持ち主（たまごさん）がログインしていれば PC・スマホで見られる。jotai に locked として出す。
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
CLIENT = os.path.join(HOME, ".tamago", "keys", "google_oauth_client.json")
TOKEN = os.path.join(HOME, ".tamago", "yt_gentei_token.json")
DAICHO = os.path.join(HOME, ".tamago", "yt_gentei", "daicho.json")
JOTAI = os.path.join(REPO, "status", "yt_gentei", "jotai.json")
OUTBOX = os.path.join(REPO, "status", "dispatch_outbox.jsonl")

KOUKAI = "unlisted"                      # ← 唯一の公開設定。変えない
PLAYLIST = "試作（限定公開）"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube"
PORT = 41997
URL_HOURS = 24
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


# ---------- 小物 ----------
def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _rj(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p, d, secret=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    t = p + ".tmp"
    with open(t, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    if secret:
        os.chmod(t, 0o600)
    os.replace(t, p)


def _dispatch(msg):
    try:
        with open(OUTBOX, "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": _now(), "from": "yt_gentei", "type": "yt_gentei", "text": msg}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _jotai(**kw):
    j = _rj(JOTAI, {}) or {}
    j.update(kw)
    j["at"] = _now()
    d = _rj(DAICHO, {}) or {}
    j["agetta_honsuu"] = len(d.get("videos", {}))
    j["locked_honsuu"] = sum(1 for v in d.get("videos", {}).values() if v.get("jissai") == "private")
    _wj(JOTAI, j)
    return j


def _body(title, desc):
    """送る中身。公開設定は KOUKAI 固定。unlisted 以外になったら作らない。"""
    b = {"snippet": {"title": (title or "試作")[:100], "description": (desc or "")[:4900], "categoryId": "10"},
         "status": {"privacyStatus": KOUKAI, "selfDeclaredMadeForKids": False, "embeddable": True}}
    if b["status"]["privacyStatus"] != "unlisted":
        raise RuntimeError("unlisted 以外は送らない")
    return b


def _http(method, url, tok=None, data=None, headers=None, raw=False):
    h = dict(headers or {})
    if tok:
        h["Authorization"] = "Bearer " + tok
    if data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json; charset=UTF-8")
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    r = urllib.request.urlopen(req, timeout=600)
    return r if raw else json.loads(r.read().decode() or "{}")


# ---------- 鍵 ----------
def _client():
    c = _rj(CLIENT)
    if not c:
        return None
    c = c.get("installed") or c.get("web") or c
    return c if c.get("client_id") else None


def _token():
    t = _rj(TOKEN)
    c = _client()
    if not t or not c:
        return None
    if t.get("exp", 0) - 120 > time.time():
        return t["access_token"]
    if not t.get("refresh_token"):
        return None
    try:
        r = _http("POST", c.get("token_uri", "https://oauth2.googleapis.com/token"),
                  data=urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                               "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode(),
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    except urllib.error.HTTPError as e:
        _jotai(state="kyoka_kire", why="更新できない（%s）。--signin で許可URLを出し直す" % e.code)
        return None
    t["access_token"] = r["access_token"]
    t["exp"] = time.time() + int(r.get("expires_in", 3600))
    _wj(TOKEN, t, secret=True)
    return t["access_token"]


CLIENT_TEJUN = ("Google には自動のクライアント登録が無いため、OAuth クライアントJSONが要る："
                "Google Cloud コンソール（YOUTUBE_DATA_API_KEY を作ったプロジェクト）→ "
                "Google Auth Platform で同意画面（外部・テスト中・テストユーザーに eggypop2010@gmail.com）→ "
                "クライアント作成（種類＝デスクトップ アプリ）→ JSON をダウンロード → ~/.tamago/keys/google_oauth_client.json")


def signin():
    c = _client()
    if not c:
        j = _jotai(state="client_nashi", why=CLIENT_TEJUN)
        _dispatch("YouTube限定公開の道：OAuthクライアントJSONが無いので止まっています。" + CLIENT_TEJUN)
        print(json.dumps(j, ensure_ascii=False, indent=1))
        return 3
    ver = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    chal = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).rstrip(b"=").decode()
    st = secrets.token_urlsafe(16)
    redir = "http://127.0.0.1:%d" % PORT
    url = c.get("auth_uri", "https://accounts.google.com/o/oauth2/auth") + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redir, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": st,
        "code_challenge": chal, "code_challenge_method": "S256"})
    kigen = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() + URL_HOURS * 3600))
    _jotai(state="kyoka_machi", kyoka_url=url, kigen=kigen,
           why="@joy-relief-station を持つ Google アカウントで開いて「許可」。チャンネルを選ぶ画面が出たら joy-relief-station を選ぶ")
    _dispatch("YouTube限定公開の許可URL（期限 %s）：%s" % (kigen, url))
    print(url)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            ok = q.get("state") == st and "code" in q
            if ok:
                got["code"] = q["code"]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<p>%s</p>" % ("許可を受け取りました。閉じてOKです。" if ok else "受け取れませんでした")).encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    srv.timeout = 30
    end = time.time() + URL_HOURS * 3600
    while "code" not in got and time.time() < end:
        srv.handle_request()
    srv.server_close()
    if "code" not in got:
        _jotai(state="kyoka_kigengire", kyoka_url=None)
        return 4
    r = _http("POST", c.get("token_uri", "https://oauth2.googleapis.com/token"),
              data=urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                           "code": got["code"], "code_verifier": ver, "grant_type": "authorization_code",
                                           "redirect_uri": redir}).encode(),
              headers={"Content-Type": "application/x-www-form-urlencoded"})
    r["exp"] = time.time() + int(r.get("expires_in", 3600))
    _wj(TOKEN, r, secret=True)
    ch = _http("GET", API + "/channels?part=snippet&mine=true", r["access_token"])
    name = ((ch.get("items") or [{}])[0].get("snippet") or {}).get("customUrl", "?")
    _jotai(state="ok", kyoka_url=None, channel=name)
    _dispatch("YouTube限定公開の許可を受け取りました（チャンネル %s）" % name)
    # 許可待ちの間に積まれた分を上げる
    machi = (_rj(DAICHO, {}) or {}).get("machi", [])
    for m in list(machi):
        put(m["path"], m.get("title"), m.get("desc"))
    return 0


# ---------- 上げる ----------
def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _playlist(tok, d):
    pid = d.get("playlist_id")
    if pid:
        return pid
    r = _http("GET", API + "/playlists?part=snippet&mine=true&maxResults=50", tok)
    for it in r.get("items", []):
        if it["snippet"]["title"] == PLAYLIST:
            pid = it["id"]
    if not pid:
        pid = _http("POST", API + "/playlists?part=snippet,status", tok,
                    {"snippet": {"title": PLAYLIST, "description": "ごきげん補給所の試作。確認用（限定公開）"},
                     "status": {"privacyStatus": KOUKAI}})["id"]
    d["playlist_id"] = pid
    d["playlist_url"] = "https://www.youtube.com/playlist?list=" + pid
    return pid


def put(path, title=None, desc=None):
    path = os.path.abspath(path)
    d = _rj(DAICHO, {}) or {}
    d.setdefault("videos", {})
    sha = _sha(path)
    if sha in d["videos"]:
        v = d["videos"][sha]
        print(v["url"])
        return v
    title = title or os.path.splitext(os.path.basename(path))[0]
    tok = _token()
    if not tok:
        d.setdefault("machi", [])
        if not any(m["path"] == path for m in d["machi"]):
            d["machi"].append({"path": path, "title": title, "desc": desc, "at": _now()})
        _wj(DAICHO, d, secret=True)
        j = _jotai()
        print("許可待ち：上げる列に積みました（%s）。state=%s" % (os.path.basename(path), j.get("state")))
        return None
    size = os.path.getsize(path)
    r = _http("POST", UPLOAD + "?uploadType=resumable&part=snippet,status", tok, _body(title, desc),
              headers={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)}, raw=True)
    loc = r.headers["Location"]
    with open(path, "rb") as f:
        v = _http("PUT", loc, tok, f.read(), headers={"Content-Type": "video/mp4"})
    vid = v["id"]
    # 確かめる：public なら即 private に倒す
    s = _http("GET", API + "/videos?part=status&id=" + vid, tok)
    jissai = ((s.get("items") or [{}])[0].get("status") or {}).get("privacyStatus", "?")
    if jissai == "public":
        _http("PUT", API + "/videos?part=status", tok, {"id": vid, "status": {"privacyStatus": "private"}})
        jissai = "private"
        _dispatch("【要確認】%s が public になっていたので private に倒しました" % vid)
    try:
        _http("POST", API + "/playlistItems?part=snippet", tok,
              {"snippet": {"playlistId": _playlist(tok, d), "resourceId": {"kind": "youtube#video", "videoId": vid}}})
    except Exception as e:
        print("再生リストに入らず：%s" % e, file=sys.stderr)
    rec = {"id": vid, "url": "https://youtu.be/" + vid, "title": title, "file": os.path.basename(path),
           "jissai": jissai, "at": _now()}
    d["videos"][sha] = rec
    d["machi"] = [m for m in d.get("machi", []) if m["path"] != path]
    _wj(DAICHO, d, secret=True)
    _jotai(state="ok", playlist_url=d.get("playlist_url"))
    print(rec["url"] + ("" if jissai == "unlisted" else "  （%s：未審査のプロジェクトのため。持ち主のログインで見られる）" % jissai))
    return rec


# ---------- 逆テスト ----------
def self_test():
    global KOUKAI, DAICHO, JOTAI, OUTBOX, TOKEN, CLIENT
    import tempfile
    tmp = tempfile.mkdtemp(prefix="yt_gentei_test_")
    try:
        b = _body("t", "d")
        assert b["status"]["privacyStatus"] == "unlisted"
        KOUKAI = "public"
        try:
            _body("t", "d")
            raise AssertionError("public を作ってしまった")
        except RuntimeError:
            pass
        KOUKAI = "unlisted"
        DAICHO, JOTAI, OUTBOX = (os.path.join(tmp, n) for n in ("d.json", "j.json", "o.jsonl"))
        TOKEN, CLIENT = os.path.join(tmp, "t.json"), os.path.join(tmp, "c.json")
        mp4 = os.path.join(tmp, "a.mp4")
        with open(mp4, "wb") as f:
            f.write(b"x" * 10)
        assert put(mp4) is None                     # 鍵なし → 積むだけ
        put(mp4)
        assert len(_rj(DAICHO)["machi"]) == 1          # 二重に積まない
        assert signin() == 3 and _rj(JOTAI)["state"] == "client_nashi"
        print("SELF-TEST PASS")
        return 0
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)       # 作ったら消す


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if a[0] == "--self-test":
        return self_test()
    if a[0] == "--signin":
        return signin()
    if a[0] == "--jotai":
        print(json.dumps(_jotai(), ensure_ascii=False, indent=1))
        return 0
    if a[0] == "put":
        t = a[a.index("--title") + 1] if "--title" in a else None
        ds = a[a.index("--desc") + 1] if "--desc" in a else None
        return 0 if put(a[1], t, ds) is not None or True else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
