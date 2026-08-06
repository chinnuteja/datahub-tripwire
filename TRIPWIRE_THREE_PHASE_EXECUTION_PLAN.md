# Tripwire — Three-Phase Vertical-Slice Execution Plan

## Mission

Build one complete path so convincingly that every important claim can be demonstrated,
replayed, and inspected:

```text
real dbt/SQL diff
  → real DataHub MCP context
  → baseline/candidate DuckDB execution
  → fraud feature comparison
  → deterministic model replay
  → Fraud Review Agent replay
  → minimized failure witness
  → GitHub verdict
  → DataHub Change Passport
  → human-approved reusable protection
  → second related change caught
```

The governing product contract is [docs/PRODUCT_CONTRACT.md](docs/PRODUCT_CONTRACT.md).
This plan deliberately excludes the optional upstream open-source contribution, which
the project author will pursue separately. The core will still publish reusable schemas
and fixtures so that contribution can be built without reworking Tripwire.

## Baseline audit — 5 August 2026

### Present before implementation

- [x] Final research-backed concept and competitive positioning.
- [x] Apache 2.0 license.
- [x] Python package skeleton and working `tripwire version` CLI command.
- [x] Minimal pytest and Ruff configuration.
- [x] Product contract with explicit verdict semantics and thirteen acceptance criteria.
- [x] This gated execution plan.

### Not implemented yet

- [ ] No DataHub instance, seeded graph, authentication, or MCP integration.
- [ ] No demo dbt/SQL project or versioned DuckDB data.
- [ ] No model or Fraud Review Agent runtime.
- [ ] No SQL diff parser, entity resolver, or Context Coverage audit.
- [ ] No baseline/candidate evaluator or counterexample minimizer.
- [ ] No policy engine, Change Passport, DataHub write-back, or learned protection.
- [ ] No GitHub Check, web application, hosted demo, sample output, or end-to-end test.

### Corrections made during the audit

- [x] Replaced the older `JUDGE → ACT → REMEMBER` framing with
  `TRACE → TEST → WITNESS → ACT → IMMUNIZE`.
- [x] Replaced `PASS / REVIEW / BLOCK` with the honest safety states
  `SAFE_WITHIN_SCOPE / UNVERIFIED / UNSAFE`.
- [x] Changed the core claim from inferred risk to executed consumer behavior.
- [x] Made Context Coverage, concrete witnesses, human-approved memory, and the
  learn-then-catch scenario mandatory.
- [x] Clarified that mocks cannot power the judge-facing headline path.

## Execution rules for every phase

- A checked box means a committed artifact or automated test proves the claim; it does
  not mean “code exists somewhere.”
- We do not enter the next phase until the current phase's exit gate passes.
- The real headline path must never silently fall back to mock DataHub context.
- Failures are explicit: missing context, ambiguous identity, unavailable execution, or
  incomplete evaluation produces `UNVERIFIED` with a reason code.
- All demo inputs, seeds, configuration, expected outputs, and policy versions are pinned.
- Every external operation is retryable, idempotent where applicable, and accompanied by
  a useful error message.
- Scope stays narrow until the path is excellent. Additional warehouses, model types, or
  agent frameworks are stretch work only after Phase 3 passes.

## Scalable architecture locked before feature work

```text
tripwire/domain/           typed entities, verdicts, evidence, passports
tripwire/ports/            provider interfaces and capability contracts
tripwire/providers/        DataHub MCP/API and GitHub adapters
tripwire/change/           dbt identity and SQL diff analysis
tripwire/evaluators/       dataset, feature, model, and agent evaluations
tripwire/witness/          counterexample search and minimization
tripwire/policy/           deterministic versioned decision rules
tripwire/memory/           passport write-back and protection lifecycle
tripwire/application/      use cases and orchestration
tripwire/api/              stable API consumed by CLI and web UI
demo/                      seeded fraud system and declared scenarios
tests/                     unit, contract, integration, end-to-end, golden
examples/                  committed judge-visible outputs
web/                       polished judge-facing interface
```

