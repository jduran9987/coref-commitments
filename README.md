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

The project simulates 72 hours of activity at Acme, a fictional company, where the Platform engineering team is two weeks into a Postgres 14 → 16 migration. There's a stakeholder review Friday afternoon. Three workstreams are running in parallel: a schema diff, an index strategy review with an external consultant, and a staging dry-run.

The cast:

- **Priya Patel** — Platform engineer, owns the schema diff
- **Alex Rodriguez** — Platform engineer, owns the index strategy review
- **Alex Kim** — *Frontend* engineer, occasional drive-by participant; shares a first name with Alex Rodriguez
- **Jamie Wu** — Platform engineer, initially owns the staging dry-run
- **Sam Okafor** — Platform engineer, takes over the dry-run mid-week
- **Maya Chen** — Platform engineering manager; legal name Mei-Ling Chen, Slack shows "Maya", email and Linear use the legal name
- **Devon Brooks** — Product manager tracking the project
- **Jordan Reyes** — External Postgres consultant, appears only in email; no internal canonical identity

#### Monday — kickoff

Devon opens the umbrella Linear ticket with the week's plan; the team self-assigns to workstreams; Jordan is looped in by email.

**Active entities:** Devon, Maya, Priya, Alex Rodriguez, Jamie, Sam, Alex Kim, Jordan

**Commitments created:**
- Priya → schema diff by Wed EOD *(Slack)*
- Alex Rodriguez → index strategy review by Fri *(Slack + Linear)*
- Jamie → staging dry-run by Thu *(Slack + Linear)*
- Jordan → review notes by Thu *(Email)*

**Non-commitments:**
- Sam: *"I can help wherever needed"* — soft offer, no specific task
- Alex Kim: *"happy to help if you need a frontend perspective"* — general offer

**Coreference challenges:**
- Alex Kim's first appearance establishes the two-Alex collision for the rest of the week
- Jordan has no canonical entity — must be handled as an external sender

#### Tuesday — the messy middle

The two-Alex collision goes live in a Slack thread. Jamie transfers the dry-run to Sam. Priya picks up a second commitment implicitly. Jordan and Alex schedule a call by email.

**Active entities:** Priya, Alex Rodriguez, Alex Kim, Jamie, Sam, Devon, Jordan

**Commitments created:**
- Sam → staging dry-run by Thu *(Slack DM with Devon)* — transferred from Jamie
- Priya → pair with Sam on dry-run, Thu 9am *(Slack, implicit self-assignment)*

**Commitment modifications:**
- ENG-451: ownership transfer Jamie → Sam *(Linear comment + Slack DM confirmation across tools)*

**Non-commitments:**
- Alex Rodriguez: *"I think I'll probably get to it if nothing else comes up"* — hedged

**Coreference challenges:**
- *"Quick q for Alex"* (Priya) → Alex Rodriguez, resolvable by thread context (he owns indexes)
- *"Alex, can you share that doc?"* (Jamie) → genuinely **ambiguous** — both Alexes are active in the thread
- Sam's *"I'll pick it up"* (Slack DM) must dedupe against Jamie's *"Sam is handling this now"* (Linear) — same commitment, two tools

#### Wednesday — slippage and a declined transfer-back

Schema diff slips a day. Sam hits a snag and gets permission from Maya to push. Jamie offers to take the dry-run back; Sam declines. Alex Rodriguez completes the index strategy work by email.

**Active entities:** Priya, Devon, Sam, Maya, Jamie, Alex Rodriguez, Jordan, Alex Kim

**Commitments created:**
- Alex Rodriguez → update proposal doc tonight *(Email)* — completed same evening

**Commitment modifications:**
- Priya's schema diff: due date Wed → Thu *(Slack DM, then channel announcement)*
- Sam's dry-run: due date Thu → Fri AM *(Linear comment, with permission from Maya)*
- Sam's dry-run: transfer back to Jamie offered and **declined** — commitment stays with Sam

**Non-commitments:**
- Maya: *"Friday AM is fine if it has to slip"* — permission, not a commitment
- Jamie: *"if Sam wants me to take the dry-run back I can"* — offer, declined

**Coreference challenges:**
- Priya's DM update + channel announcement should match the *same* existing commitment, not create a duplicate
- Sam tags *"Maya"* on Linear — must resolve to Mei-Ling Chen (Linear stores the legal name)

#### Thursday — convergence

Devon checks status. Three engineers reply with updates on existing work. Jordan signs off. Alex Kim makes another conditional offer.

**Active entities:** Devon, Priya, Sam, Alex Rodriguez, Jordan, Alex Kim, Maya

**Commitments created:** none

**Commitment modifications:**
- Status updates on ENG-447 *(Linear)* roll up to existing commitments — schema diff, dry-run, index strategy — not new commitments
- Sam's *"Confirmed pairing with Priya at 9am Friday"* *(Linear)* and the matching Slack exchange reference the same existing commitment

**Non-commitments:**
- Alex Kim: *"if you need someone to QA the FE after the migration, ping me — Maya knows how to reach me"* — conditional

**Coreference challenges:**
- Three status replies on ENG-447 must each match the right existing commitment by owner + task similarity
- *"Maya knows how to reach me"* — name reference (no pronoun), resolves via `slack_display_name`

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
