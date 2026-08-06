# TRIPWIRE — Final Research-Backed Project Idea

## Final name

**TRIPWIRE — The Adaptive Change-Safety Agent for Data and AI**

## Taglines

> **DataHub maps the organism. Tripwire gives it an immune system.**

> **Every risky change teaches the graph how to stop the next one.**

## One-sentence pitch

Tripwire uses DataHub to discover every dataset, ML model, deployment, and AI agent
affected by a proposed data-code change; generates and executes consumer-specific
safety tests; produces a concrete counterexample when behavior breaks; coordinates
the appropriate fix or approval; and converts accepted findings into permanent
contracts and regression tests so future changes are caught deterministically.

---

## 1. The idea in simple language

A company may have thousands of tables and pipelines. Those tables feed dashboards,
machine-learning models, and autonomous AI agents. A developer can make a tiny SQL
change without realizing that a fraud model or customer-facing agent depends on the
old behavior.

DataHub contains the organizational map:

- which datasets and columns exist;
- what depends on them;
- which features feed which models;
- which models are deployed to production;
- which AI agents consume which data;
- who owns each asset;
- which contracts, quality checks, incidents, and business definitions apply.

Tripwire uses that map during code review. It does not merely say, “This looks risky.”
It asks each important downstream consumer to demonstrate that it still behaves
correctly.

For example, a developer adds this filter:

```sql
WHERE status != 'refunded'
```

The schema has not changed, so an ordinary schema test passes. Tripwire discovers
through DataHub that the table feeds a fraud feature, a production fraud model, and
an AI agent that reviews suspicious transactions. It then compares the old and new
behavior using bounded test data.

Tripwire may find a concrete witness:

```text
Transaction txn_1042

Before the change:
  fraud score = 0.91
  Fraud Review Agent = ESCALATE

After the change:
  fraud score = 0.38
  Fraud Review Agent = APPROVE

Verdict: UNSAFE — a critical behavior changed.
```

Tripwire blocks the merge, explains the exact lineage path, identifies the owner,
and recommends a safe migration. After an owner approves the lesson, Tripwire turns
it into a durable contract or regression test. A similar mistake in the future is
then caught deterministically without depending on fresh AI speculation.

That is the central product idea:

> **Temporary agent reasoning becomes permanent organizational protection.**

---

## 2. The problem we solve

Existing CI checks commonly answer questions such as:

- Does the SQL parse?
- Did the schema change?
- Did dbt tests pass?
- What tables or dashboards appear downstream?
- Did aggregate data values change?

Those checks are useful, but an ML model or AI agent can fail even when all columns
remain present. Filters, joins, aggregation rules, null handling, units, time windows,
and business definitions can change the meaning of data without breaking its shape.

The real question is not only:

> “What might be affected?”

It is:

> “Do the important downstream consumers still satisfy their declared behavior?”

Tripwire bridges the gap between lineage-based impact analysis and executable
consumer safety.

---

## 3. How Tripwire works

### Stage 1 — Resolve the change

Tripwire reads the Git diff and dbt build artifacts. SQLGlot parses old and new SQL
into syntax trees so structural changes are detected deterministically.

The dbt manifest and explicit configuration map a changed file to its exact DataHub
URN. Tripwire resolves dbt-to-warehouse sibling entities rather than asking an LLM
to guess which catalog asset the file represents.

### Stage 2 — Audit DataHub context

Through the DataHub MCP Server and SDK, Tripwire retrieves:

- schema and column metadata;
- upstream and downstream lineage;
- exact paths between changed and critical assets;
- transformation SQL and real query-usage patterns;
- ownership, tags, domains, and glossary terms;
- assertions, active incidents, and relevant context documents;
- ML features, models, training relationships, and deployments;
- registered AI agents, their tools, models, skills, and consumed datasets;
- previous Tripwire Change Passports and accepted regression lessons.

Tripwire also measures context completeness. Empty or capped lineage is never treated
as proof that no dependencies exist.

### Stage 3 — Compile a Change Passport

