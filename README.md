# coref-commitments

A demo pipeline for coreference resolution and commitment extraction across Slack, Email, and Linear. Given a week of workplace messages, it identifies who said what to whom, resolves ambiguous references to the right person, and produces a per-person action-item digest.

The interesting problem is coreference, not commitment extraction. "Alex" can be two people. "I'll" commits in one message and doesn't in the next. A promise made on Slack that gets restated on Linear is one commitment, not two. Pattern matching doesn't solve any of this — context does. The project is currently in the ground-truth annotation phase; pipeline modules follow.

---

## Why this project

Real workplace data is full of references that require context to resolve:

- **Name collisions.** Two people named Alex are active in the same thread. Who does Jamie mean when they write "Alex, can you share that doc?" At the moment of the message, it's genuinely ambiguous. Only the reply disambiguates it.
- **Implicit ownership.** Priya writes "actually I got it" — no "I will", no modal, no explicit deliverable. A regex misses this. It's a commitment.
- **Adversarial "I'll".** Priya also writes "I'll believe it when I see it." This is idiomatic skepticism. A naive extractor that pattern-matches on "I'll" gets it wrong.
- **Cross-tool restatements.** Jamie commits to a staging dry-run on Slack on Monday. On Tuesday she announces on Linear that Sam is handling it instead. On Wednesday Sam confirms via DM. These aren't three commitments — they're one commitment with two modification events.

A dedicated eval can measure whether the pipeline handles these cases. A dedicated eval requires dedicated ground truth. Ground truth requires decisions locked in writing before any annotation happens. That ordering is what this project takes seriously.

---

## Approach: ground truth first

Decisions were written before annotation began. Annotations were authored before any pipeline code was written. This ordering is deliberate: if ground truth is shaped by what the pipeline happens to emit, the eval measures nothing except the pipeline's self-consistency.

The ground-truth workflow:

1. Lock all modeling decisions in `DECISIONS.md` with full rationale.
2. Author `mentions_truth.json` — 82 message rows, one per message, with all mention-level coreference resolution recorded.
3. Author `commitments_truth.json` — 6 commitments, 14 modification events, 7 adversarial non-commitment cases.
4. Author `MESSAGES.md` — a chronological per-message reasoning trace cross-referencing both truth files.
5. Pipeline code follows.

---

## Data model

**Canonical entities** (v1 scope): people and Linear tickets only. No teams, channels, or departments as canonical entities. Promoting channels to canonical entities would require a new resolver path for entities with no aliasing problem — not worth it at this stage.

**External resolution**: People absent from the canonical identity store resolve as `external_unknown`. Jordan Reyes (`jordan@pgconsult.io`) is the deliberate external in v1. The identity store must not be augmented with magic aliases or observational shortcuts.

### Reserved namespaces

String labels used in `owed_to` fields — these are not canonical entity IDs:

| Namespace | Example | Meaning |
|-----------|---------|---------|
| `channel:*` | `channel:db-migration` | Commitment made to a whole channel; not a canonical entity |
| `external:*` | `external:email:jordan@pgconsult.io` | Commitment owed to a person outside the identity store; not a canonical entity |

### `mentions_truth.json` schema

**Message row** — one per message (82 total):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `msg_id` | string | yes | Message ID matching the source file (e.g. `S019`, `E004`, `L008`) |
| `source` | enum | yes | `slack`, `email`, or `linear` |
| `sender_canonical_id` | string | yes | Canonical ID of the message sender, or `external_unknown` for externals |
| `is_filler` | boolean | yes | True for off-topic messages tagged `_note: "filler"` in the source. Filler rows always have `mentions: []` |
| `mentions` | array | yes | List of mention objects; empty array when no annotatable mentions exist |

**Mention object** — one per resolved surface form. Multiple tokens in one message collapse to one row per Decision 11:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `surface` | string | yes | The first surface form token ("I", "Alex", "you", etc.) |
| `surface_count` | integer | no | Total tokens collapsed into this row. Omitted when 1 |
| `category` | enum | yes | One of seven mention categories (see Mention categories section) |
| `resolves_to` | string \| null | yes | Canonical ID of the resolved entity, `external_unknown` for externals, or `null` when ambiguous |
| `candidates` | array | no | Present when `resolves_to` is null; lists the plausible canonical IDs |
| `external_id` | string | no | Present when `resolves_to` is `external_unknown`; namespaced identifier (e.g. `email:jordan@pgconsult.io`) |
| `external_label` | string | no | Display name for the external (e.g. `Jordan Reyes`) |
| `note` | string | no | Annotation reasoning note; not used by the pipeline |

