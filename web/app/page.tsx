import semanticPassport from "../public/evidence/01-unsafe-semantic-passport.json";
import activeProtection from "../public/evidence/02-active-protection.json";
import memoryReceipt from "../public/evidence/03-datahub-memory-receipt.json";
import learnedPassport from "../public/evidence/04-learned-catch-passport.json";
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
      candidate: semanticPassport.change.candidate_revision,
      verdict: semanticPassport.verdict,
      reason: semanticPassport.reason_codes[0],
      contextFacts: semanticPassport.context.length,
      lineagePaths: semanticPassport.lineage.length,
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
  };

  return <TripwireConsole evidence={evidence} />;
}