Tripwire creates a structured, reviewable artifact called a **Change Passport**.

It contains four separated evidence layers:

| Layer | Contents | Authority |
|---|---|---|
| Verified context | URNs, schemas, paths, owners, tags, deployment state | DataHub |
| Change evidence | Modified fields, filters, joins, expressions, aggregations | Deterministic parser |
| Safety evidence | Contract results, diffs, drift metrics, model and agent replays | Executed tests |
| Policy decision | Verdict, required approval, remediation, override rules | Versioned policy |

An inference is never presented as a DataHub fact or an observed test result.

### Stage 4 — Generate and execute consumer-specific tests

Tripwire selects tests based on what DataHub says is downstream:

| Consumer | Example safety checks |
|---|---|
| Dataset or data product | Schema compatibility, row/value diff, nulls, keys, business invariants |
| ML feature | Distribution comparison, missingness, range, units, freshness, leakage rules |
| ML model | Prediction comparison, critical-slice behavior, existing evaluation suite |
| AI agent | Golden-task replay, decision comparison, tool-call trajectory, policy constraints |
| Governed asset | PII boundary, retention, domain, approval, and ownership policy |

The reasoning model proposes hypotheses and tests. Deterministic tools execute the
tests. The model cannot block a change solely because it generated a confident story.

### Stage 5 — Produce an honest verdict

Tripwire has three primary outcomes:

#### `UNSAFE`

A contract, regression test, model evaluation, agent replay, or governance rule
failed. Tripwire can point to concrete evidence or a counterexample.

Action: block and remediate.

#### `SAFE_WITHIN_SCOPE`

Every registered and generated check passed within the declared evaluation scope.
This is bounded evidence, not a mathematical claim that every possible input is safe.

Action: allow with an evidence summary.

#### `UNVERIFIED`

Tripwire cannot establish safety because context or an evaluation oracle is missing.
Examples include capped lineage, an unresolved asset, no model adapter, or an AI agent
with no golden evaluation cases.

Action: require a human owner to review or create the missing test.

This prevents a dangerous false-green result.

### Stage 6 — Act and remember

Depending on the evidence, Tripwire can:

- post a GitHub Check and detailed PR report;
- block a verified unsafe change;
- notify the exact owner from DataHub;
- generate a mechanical SQL patch or compatibility view;
- propose dataset versioning or a consumer migration plan;
- generate a validation query or model-retraining checklist;
- raise and later resolve a DataHub incident;
- save the Change Passport as a DataHub document linked to affected assets;
- propose a new ODCS rule, DataHub assertion, or regression fixture.

Permanent protection requires owner approval. Tripwire does not silently turn its own
guess into organizational policy.

---

## 4. The adaptive-memory loop

The word “adaptive” has a precise meaning in Tripwire:

```text
New change
   ↓
DataHub-grounded investigation
   ↓
Executed safety test finds a failure
   ↓
Human owner reviews the finding
   ↓
Accepted lesson becomes a contract/evaluation fixture
   ↓
Lesson is stored in DataHub and the repository
   ↓
Future similar changes fail deterministically
```

Tripwire does not modify policy autonomously. Human-approved outcomes become durable,
executable knowledge.

This makes DataHub write-back meaningful. The graph is not simply decorated with an
`at-risk` tag; it gains a reusable safety rule that affects a later review.

---

## 5. Final demonstration world

The fictional company is **Vantage Pay**, a fintech with synthetic data and metadata.

```text
raw.transactions
      ↓
staging.stg_transactions
      ↓
analytics.fct_transactions
      ↓
features: txn_velocity_7d + avg_amount_30d
      ↓
fraud_model_v4
      ↓
fraud-scorer-prod
      ↓
Fraud Review Agent
      ↓
ESCALATE / APPROVE
```

The DataHub graph also contains ownership, production criticality, governance tags,
quality assertions, context documents, and the Tripwire agent itself.

### Scenario A — Mechanical interface break