This is a modular monolith, not premature microservices. Typed ports let us replace
DuckDB, the model runtime, GitHub, or DataHub transport without putting provider-specific
logic inside the safety engine. A run manifest and stable schema make later workers or a
queue possible without redesigning the domain.

---

# Phase 1 — Build the Truth Spine

## Outcome

From one command, create the deterministic fraud demo world, seed its full graph into a
real DataHub instance, and prove through genuine MCP reads that Tripwire can resolve a
changed dbt node and trace it to the feature table, model, deployment, AI agent, owners,
and governance context. No safety verdict is claimed in this phase.

## 1.1 Repository and domain foundation

- [x] Create the modular package boundaries defined above without circular imports.
- [x] Define Pydantic schemas for `ChangeRequest`, `EntityRef`, `ContextFact`,
  `LineagePath`, `ContextCoverage`, `EvaluationSpec`, `EvaluationResult`,
  `Counterexample`, `Verdict`, `ChangePassport`, and `Protection`.
- [x] Add stable JSON Schema exports for Change Passports and protections.
- [x] Give every run a content-derived ID, UTC timestamps, tool/policy versions, commit
  SHA, and input hashes.
- [ ] Define machine-readable reason codes for every `UNVERIFIED` condition.
- [x] Add configuration loading with checked-in safe defaults and `.env.example`; secrets
  must be environment-only.
- [ ] Add structured logs with automatic secret and raw-sensitive-field redaction.
- [ ] Lock development gates: Ruff, static typing, pytest, coverage for core logic, and
  dependency audit.

## 1.2 Deterministic fraud system

- [ ] Create a small dbt-compatible SQL project with baseline, unsafe semantic,
  mechanical-break, safe-additive, and second-related changes as real patches/commits.
- [x] Create a versioned synthetic transaction dataset containing ordinary traffic and
  boundary cases; use fixed seeds and document the data dictionary.
- [x] Execute the baseline transformation in DuckDB and produce a fraud feature table.
- [x] Implement and serialize one deterministic, inspectable fraud model with a pinned
  feature contract and threshold.
- [x] Implement a deterministic Fraud Review Agent that consumes the model output and
  selected transaction context and returns a typed action plus reasons.
- [x] Add golden tests proving identical input produces identical feature, prediction,
  and agent outputs on repeated runs.
- [x] Ensure at least one semantic change can eventually flip a meaningful model/agent
  decision without relying on random chance or a hard-coded verdict.

## 1.3 Real DataHub demo graph

- [ ] Pin a supported DataHub quickstart/container version and record its image digests.
- [ ] Provide a one-command bootstrap plus readiness/health checks and an explicit reset
  command whose exact targets are documented.
- [ ] Seed raw datasets, dbt models, schema fields, column lineage, owners, domains, tags,
  quality/governance signals, feature/model/deployment relationships, and the AI agent.
- [ ] Register the Fraud Review Agent with its consumed datasets, model, tools, and owner
  so it is a real graph consumer rather than a label in Tripwire.
- [ ] Make the seed operation idempotent and verify no duplicate entities after reruns.
- [ ] Export a human-readable seed manifest mapping every demo artifact to its exact URN.
- [ ] Capture screenshots or queries proving the graph is visible in DataHub itself.

## 1.4 Genuine MCP context adapter

- [x] Configure and document the official DataHub MCP path used by the application.
- [ ] Implement a typed MCP adapter for entity lookup, schema fields, lineage, ownership,
  tags/governance, models/deployments, AI agents, and saved Tripwire memory.
- [x] Save raw response envelopes and normalized facts with source operation, entity URN,
  retrieval time, and truncation/pagination information.
- [x] Resolve dbt nodes from `manifest.json`, environment/platform mappings, and exact
  URNs; fuzzy matching is forbidden in the decision path.
