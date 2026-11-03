# Argentis Simulation Lab

## 2026-11-03 — Explicit runs, instrumented workers, isolated projects

- Page navigation loads existing status and events. Start/Retry are explicit;
  platform, round cap, starting hour, and graph-memory choice persist.
- Start requests are serialized and idempotent. Retry copies the previous attempt
  before supported cleanup. Interrupted workers become visibly failed on reload.
- All platforms use the instrumented runner, including single-platform runs.
  Idle rounds advance, action events persist, and completion permits interviews.
- LLM calls and simulation steps have timeouts; simulation work has a 30-minute
  wall-clock bound. Worker stdout is unbuffered.
- Built SPA and API share one private threaded Gunicorn service behind the
  existing password gateway. One worker is required for in-memory run ownership.
- New-project form names the workspace and explains graph isolation. Existing
  project/graph creation remains authoritative; no graph is shared implicitly.

Blast radius: checked runner launch, monitor, terminal status, graph-write drain,
interview IPC, report eligibility, retry cleanup, API consumers, navigation,
platform preparation, history, graph ownership, gateway routing, and volume mount.
No Argentis production services or original graph/documents are changed.

Upstream: https://github.com/666ghj/MiroFish, AGPL-3.0 (LICENSE retained).
Fork source: https://github.com/boadinoel/argentis-simulation-lab