`amount_usd` is renamed to `amount`. Tripwire finds the exact downstream reference,
blocks the change, and generates a valid compatibility patch.

### Scenario B — Semantic behavioral regression

Refunded transactions are filtered out. The schema remains unchanged. Tripwire finds
a transaction whose feature, model prediction, and agent action change. It blocks the
PR and proposes the correct validation/migration path.

### Scenario C — Safe additive change

A nullable unused column is added. All registered checks pass. Tripwire returns
`SAFE_WITHIN_SCOPE`, demonstrating that it does not create alert fatigue.

### Scenario D — The graph has learned

A second PR introduces a similar refund-related mistake. The permanent test created
from Scenario B catches it immediately and cites the earlier Change Passport.

This is the final demo line:

> **The first dangerous change taught Tripwire. The second never had a chance.**

---

## 6. Competitive-differentiation chart

This chart represents capabilities described in the reviewed public documentation.
It does not claim that competitors have no private or undocumented implementations.

| Capability | DataHub impact analysis | Metaplane / Datafold / Recce | Monte Carlo PR Agent | Final Tripwire |
|---|---:|---:|---:|---:|
| Trace downstream impact | Yes | Yes | Yes | Yes, via DataHub |
| Read a PR/dbt change | No | Yes | Yes | Yes |
| Compare old/new table data | No | Yes | Generates or supports validation | Yes, through adapters |
| Trace ML models and deployments | DataHub graph capability | Limited/product-specific | Asset context | Core workflow |
| Trace registered AI-agent consumers | DataHub graph capability | Not the main focus | Not described as the core workflow | Core workflow |
| Replay model behavior | No | Not the main workflow | Validation-oriented | Yes |
| Replay AI-agent decisions and tool calls | No | No documented core workflow | No documented core workflow | Yes |
| Produce a minimal behavioral counterexample | No | Data differences | Risk findings/queries | Core evidence artifact |
| Treat missing context as `UNVERIFIED` | Shows available lineage | Varies | Risk scoring | Explicit safety state |
| Generate fix/migration/approval plan | No | Review workflow | Recommendations/notebooks | Yes |
| Write decision back to DataHub | N/A | External system | External system | Yes |
| Convert accepted lesson into contract/test | No | Reusable checks vary | Monitor/validation workflows | Core adaptive loop |
| Use the remembered lesson in a later PR | No | Product history varies | PR/incident history | Demonstrated end-to-end |

The unique claim is the complete loop, not any individual row in the table:

> **DataHub context → executed cross-consumer evidence → concrete witness → approved
> executable memory → deterministic future protection.**

---

## 7. Open-source contribution opportunity chart

DataHub's official Skills repository currently contains separate workflows for search,
lineage, enrichment, quality, setup, and connector development. Tripwire can contribute
a missing workflow that converts proposed code changes into executable safety cases.

| Contribution | What it adds to DataHub's ecosystem | Independent value |
|---|---|---|
| `datahub-change-safety` Skill | Resolves changed assets, audits lineage completeness, identifies critical consumers, plans tests, and writes a Change Passport | Any coding agent can perform a safer DataHub-grounded change review |
| Change Passport schema/template | A reusable evidence format separating facts, changes, tests, decisions, and resolution | Standardizes auditable agent decisions |
| ML/AI lineage seed example | A complete dataset → feature → model → deployment → AI-agent graph | Helps developers learn and test modern DataHub ML/agent metadata |
| ODCS safety-rule example | Demonstrates converting an accepted incident lesson into an ODCS rule and DataHub assertion | Shows a practical contract-first learning loop |
| MCP/lineage documentation fixes | Documents sibling resolution, truncation handling, context coverage, and OSS write-back fallbacks discovered during implementation | Reduces failure modes for future DataHub agent builders |
| Optional adapter interface | Defines a small protocol for dataset, model, and AI-agent evaluators | Lets the community add new execution backends without changing Tripwire core |

The primary contribution should be the `datahub-change-safety` Skill. The seed world and
documentation can support that contribution, but should not replace it.