### `commitments_truth.json` schema

**Commitment row** — one per commitment (6 total):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `commitment_id` | string | yes | Stable identifier (e.g. `c_001`) |
| `owner` | string | yes | Canonical ID of the person who made the commitment, or `external_unknown` |
| `external_id` | string | no | Present when `owner` is `external_unknown`; namespaced identifier |
| `external_label` | string | no | Display name when owner is external |
| `owed_to` | array | yes | List of canonical IDs, `channel:*` labels, or `external:*` labels the commitment is owed to |
| `external_labels` | object | no | Present when `owed_to` contains external strings; maps each external string to a display name |
| `task` | string | yes | Plain-language description of the committed deliverable |
| `due` | date | yes | Due date in `YYYY-MM-DD` format |
| `status` | enum | yes | `open`, `in_progress`, or `completed` — snapshot at time of authoring |
| `source_message_ref` | object | yes | Pointer to the originating message (see `source_message_ref` below) |
| `confidence` | enum | yes | `high` or `medium` |
| `confidence_note` | string | no | Required when `confidence` is `medium`; explains the ambiguity |

**Modification event** — one per change to an existing commitment (14 total). Type-specific fields apply depending on `type`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | string | yes | Stable identifier (e.g. `m_007`) |
| `commitment_id` | string | yes | ID of the commitment this event modifies |
| `type` | enum | yes | `due_date_update`, `ownership_transfer`, `status_update`, or `transfer_declined` |
| `new_due` | date | no | Present for `due_date_update` events |
| `new_owner` | string | no | Present for `ownership_transfer` events; canonical ID of the new owner |
| `new_status` | enum | no | Present for `status_update` events; one of `in_progress`, `confirmed`, `completed` |
| `source_message_ref` | object | yes | Pointer to the message that triggered the event |
| `resolution_message_ref` | object | no | Present for `ownership_transfer` and `transfer_declined`; points to the acceptance or decline message |
| `confidence` | enum | yes | `high` or `medium` |
| `confidence_note` | string | no | Required when `confidence` is `medium` |

**Non-commitment row** — adversarial cases the pipeline must not classify as commitments (7 total):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_message_ref` | object | yes | Pointer to the message |
| `reason` | string | yes | Explains why this message does not qualify as a commitment |
| `confidence` | enum | yes | `high` or `medium` |

**`source_message_ref` object** — used across all row types in both truth files:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | enum | yes | `slack`, `email`, or `linear` |
| `msg_id` | string | yes | Message ID matching the source file |

---

## The mock dataset

A 72-hour window: Monday May 11 through Thursday May 14, 2026. One migration project (`ENG-447: Postgres 14 → 16 migration`), three sub-workstreams, seven people, one external consultant.

| Source | Messages |
|--------|----------|
| Slack (`#db-migration` + 2 DM threads) | 59 |
| Email (1 thread, 9 messages) | 9 |
| Linear (3 tickets, 14 comments) | 14 |
| **Total** | **82** |

**People:**
- Priya Patel — schema diff workstream
- Alex Rodriguez — index strategy workstream
- Alex Kim — Frontend Engineering (the other Alex; name collision is deliberate)
- Jamie Wu — staging dry-run (transfers ownership mid-week)
- Sam Okafor — picks up dry-run after Jamie
- Maya Chen (preferred name) / Mei-Ling Chen (legal name) — Engineering Manager; display name doesn't match identity store
- Devon Brooks — Senior PM; owns ENG-447

**External:** Jordan Reyes (`jordan@pgconsult.io`) — external Postgres consultant; not in the canonical store.

**Tickets:** ENG-447 (umbrella), ENG-451 (staging dry-run), ENG-462 (index strategy).

The dataset includes filler messages (off-topic chatter tagged `_note: "filler"` in the source), adversarial cases planted to test false-positive extraction, and several cross-tool restatements of the same commitment.

---

## Ground truth files

### `mentions_truth.json`

