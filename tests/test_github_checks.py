from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from tripwire.domain import (
    ChangePassport,
    OwnerRoute,
    ScopeAccounting,
    Verdict,
    VerifiedRemediation,
)
from tripwire.providers.github_checks import (
    GitHubChecksClient,
    GitHubRepository,
    build_check_payload,
    conclusion_for,
    render_check_markdown,
    select_changed_dbt_sql_path,
    select_demo_candidate,
)

EXAMPLES = Path("examples/learned-loop")
PUBLIC_PROOF = Path("examples/public-proof")


def _passport(filename: str = "01-unsafe-semantic-passport.json") -> ChangePassport:
    return ChangePassport.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


def test_unsafe_passport_renders_enforceable_concrete_report() -> None:
    passport = _passport()

    payload = build_check_payload(passport, head_sha="abc123", details_url="https://example.test")
    report = render_check_markdown(passport)

    assert payload["conclusion"] == "failure"
    assert payload["external_id"] == passport.run.run_id
    assert payload["details_url"] == "https://example.test"
    assert "Transaction `TX-009` reproduces the failure" in report
    assert "Fraud Review Agent" in report
    assert "does not treat missing evidence as safe" in report


def test_report_exposes_scope_owner_routing_and_verified_fix() -> None:
    passport = _passport().model_copy(
        update={
            "scope_accounting": ScopeAccounting(
                required_operations=3,
                completed_operations=3,
                critical_consumers_discovered=2,
                critical_consumers_evaluated=2,
                unresolved_gaps=0,
                lineage_frontier_complete=True,
            ),
            "owner_routes": (
                OwnerRoute(
                    owner_urn="urn:li:corpuser:fraud-platform",
                    display_name="Fraud Platform Team",
                    source_entity_urn=_passport().coverage.critical_consumers[0].urn,
                ),
            ),
            "remediation": VerifiedRemediation(
                remediation_id="fix_0123456789abcdef",
                summary="Restore null semantics and replay every critical consumer.",
                change_fact_ids=("chg_0123456789abcdef",),
                patch=(
                    "@@ -1 +1 @@\n"
                    "-COALESCE(device_age_days, 365)\n"
                    "+COALESCE(device_age_days, 0)\n"
                ),
                fixed_output_hash="a" * 64,
                restored_evaluations=("model-1", "agent-2"),
            ),
        }
    )

    report = render_check_markdown(passport)

    assert "Metadata operations: **3/3**" in report
    assert "Critical consumers evaluated: **2/2**" in report
    assert "Fraud Platform Team" in report
    assert "Executed remediation" in report
    assert "COALESCE(device_age_days, 0)" in report


def test_report_exposes_the_executed_model_artifact() -> None:
    passport = ChangePassport.model_validate_json(
        (PUBLIC_PROOF / "unsafe-pr-passport.json").read_text(encoding="utf-8")
    )

    report = render_check_markdown(passport)

    assert "fraud-risk-calibrator/2.0.0" in report
    assert "7d7edecb0868ae9fc068c5c73679b261f51e71bc2099f2fc0b6fd7887b9f89f6" in report
    assert "Rows replayed: **12**" in report


@pytest.mark.parametrize(
    ("verdict", "conclusion"),
    [
        (Verdict.UNSAFE, "failure"),
        (Verdict.SAFE_WITHIN_SCOPE, "success"),
        (Verdict.UNVERIFIED, "action_required"),
    ],
)
def test_verdict_mapping_is_fail_closed(verdict: Verdict, conclusion: str) -> None:
    assert conclusion_for(verdict).value == conclusion


def test_repository_parser_rejects_ambiguous_values() -> None:
    assert GitHubRepository.parse("datahub/tripwire").owner == "datahub"
    with pytest.raises(ValueError, match="owner/name"):
        GitHubRepository.parse("tripwire")


def test_candidate_selection_uses_actual_changed_sql_path() -> None:
    assert select_demo_candidate(
        ["README.md", "demo/fraud/sql/safe_additive.sql"]
    ) == "safe_additive"
    assert select_demo_candidate(
        ["demo\\fraud\\sql\\unsafe_semantic.sql"]
    ) == "unsafe_semantic"
    with pytest.raises(ValueError, match="exactly one"):
        select_demo_candidate([])
    with pytest.raises(ValueError, match="exactly one"):
        select_demo_candidate(
            [
                "demo/fraud/sql/safe_additive.sql",
                "demo/fraud/sql/unsafe_semantic.sql",
            ]
        )


def test_dbt_path_selection_requires_exactly_one_model() -> None:
    assert select_changed_dbt_sql_path(
        ["README.md", "demo/fraud/models/fct_fraud_features.sql"]
    ) == "demo/fraud/models/fct_fraud_features.sql"
    with pytest.raises(ValueError, match="exactly one dbt SQL model"):
        select_changed_dbt_sql_path([])
    with pytest.raises(ValueError, match="exactly one dbt SQL model"):
        select_changed_dbt_sql_path(
            [
                "demo/fraud/models/first.sql",
                "demo/fraud/models/second.sql",
            ]
        )


def test_publish_creates_check_when_run_is_new() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"check_runs": []})
        return httpx.Response(
            201,
            json={"id": 91, "html_url": "https://github.test/checks/91"},
        )

    with GitHubChecksClient(
        token="test-token",
        repository=GitHubRepository.parse("acme/fraud"),
        api_url="https://github.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        receipt = client.publish(_passport(), head_sha="abc123")

    assert receipt.operation == "created"
    assert receipt.check_run_id == 91
    assert [request.method for request in requests] == ["GET", "POST"]
    body = json.loads(requests[1].content)
    assert body["conclusion"] == "failure"
    assert body["head_sha"] == "abc123"


def test_publish_updates_same_run_without_duplicate() -> None:
    passport = _passport()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"check_runs": [{"id": 91, "external_id": passport.run.run_id}]},
            )
        return httpx.Response(
            200,
            json={"id": 91, "html_url": "https://github.test/checks/91"},
        )

    with GitHubChecksClient(
        token="test-token",
        repository=GitHubRepository.parse("acme/fraud"),
        api_url="https://github.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        receipt = client.publish(passport, head_sha="abc123")

    assert receipt.operation == "updated"
    assert [request.method for request in requests] == ["GET", "PATCH"]
    assert requests[1].url.path.endswith("/check-runs/91")
    body = json.loads(requests[1].content)
    assert "head_sha" not in body
