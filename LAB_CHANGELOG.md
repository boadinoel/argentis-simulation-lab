# Argentis Simulation Lab

## 2026-11-03 â€” Explicit runs, instrumented workers, isolated projects

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

Validation: lifecycle tests cover concurrent starts, terminal reconnect, interrupted
workers, retry evidence archives, strict options, and parallel completion. Existing
barrier tests exercise the underlying upstream handler separately from the lab guard.

- Project workspace lists projects even before a simulation is prepared, with direct
  links to saved runs, reports, and interviews. Mobile opens the run workbench.
- Pin the upstream runtime image digest used during validation.

- Preparation checks require only enabled-platform profiles, preventing unnecessary
  regeneration and allowing single-platform retries. Simulation creation rejects a
  graph ID belonging to a different project.

- Interview availability also checks the owned worker, so a stale alive file after
  a container restart cannot advertise a functioning interview session. Saved
  reports, action timelines, and interview transcripts remain on the volume.

- Phone browser QA found clipped report controls and split-column events; mobile
  now uses full-width timeline cards and shows only the selected platforms.

- Explicit Open agent interviews restores OASIS against saved databases after a
  restart without reset, sign-up, rounds, or graph writes. Restored interview context
  comes from saved personas, events, and transcripts; ephemeral model memory is not
  claimed to survive. Existing reports are reused unless separately regenerated.

- Report and interview screens adapt to phones. Entering the interview screen
  reconnects its saved environment and waits for IPC readiness; it never starts
  simulation rounds or sends a model request just from navigation.

- English is the backend default, including background tasks and browser regional
  language headers. Interview instructions and persona country fields no longer
  force Chinese. New opening posts require an exact agent ID/name match.
- Reports read persisted actions/rounds directly and distinguish source claims,
  scripted conditions, synthetic responses and interpretation. Graph entity counts
  are no longer presented as active participant counts.
- Added an explicit, bounded eight-round facilitated strategic workshop using
  sixteen dossier-grounded stakeholder archetypes. Every round records genuine
  OASIS model replies and publishes them for subsequent rebuttals; source evidence
  stays private on the volume, with its checksum retained. This is a qualitative
  exercise, not calibrated forecasting or independent randomized scenario arms.

Blast radius: checked locale propagation, generated profiles, seed identity, worker
rounds, persisted events, report evidence, interview prompts, phone chat and prior
run reads. Original histories remain intact; graph memory stays off for this run.

- Report reader-barrier fixture targets its upstream handler directly; lab lifecycle
  validation has separate coverage. Locale/persona/evidence and existing lifecycle
  checks passed (50), with report/JSON checks exercised separately.

- Organizational workshop profiles supply required OASIS demographic fields as
  unspecified values; failed-worker messages are English while full diagnostics
  remain in the preserved log.

- Separated Camel memory capacity (32,768 tokens) from the provider reply cap
  (1,024 tokens). The installed Camel version otherwise uses max_tokens for both,
  which rejected dossier-grounded personas before any model call. Both social
  workers and restored interviews share this model adapter.

- Existing projects now have a research workspace: append PDF/Markdown/text to the
  same Zep graph, retain original files and cumulative revision snapshots, show
  durable update history, deduplicate uploads and reconcile recorded batches without
  blindly replaying mutations. Incomplete/ambiguous updates remain visibly blocked.
- New scenarios reuse a project's graph with their own objective, source checksum,
  revision and text snapshot. Previously saved results remain intact. Preparing or
  generating a new report against a changed revision requires a new scenario rather
  than silently using newer knowledge. Historical agent interviews remain available.
- Graph updates serialize with active runs, preparation, reports and reset/delete.
  Agent preparation is explicit, bounded to a displayed 1–50-agent maximum, and
  visiting preparation no longer stops a run. Starts remain explicit.
- Completed the 16-role, eight-round English workshop (128 generated contributions).
  Its report received an explicit editorial evidence review: preserve the original
  draft, distinguish hypothetical constraints from facts, correct ARR arithmetic and
  disclose shared-model/fixed-order unanimity. Generated reports still require review.

Blast radius: checked uploads, duplicate submissions, interrupted batch recovery,
Zep graph lifecycle consumers, project text/files, scenario creation and objective,
preparation, run start, report generation/chat, archived revisions and mobile routing.
No production services or customer research are committed to this repository.