One row per message (82 total). Each row records the message ID, source, sender's canonical ID, a filler flag, and a list of mention objects. Each mention records the surface form, category, and resolution target.

Abbreviated example:

```json
{
  "msg_id": "S019",
  "source": "slack",
  "sender_canonical_id": "person_jamie_wu",
  "is_filler": false,
  "mentions": [
    {
      "surface": "Alex",
      "category": "first_name_ambiguous",
      "resolves_to": null,
      "candidates": ["person_alex_rodriguez", "person_alex_kim"]
    },
    {
      "surface": "you",
      "category": "pronoun_within_thread",
      "resolves_to": null,
      "candidates": ["person_alex_rodriguez", "person_alex_kim"],
      "note": "Inherits ambiguity from 'Alex' in same message"
    }
  ]
}
```

This is S019 — the marquee ambiguity case. Jamie asks "Alex, can you share that doc?" when both Alex Rodriguez and Alex Kim are active in the thread. The ground truth records it as genuinely ambiguous at annotation time; the resolution only becomes clear when Alex Rodriguez responds in S020.

Contrast with a resolved case:

```json
{
  "msg_id": "S016",
  "source": "slack",
  "sender_canonical_id": "person_priya_patel",
  "is_filler": false,
  "mentions": [
    {
      "surface": "Alex",
      "category": "first_name_disambiguated_by_context",
      "resolves_to": "person_alex_rodriguez",
      "note": "Index naming convention is Alex Rodriguez's workstream (ENG-462)"
    }
  ]
}
```

Same surface form, different context. Priya asks about index naming convention — that's Alex Rodriguez's workstream. The pipeline needs to know that to get this right.

### `commitments_truth.json`

Six commitments (`c_001`–`c_006`), 14 modification events (`m_001`–`m_014`), and 7 adversarial non-commitment cases.

Abbreviated commitment example:

```json
{
  "commitment_id": "c_005",
  "owner": "person_priya_patel",
  "owed_to": ["person_sam_okafor", "channel:db-migration"],
  "task": "pair with Sam on staging dry-run",
  "due": "2026-05-14",
  "status": "open",
  "source_message_ref": {"source": "slack", "msg_id": "S027"},
  "confidence": "medium",
  "confidence_note": "Implicit assignment via S027 ('actually I got it'); specific time (9am Thursday) fixed in S029/S030."
}
```

Abbreviated modification event example:

```json
{
  "event_id": "m_007",
  "commitment_id": "c_003",
  "type": "ownership_transfer",
  "new_owner": "person_sam_okafor",
  "source_message_ref": {"source": "linear", "msg_id": "L008"},
  "resolution_message_ref": {"source": "slack", "msg_id": "S023"},
  "confidence": "high",
  "confidence_note": "Transfer announced by Jamie on Linear (L008); Sam accepts via DM to Devon (S023)."
}
```

The `non_commitments` section records adversarial cases — messages a naive extractor would plausibly flag as commitments but shouldn't. Each row carries a `reason` field explaining the disqualifier. This gives the future eval a way to measure false-positive rate, not just recall.

### `MESSAGES.md`

A chronological cross-reference of all 82 messages and how each contributes to the two truth files. Covers: which messages create commitments, which are modification events, which are restatements, which are filler, and what the coreference decisions are for each mention. Used as the annotation reasoning trace during authoring.

---

## Mention categories

Seven categories cover all person-mention surface forms in v1:

**`speaker_self_reference`** — First-person surface forms ("I", "me", "my", "I'll", "I'm", "I've") resolving to the message sender's canonical ID. The most common category. Multiple first-person tokens in one message collapse to one row.

> S001: Priya writes "I'm taking the schema diff this week. I'll have it ready by EOD Wed." → `person_priya_patel`. Two surface forms; `surface_count: 2`.

**`external_name_reference`** — Body-text reference to a person not in the canonical identity store, identified by name. Resolves to `external_unknown`; the mention row carries `external_id` and `external_label`.

> S002: Alex writes "pulling Jordan in over email today." → `external_unknown`, `external_id: "email:jordan@pgconsult.io"`, `external_label: "Jordan Reyes"`.

**`first_name_ambiguous`** — A first name that cannot be resolved at annotation time because multiple candidates are plausible in context.