---

## 8. What changed from the original idea

| Original Tripwire | Final Tripwire |
|---|---|
| PR risk-classification bot | Adaptive change-safety agent |
| Main output was an LLM risk score | Main output is executed safety evidence |
| Downstream lineage produced a blast-radius report | Lineage selects which consumer tests must run |
| Primarily protected ML models | Protects datasets, ML models, deployments, and AI agents |
| Semantic drift inferred from the SQL diff | Semantic risk becomes a hypothesis tested against bounded examples |
| `PASS / REVIEW / BLOCK` | `SAFE_WITHIN_SCOPE / UNVERIFIED / UNSAFE` |
| Auto-fix was the main action | Patch, compatibility layer, versioning, validation, retraining, or approval are selected proportionately |
| Memory was mostly tags and structured properties | Memory becomes a Change Passport plus approved executable contract/evaluation |
| Later runs could read an old note | Later runs execute the durable rule created from the old outcome |
| Differentiated mainly from DataHub UI | Differentiated from an established market of PR-impact tools |

The original idea asked, “Could this change break something?”

The final idea asks:

> **“What must remain true for every critical consumer, and what evidence do we have?”**

---

## 9. Why this is the best version of the idea

### It makes DataHub essential

Without DataHub, Tripwire does not know the real consumers, ownership, ML deployment
status, agent dependencies, governance context, assertions, or historical decisions.
DataHub is the control plane, not a decorative database lookup.

### It goes beyond shipped impact analysis

DataHub provides the map. Tripwire turns the map into a test plan, executes the plan,
coordinates action, and returns the result to the graph.

### It addresses the crowded competitive market

Research showed that PR comments, blast-radius reports, data diffs, validation queries,
and CI gating already exist. The final concept moves the innovation to cross-consumer
behavioral evidence and durable organizational learning.

### It is technically honest

Tripwire distinguishes verified facts, inferred risk, executed evidence, and policy.
It admits `UNVERIFIED` when it cannot establish safety and describes successful results
as bounded rather than universal proof.

### It creates an unforgettable demonstration

A judge can see one transaction change a production model and an AI agent's action,
then see that failure become a permanent contract that catches a later PR. The value is
visible, causal, and understandable in minutes.

### It produces excellent sample artifacts

The repository can contain Change Passports, counterexamples, generated SQL patches,
ODCS rules, regression fixtures, GitHub reports, and DataHub screenshots. Judges can
evaluate artifact quality even without running the full system.

### It creates a credible open-source contribution

The missing `datahub-change-safety` workflow is useful beyond the hackathon and fits the
structure of the official DataHub Skills project.

---

## 10. Is the idea unique?

Individual pieces are not unique:

- lineage impact analysis already exists;
- dbt and data diffs already exist;
- model and agent evaluation tools already exist;
- data contracts and assertions already exist;
- incident memory already exists.

The originality is in how Tripwire composes them around DataHub:

1. a proposed data-code change selects downstream consumers through the context graph;
2. each consumer receives a different, generated safety evaluation;
3. failures are explained with concrete behavioral counterexamples;
4. missing evidence becomes an honest `UNVERIFIED` outcome;
5. accepted findings become executable contracts and regression fixtures;
6. the next review retrieves and runs the organization's accumulated knowledge.

Based on the public documentation reviewed, this complete combination is strongly
differentiated. The claim should remain “novel composition and workflow,” not “no one
has ever implemented any similar component.”

---

## 11. Is the idea useful?

Yes. It addresses a real organizational failure mode:

- data producers cannot manually know every consumer;
- ML models can degrade without schema failures;
- autonomous agents can turn bad data into real actions;
- generic risk scores are difficult to trust;
- one-time incident knowledge is often lost in chats and postmortems;
- maintaining regression suites manually does not scale with a changing data graph.

Tripwire gives data engineers earlier feedback, ML owners concrete behavioral evidence,
AI-platform teams agent regression protection, and governance teams an auditable record
of who approved what and why.

---

