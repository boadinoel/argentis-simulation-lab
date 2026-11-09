# Native visual studies

This opt-in worker configuration sends image bytes through OASIS INTERVIEW
ManualActions. It is not a generic upload-screen image picker. Prepare private
images and profiles, then launch through the ordinary simulation start endpoint.
The underlying model must support image inputs; provider errors fail visibly.

```json
{"visual_study":{"version":1,"images":["images/portrait.jpeg"],
 "rounds":[{"prompt":"Assess only these images."},
           {"prompt":"Here is the newly disclosed information..."}]}}
```

Set total rounds to the stage count, enable one platform to avoid duplicate
spending, disable graph-memory writes, and use fresh profiles and a fresh project
whose source contains no withheld information. No initial feed posts or strategic
workshop rounds are allowed in this mode. Personal preferences may be in profiles;
withheld subject facts must appear only in the intended later prompt. The module
never reads future prompts, source documents or graph data into an earlier stage.

Images must be static JPEG, PNG or WEBP, at most four files and 5 MB each, resolving
inside the simulation directory. API requests contain high-detail data URLs.
No URL fetches are performed. Do not commit private images or report contents.

The worker saves visual_requests.jsonl before calls, per-agent stage responses
with image hashes, and native OASIS interview traces. It does not post replies to
a shared feed. History prompts are converted back to strings with image receipts;
the private source images remain on the volume. Each new stage uses only that
agent's saved earlier answers. All prepared agents participate. Model replies
remain unvalidated synthetic judgments, not independent human evidence.

Provider retries are off for this mode. Existing step timeouts still apply; a
missing/empty answer fails the run and retains evidence. Do not silently restart
failed paid studies. A restored interview session is a separate follow-up, not a
replay of the controlled image study. It does not automatically reattach images.

Verification covers image bytes, directory traversal, delayed disclosure,
per-agent memory separation, native OASIS's multimodal contract and textual
history persistence. Ordinary text simulations retain existing behavior.
