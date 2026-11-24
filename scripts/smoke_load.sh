#!/usr/bin/env bash
set -euo pipefail
API="${API_URL:-http://127.0.0.1:8000}"
N="${N:-40}"
ok=0
for i in $(seq 1 "$N"); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/health" || true)
  if [ "$code" = "200" ]; then ok=$((ok+1)); fi
done
echo "health_ok=$ok/$N"
# rate limit probe (may 429)
limited=0
for i in $(seq 1 150); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/" || true)
  if [ "$code" = "429" ]; then limited=$((limited+1)); fi
done
echo "rate_limited_hits=$limited"
echo "LOAD_SMOKE_DONE"