## 12. Honest boundaries

Tripwire must not claim more than it can prove.

- Bounded evaluations cannot establish correctness for every possible input.
- Drift does not automatically mean model quality degraded.
- A missing lineage edge can hide a real consumer.
- AI-agent evaluations require representative golden cases and stable adapters.
- Generated contracts require owner approval.
- Mechanical patches can be automated more safely than semantic business decisions.
- The initial implementation should support dbt/SQL, one ML adapter, and one agent
  replay adapter well before claiming universal stack support.

These boundaries improve the product's credibility rather than weakening its story.

---

## 13. Judging-criteria fit

| Criterion | Why final Tripwire is strong |
|---|---|
| Use of DataHub | Reads schemas, exact lineage, queries, ownership, ML and agent metadata; writes incidents, documents, properties, and reusable lessons back |
| Technical execution | Deterministic identity and SQL parsing, typed evidence, executable adapters, three-state policy, completeness checks, idempotent memory |
| Originality | Cross-consumer safety-test compiler, counterexample witness, and approved contract-learning loop |
| Real-world usefulness | Prevents silent behavioral regressions across data, ML, and increasingly autonomous AI systems |
| Submission quality | Concrete two-PR story, visual causal evidence, sample artifacts, and judge-friendly local/hosted demo |
| OSS bonus | New `datahub-change-safety` Skill plus reusable seed, schema, and documentation contributions |

---

## 14. Final three-minute story

1. Show a one-line refund filter in a pull request.
2. Show DataHub's path from that table to a feature, production model, and Fraud Review Agent.
3. Run Tripwire and reveal the concrete transaction whose final action changes.
4. Show the failed model and agent evaluations and the `UNSAFE` GitHub gate.
5. Apply or display the safe migration and rerun the evaluations successfully.
6. Save the Change Passport and approved new rule into DataHub.
7. Open a second similar PR and show the remembered rule catching it immediately.
8. End with:

> **The first dangerous change taught Tripwire. The second never had a chance.**

---

## 15. Research foundations

- [DataHub MCP Server](https://github.com/acryldata/mcp-server-datahub)
- [DataHub Agent Registry](https://docs.datahub.com/docs/api/tutorials/agent-registry)
- [DataHub ML Model metadata](https://docs.datahub.com/docs/generated/metamodel/entities/mlmodel)
- [DataHub Documents API](https://docs.datahub.com/docs/api/tutorials/documents)
- [DataHub Incidents API](https://docs.datahub.com/docs/api/tutorials/incidents)
- [DataHub ODCS ingestion](https://docs.datahub.com/docs/generated/ingestion/sources/odcs)
- [Official DataHub Skills](https://github.com/datahub-project/datahub-skills)
- [Monte Carlo PR Agent](https://docs.getmontecarlo.com/docs/pr-agent)
- [Metaplane Data CI/CD](https://docs.metaplane.dev/docs/data-ci-cd)
- [Datafold CI](https://docs.datafold.com/deployment-testing/how-it-works)
- [Recce](https://github.com/DataRecce/recce)
- [SQLGlot](https://github.com/tobymao/sqlglot)
- [Explaining Wrong Queries Using Small Examples](https://arxiv.org/abs/1904.04467)
- [VeriEQL bounded SQL equivalence](https://arxiv.org/abs/2403.03193)
- [Evidently drift methods](https://docs.evidentlyai.com/metrics/explainer_drift)
- [LangSmith evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)

---

## Final decision

Build **Tripwire as an adaptive change-safety agent**, not as a generic PR risk bot.

Its core product contract is:

> **TRACE → TEST → WITNESS → ACT → IMMUNIZE**

- **TRACE:** use DataHub to identify every critical consumer.
- **TEST:** compile and execute consumer-specific safety evaluations.
- **WITNESS:** show concrete evidence when behavior changes.
- **ACT:** block, patch, migrate, validate, retrain, or request approval.
- **IMMUNIZE:** convert the accepted lesson into durable graph context and executable protection.