> S019: Jamie writes "Alex, can you share that doc?" with both Alex Rodriguez and Alex Kim active in the thread. → `resolves_to: null`, `candidates: ["person_alex_rodriguez", "person_alex_kim"]`.

**`first_name_disambiguated_by_context`** — A first name resolvable by thread membership, topic, or workstream context.

> S016: Priya asks about the index naming convention — Alex Rodriguez's workstream. "Alex" → `person_alex_rodriguez`.

**`preferred_name_to_legal`** — A display-name reference to someone whose canonical record uses a different legal name.

> S049: Alex Kim writes "Maya knows how to reach me." Maya → `person_maya_chen` (legal name: Mei-Ling Chen).

**`addressed_to`** — Direct address forms naming the recipient rather than referring to a third party.

> Not annotated in v1 for `@here` and similar broadcast addresses — these are group references and fall under Mention Rule 2.

**`pronoun_within_thread`** — Pronouns ("him", "her", "they", "you") whose referent is established by thread or DM context.

> S024: Devon's DM to Sam — "ping me if you need anything." "you" → `person_sam_okafor`.

---

## Commitment model

**What counts:** A stated intention to do a specific task, by a specific person, with no escape clause. Modals ("I can", "I'll") count when task and timing are concrete. Implicit ownership claims without a modal surface form also count (S027: "actually I got it").

**What doesn't count:**
- Conditional offers: "happy to help if you need a frontend perspective" — conditional on being needed (S010)
- Explicit escape clauses: "I think I'll probably get to it if nothing else comes up" — both "probably" and the conditional disqualify it (S026)
- Permission-granting: "Friday AM is fine if it has to slip" — Maya approving Sam's request, not committing to anything herself (L010)
- Sub-tasks of an existing commitment: Alex updating the proposal doc after his call with Jordan is a status update on c_002, not a new commitment
- Meeting attendance: the Friday 2pm stakeholder review is an event category, not a deliverable — out of scope for v1

**Cross-tool restatements** collapse to one row. The originating message wins as `source_message_ref`. When the same commitment is restated on a different platform, that restatement becomes a `status_update` modification event, not a new commitment row.

**Modification events** record changes to existing commitments: `due_date_update`, `ownership_transfer`, `status_update`, and `transfer_declined`. A declined transfer offer gets its own event type so the eval can verify the pipeline recognized the exchange without changing the commitment's state.

**The `non_commitments` section** records seven adversarial cases — selected on the criterion "would a naive pattern-matcher get this wrong?" The section makes the false-positive test self-contained.

---

## Worked examples

### 1. The marquee ambiguity: S019

It's Tuesday morning. Priya has asked Alex Rodriguez about index naming in S016 (Alex responded in S017). Alex Kim chimed in from the frontend team in S018. Now Jamie writes in the thread:

> "Alex, can you share that doc?"

Both Alexes are in this thread. The topic — a wiki doc about index naming — belongs to Alex Rodriguez's workstream. But Jamie doesn't say that. At annotation time, this is recorded as `first_name_ambiguous` with two candidates. The resolution only materializes in S020, when Alex Rodriguez answers with the link.

The pipeline needs to handle this as a genuinely ambiguous case at the point of mention, while being able to retrospectively resolve it from the reply.

### 2. The implicit commitment: S027

Tuesday afternoon. Priya has asked the channel "@here who can pair with Sam on the dry-run Thursday morning?" (S025). Alex Rodriguez hedges: "I think I'll probably get to it if nothing else comes up" (S026 — not a commitment; escape clause disqualifies it). Two minutes later, Priya writes:

> "actually I got it, makes sense since I wrote the schema"

No "I will". No modal. No explicit deliverable stated. But Priya is answering her own question — taking ownership of something she just asked the channel for. This is c_005. A regex misses it. Catching it is part of what the coreference layer exists to do.

### 3. The adversarial "I'll": S009

The same morning as the staging dry-run discussion, Priya writes in the channel:

> "I'll believe it when I see it"

(About the coffee machine being fixed.) This is idiomatic skepticism, not a promise. The pipeline must not pattern-match on "I'll" and emit a commitment. This message is in the `non_commitments` section with `confidence: high` and is also marked `is_filler: true` — the filler designation dominates, and the `mentions_truth.json` row has `mentions: []` even though the "I'll" surface form is there.

The non-commitment row still tests the commitment extractor independently of the mention-layer decision.

