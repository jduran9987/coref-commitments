# coref-commitments

A project exploring LLM-driven coreference resolution across Slack threads, email chains, and Linear comments. The system pulls action items from distributed team communication and resolves every person-mention — first names, pronouns, "I", "me", "him" — to canonical identities, producing per-person digests of who owes what to whom.

Managed with [uv](https://docs.astral.sh/uv/).

## The coreference problem

Coreference resolution is the task of figuring out when different expressions in text refer to the same entity. In *"Alex picked it up — he said he'd be done by Friday,"* a system that wants to understand the sentence needs to know "he" refers to "Alex" and "it" refers to whatever was just discussed. Humans resolve this without thinking. Machines have struggled with it for decades.

Classical NLP approaches used hand-coded heuristics (he/she prefers the nearest gender-matching subject) and later statistical models trained on annotated corpora like OntoNotes. These work moderately well on edited news text. They fail on workplace conversation, which is harder in nearly every way that matters: messages are short and context-poor, references are implicit (*"got it,"* *"I'll take this"*), coreference chains span tools (a Slack thread continues in email, then resolves in a Linear comment), first names collide ("Alex" might be one of two people), and the same person has different identifiers in every system.

LLMs help here for three reasons traditional models can't match: broad world knowledge, in-context reasoning over heterogeneous conversation history, and the ability to weigh soft signals (thread participants, team membership, recent mentions, pronouns) without explicit rules. They're not magic — genuinely ambiguous cases still fail — but they raise the floor enough to make tools like this one viable.

LLMs do *not* solve identity reconciliation across systems. Knowing that Slack user `U07MAYA` and Linear user `mchen` are the same person is the job of a deterministic consolidation pipeline reading upstream APIs (HRIS, IdP, per-tool user directories). The LLM picks up where that store ends: resolving "him," "Maya," "their manager," and "the dry-run" against canonical entities at the message level.

## This project

We're building an **action-item tracker** that pulls commitments from Slack, email, and Linear, resolves every person-mention to a canonical identity, and produces a daily per-person digest of what each engineer owes and is owed. The coreference layer is the load-bearing piece: a message like *"I'll have it ready by EOD Wed"* contains no resolvable identifier on its own. The system has to know who "I" is (the Slack author), who's implicitly owed (the channel), and that this is a real commitment, not a hedge (*"I'll probably get to it if nothing else comes up"*).

### Scenario

The project simulates 72 hours of activity at a fictional company (Acme) where the Platform engineering team is in the middle of a Postgres 14 → 16 migration. There's a stakeholder review Friday afternoon. Three workstreams are running in parallel: a schema diff (Priya), an index strategy review with an external consultant (Alex Rodriguez), and a staging dry-run (initially Jamie, transferred mid-week to Sam).

The cast — seven internal employees and one external consultant — is designed to exercise every coreference case the system needs to handle. **Alex Rodriguez** (Platform) shares a first name with **Alex Kim** (Frontend), creating routine disambiguation work. **Maya Chen**, the engineering manager, has the legal name "Mei-Ling Chen" — her Slack display name says "Maya" but her email and Linear records use "Mei-Ling," so the system must match these to a single canonical person. **Devon Brooks** (PM) tracks the project. **Jordan Reyes**, an external Postgres consultant, appears only in email and has no record in any of the company's internal systems.

Across the 72 hours, the data exercises:

- Speaker resolution across three tools (same person, three different IDs per system)
- Within-thread pronoun resolution
- First-name disambiguation when multiple people share a name
- Implicit assignment (*"@here who can help?"* → *"I got it"*)
- Ownership transfer with cross-tool confirmation
- Transfer offered but declined — should *not* move the commitment back
- Due-date updates on existing commitments vs new commitments
- Status updates rolling up to existing commitments
- External unknowns (Jordan, no canonical record)
- Preferred-name vs legal-name divergence
- Deliberate non-commitments — hedges, conditional offers, permission-granting — that look like commitments to a naive extractor

The expected output is a Slack DM digest delivered to each engineer Friday morning, listing their open commitments and what others owe them, with each row linked back to the source message.

## Repository layout

```
.
├── pyproject.toml
├── README.md
└── src/
    └── coref_commitments/
        ├── __init__.py
        └── data/
            ├── identity/
            │   ├── canonical_entities.json    # People, consolidated from HRIS / IdP / Slack / Linear
            │   └── canonical_tickets.json     # Linear tickets
            └── mock_sources/
                ├── slack_messages.json
                ├── email_messages.json
                └── linear_comments.json
```

**Identity stores.** The two files in `data/identity/` represent what a consolidation pipeline would produce by joining upstream systems (HRIS like Workday, the identity provider like Okta, Slack's `users.list`, Linear's GraphQL users query). Fields are strictly limited to what real upstream APIs expose — no observational data, no learned aliases, no nicknames. Pronouns are sparse (only set when the person has explicitly filled in the field), which mirrors production reality. Jordan Reyes is deliberately *not* in the entity store: external consultants have no HRIS record, no Slack identity, and no Linear account. Handling these unresolved senders is part of the project's challenge, not something the data pre-solves.

**Mock upstream sources.** The three files in `data/mock_sources/` are shaped like real API responses (Slack's `conversations.history`, Gmail thread format, Linear's GraphQL comment shape). Source adapters can later be swapped to hit live APIs without rippling through the rest of the pipeline. Some Slack messages contain a `_note` field marking authoring annotations (filler messages, specific test cases) — these are documentation, not data, and should be stripped during ingestion.
