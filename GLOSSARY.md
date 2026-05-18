# Glossary

## Project-specific terms

**canonical_id** — Stable unique identifier for a person or ticket (e.g. `person_priya_patel`, `ticket_eng_447`). The resolution target for all mention types.

**canonical entity** — An entity with a record in the identity store. v1 scope: people and Linear tickets only. Channels, teams, and externals are not canonical entities.

**mention** — A surface-form reference to a person in a message ("I", "Alex", "him", "Priya"). The unit of coreference annotation. Each mention has a type category and resolves to a canonical_id (or `external_unknown`).

**commitment** — A stated intention to do a specific task by a specific person, with no escape clause. Annotated in `commitments_truth.json`. See Decision 1 for the full definition.

**modification event** — A change to an existing commitment: due-date slip, ownership transfer, status update, or declined transfer. Recorded as a separate row linked to the parent commitment by `commitment_id`.

**non-commitment** — A message a naive extractor would plausibly mis-classify as a commitment. Recorded in the `non_commitments` section of `commitments_truth.json` with a `reason` field. Used to measure false-positive rate.

**filler message** — A Slack message tagged `_note: "filler"` in the source data — off-topic chatter unrelated to the migration. Receives an explicit `mentions: []` row in `mentions_truth.json`. Stripped during ingestion.

**cross-tool restatement** — The same commitment stated in one tool (e.g. Slack) and then repeated in another (e.g. Linear). Collapses to one row; originating message wins as `source_message_ref`. Restatements become modification events of type `status_update`.

**external_unknown** — Resolution label for a person not in the canonical identity store. Jordan Reyes (`jordan@pgconsult.io`) is the deliberate external in v1. Commitment rows where an external is the owner carry `owner: "external_unknown"`, `external_id`, and `external_label`.

**`channel:*` namespace** — Reserved string prefix for `owed_to` values when a commitment is made to a whole channel (e.g. `"channel:db-migration"`). Not a canonical entity type — no identity record exists. Digest renderer special-cases the prefix at render time.

**external_name_reference** — Mention category for a body-text reference to a person not in the canonical identity store, identified by name (e.g. "Jordan" in S002, L001). Resolves to `external_unknown`; the mention row carries `external_id` and `external_label`. Distinct from `first_name_disambiguated_by_context`, which assumes a canonical resolution target. See Decision 10.

**speaker_self_reference** — Mention category for first-person surface forms ("I", "me", "my", "I'll", etc.) that resolve to the message sender's canonical_id. Multiple first-person tokens in one message collapse to one row per Decision 11. When the sender is an external, resolves to `external_unknown` with `external_id` per Decision 12.

**first_name_ambiguous** — Mention category for a first name that cannot be resolved at annotation time (e.g. "Alex" in S019, where both Alex Rodriguez and Alex Kim are active in the thread).

**first_name_disambiguated_by_context** — Mention category for a first name resolvable by thread, topic, or workstream context (e.g. "Alex" in S016 resolves to Alex Rodriguez because index naming is his workstream).

**preferred_name_to_legal** — Mention category for a display-name reference to someone whose canonical record uses a different legal name (e.g. "Maya" → Mei-Ling Chen).

**addressed_to** — Mention category for direct address forms ("@here", "@Sam") that name the recipient rather than referring to a third party.

**pronoun_within_thread** — Mention category for pronouns ("him", "her", "they", "you") whose referent is established by thread context.

**ground truth** — Hand-written correct answers used to score pipeline output. In this project: `mentions_truth.json` and `commitments_truth.json`. Authored before pipeline code.

**eval harness** — The script that runs the pipeline, matches its output to ground truth, and reports precision/recall scores per mention category and per commitment type.

## General LLM / eval terms

**precision** — Of the items the pipeline emitted, what fraction were correct? High precision = low false-positive rate.

**recall** — Of the correct items that exist in ground truth, what fraction did the pipeline find? High recall = low false-negative rate.

**RAG (Retrieval-Augmented Generation)** — Pattern where a model retrieves relevant document chunks at query time rather than relying on training data. Used here as a metaphor: project files in knowledge serve as RAG-retrievable context rather than being loaded in every message.
