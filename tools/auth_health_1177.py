#!/usr/bin/env python3
"""1177: read-only fal authentication health check. Never logs credentials."""
import datetime
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
from kagi import get

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "status" / "auth1177"
def check():
    result = {"service": "fal", "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "probe": "authenticated_model_metadata", "generation_run": False,
              "human_login_count": None}
    key = get("FAL_KEY")
    if not key:
        result["state"] = "missing_key"
        return result
    request = urllib.request.Request("https://api.fal.ai/v1/models?endpoint_id=fal-ai/flux/dev",
                                     headers={"Authorization": "Key " + key})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
            rows = data.get("models", [])
            authenticated = bool(rows) and isinstance(rows[0].get("metadata", {}).get("is_favorited"), bool)
            result["http_status"] = response.status
            result["state"] = "authenticated" if response.status == 200 and authenticated else "unverified"
    except urllib.error.HTTPError as error:
        result["http_status"] = error.code
        result["state"] = {401: "authentication_failed", 403: "permission_denied",
                           429: "rate_limited"}.get(error.code, "http_error")
    except Exception:
        result["state"] = "network_or_response_error"
    return result

def main():
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    result = check()
    fd, name = tempfile.mkstemp(dir=str(STATE), prefix="health-")
    with os.fdopen(fd, "w") as output:
        json.dump(result, output, ensure_ascii=False)
        output.write("\n")
    os.replace(name, STATE / "fal-health.json")
    with (STATE / "checks.jsonl").open("a") as output:
        output.write(json.dumps(result) + "\n")
    print(json.dumps(result))
    return 0 if result["state"] == "authenticated" else 2
if __name__ == "__main__":
    raise SystemExit(main())
