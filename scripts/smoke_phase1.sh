#!/usr/bin/env bash
set -euo pipefail
API="${API_URL:-http://localhost:8000}"
EMAIL="founder+smoke-$(date +%s)@example.com"
PASS="password123"
NAME="Smoke Founder"
CO="Smoke Co $(date +%s)"

echo "== health =="
curl -sf "$API/health" | tee /tmp/aicos-health.json
echo

echo "== signup =="
SIGNUP=$(curl -sf -X POST "$API/auth/signup" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"name\":\"$NAME\",\"company_name\":\"$CO\"}")
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$SIGNUP")
echo "token ok"

echo "== companies =="
ME=$(curl -sf "$API/companies/mine" -H "Authorization: Bearer $TOKEN")
CID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["company_id"])' <<<"$ME")
echo "company $CID"

echo "== model =="
curl -sf -X POST "$API/companies/$CID/models" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Stub OpenAI","provider":"openai","model_name":"gpt-4.1","is_default":true}' >/tmp/aicos-model.json
echo "model created"

echo "== ceo =="
CEO=$(curl -sf -X POST "$API/ceo/advise" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"message\":\"Prioritize Phase 1 ship criteria\",\"company_id\":\"$CID\"}")
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["acknowledgment"]; assert d["plan"]; print("ceo ok stub=", d["stub"])' <<<"$CEO"

echo "== overview =="
curl -sf "$API/companies/$CID/overview" -H "Authorization: Bearer $TOKEN" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["ceo"]; assert d["model_status"]["configured"]; print("overview ok")'

echo "SMOKE PASS"
