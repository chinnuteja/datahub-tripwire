# Tripwire, explained from zero

Written in plain language. No prior knowledge assumed. Read top to bottom before recording
the demo video.

---

## 1. What is DataHub, and why does it exist?

A modern company does not keep its data in one place. It keeps it in hundreds of database
tables, which feed other tables, which feed machine-learning models, which feed dashboards
and automated systems that make real decisions — approving a payment, flagging a customer,
reordering stock.

Nobody can hold that whole map in their head. So people started asking questions nobody
could answer:

- *Where does this number actually come from?*
- *If I change this table, what breaks?*
- *Who owns this thing? Who do I ask?*

**DataHub is the map.** It is an open-source catalog that records every data asset a
company has, how they connect to each other (this is called **lineage**), who owns them,
and what they mean. LinkedIn built it and open-sourced it; Apple, Pinterest and Netflix
use it.

The key idea: DataHub knows **what is connected to what**.

---

## 2. The real-world problem we are solving

DataHub can tell you that Table A feeds Model B. It cannot tell you whether a change you
just made to Table A **broke** Model B.

That gap is where expensive accidents live. Here is the exact shape of one:

> An engineer edits a SQL file. The change looks harmless — a one-word difference in how
> missing values are handled. Every test passes. The pipeline runs green. Nothing errors.
>
> But three steps downstream, a fraud model now scores certain transactions lower. Cards
> that should have been sent for human review are silently auto-approved instead.
>
> Nothing is "broken." No alert fires. The system is confidently wrong, and the company
> loses money for weeks before anyone notices.

This is called a **silent regression**. Normal tests do not catch it, because nothing
crashed. The code is fine. The *behavior* changed.

And it is getting worse, because AI agents now write this SQL. Agents can generate a data
pipeline in seconds. **No agent can prove the pipeline it just wrote is safe.**

---

## 3. What Tripwire is

Tripwire is the thing that proves it — or refuses to.

When someone (a human or an agent) proposes a change to a data pipeline, Tripwire:

1. **TRACE** — asks DataHub who actually depends on this asset. Not a guess; a real query
   to the real catalog through DataHub's official MCP server.
2. **TEST** — actually runs the old code and the new code, feeds both results through the
   real downstream model and the real downstream decision system, and compares what
   happened.
3. **WITNESS** — if behavior changed, it hands you the **exact row** that proves it. Not
   "risk score 7/10." An actual transaction, with the old decision and the new one.
4. **ACT** — blocks the change, and attempts a repair it verifies by re-running everything.
5. **IMMUNIZE** — once a human approves, the failure becomes permanent memory in DataHub,
   so the *next* change that would cause the same problem is caught automatically — even
   if it is written completely differently.

### The single most important idea

Most tools tell you a change is "probably fine." Tripwire has **three** answers, and the
third one is the point:

| Verdict | Meaning |
|---|---|
| `SAFE_WITHIN_SCOPE` | Everything Tripwire could check, it checked, and it passed. |
| `UNSAFE` | It found real, executed proof that behavior changed. |
| `UNVERIFIED` | **It could not prove anything, so it refuses to say "safe."** |

That third verdict is the heart of the project. Missing evidence is never treated as good
news. This rule is enforced in the type system — the code physically cannot produce a
"safe" answer without the evidence to back it.

---

## 4. A concrete example — the story to tell in the video

The demo uses a synthetic fraud-detection pipeline.

**The change:** one word in a SQL file. `COALESCE(device_age_days, 0)` becomes
`COALESCE(device_age_days, 365)`.

In English: *"when we don't know how old a device is, assume it's brand new"* becomes
*"assume it's a year old."* A brand-new device is suspicious. A year-old device is trusted.

**What Tripwire does:** it runs both versions, and finds transaction **TX-009** — a $520
international payment from a device with no recorded age.

| | Old code | New code |
|---|---|---|
| Risk score | 0.62 | 0.44 |
| Fraud probability | 0.669 | 0.498 |
| **Decision** | **review** | **approve** |

That payment used to go to a human. Now it is auto-approved. Nothing crashed. No test
failed. That is the silent regression, caught with a receipt.

**Then it gets interesting.** A human approves this as a rule. Later, someone writes
*completely different* SQL —
`CASE WHEN device_age_days IS NULL THEN 365` — which looks nothing like the first change
but causes the exact same bug. Tripwire catches it, because DataHub remembered.

**That is the moment to film.** It is the difference between a linter and a memory.

---

## 5. What we achieved

### It uses DataHub properly — both directions

Most projects read from a catalog. Tripwire reads **and writes back**, using DataHub's own
built-in features rather than inventing its own:

- An approved rule becomes a real **DataHub Assertion**, appearing in DataHub's own
  Validation tab with genuine pass/fail history.
- A blocked change becomes a real **DataHub Incident**, attached to the affected asset and
  every downstream system that failed.

