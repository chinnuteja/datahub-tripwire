"""GitHub Checks adapter for evidence-backed Tripwire verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from tripwire.domain import ChangePassport, EvaluationStatus, Verdict

CHECK_NAME = "Tripwire / Change Safety"
DEMO_CANDIDATES = frozenset(
    {"safe_additive", "unsafe_mechanical", "unsafe_related", "unsafe_semantic"}
)


class CheckConclusion(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    ACTION_REQUIRED = "action_required"


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    name: str

    @classmethod
    def parse(cls, value: str) -> GitHubRepository:
        parts = value.strip().split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("repository must use the exact 'owner/name' form")
        return cls(owner=parts[0], name=parts[1])


@dataclass(frozen=True)
class GitHubPublishReceipt:
    check_run_id: int
    html_url: str
    operation: str
    conclusion: CheckConclusion


def conclusion_for(verdict: Verdict) -> CheckConclusion:
    """Map Tripwire's honest verdict states to GitHub's enforcement states."""

    if verdict is Verdict.SAFE_WITHIN_SCOPE:
        return CheckConclusion.SUCCESS
    if verdict is Verdict.UNSAFE:
        return CheckConclusion.FAILURE
    return CheckConclusion.ACTION_REQUIRED


def select_demo_candidate(changed_paths: list[str]) -> str:
    """Resolve exactly one supported demo candidate from a real git path list."""

    candidates = {
        Path(path.replace("\\", "/")).stem
        for path in changed_paths
        if path.replace("\\", "/").startswith("demo/fraud/sql/")
        and Path(path.replace("\\", "/")).stem in DEMO_CANDIDATES
    }
    if len(candidates) != 1:
        found = ", ".join(sorted(candidates)) or "none"
        raise ValueError(
            "exactly one supported demo candidate must change; " f"resolved candidates: {found}"
        )
    return candidates.pop()


def select_changed_dbt_sql_path(
    changed_paths: list[str],
    *,
    project_dir: str = "demo/fraud",
) -> str:
    """Fail closed unless a pull request changes exactly one dbt SQL model."""

    prefix = project_dir.strip("/\\").replace("\\", "/") + "/models/"
    candidates = {
        normalized
        for path in changed_paths
        if (normalized := path.replace("\\", "/")).startswith(prefix)
        and normalized.lower().endswith(".sql")
    }
    if len(candidates) != 1:
        found = ", ".join(sorted(candidates)) or "none"
        raise ValueError(
            "exactly one dbt SQL model must change; " f"resolved paths: {found}"
        )
    return candidates.pop()


def _title(passport: ChangePassport) -> str:
    if passport.verdict is Verdict.UNSAFE:
        return "Blocked: executed evidence found a critical behavior change"
    if passport.verdict is Verdict.SAFE_WITHIN_SCOPE:
        return "Passed within the evaluated scope"
    return "Action required: Tripwire could not prove safety"


def _critical_counts(passport: ChangePassport) -> tuple[int, int, int]:
    critical = [evaluation for evaluation in passport.evaluations if evaluation.critical]
    passed = sum(item.status is EvaluationStatus.PASSED for item in critical)
    failed = sum(item.status is EvaluationStatus.FAILED for item in critical)
    unresolved = len(critical) - passed - failed
    return passed, failed, unresolved


def render_check_markdown(passport: ChangePassport) -> str:
    """Render a compact, deterministic check report from a Change Passport."""

    passed, failed, unresolved = _critical_counts(passport)
    lines = [
        f"# {_title(passport)}",
        "",
        f"**Verdict:** `{passport.verdict.value}`  ",
        f"**Run:** `{passport.run.run_id}`  ",
        f"**Context coverage:** `{passport.coverage.status.value}`  ",
        (
            "**Critical evaluations:** "
            f"{passed} passed · {failed} failed · {unresolved} unresolved"
        ),
        "",
        "## Why",
        "",
        *[f"- `{code}`" for code in passport.reason_codes],
    ]

    if passport.scope_accounting is not None:
        scope = passport.scope_accounting
        lines.extend(
            [
                "",
                "## Evidence coverage",
                "",
                (
                    "- Metadata operations: "
                    f"**{scope.completed_operations}/{scope.required_operations}**"
                ),
                (
                    "- Critical consumers evaluated: "
                    f"**{scope.critical_consumers_evaluated}/"
                    f"{scope.critical_consumers_discovered}**"
                ),
                f"- Unresolved context gaps: **{scope.unresolved_gaps}**",
                (
                    "- Lineage frontier complete: **"
                    f"{'yes' if scope.lineage_frontier_complete else 'no'}**"
                ),
            ]
        )

    if passport.owner_routes:
        grouped: dict[tuple[str, str], set[str]] = {}
        for route in passport.owner_routes:
            grouped.setdefault((route.owner_urn, route.display_name), set()).add(
                route.source_entity_urn
            )
        lines.extend(["", "## Required review routing", ""])
        lines.extend(
            f"- **{display_name}** (`{owner_urn}`) — {len(entities)} affected asset(s)"
            for (owner_urn, display_name), entities in sorted(grouped.items())
        )

    if passport.counterexample is not None:
        witness = passport.counterexample
        transaction_id = witness.transaction.get("transaction_id", witness.witness_id)
        lines.extend(
            [
                "",
                "## Concrete witness",
                "",
                f"Transaction `{transaction_id}` reproduces the failure.",
                "",
                f"- Violated invariant: {witness.violated_invariant}",
                f"- Replay hash: `{witness.replay_hash}`",
                *(
                    [
                        "- Minimization: "
                        f"{witness.accepted_simplifications} accepted of "
                        f"{witness.minimization_attempts} attempted simplifications."
                    ]
                    if witness.minimization_attempts
                    else []
                ),
                "- Full before/after observations are preserved in the Change Passport.",
            ]
        )

    failed_evaluations = [
        evaluation
        for evaluation in passport.evaluations
        if evaluation.status is EvaluationStatus.FAILED
    ]
    if failed_evaluations:
        lines.extend(["", "## Failed consumers", ""])
        lines.extend(
            f"- **{item.consumer.display_name}** — {item.summary}"
            for item in failed_evaluations
        )

    if passport.remediation is not None:
        remediation = passport.remediation
        lines.extend(
            [
                "",
                "## Executed remediation",
                "",
                f"**Status:** `{remediation.status.value}`  ",
                remediation.summary,
                "",
                f"- Remediation: `{remediation.remediation_id}`",
                f"- Restored evaluations: {', '.join(remediation.restored_evaluations)}",
                f"- Fixed output hash: `{remediation.fixed_output_hash}`",
                "",
                "```diff",
                remediation.patch.rstrip(),
                "```",
            ]
        )

    if passport.limitations:
        lines.extend(["", "## Scope and limitations", ""])
        lines.extend(f"- {limitation}" for limitation in passport.limitations)

    lines.extend(
        [
            "",
            "---",
            "Generated from executed evidence. Tripwire does not treat missing evidence as safe.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_check_payload(
    passport: ChangePassport,
    *,
    head_sha: str,
    details_url: str | None = None,
) -> dict[str, Any]:
    """Build the GitHub API payload without performing a network operation."""

    markdown = render_check_markdown(passport)
    payload: dict[str, Any] = {
        "name": CHECK_NAME,
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion_for(passport.verdict).value,
        "external_id": passport.run.run_id,
        "output": {
            "title": _title(passport),
            "summary": markdown[:65_535],
        },
    }
    if details_url:
        payload["details_url"] = details_url
    return payload


def write_check_report(passport: ChangePassport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_check_markdown(passport), encoding="utf-8")


class GitHubChecksClient:
    """Create or update one stable GitHub Check Run per Tripwire run ID."""

    def __init__(
        self,
        *,
        token: str,
        repository: GitHubRepository,
        api_url: str = "https://api.github.com",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token:
            raise ValueError("GitHub token cannot be empty")
        self._repository = repository
        self._client = httpx.Client(
            base_url=api_url.rstrip("/"),
            transport=transport,
            timeout=20,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "datahub-tripwire",
            },
        )

    def __enter__(self) -> GitHubChecksClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self._client.close()

    @property
    def _repo_path(self) -> str:
        return f"/repos/{self._repository.owner}/{self._repository.name}"

    def publish(
        self,
        passport: ChangePassport,
        *,
        head_sha: str,
        details_url: str | None = None,
    ) -> GitHubPublishReceipt:
        payload = build_check_payload(passport, head_sha=head_sha, details_url=details_url)
        existing = self._find_existing(head_sha=head_sha, run_id=passport.run.run_id)
        operation = "updated" if existing is not None else "created"
        if existing is None:
            response = self._client.post(f"{self._repo_path}/check-runs", json=payload)
        else:
            update_payload = {key: value for key, value in payload.items() if key != "head_sha"}
            response = self._client.patch(
                f"{self._repo_path}/check-runs/{existing}", json=update_payload
            )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("GitHub returned an invalid Check Run response")
        check_id = body.get("id")
        html_url = body.get("html_url")
        if not isinstance(check_id, int) or not isinstance(html_url, str):
            raise ValueError("GitHub Check Run response omitted id or html_url")
        return GitHubPublishReceipt(
            check_run_id=check_id,
            html_url=html_url,
            operation=operation,
            conclusion=conclusion_for(passport.verdict),
        )

    def _find_existing(self, *, head_sha: str, run_id: str) -> int | None:
        response = self._client.get(
            f"{self._repo_path}/commits/{head_sha}/check-runs",
            params={"check_name": CHECK_NAME, "filter": "latest", "per_page": 100},
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("GitHub returned an invalid Check Runs response")
        runs = body.get("check_runs", [])
        if not isinstance(runs, list):
            raise ValueError("GitHub Check Runs response omitted check_runs")
        for item in runs:
            if not isinstance(item, dict) or item.get("external_id") != run_id:
                continue
            check_id = item.get("id")
            if isinstance(check_id, int):
                return check_id
        return None
