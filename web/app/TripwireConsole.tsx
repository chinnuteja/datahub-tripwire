"use client";

import { useState } from "react";

type Evaluation = {
  id: string;
  kind: string;
  status: string;
  summary: string;
  consumer: string;
};

type Evidence = {
  first: {
    runId: string;
    candidate: string;
    verdict: string;
    reason: string;
    contextFacts: number;
    lineagePaths: number;
    consumers: { name: string; kind: string; urn: string }[];
    evaluations: Evaluation[];
    witness: {
      id: string;
      transactionId: string;
      amount: number;
      international: boolean;
      merchantRisk: string;
      deviceAge: unknown;
      baselineAction: string;
      candidateAction: string;
      baselineProbability: number;
      candidateProbability: number;
      baselineSignal: number;
      candidateSignal: number;
    };
    protectionId: string;
  };
  protection: {
    id: string;
    name: string;
    status: string;
    invariant: string;
    version: number;
    approvedBy: string;
    approvedAt: string;
    affectedCount: number;
  };
  memory: {
    passportUrn: string;
    protectionUrn: string;
    tagUrn: string;
    attachedCount: number;
    hash: string;
  };
  learned: {
    runId: string;
    candidate: string;
    verdict: string;
    reason: string;
    evaluations: Evaluation[];
    appliedCount: number;
    proposedAgain: boolean;
    learnedObservation: Record<string, unknown>;
  };
};

const stages = ["Trace", "Test", "Witness", "Act", "Immunize"] as const;
type Stage = (typeof stages)[number];