This matters because the hackathon rules say building *on top of* DataHub's features is
welcome, but rebuilding them from scratch is not. Tripwire produces evidence *for* the
governance surfaces DataHub already ships.

### It refuses to overstate — three honesty rules

1. **A fix that exists is not a fix that shipped.** Even when Tripwire finds *and verifies*
   a repair, the incident stays open and says so: *"a verified fix is available but has not
   been applied."* Only a later run that actually passes closes it.
2. **`UNVERIFIED` claims nothing.** No assertion result, no incident.
3. **A rule's first recorded run is the real failure that created it**, never a synthetic
   pass it did not earn.

### It is not a one-trick demo

A second, unrelated domain (inventory stockout risk) runs through the **same** engine with
its own data schema, its own model, its own downstream agent, and a *different kind* of bug
— proving the engine is domain-neutral rather than hard-coded to the fraud demo.

### It can be checked by a stranger

- `tripwire witness replay` re-derives the failing row in a fresh process, from the SQL
  files alone, with no DataHub involved. If the evidence were fake, this would fail.
- 64 automated tests, 91% enforced code coverage, strict type checking, and CI that runs
  everything on every change.

### It contributes back

While building this, we hit a genuine gap in DataHub's own documentation: it tells Python
users to call a function that only exists in the paid version. We reported it with a fix:
[datahub-project/datahub#19055](https://github.com/datahub-project/datahub/pull/19055).

---

## 6. What "Phase 2" was, and why we deliberately did not build it

The hackathon is called an *Agent* Hackathon, and Tripwire contains no large language
model. It is deterministic: the same input always produces the same output. So we
considered adding one.

**The plan.** Tripwire's automatic repair is currently a narrow rule — it can only reverse
one specific kind of mistake. The idea was to let an LLM *propose* the fix instead, then
run that proposal through the existing verification: execute it, compare against the
original behavior, and **reject it unless the results match exactly**. Up to three attempts,
each time feeding the model the real failing rows.

The slogan would have been: *the LLM proposes, the database decides.*

**Why we did not build it.**

1. **The brief does not require it.** The "Production ML Agents" challenge asks for
   something that *"uses DataHub's end-to-end ML lineage… to catch silent problems that can
   break ML systems before they cost money."* That is a description of Tripwire.
2. **Tripwire is already agent-facing.** It ships as an Agent Skill, so any coding agent
   can call it. It reads DataHub through the MCP server, takes action, and writes results
   back so the next agent inherits the knowledge — which is the brief's own wording.
3. **The cost was real.** It would add an external dependency and randomness to a project
   whose entire credibility rests on being deterministic and reproducible.
4. **Time.** Adding a half-finished AI feature on deadline day, to a project whose whole
   argument is *"never claim what you cannot prove,"* would have undercut the thing that
   makes it good.

This was a deliberate engineering decision, not an omission. It is worth saying out loud in
the video: **Tripwire is the verification layer agents call — the thing that makes agent-written
data code trustworthy.**

---

## 7. What to record

Three minutes maximum. Suggested shape:

**0:00–0:25 — The problem.** One sentence: agents can write SQL, nothing can prove it is
safe. Show the one-word SQL change.

**0:25–1:10 — The catch.** Run the unsafe assessment. Show `UNSAFE`, and show TX-009 with
review → approve. Emphasise: nothing crashed, no test failed.

**1:10–1:50 — The memory (your strongest 30 seconds).** Show the *different* SQL being
caught by the rule learned from the first failure.

**1:50–2:30 — DataHub.** Open the Validation and Incidents tabs and show Tripwire's
findings living inside DataHub itself. Read the incident message aloud — *"a verified fix is
available but has not been applied"* — and explain why it is not marked resolved.

**2:30–3:00 — Trust.** `UNVERIFIED` means it refuses to guess. Mention the second domain,
the tests, and the upstream DataHub contribution.

### Before you hit record

```powershell
# start DataHub if you want the UI on camera (needs Docker running)
uv run datahub docker quickstart --version v1.7.0 --accept-version-default

# the unsafe catch
uv run tripwire assess --candidate unsafe_semantic `
  --context-file examples/contexts/fraud-feature-recorded.json `
  --output artifacts/runtime/demo-unsafe.json

# the learned catch — the best moment
uv run tripwire assess --candidate unsafe_related `
  --output artifacts/runtime/demo-related.json

# proof anyone can re-run
uv run tripwire witness replay --passport examples/minimized-witness-passport.json `
  --baseline-sql demo/fraud/sql/baseline.sql `
  --candidate-sql demo/fraud/sql/unsafe_semantic.sql
```

The DataHub dataset page:

```
http://localhost:9002/dataset/urn:li:dataset:(urn:li:dataPlatform:duckdb,tripwire_fraud.fraud.fct_fraud_features,PROD)
```

---

## 8. One line, if you only get one

> **DataHub maps the organism. Tripwire gives it an immune system — one that remembers
> every infection, and refuses to say "healthy" when it cannot prove it.**
