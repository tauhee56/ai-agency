# MetaGPT adapter (optional / disabled)

**Status:** disabled by default (`METAGPT_ENABLED=false`).

MetaGPT requires Python `<3.12` while the API and CrewAI/OpenHands path use `>=3.12`.
This directory is the reserved home for a **Python 3.11** worker image.

## Enable later

1. Build a `python:3.11` image installing `metagpt==<pinned>`.
2. Set `METAGPT_ENABLED=true` on the API.
3. Implement Adapter Protocol v1 job handler mapping `goal` → `generate_repo` / `Team.run`.
4. Never import MetaGPT into `apps/api`.

Until then, API returns 400 / feature flag `metagpt_status: disabled` for MetaGPT runs.