- [ ] Detect dbt/warehouse siblings and traverse the graph without treating duplicates as
  separate business assets.
- [ ] Detect empty, capped, cyclic, stale, unauthorized, or ambiguous context and reflect
  it in `ContextCoverage`.
- [ ] Implement a labeled snapshot adapter only for unit tests/offline exploration; make
  the UI and report visibly identify the provider in use.

## 1.5 Phase 1 tests and evidence

- [ ] Unit-test identity normalization, cycle handling, pagination, coverage calculation,
  reason codes, and serialization.
- [ ] Contract-test MCP response normalization against captured real responses.
- [ ] Integration-test seeding and MCP retrieval against a fresh DataHub instance.
- [ ] Prove that changing the seeded graph changes the discovered path; this defeats a
  hard-coded lineage implementation.
- [ ] Prove that removed permissions, missing lineage, and ambiguous identity do not
  become “no downstream impact.”
- [ ] Commit a redacted Phase 1 context bundle in `examples/` for judges.
- [ ] Document exact Windows/Linux prerequisites and fresh-clone commands.

## Phase 1 exit gate — “The graph is the truth”

All of the following must pass before Phase 2:

- [ ] A fresh environment boots and seeds DataHub with one documented command.
- [ ] A real SQL/dbt artifact maps deterministically to the expected DataHub URN.
- [ ] Genuine MCP reads reconstruct the path from changed transformation through feature,
  model, deployment, and Fraud Review Agent, including owners and governance context.
- [ ] The result changes when the DataHub graph changes, with no code modification.
- [ ] Missing critical context yields a specific incomplete-coverage result.
- [ ] Unit, contract, integration, lint, type, and secret-scan gates are green.
- [ ] No mock or static blast-radius list participates in the recorded headline proof.

### Failure-busting checks

- Kill DataHub during retrieval: the run must fail clearly and remain retryable.
- Cap lineage depth: Context Coverage must expose the unresolved frontier.
- Create two plausible entity matches: resolution must stop as ambiguous.
- Seed twice: entity and relationship counts must remain stable.
- Remove the model/agent edge: Tripwire must no longer claim it discovered that consumer.

---

# Phase 2 — Build the Evidence Engine and Wow Moment

## Outcome

Given a real diff and the MCP-derived consumer path, execute baseline and candidate
behavior end to end, find a minimized transaction that demonstrates a critical behavior
change, and issue a reproducible `UNSAFE`, `SAFE_WITHIN_SCOPE`, or `UNVERIFIED` verdict.
This phase creates the technical centerpiece judges will remember.

## 2.1 Deterministic change understanding

- [x] Parse git/dbt/SQL changes with an AST-capable parser; line diffs are display-only.
- [x] Classify changed projections, aliases, predicates, joins, aggregations, windows,
  casts, null handling, and referenced columns.
- [ ] Bind the change to the exact dbt node and baseline/candidate compiled SQL.
- [ ] Reject unsupported or partially parsed constructs as `UNVERIFIED`, never guessed.
- [x] Record parser version, normalized AST change, file/line evidence, and code hashes.
- [ ] Test formatting-only, comments-only, semantically equivalent, mechanical breaking,
  and semantic-change examples.

## 2.2 Consumer-aware test compilation

- [ ] Convert DataHub consumer types, criticality, contracts, governance, and remembered
  protections into an explicit `EvaluationPlan` before executing anything.
- [ ] Require dataset/schema, feature, model, and AI-agent evaluators for the headline
  critical path.
- [ ] Show why each evaluation was selected and which graph fact required it.
- [ ] Report uncovered critical consumers or unavailable runtimes as `UNVERIFIED`.
- [ ] Version the evaluation-plan compiler independently from decision policy.
- [x] Add tests proving different graph metadata compiles a different plan.

## 2.3 Old-versus-new execution

