# OpenHands adapter

## Blocker on this VM

`docker` CLI is **not installed**. Real sandboxed Agent Server conversations cannot run here.

## What ships instead

- Protocol-compatible **stub worker** (`OPENHANDS_STUB=1`, default)
- Creates per-run workspace under `/tmp/aicos-openhands/{run_id}`
- Emits `approval.needed` for simulated **deploy**
- Honors kill switch Redis key `aicos:run:cancel:{run_id}`

## Enable real path later

1. Install Docker + Agent Server
2. Set `OPENHANDS_STUB=0`, `OPENHANDS_AGENT_SERVER_URL=...`, `OPENHANDS_ENABLED=true`
3. Pin software-agent-sdk / Agent Server versions per INTEGRATION_PLAN