function shortUrn(value: string) {
  return value.length > 48 ? `${value.slice(0, 28)}…${value.slice(-16)}` : value;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function TripwireConsole({ evidence }: { evidence: Evidence }) {
  const [stage, setStage] = useState<Stage>("Witness");
  const [scenario, setScenario] = useState<"first" | "learned">("learned");

  const scrollToWorkbench = (nextStage: Stage) => {
    setStage(nextStage);
    document.getElementById("workbench")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Tripwire home">
          <span className="brand-mark">T</span>
          <span>TRIPWIRE</span>
          <span className="brand-slash">/</span>
          <span className="brand-datahub">DATAHUB</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#proof">Proof</a>
          <a href="#workbench">Evidence</a>
          <a href="#memory">Memory</a>
        </nav>
        <span className="live-pill"><i /> Live graph verified</span>
      </header>

      <section className="hero" id="top">
        <div className="hero-grid" />
        <div className="hero-copy">
          <div className="eyebrow"><span>TRACE → TEST → WITNESS → ACT → IMMUNIZE</span></div>
          <h1>Data systems should<br /><em>remember</em> what broke them.</h1>
          <p className="hero-lede">
            Tripwire traces a proposed data change through DataHub, executes every critical
            consumer, proves the failure with one transaction, then turns the approved lesson
            into protection the next agent inherits.
          </p>
          <div className="hero-actions">
            <button className="primary-action" onClick={() => scrollToWorkbench("Witness")}>
              Inspect the witness <span>↘</span>
            </button>
            <button className="text-action" onClick={() => scrollToWorkbench("Immunize")}>
              See the learned catch <span>→</span>
            </button>
          </div>
          <div className="proof-strip" id="proof">
            <div><strong>{evidence.first.contextFacts}</strong><span>live MCP facts</span></div>
            <div><strong>{evidence.first.consumers.length}</strong><span>critical consumers</span></div>
            <div><strong>1</strong><span>minimal witness</span></div>
            <div><strong>{evidence.memory.attachedCount}</strong><span>assets immunized</span></div>
          </div>
        </div>

        <aside className="verdict-terminal" aria-label="Latest Tripwire verdict">
          <div className="terminal-topline">
            <span>CHANGE SAFETY CHECK</span>
            <span className="terminal-run">{evidence.learned.runId.slice(0, 13)}…</span>
          </div>
          <div className="verdict-heading">
            <div>
              <span className="muted-label">VERDICT</span>
              <strong>{evidence.learned.verdict}</strong>
            </div>
            <div className="blocked-seal">BLOCKED</div>
          </div>
          <div className="terminal-rule" />
          <div className="change-file">
            <span className="file-icon">SQL</span>
            <div><strong>{evidence.learned.candidate}.sql</strong><small>distinct code shape · same defect</small></div>
            <span className="danger-dot" />
          </div>
          <div className="mini-diff" aria-label="Simplified SQL change">
            <div className="diff-neutral"><span>18</span>case when device_age_days is null</div>
            <div className="diff-remove"><span>19</span>- then 0 <b>/* risky */</b></div>
            <div className="diff-add"><span>19</span>+ then 365 <b>/* trusted */</b></div>
          </div>
          <div className="caught-by">
            <span className="memory-glyph">◎</span>
            <div><small>CAUGHT BY ORGANIZATIONAL MEMORY</small><strong>{evidence.learned.reason}</strong></div>
          </div>
          <div className="terminal-footer">
            <span><i className="ok" /> DataHub MCP</span>
            <span><i className="ok" /> {evidence.learned.evaluations.length} evaluations</span>
            <span><i className="ok" /> exit 1</span>
          </div>
        </aside>
      </section>

      <section className="story-intro">
        <div className="section-kicker">THE EVIDENCE CHAIN</div>
        <h2>Not another risk score.<br />A case you can inspect.</h2>
        <p>Every claim below comes from the live Change Passports included with the project.</p>
      </section>

      <section className="workbench" id="workbench">
        <div className="stage-tabs" role="tablist" aria-label="Tripwire evidence stages">
          {stages.map((item, index) => (
            <button
              key={item}
              className={stage === item ? "stage-tab active" : "stage-tab"}
              onClick={() => setStage(item)}
              role="tab"
              aria-selected={stage === item}
            >
              <span>0{index + 1}</span><strong>{item}</strong>
            </button>
          ))}
        </div>

        <div className="stage-panel" role="tabpanel">
          {stage === "Trace" && <TracePanel evidence={evidence} />}
          {stage === "Test" && <TestPanel evidence={evidence} />}
          {stage === "Witness" && <WitnessPanel evidence={evidence} />}
          {stage === "Act" && <ActPanel evidence={evidence} />}
          {stage === "Immunize" && <ImmunizePanel evidence={evidence} />}
        </div>
      </section>

      <section className="scenario-section" id="memory">
        <div className="scenario-header">
          <div>
            <div className="section-kicker">THE ADAPTIVE PROOF</div>
            <h2>Two changes.<br />One learned invariant.</h2>
          </div>
          <div className="scenario-toggle" role="group" aria-label="Choose proof scenario">
            <button className={scenario === "first" ? "active" : ""} onClick={() => setScenario("first")}>01 · Learn</button>
            <button className={scenario === "learned" ? "active" : ""} onClick={() => setScenario("learned")}>02 · Catch</button>
          </div>
        </div>

        {scenario === "first" ? (
          <div className="scenario-card learn-card">
            <div className="scenario-index">01</div>
            <div className="scenario-main">
              <span className="scenario-label">FIRST REGRESSION</span>
              <h3>{evidence.first.candidate}.sql</h3>
              <p>Unknown device age is silently treated as trusted. The fraud score drops across an agent decision boundary.</p>
              <div className="scenario-result"><span>WITNESS</span><strong>{evidence.first.witness.transactionId}</strong><b>{evidence.first.witness.baselineAction} → {evidence.first.witness.candidateAction}</b></div>
            </div>
            <div className="scenario-outcome">
              <span>OUTPUT</span><strong>PROTECTION<br />PROPOSED</strong><small>{evidence.first.protectionId}</small>
            </div>
          </div>
        ) : (
          <div className="scenario-card catch-card">
            <div className="scenario-index">02</div>
            <div className="scenario-main">
              <span className="scenario-label">DISTINCT LATER CHANGE</span>
              <h3>{evidence.learned.candidate}.sql</h3>
              <p>A different SQL expression recreates the defect. DataHub lineage returns the active memory and Tripwire replays its fixture.</p>
              <div className="scenario-result"><span>APPLIED MEMORY</span><strong>v{evidence.protection.version}</strong><b>{evidence.learned.appliedCount} retrieved · {evidence.learned.evaluations.length} tests</b></div>
            </div>
            <div className="scenario-outcome danger">
              <span>OUTPUT</span><strong>CHANGE<br />BLOCKED</strong><small>{evidence.learned.reason}</small>
            </div>
          </div>
        )}

        <div className="memory-ledger">
          <div className="ledger-title"><span>DATAHUB MEMORY LEDGER</span><b>ACTIVE</b></div>
          <div className="ledger-row"><span>Protection</span><code>{evidence.protection.id} · v{evidence.protection.version}</code></div>
          <div className="ledger-row"><span>Approved by</span><code>{shortUrn(evidence.protection.approvedBy)}</code></div>
          <div className="ledger-row"><span>Attached to</span><code>{evidence.protection.affectedCount} affected graph entities</code></div>
          <div className="ledger-row"><span>Payload proof</span><code>{evidence.memory.hash.slice(0, 18)}…{evidence.memory.hash.slice(-10)}</code></div>
        </div>
      </section>

      <section className="closing-proof">
        <span className="closing-mark">T</span>
        <h2>The graph knows what depends on you.<br />Tripwire proves what your change will do.</h2>
        <div className="closing-actions">
          <a className="primary-action" href="/evidence/04-learned-catch-passport.json" download>Download live Passport <span>↓</span></a>
          <a className="text-action light" href="https://datahub.com" target="_blank" rel="noreferrer">Built on DataHub <span>↗</span></a>
        </div>
      </section>

      <footer>
        <div className="brand"><span className="brand-mark">T</span><span>TRIPWIRE</span></div>
        <p>Adaptive change safety for data, ML &amp; AI systems.</p>
        <div><span>DATAHUB v1.7.0</span><span>MCP v0.6.0</span><span>APACHE 2.0</span></div>
      </footer>
    </main>
  );
}

function PanelHeader({ number, title, copy }: { number: string; title: string; copy: string }) {
  return <div className="panel-header"><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></div>;
}

function TracePanel({ evidence }: { evidence: Evidence }) {
  return <div className="panel-layout">
    <PanelHeader number="01" title="Trace the real blast radius" copy="Exact URNs, schema, ownership, and downstream lineage returned by the official DataHub MCP server." />
    <div className="trace-map">
      <div className="trace-node source"><small>CHANGED DATASET</small><strong>Fraud Features</strong><code>duckdb · PROD</code></div>
      <div className="trace-connector"><i /><span>live lineage</span><i /></div>
      <div className="trace-consumers">
        {evidence.first.consumers.map((consumer) => <div className="trace-node" key={consumer.urn}><small>{consumer.kind.replace("_", " ")}</small><strong>{consumer.name}</strong><code>{shortUrn(consumer.urn)}</code></div>)}
      </div>
      <div className="coverage-badge"><span>✓</span><div><strong>Context coverage complete</strong><small>{evidence.first.contextFacts} MCP facts · {evidence.first.lineagePaths} lineage paths · no unresolved frontier</small></div></div>
    </div>
  </div>;
}

function TestPanel({ evidence }: { evidence: Evidence }) {
  return <div className="panel-layout">
    <PanelHeader number="02" title="Execute every critical consumer" copy="Baseline and candidate run over identical inputs. Models and agents are replayed, not guessed from metadata." />
    <div className="evaluation-table">
      <div className="table-head"><span>EVALUATION</span><span>CONSUMER</span><span>RESULT</span></div>
      {evidence.learned.evaluations.map((evaluation) => <div className="evaluation-row" key={evaluation.id}>
        <div><span className={`kind-icon ${evaluation.kind}`}>{evaluation.kind.slice(0, 1).toUpperCase()}</span><div><strong>{evaluation.kind} replay</strong><small>{evaluation.id}</small></div></div>
        <span>{evaluation.consumer}</span>
        <b className={evaluation.status === "failed" ? "status-failed" : "status-pass"}>{evaluation.status}</b>
      </div>)}
      <div className="evaluation-note"><span>EXECUTED EVIDENCE</span><p>All {evidence.learned.evaluations.length} evaluations completed. The learned protection failed on a concrete replay—not a heuristic score.</p></div>
    </div>
  </div>;
}

function WitnessPanel({ evidence }: { evidence: Evidence }) {
  const witness = evidence.first.witness;
  return <div className="panel-layout witness-layout">
    <PanelHeader number="03" title="Show me the transaction" copy="One minimal, synthetic fixture proves the causal path from changed feature to model score to agent action." />
    <div className="witness-card">
      <div className="witness-top"><div><span>MINIMAL COUNTEREXAMPLE</span><strong>{witness.transactionId}</strong></div><code>{evidence.first.witness.id}</code></div>
      <div className="transaction-facts">
        <div><span>AMOUNT</span><strong>${witness.amount}</strong></div><div><span>INTERNATIONAL</span><strong>{witness.international ? "Yes" : "No"}</strong></div><div><span>MERCHANT RISK</span><strong>{witness.merchantRisk}</strong></div><div><span>DEVICE AGE</span><strong>{witness.deviceAge === null ? "Unknown" : String(witness.deviceAge)}</strong></div>
      </div>
      <div className="before-after">
        <div className="behavior before"><span>BASELINE</span><div className="signal"><small>fraud signal</small><strong>{witness.baselineSignal}</strong></div><div className="probability-bar"><i style={{ width: percent(witness.baselineProbability) }} /></div><div className="agent-action"><small>MODEL {percent(witness.baselineProbability)}</small><b>{witness.baselineAction}</b></div></div>
        <div className="behavior-arrow"><span>−17.1</span><small>points</small><b>→</b></div>
        <div className="behavior after"><span>CANDIDATE</span><div className="signal"><small>fraud signal</small><strong>{witness.candidateSignal}</strong></div><div className="probability-bar"><i style={{ width: percent(witness.candidateProbability) }} /></div><div className="agent-action"><small>MODEL {percent(witness.candidateProbability)}</small><b>{witness.candidateAction}</b></div></div>
      </div>
      <div className="causal-path"><span>NULL DEVICE</span><i>→</i><span>FEATURE DROPS</span><i>→</i><span>MODEL CROSSES 0.62</span><i>→</i><strong>AGENT APPROVES</strong></div>
    </div>
  </div>;
}

function ActPanel({ evidence }: { evidence: Evidence }) {
  return <div className="panel-layout">
    <PanelHeader number="04" title="Turn evidence into a decision" copy="A reviewer gets the verdict, scope, causal witness, and owner action in one GitHub-native check." />
    <div className="github-check">
      <div className="gh-header"><span className="gh-fail">×</span><div><strong>Tripwire / change-safety</strong><small>Failed in 23s</small></div><button type="button">Details</button></div>
      <div className="gh-body">
        <div className="gh-title"><span>⛔</span><div><h4>Change blocked: learned protection violated</h4><code>{evidence.learned.reason}</code></div></div>
        <div className="gh-grid"><div><span>Changed asset</span><strong>Fraud Features</strong></div><div><span>Critical consumers</span><strong>{evidence.first.consumers.length} evaluated</strong></div><div><span>Failure witness</span><strong>{evidence.first.witness.transactionId}</strong></div><div><span>Applied memory</span><strong>{evidence.protection.id} · v1</strong></div></div>
        <div className="gh-annotation"><span>demo/fraud/sql/{evidence.learned.candidate}.sql</span><b>Agent decision changes from review → approve for the approved regression fixture.</b></div>
        <div className="gh-footer"><span>Context: live DataHub MCP</span><span>Policy: tripwire-policy/1.0.0</span><span>Exit code: 1</span></div>
      </div>
    </div>
  </div>;
}

function ImmunizePanel({ evidence }: { evidence: Evidence }) {
  return <div className="panel-layout">
    <PanelHeader number="05" title="Make the organization harder to break" copy="Only a human-approved witness becomes active memory. DataHub carries that knowledge to the next change and the next agent." />
    <div className="immunize-flow">
      <div className="immunize-step done"><span>01</span><div><small>TRIPWIRE</small><strong>Protection proposed</strong><p>Witness {evidence.first.witness.transactionId} becomes a versioned regression fixture.</p></div><b>✓</b></div>
      <div className="immunize-line" />
      <div className="immunize-step done"><span>02</span><div><small>HUMAN GATE</small><strong>Explicitly approved</strong><p>{shortUrn(evidence.protection.approvedBy)}</p></div><b>✓</b></div>
      <div className="immunize-line" />
      <div className="immunize-step done"><span>03</span><div><small>DATAHUB GRAPH</small><strong>Memory attached</strong><p>Passport + protection + tag on {evidence.memory.attachedCount} affected entities.</p></div><b>✓</b></div>
      <div className="immunize-line hot" />
      <div className="immunize-step caught"><span>04</span><div><small>NEXT CHANGE</small><strong>Defect caught again</strong><p>{evidence.learned.candidate}.sql violates inherited memory.</p></div><b>×</b></div>
    </div>
  </div>;
}