- [ ] Materialize isolated baseline and candidate DuckDB states from identical inputs.
- [ ] Enforce resource/time limits and capture deterministic execution diagnostics.
- [ ] Compare schema, row behavior, key uniqueness, nulls, aggregates, and fraud features.
- [ ] Replay the pinned model on both feature outputs and compare predictions, scores, and
  threshold crossings.
- [ ] Replay the Fraud Review Agent on both results and compare its typed actions/reasons.
- [ ] Preserve a compact evidence table linking each observation to the exact input row
  and consumer.
- [ ] Make evaluator errors distinguishable from failed evaluations; errors produce
  `UNVERIFIED`, not `UNSAFE` or safe.

## 2.4 Counterexample search and minimization

- [x] Search the bounded synthetic domain for inputs that cause a critical baseline/
  candidate behavior difference.
- [x] Minimize the first failing transaction while preserving the failure.
- [x] Verify the minimized witness by replaying the entire transformation → model → agent
  chain in a clean process.
- [x] Explain the causal path using observed values, not an LLM narrative.
- [x] Save the witness as a portable, privacy-safe fixture with provenance and hashes.
- [ ] Prove that changing/removing the harmful SQL removes the failure.

## 2.5 Honest policy and Change Passport

- [ ] Implement the three-state policy as pure, versioned, table-driven rules.
- [ ] Require sufficient Context Coverage plus all critical evaluations passing before
  `SAFE_WITHIN_SCOPE` is possible.
- [ ] Return `UNSAFE` only for an executed critical failure or configured hard governance
  rule, with the violated rule and owner action.
- [ ] Return `UNVERIFIED` for missing context, unsupported SQL, runtime failure, uncovered
  critical consumer, or inconclusive evaluation.
- [ ] Assemble a signed/hash-verifiable Change Passport separating DataHub facts, change
  facts, execution observations, policy, limitations, and artifacts.
- [ ] Render the same passport as JSON, concise Markdown, and a UI/API view.
- [ ] Add schema-migration/version-compatibility tests for the passport format.

## 2.6 Headline scenario proof

- [ ] Mechanical break returns `UNSAFE` with the actual failing contract/reference.
- [ ] Semantic change returns `UNSAFE` with one minimized transaction showing feature,
  model, and agent behavior before and after.
- [ ] Safe additive change returns `SAFE_WITHIN_SCOPE` without noisy invented risk.
- [ ] Deliberately missing model runtime returns `UNVERIFIED` with remediation steps.
- [ ] Repeated runs produce byte-stable normalized evidence apart from approved timestamps.
- [ ] Commit all four sample passports and artifacts under `examples/`.

## Phase 2 exit gate — “Show me the transaction”

All of the following must pass before Phase 3:

- [ ] One command evaluates each real patch against MCP-derived context.
- [ ] The semantic scenario displays a concrete transaction whose feature value, model
  result, and Fraud Review Agent action change.
- [ ] The witness replays independently and disappears when the defect is removed.
- [ ] The safe scenario passes only after every declared critical evaluator ran.
- [ ] At least one incomplete-evidence scenario produces `UNVERIFIED`.
- [ ] Property/mutation tests show the verdict is derived from behavior and policy, not
  from scenario names, filenames, or hard-coded expected results.
- [ ] All passports validate against the public schema and state exact scope/limitations.
- [ ] Core unit, integration, end-to-end, determinism, lint, type, and security gates pass.

### Failure-busting checks

- Rename scenario files and randomize non-semantic row order: verdicts must not change.
- Corrupt one evaluator output: schema validation must stop policy evaluation.
- Make the model runtime unavailable: the system must not return safe.
- Supply a schema-preserving harmful predicate: schema checks alone must not pass it.
- Supply a harmless formatting-only diff: Tripwire must avoid a false alarm.
- Replay the witness in a separate clean process: the same critical difference must occur.

---

# Phase 3 — Close the Loop and Make It Judge-Proof

## Outcome

