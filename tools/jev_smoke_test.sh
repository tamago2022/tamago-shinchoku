#!/bin/zsh
set -euo pipefail
KEY_FILE="$HOME/.config/typesafe/api_key"
OUT="/tmp/jev_smoke_result.json"
REQ="/tmp/jev_smoke_request.json"
[[ -s "$KEY_FILE" ]] || { echo '{"error":"KEY_MISSING"}' > "$OUT"; exit 2; }
cat > "$REQ" <<'JSON'
{
  "state": {"task":"Fix a typo in a button label","reversible":true,"spend":false,"founder_value_judgment":false},
  "model": "jev-latest",
  "questions": {
    "route": {
      "type":"choice",
      "instructions":"Who should decide this task under these company rules? Reversible low-risk implementation work should be handled by AI. Founder is only for new spend, irreversible change, secrets/legal, fundamental brand change, or final human value judgment.",
      "criteria": {
        "AIで進める":"Routine reversible work with no new spend or founder-only value judgment.",
        "鬼監督へ":"Implementation is done or evidence exists and the next step is independent QA/review.",
        "Founder判断":"Requires new spend, irreversible or major change, secrets/legal, fundamental brand/worldview change, or final human value judgment.",
        "保留":"There is not enough information to decide safely."
      }
    }
  }
}
JSON
API_KEY="$(cat "$KEY_FILE")"
START=$(python3 - <<'PY'
import time; print(time.time())
PY
)
HTTP=$(curl -sS -o "$OUT" -w '%{http_code}' -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' --data-binary "@$REQ" https://api.typesafe.ai/v1/systemone)
END=$(python3 - <<'PY'
import time; print(time.time())
PY
)
unset API_KEY
python3 - "$OUT" "$HTTP" "$START" "$END" <<'PY'
import json,sys
p,http,s,e=sys.argv[1:]
try: data=json.load(open(p))
except Exception as ex: data={"raw_error":str(ex)}
data["_http_status"]=int(http)
data["_elapsed_sec"]=round(float(e)-float(s),3)
open(p,"w").write(json.dumps(data,ensure_ascii=False,indent=2))
PY
echo "$OUT"