### 4. When does a possibility become a commitment: L009 → L011

Wednesday. Sam is running into replication lag issues on the staging dry-run. He posts on Linear (ENG-451):

> "Hitting a snag with the replication lag, might need to push to Friday morning. Maya, can you weigh in on whether that's acceptable given the review?"

This is a request for permission, not a commitment modification. Maya responds: "Friday AM is fine if it has to slip, but loop me in earlier next time." Still not a modification event — this is Maya granting permission.

Then Sam writes: "ack, will do. Updating ETA to Fri AM." (L011)

That's the moment the slip becomes firm. The modification event `m_008` is anchored to L011, not L009. The confidence note explains why: L009 raised a possibility; L011 is where Sam formally updated the ETA.

The pipeline needs to distinguish these three message types: possibility-raised, permission-granted, and commitment-updated. They arrive in sequence within the same ticket thread.

---

## Decisions and mention rules

Fifteen decisions (one retired) and three mention rules govern the annotations. All were locked before annotation began in `DECISIONS.md`. A few representative examples:

**Decision 1 (commitment definition):** The full definition with sub-rules covers modals, escape clauses, sub-tasks, and cross-tool restatements. Two specific calls are locked inside it: S027 counts as a commitment (implicit ownership, no surface modal); E006 ("I'll update the proposal doc tonight") does not mint a new commitment — it's a status update on the existing index strategy commitment.

**Decision 7 (cross-tool restatement):** One row in `commitments_truth.json`, originating message wins. This is the hardest discrimination task for the pipeline — recognizing a restatement as a reference to an existing commitment rather than a new one. Making "one row" the explicit ground-truth rule focuses the eval on exactly this.

**Decision 11 (self-reference collapse):** Multiple first-person surface forms in one message collapse to one `speaker_self_reference` row. The pipeline answers "who does 'I' refer to" once per message; counting every token would inflate mention totals and double-count resolution agreement.

**Decision 14 (filler dominates):** Filler messages get `mentions: []` even when they contain a real disambiguation case (e.g. S045: "wrong channel Alex 😄"). The filler designation is applied uniformly so the eval harness has a clean rule without case-by-case exceptions.

**Mention Rule 1 (no implicit self-references):** A `speaker_self_reference` requires an explicit surface form. "happy to help" with no "I" in the text is not annotated. This keeps the annotation scope to surface-form resolution and out of intent inference.

**Mention Rule 2 (group references out of scope):** "We", "the team", "all" — no canonical entity to resolve to in v1. If group coreference becomes a v2 requirement, it can be added as a new category.

---

## Status and roadmap

| Module | Status |
|--------|--------|
| Use case definition | Done |
| Project setup | Done |
| Mock upstream sources | Done |
| Ground-truth annotations | **Active** |
| Source adapters / normalization | Upcoming |
| Identity resolver | Upcoming |
| Coreference resolver | Upcoming |
| Commitment extractor | Upcoming |
| Eval harness | Upcoming |
| Digest renderer | Upcoming |

**Current state:** Both ground-truth files are authored and locked. `MESSAGES.md` is in the repo. README update (this file) is the remaining task in the ground-truth module before moving to Module 5.

**Next:** Source adapters / normalization — ingesting each source format into a normalized message stream, stripping authoring metadata (the `_note` fields in Slack messages), and preparing input for the resolver layers.

---

## Repo layout

```
coref-commitments/
├── README.md
├── DECISIONS.md           # All modeling decisions with rationale
├── MESSAGES.md            # Per-message annotation reasoning trace
├── pyproject.toml
└── src/
    └── coref_commitments/
        └── data/
            ├── identity/
            │   ├── canonical_entities.json
            │   └── canonical_tickets.json
            ├── mock_sources/
            │   ├── slack_messages.json
            │   ├── email_messages.json
            │   └── linear_comments.json
            └── evals/
                ├── mentions_truth.json
                └── commitments_truth.json
```

The `identity/` directory is the canonical store — the resolution target for all mention types. The `mock_sources/` directory contains the raw message data in shapes close to real API responses (Slack event payloads, email thread format, Linear comment format). The `evals/` directory contains the ground truth files authored against those sources.

Pipeline modules will add directories under `src/coref_commitments/` for adapters, resolvers, extractors, eval harness, and digest renderer as each module is implemented.
