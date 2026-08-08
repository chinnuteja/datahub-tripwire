import semanticPassport from "../public/evidence/live-v2-unsafe-passport.json";
import activeProtection from "../public/evidence/live-v2-active-protection.json";
import memoryReceipt from "../public/evidence/live-v2-writeback-receipt.json";
import learnedPassport from "../public/evidence/live-v2-related-catch-passport.json";
import safePassport from "../public/evidence/live-v2-safe-control-passport.json";
import { TripwireConsole } from "./TripwireConsole";

export const metadata = {
  title: "Tripwire — Data systems that remember",
  description:
    "An adaptive change-safety agent powered by DataHub context, executed evidence, and organizational memory.",
};

export default function Home() {
  const witness = semanticPassport.counterexample;
  const learnedEvaluation = learnedPassport.evaluations.find(
    (evaluation) => evaluation.kind === "protection",
  );

  const evidence = {
    first: {
      runId: semanticPassport.run.run_id,
      engineCommit: semanticPassport.run.commit_sha,
      candidate: semanticPassport.change.candidate_revision,
      verdict: semanticPassport.verdict,
      reason: semanticPassport.reason_codes[0],
      contextFacts: semanticPassport.context.length,
      lineagePaths: semanticPassport.lineage.length,
      resolvedEntity: semanticPassport.resolved_entity?.urn ?? "",
      changeFacts: semanticPassport.change_facts.length,
      completedOperations: semanticPassport.scope_accounting.completed_operations,
      requiredOperations: semanticPassport.scope_accounting.required_operations,
      consumers: semanticPassport.coverage.critical_consumers.map((consumer) => ({
        name: consumer.display_name,
        kind: consumer.kind,
        urn: consumer.urn,
      })),
      evaluations: semanticPassport.evaluations.map((evaluation) => ({
        id: evaluation.evaluation_id,
        kind: evaluation.kind,
        status: evaluation.status,
        summary: evaluation.summary,
        consumer: evaluation.consumer.display_name,
      })),
      witness: {
        id: witness.witness_id,
        transactionId: String(witness.transaction.transaction_id),
        amount: Number(witness.transaction.amount_usd),
        international: Boolean(witness.transaction.is_international),
        merchantRisk: String(witness.transaction.merchant_risk),
        deviceAge: witness.transaction.device_age_days,
        baselineAction: witness.baseline.action,
        candidateAction: witness.candidate.action,
        baselineProbability: witness.baseline.model_result.probability,
        candidateProbability: witness.candidate.model_result.probability,
        baselineSignal: witness.baseline.model_result.feature_values.fraud_signal,
        candidateSignal: witness.candidate.model_result.feature_values.fraud_signal,
      },
      protectionId: semanticPassport.proposed_protection?.protection_id ?? "",
      owner: semanticPassport.owner_routes[0]?.display_name ?? "Unrouted",
      modelVersion: String(semanticPassport.evaluations[0]?.observations.model_version ?? ""),
      modelArtifactHash: String(
        semanticPassport.evaluations[0]?.observations.model_artifact_hash ?? "",
      ),
      replayedRows: Number(semanticPassport.evaluations[0]?.observations.replayed_rows ?? 0),
    },
    protection: {
      id: activeProtection.protection_id,
      name: activeProtection.name,
      status: activeProtection.status,
      invariant: activeProtection.invariant,
      version: activeProtection.version,
      approvedBy: activeProtection.approved_by ?? "",
      approvedAt: activeProtection.approved_at ?? "",
      affectedCount: activeProtection.affected_entities.length,
    },
    memory: {
      passportUrn: memoryReceipt.passport_urn,
      protectionUrn: memoryReceipt.protection_urn,
      tagUrn: memoryReceipt.tag_urn,
      attachedCount: memoryReceipt.attached_entities.length,
      hash: memoryReceipt.payload_hash,
    },
    learned: {
      runId: learnedPassport.run.run_id,
      candidate: learnedPassport.change.candidate_revision,
      verdict: learnedPassport.verdict,
      reason: learnedPassport.reason_codes[0],
      evaluations: learnedPassport.evaluations.map((evaluation) => ({
        id: evaluation.evaluation_id,
        kind: evaluation.kind,
        status: evaluation.status,
        summary: evaluation.summary,
        consumer: evaluation.consumer.display_name,
      })),
      appliedCount: learnedPassport.applied_protections.length,
      proposedAgain: learnedPassport.proposed_protection !== null,
      learnedObservation: learnedEvaluation?.observations ?? {},
    },
    safe: {
      runId: safePassport.run.run_id,
      candidate: safePassport.change.candidate_revision,
      verdict: safePassport.verdict,
      reason: safePassport.reason_codes[0],
      resolvedEntity: safePassport.resolved_entity?.urn ?? "",
      changeFacts: safePassport.change_facts.length,
      evaluations: safePassport.evaluations.map((evaluation) => ({
        id: evaluation.evaluation_id,
        kind: evaluation.kind,
        status: evaluation.status,
        summary: evaluation.summary,
        consumer: evaluation.consumer.display_name,
      })),
      modelVersion: String(safePassport.evaluations[0]?.observations.model_version ?? ""),
      modelArtifactHash: String(
        safePassport.evaluations[0]?.observations.model_artifact_hash ?? "",
      ),
      replayedRows: Number(safePassport.evaluations[0]?.observations.replayed_rows ?? 0),
    },
  };

  return <TripwireConsole evidence={evidence} />;
}