Turn the evidence engine into a complete product: publish a real GitHub decision, write
the Change Passport to DataHub, require human acceptance before converting the witness
into durable protection, and prove that a different later change is caught by that
remembered protection. Package the whole story as a polished, hosted, reproducible demo.

## 3.1 GitHub workflow and safe action

- [x] Build a GitHub Action/Check adapter with minimal documented permissions.
- [x] Post verdict, Context Coverage, causal path, witness, owners, scope, limitations,
  and deep links without exposing secrets or sensitive raw rows.
- [x] Map `UNSAFE` to a failing check, `SAFE_WITHIN_SCOPE` to passing, and `UNVERIFIED`
  to the configured evidence/approval gate.
- [x] Make comments/check updates idempotent using the stable run/change ID.
- [x] Support a fully local GitHub-style report for reviewers without credentials.
- [ ] Generate remediation suggestions only when mechanically verifiable; label every
  suggestion and require review rather than silently editing code.
- [ ] Test retries, duplicate webhooks, renamed branches, forked PR restrictions, API rate
  limits, and unavailable GitHub.

## 3.2 DataHub write-back and adaptive memory

- [ ] Enable only the required DataHub mutation capabilities and document them.
- [ ] Store the Change Passport in an inspectable DataHub representation and attach its
  stable ID/status to every materially affected asset.
- [ ] Record proposed, accepted, rejected, superseded, and rolled-back lifecycle states.
- [ ] Make writes idempotent and verify stable entity/property counts after retries.
- [ ] Add a human approval operation that promotes a witness into a versioned protection;
  no automatic self-written policy enters enforcement.
- [ ] Materialize the accepted protection as a regression fixture/evaluation rule and,
  where suitable, an ODCS/assertion-compatible artifact.
- [ ] Query DataHub for relevant prior protections during later evaluation planning.
- [ ] Make provenance visible: who approved it, from which change/witness, when, which
  assets it protects, and which version is active.
- [ ] Support disable/supersede/rollback without deleting audit history.

## 3.3 The learned-protection proof

- [ ] Accept the first semantic witness through the real approval flow.
- [ ] Verify the passport and protection appear on the affected assets in DataHub.
- [ ] Introduce a distinct second SQL change that violates the same invariant through a
  different expression or code shape.
- [ ] Prove the second evaluation plan retrieves the learned protection from DataHub.
- [ ] Execute the remembered fixture/rule and return `UNSAFE` with the new evidence.
- [ ] Prove that disabling the protection in DataHub changes the compiled plan, while core
  built-in evaluations remain intact.
- [ ] Commit before/after graph evidence and both passports in `examples/learned-loop/`.

## 3.4 Product-grade judge experience

- [ ] Build a polished web interface over the same application API used by the CLI; do
  not duplicate verdict logic in the frontend.
- [x] Design a five-part story view: Trace, Test, Witness, Act, Immunize.
- [ ] Show live-vs-snapshot provider status prominently and default the hosted headline
  demo to a real integration whenever the platform permits it.
- [ ] Let a judge run the unsafe, safe, unverified, and learned-protection scenarios with
  clear progress, recoverable errors, and no hidden setup knowledge.
- [ ] Add an architecture view, context-coverage panel, evidence provenance, DataHub and
  GitHub links, raw passport download, and replay button.
- [x] Meet keyboard, contrast, responsive-layout, loading, empty, and failure-state checks.
- [ ] Add telemetry limited to operational events; never collect sensitive transaction
  content.

## 3.5 Reproducibility, deployment, and submission assets

- [ ] Provide a fresh-clone quickstart with pinned prerequisites and one primary command.
- [ ] Add container health checks, migrations, seed verification, backup/reset guidance,
  and clean teardown scoped only to Tripwire resources.
- [ ] Run the full story in CI against the real seeded DataHub service, not snapshots only.
- [ ] Add a public hosted demo or a dependable hosted application plus fallback recorded
  scenario artifacts.
