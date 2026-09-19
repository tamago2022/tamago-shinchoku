import json, os, time, urllib.request, urllib.error, mimetypes

KEY_PATH = "/Users/mac/Documents/AI作業/fal_key.txt"

def _key():
    with open(KEY_PATH, "r") as f:
        return f.read().strip()

def _headers(extra=None):
    h = {"Authorization": f"Key {_key()}"}
    if extra:
        h.update(extra)
    return h

def upload_file(path, content_type=None):
    if content_type is None:
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    fname = os.path.basename(path)
    req = urllib.request.Request(
        "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
        data=json.dumps({"content_type": content_type, "file_name": fname}).encode(),
        headers=_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.loads(r.read().decode())
    upload_url = info["upload_url"]
    file_url = info["file_url"]
    with open(path, "rb") as f:
        data = f.read()
    put_req = urllib.request.Request(upload_url, data=data, headers={"Content-Type": content_type}, method="PUT")
    with urllib.request.urlopen(put_req, timeout=60) as r:
        pass
    return file_url

def run_sync(model_id, payload, timeout=180):
    req = urllib.request.Request(
        f"https://fal.run/{model_id}",
        data=json.dumps(payload).encode(),
        headers=_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}")

def submit_queue(model_id, payload):
    req = urllib.request.Request(
        f"https://queue.fal.run/{model_id}",
        data=json.dumps(payload).encode(),
        headers=_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}")

def poll_queue(status_url, response_url, interval=3, max_wait=600):
    start = time.time()
    while time.time() - start < max_wait:
        req = urllib.request.Request(status_url, headers=_headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            st = json.loads(r.read().decode())
        if st.get("status") == "COMPLETED":
            req2 = urllib.request.Request(response_url, headers=_headers())
            with urllib.request.urlopen(req2, timeout=30) as r2:
                return json.loads(r2.read().decode())
        if st.get("status") == "FAILED":
            raise RuntimeError(f"FAILED: {st}")
        time.sleep(interval)
    raise TimeoutError("polling timed out")

def find_url(obj):
    """レスポンスJSONの中から再帰的に最初の 'url' フィールドを探す（fal各モデルの出力キー名の揺れに対応）。"""
    if isinstance(obj, dict):
        if "url" in obj and isinstance(obj["url"], str):
            return obj["url"]
        for v in obj.values():
            u = find_url(v)
            if u:
                return u
    elif isinstance(obj, list):
        for v in obj:
            u = find_url(v)
            if u:
                return u
    return None

def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    return dest
