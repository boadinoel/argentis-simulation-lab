# Simulation Lab model policy

User instruction, 2026-11-13: do not run new research on outdated GPT-4 models.

The Lab default is `gpt-6-astra`, verified against official model documentation
and account access on this date. Use medium reasoning, bounded output and no
automatic model downgrade. Before a new research study, recheck the configured
model against current official guidance; this dated choice is not a perpetual
claim to be the latest. Never silently choose an older/cheaper model to save cost.

New GPT-6 worker calls use Responses, including image and function-tool requests.
The narrow Camel adapter retains tool call IDs and encrypted reasoning only for
matching supplied history. API storage is disabled. Streaming is explicitly
unsupported in this adapter, rather than silently discarding stream settings.
GPT-4/3.5 selections fail before new Lab requests. Old outputs and historical
test fixtures retain their original model labels; upgrading does not relabel them.

Worker `model_receipts.jsonl` records requested/returned model, response ID, endpoint,
completion status and token usage. It never contains prompts, photos, keys or
reasoning. Report the model and limitations in each study. A newer model is not
evidence that synthetic personas represent real people.

Sources checked:
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md
- https://developers.openai.com/api/docs/guides/migrate-to-responses