- [x] Create an `examples/` index with passports, reports, witnesses, graph proof, and
  generated protections that judges can inspect without running anything.
- [ ] Write the final README: problem, differentiation, architecture, security model,
  five-minute setup, demo path, limitations, and troubleshooting.
- [ ] Confirm Apache 2.0 is detected at repository top level and repository metadata links
  are correct.
- [ ] Produce a sub-three-minute demonstration script and shot list centered on the
  semantic witness and learned-protection reveal.
- [ ] Rehearse the video path from a clean state and capture a complete backup recording.
- [ ] Run fresh-machine testing on Windows and Linux and record exact versions/results.

## Phase 3 exit gate — “The graph learned”

The project is submission-ready only when:

- [ ] All thirteen product-contract acceptance criteria have linked evidence.
- [ ] A real GitHub check blocks the unsafe PR and passes the safe PR.
- [ ] The first semantic failure produces a DataHub-visible Change Passport.
- [ ] Human approval creates a reusable protection with full provenance.
- [ ] A different second change retrieves and fails that protection.
- [ ] Repeated write-back/webhook operations create no duplicates.
- [ ] A fresh judge can run or understand the complete story in five minutes.
- [ ] The hosted path, local fallback, and committed sample outputs tell the same story.
- [ ] CI, end-to-end, fault-injection, determinism, security, accessibility, and fresh-clone
  checks are green.
- [ ] The final video is under three minutes and visibly proves functionality rather than
  relying on slides or narration.

### Failure-busting checks

- Replay the same GitHub event and DataHub write ten times: one logical record remains.
- Revoke write permission: evaluation still completes and reports write-back failure
  without falsely claiming memory was stored.
- Reject rather than accept a witness: it must not become enforced protection.
- Supersede a protection: future plans use only the active version and retain history.
- Open the hosted demo with no warm cache: progress and recovery remain understandable.
- Give the quickstart to a person unfamiliar with the repository: every missing step is
  treated as a release blocker.

---

## Proof matrix

| Winning claim | Required proof | Phase |
|---|---|---|
| DataHub is essential | Changing graph metadata changes the discovered path/evaluation plan | 1–2 |
| MCP is genuine | Raw operation provenance plus integration test against seeded DataHub | 1 |
| Semantic breaks are caught | Schema-preserving change causes executed downstream failure | 2 |
| Verdict is trustworthy | Three-state policy, Context Coverage, and fault tests | 2 |
| Failure is memorable | Minimized transaction with feature/model/agent before-and-after | 2 |
| Safe changes are not noisy | Additive scenario passes every declared critical evaluation | 2 |
| Write-back matters | Accepted witness becomes an executable retrieved protection | 3 |
| The graph learns | Different second change is caught by remembered protection | 3 |
| Product works end to end | GitHub + DataHub + web/CLI + fresh-clone E2E proof | 3 |
| Submission is judge-friendly | Hosted demo, examples, README, and sub-three-minute video | 3 |

## What the project author must provide when needed

Implementation can proceed autonomously through local development and deterministic
integration testing. The project author is only required for external authority that
cannot be safely inferred:

- access tokens or accounts for the final GitHub/DataHub/hosting integrations;
- approval of public repository and deployment actions;
- final branding preferences and submission form details;
- human approval during the recorded protection-promotion step;
- recording/publishing the final video and the separate upstream contribution track.

These needs do not block Phase 1: local DataHub, MCP, DuckDB, model, agent, and tests can
be built and proven without waiting for public credentials.

## Approval protocol

1. The project author approves this plan.
2. Only Phase 1 becomes active.
3. Phase 1 ends with an evidence-backed gate review, not a progress claim.
4. Phase 2 begins only after explicit acceptance of the Phase 1 gate.
5. Phase 3 begins only after explicit acceptance of the Phase 2 gate.

No implementation phase has been started by writing this plan.
