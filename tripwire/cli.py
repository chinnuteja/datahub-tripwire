"""Command-line interface over Tripwire's real application services."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from tripwire import __version__
from tripwire.application import AssessmentService, write_change_passport
from tripwire.change import (
    ChangeAnalysisError,
    analyze_git_change,
    analyze_sql_change,
    render_dbt_sql_for_analysis,
)
from tripwire.config import load_settings
from tripwire.demo import resolve_slice
from tripwire.demo.fraud import build_demo_world, replay_fraud_transaction, write_demo_build
from tripwire.domain import ChangePassport, EntityKind, Protection, Verdict
from tripwire.memory import (
    DataHubMemoryStore,
    approve_protection,
    write_memory_receipt,
    write_protection,
)
from tripwire.ports import ContextSnapshot
from tripwire.provenance import sha256_value
from tripwire.providers import (
    DataHubMCPProvider,
    DataHubSeeder,
    GitHubChecksClient,
    GitHubRepository,
    select_changed_dbt_sql_path,
    select_demo_candidate,
    write_check_report,
)
from tripwire.providers.datahub_seed import write_seed_result

app = typer.Typer(
    name="tripwire",
    help="Prove whether data-code changes are safe for downstream consumers.",
    no_args_is_help=True,
)
demo_app = typer.Typer(help="Execute the deterministic fraud demonstration world.")
schema_app = typer.Typer(help="Export Tripwire's public evidence contracts.")
datahub_app = typer.Typer(help="Seed and inspect the real DataHub context graph.")
protection_app = typer.Typer(help="Approve and publish reusable Tripwire protections.")
github_app = typer.Typer(help="Render and publish evidence-backed GitHub Checks.")
witness_app = typer.Typer(help="Independently replay portable Tripwire witnesses.")
app.add_typer(demo_app, name="demo")
app.add_typer(schema_app, name="schema")
app.add_typer(datahub_app, name="datahub")
app.add_typer(protection_app, name="protection")
app.add_typer(github_app, name="github")
app.add_typer(witness_app, name="witness")


@app.callback()
def main() -> None:
    """Trace, test, witness, act, and immunize with DataHub context."""


@app.command()
def version() -> None:
    """Print the installed Tripwire version."""

    typer.echo(__version__)


@app.command()
def assess(
    candidate: Annotated[
        str,
        typer.Option(help="Candidate SQL scenario under the slice's sql directory."),
    ] = "unsafe_semantic",
    slice_name: Annotated[
        str,
        typer.Option(
            "--slice",
            help="Vertical slice to evaluate. Both slices share one evaluator.",
        ),
    ] = "fraud",
    urn: Annotated[
        str,
        typer.Option(help="Exact changed DataHub dataset URN."),
    ] = (
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
        "tripwire_fraud.fraud.fct_fraud_features,PROD)"
    ),
    context_file: Annotated[
        Path | None,
        typer.Option(
            help="Explicit recorded ContextSnapshot for offline/replay mode; live MCP is default."
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(help="Optional Change Passport JSON destination."),
    ] = None,
    requested_by: Annotated[
        str,
        typer.Option(help="Actor requesting the assessment."),
    ] = "local-user",
) -> None:
    """Execute the Tripwire vertical slice and emit a Change Passport."""

    settings = load_settings()
    settings.ensure_runtime_directories()
    if context_file:
        snapshot = ContextSnapshot.model_validate_json(context_file.read_text(encoding="utf-8"))
    else:
        provider = DataHubMCPProvider(settings)
        try:
            root = asyncio.run(provider.resolve_exact(urn))
            snapshot = asyncio.run(provider.trace_critical_consumers(root))
        except Exception as exc:
            typer.echo(f"Live DataHub MCP context retrieval failed: {exc}", err=True)
            raise typer.Exit(code=2) from None

    try:
        spec = resolve_slice(slice_name)
    except KeyError:
        typer.echo(f"Unknown slice: {slice_name!r}", err=True)
        raise typer.Exit(code=2) from None
    demo_dir = settings.demo_dir if spec.name == "fraud" else Path("demo") / spec.name

    baseline_path = demo_dir / "sql" / "baseline.sql"
    candidate_path = demo_dir / "sql" / f"{candidate}.sql"
    try:
        baseline_sql = baseline_path.read_text(encoding="utf-8")
        candidate_sql = candidate_path.read_text(encoding="utf-8")
        change_facts = analyze_sql_change(baseline_sql, candidate_sql)
    except (OSError, ChangeAnalysisError) as exc:
        typer.echo(f"Candidate SQL analysis failed: {exc}", err=True)
        raise typer.Exit(code=2) from None

    service = AssessmentService(root=Path.cwd(), demo_dir=demo_dir, spec=spec)
    passport = service.assess(
        candidate=candidate,
        context=snapshot,
        requested_by=requested_by,
        changed_path=f"{demo_dir.as_posix()}/sql/{candidate}.sql",
        resolved_entity=snapshot.root,
        change_facts=change_facts,
        baseline_sql=baseline_sql,
        candidate_sql=candidate_sql,
    )
    target = output or settings.artifact_dir / f"change-passport-{candidate}.json"
    _emit_assessment(passport=passport, target=target, candidate=candidate)


def _emit_assessment(
    *,
    passport: ChangePassport,
    target: Path,
    candidate: str,
) -> None:
    write_change_passport(passport, target)
    typer.echo(
        json.dumps(
            {
                "run_id": passport.run.run_id,
                "candidate": candidate,
                "verdict": passport.verdict.value,
                "reason_codes": passport.reason_codes,
                "critical_evaluations": len(passport.evaluations),
                "witness": (
                    passport.counterexample.witness_id if passport.counterexample else None
                ),
                "artifact": str(target),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if passport.verdict is Verdict.UNSAFE:
        raise typer.Exit(code=1)
    if passport.verdict is Verdict.UNVERIFIED:
        raise typer.Exit(code=2)


@app.command("assess-git")
def assess_git(
    base_ref: Annotated[
        str,
        typer.Option(help="Base Git revision containing the previous SQL."),
    ],
    head_ref: Annotated[
        str,
        typer.Option(help="Candidate Git revision containing the proposed SQL."),
    ],
    changed_path: Annotated[
        str,
        typer.Option(help="Exact changed dbt SQL path relative to the repository."),
    ],
    manifest_path: Annotated[
        Path,
        typer.Option(help="dbt manifest used for exact node and DataHub URN resolution."),
    ] = Path("demo/fraud/target/manifest.json"),
    project_dir: Annotated[
        Path,
        typer.Option(help="dbt project directory relative to the repository."),
    ] = Path("demo/fraud"),
    context_file: Annotated[
        Path | None,
        typer.Option(
            help="Explicit recorded ContextSnapshot for offline/replay mode; live MCP is default."
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(help="Optional Change Passport JSON destination."),
    ] = None,
    requested_by: Annotated[
        str,
        typer.Option(help="Actor requesting the assessment."),
    ] = "local-user",
) -> None:
    """Assess a real Git SQL change from AST facts through exact DataHub context."""

    root_path = Path.cwd()
    settings = load_settings()
    settings.ensure_runtime_directories()
    try:
        analysis = analyze_git_change(
            root=root_path,
            base_revision=base_ref,
            candidate_revision=head_ref,
            changed_path=changed_path,
            manifest_path=manifest_path,
            project_dir=project_dir,
        )
        if context_file:
            snapshot = ContextSnapshot.model_validate_json(
                context_file.read_text(encoding="utf-8")
            )
            if snapshot.root.urn != analysis.resolved_entity.urn:
                raise ChangeAnalysisError(
                    "CONTEXT_ROOT_MISMATCH: recorded context does not match the exact dbt URN"
                )
        else:
            provider = DataHubMCPProvider(settings)
            resolved = asyncio.run(provider.resolve_exact(analysis.resolved_entity.urn))
            if resolved.urn != analysis.resolved_entity.urn:
                raise ChangeAnalysisError(
                    "DATAHUB_IDENTITY_MISMATCH: MCP returned a different entity URN"
                )
            snapshot = asyncio.run(provider.trace_critical_consumers(resolved))
    except Exception as exc:
        typer.echo(f"Git change analysis or DataHub context retrieval failed: {exc}", err=True)
        raise typer.Exit(code=2) from None

    candidate_name = f"git-{head_ref[:12]}"
    passport = AssessmentService(root=root_path, demo_dir=settings.demo_dir).assess(
        candidate=candidate_name,
        context=snapshot,
        repository=root_path.name,
        base_revision=analysis.base_revision,
        candidate_revision=analysis.candidate_revision,
        requested_by=requested_by,
        changed_path=analysis.changed_path,
        resolved_entity=analysis.resolved_entity,
        change_facts=analysis.facts,
        baseline_sql=analysis.baseline_sql,
        candidate_sql=analysis.candidate_sql,
    )
    target = output or settings.artifact_dir / f"change-passport-{candidate_name}.json"
    _emit_assessment(passport=passport, target=target, candidate=candidate_name)


@demo_app.command("build")
def demo_build(
    scenario: Annotated[
        str,
        typer.Option(help="SQL scenario name under demo/fraud/sql."),
    ] = "baseline",
    output: Annotated[
        Path | None,
        typer.Option(help="Optional JSON build-manifest path."),
    ] = None,
) -> None:
    """Execute SQL → fraud model → Fraud Review Agent."""

    settings = load_settings()
    settings.ensure_runtime_directories()
    build = build_demo_world(demo_dir=settings.demo_dir, scenario=scenario)
    target = output or settings.artifact_dir / f"demo-{scenario}.json"
    write_demo_build(build, target)
    action_counts: dict[str, int] = {}
    for decision in build.decisions:
        action_counts[decision.action.value] = action_counts.get(decision.action.value, 0) + 1
    typer.echo(
        json.dumps(
            {
                "scenario": build.scenario,
                "rows": build.row_count,
                "actions": action_counts,
                "output_hash": build.output_hash,
                "artifact": str(target),
            },
            indent=2,
            sort_keys=True,
        )
    )


@demo_app.command("compare")
def demo_compare(
    candidate: Annotated[
        str,
        typer.Option(help="Candidate SQL scenario to compare with baseline."),
    ] = "unsafe_semantic",
) -> None:
    """Show real baseline/candidate model and agent behavior changes."""

    settings = load_settings()
    baseline = build_demo_world(demo_dir=settings.demo_dir, scenario="baseline")
    changed = build_demo_world(demo_dir=settings.demo_dir, scenario=candidate)
    baseline_by_id = {item.transaction_id: item for item in baseline.decisions}
    differences = []
    for decision in changed.decisions:
        previous = baseline_by_id[decision.transaction_id]
        if previous.action != decision.action or (
            previous.model_result.probability != decision.model_result.probability
        ):
            differences.append(
                {
                    "transaction_id": decision.transaction_id,
                    "baseline_probability": previous.model_result.probability,
                    "candidate_probability": decision.model_result.probability,
                    "baseline_action": previous.action.value,
                    "candidate_action": decision.action.value,
                }
            )
    typer.echo(json.dumps({"candidate": candidate, "differences": differences}, indent=2))


@schema_app.command("passport")
def export_passport_schema(
    output: Annotated[
        Path,
        typer.Option(help="Destination for the public JSON Schema."),
    ] = Path("schemas/change-passport.schema.json"),
) -> None:
    """Export the versioned Change Passport JSON Schema."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(ChangePassport.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    typer.echo(str(output))


@schema_app.command("protection")
def export_protection_schema(
    output: Annotated[
        Path,
        typer.Option(help="Destination for the public JSON Schema."),
    ] = Path("schemas/protection.schema.json"),
) -> None:
    """Export the versioned learned-protection JSON Schema."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(Protection.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    typer.echo(str(output))


@github_app.command("render")
def github_render(
    passport_file: Annotated[
        Path,
        typer.Option("--passport", help="Change Passport JSON to render."),
    ],
    output: Annotated[
        Path,
        typer.Option(help="Destination for the local GitHub-style Markdown report."),
    ] = Path("artifacts/runtime/tripwire-check.md"),
) -> None:
    """Render the exact report body used by the GitHub Checks adapter."""

    try:
        passport = ChangePassport.model_validate_json(
            passport_file.read_text(encoding="utf-8")
        )
        write_check_report(passport, output)
    except Exception as exc:
        typer.echo(f"GitHub report rendering failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(str(output))


@github_app.command("select-candidate")
def github_select_candidate(
    base_sha: Annotated[str, typer.Option(help="Base git commit SHA.")],
    head_sha: Annotated[str, typer.Option(help="Candidate git commit SHA.")],
) -> None:
    """Select one supported demo candidate from the actual changed SQL paths."""

    sha_pattern = re.compile(r"^[a-fA-F0-9]{7,64}$")
    if not sha_pattern.fullmatch(base_sha) or not sha_pattern.fullmatch(head_sha):
        typer.echo("Candidate selection requires valid hexadecimal git SHAs.", err=True)
        raise typer.Exit(code=2)
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                base_sha,
                head_sha,
                "--",
                "demo/fraud/sql",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        candidate = select_demo_candidate(result.stdout.splitlines())
    except Exception as exc:
        typer.echo(f"Candidate selection failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(candidate)


@github_app.command("select-dbt-path")
def github_select_dbt_path(
    base_sha: Annotated[str, typer.Option(help="Base git commit SHA.")],
    head_sha: Annotated[str, typer.Option(help="Candidate git commit SHA.")],
    project_dir: Annotated[
        str,
        typer.Option(help="dbt project directory relative to the repository."),
    ] = "demo/fraud",
) -> None:
    """Select exactly one changed dbt SQL model from a pull-request diff."""

    sha_pattern = re.compile(r"^[a-fA-F0-9]{7,64}$")
    if not sha_pattern.fullmatch(base_sha) or not sha_pattern.fullmatch(head_sha):
        typer.echo("dbt path selection requires valid hexadecimal git SHAs.", err=True)
        raise typer.Exit(code=2)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_sha, head_sha, "--", project_dir],
            check=True,
            capture_output=True,
            text=True,
        )
        changed_path = select_changed_dbt_sql_path(
            result.stdout.splitlines(), project_dir=project_dir
        )
    except Exception as exc:
        typer.echo(f"dbt path selection failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(changed_path)


@github_app.command("publish")
def github_publish(
    passport_file: Annotated[
        Path,
        typer.Option("--passport", help="Change Passport JSON to publish."),
    ],
    repository: Annotated[
        str | None,
        typer.Option(help="GitHub repository in owner/name form; defaults to GITHUB_REPOSITORY."),
    ] = None,
    head_sha: Annotated[
        str | None,
        typer.Option(help="Commit SHA for the Check Run; defaults to GITHUB_SHA."),
    ] = None,
    details_url: Annotated[
        str | None,
        typer.Option(help="Optional hosted Tripwire evidence URL."),
    ] = None,
) -> None:
    """Idempotently create or update a real GitHub Check Run."""

    token = os.getenv("GITHUB_TOKEN", "")
    repository_value = repository or os.getenv("GITHUB_REPOSITORY", "")
    head_sha_value = head_sha or os.getenv("GITHUB_SHA", "")
    if not token or not repository_value or not head_sha_value:
        typer.echo(
            "GitHub publishing requires GITHUB_TOKEN, repository, and head SHA.", err=True
        )
        raise typer.Exit(code=2)
    try:
        passport = ChangePassport.model_validate_json(
            passport_file.read_text(encoding="utf-8")
        )
        with GitHubChecksClient(
            token=token,
            repository=GitHubRepository.parse(repository_value),
        ) as client:
            receipt = client.publish(
                passport,
                head_sha=head_sha_value,
                details_url=details_url,
            )
    except Exception as exc:
        typer.echo(f"GitHub Check publishing failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(
        json.dumps(
            {
                "operation": receipt.operation,
                "check_run_id": receipt.check_run_id,
                "conclusion": receipt.conclusion.value,
                "url": receipt.html_url,
            },
            indent=2,
            sort_keys=True,
        )
    )


@witness_app.command("replay")
def witness_replay(
    passport_file: Annotated[
        Path,
        typer.Option("--passport", help="Change Passport containing a counterexample."),
    ],
    baseline_sql_file: Annotated[
        Path,
        typer.Option("--baseline-sql", help="Baseline SQL used by the original assessment."),
    ],
    candidate_sql_file: Annotated[
        Path,
        typer.Option("--candidate-sql", help="Candidate SQL used by the original assessment."),
    ],
) -> None:
    """Replay a witness in a new process and verify its cryptographic evidence hash."""

    try:
        passport = ChangePassport.model_validate_json(
            passport_file.read_text(encoding="utf-8")
        )
        witness = passport.counterexample
        if witness is None:
            raise ValueError("the Change Passport does not contain a counterexample")
        baseline_sql = render_dbt_sql_for_analysis(
            baseline_sql_file.read_text(encoding="utf-8")
        )
        candidate_sql = render_dbt_sql_for_analysis(
            candidate_sql_file.read_text(encoding="utf-8")
        )
        baseline = replay_fraud_transaction(
            sql=baseline_sql,
            transaction=witness.transaction,
        )
        candidate = replay_fraud_transaction(
            sql=candidate_sql,
            transaction=witness.transaction,
        )
        material = {
            "transaction": witness.transaction,
            "baseline": baseline.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
        }
        replay_hash = sha256_value(material)
        if replay_hash != witness.replay_hash:
            raise ValueError(
                "replay hash mismatch: supplied SQL or runtime does not reproduce the witness"
            )
        if material["baseline"] != witness.baseline or material["candidate"] != witness.candidate:
            raise ValueError("replay observations differ from the Change Passport")
    except Exception as exc:
        typer.echo(f"Witness replay failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(
        json.dumps(
            {
                "witness_id": witness.witness_id,
                "transaction_id": witness.transaction.get("transaction_id"),
                "baseline_action": baseline.action.value,
                "candidate_action": candidate.action.value,
                "replay_hash": replay_hash,
                "replay_hash_verified": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


@protection_app.command("approve")
def protection_approve(
    passport_file: Annotated[
        Path,
        typer.Option("--passport", help="Unsafe Change Passport containing a proposal."),
    ],
    approved_by: Annotated[
        str,
        typer.Option(help="Exact DataHub corpuser URN of the human approver."),
    ] = "urn:li:corpuser:fraud-platform",
    output: Annotated[
        Path | None,
        typer.Option(help="Optional active-protection JSON destination."),
    ] = None,
) -> None:
    """Human-approve a proposal and publish durable memory to DataHub."""

    settings = load_settings()
    settings.ensure_runtime_directories()
    try:
        passport = ChangePassport.model_validate_json(
            passport_file.read_text(encoding="utf-8")
        )
        if passport.proposed_protection is None:
            raise ValueError("the Change Passport does not contain a proposed protection")
        store = DataHubMemoryStore(settings)
        protection = store.find_active(passport.proposed_protection)
        if protection is None:
            protection = approve_protection(passport, approved_by=approved_by)
        elif protection.approved_by != approved_by:
            raise ValueError(
                f"protection is already approved by {protection.approved_by}; "
                "a retry must use the same approver"
            )
        receipt = store.publish(
            passport=passport,
            protection=protection,
        )
    except Exception as exc:
        typer.echo(f"Protection approval failed: {exc}", err=True)
        raise typer.Exit(code=2) from None

    protection_target = output or (
        settings.artifact_dir
        / f"active-protection-{protection.protection_id}-v{protection.version}.json"
    )
    receipt_target = settings.artifact_dir / "datahub-memory-receipt.json"
    write_protection(protection, protection_target)
    write_memory_receipt(receipt, receipt_target)
    typer.echo(
        json.dumps(
            {
                "protection_id": protection.protection_id,
                "status": protection.status.value,
                "approved_by": protection.approved_by,
                "datahub_protection_urn": receipt.protection_urn,
                "datahub_passport_urn": receipt.passport_urn,
                "attached_entities": len(receipt.attached_entities),
                # Native DataHub governance surfaces, not Tripwire-invented assets.
                "datahub_assertion_urn": receipt.assertion_urn,
                "datahub_assertion_result": receipt.assertion_result,
                "datahub_incident_urn": receipt.incident_urn,
                "datahub_incident_state": receipt.incident_state,
                "artifact": str(protection_target),
                "receipt": str(receipt_target),
            },
            indent=2,
            sort_keys=True,
        )
    )


@datahub_app.command("seed")
def datahub_seed() -> None:
    """Idempotently seed the Tripwire fraud graph into a live DataHub instance."""

    settings = load_settings()
    settings.ensure_runtime_directories()
    seeder = DataHubSeeder(settings)
    seeder.test_connection()
    result = seeder.seed(demo_dir=settings.demo_dir)
    target = settings.artifact_dir / "datahub-seed-manifest.json"
    write_seed_result(result, target)
    typer.echo(
        json.dumps(
            {
                "datahub": result.datahub_url,
                "entities": result.entity_count,
                "manifest_hash": result.manifest_hash,
                "artifact": str(target),
            },
            indent=2,
            sort_keys=True,
        )
    )


@datahub_app.command("tools")
def datahub_tools() -> None:
    """List tools exposed by the pinned official DataHub MCP server."""

    provider = DataHubMCPProvider(load_settings())
    try:
        tools = asyncio.run(provider.list_tools())
    except Exception as exc:
        typer.echo(f"DataHub MCP unavailable: {exc}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(json.dumps({"provider": "datahub-mcp/0.6.0:live", "tools": tools}, indent=2))


@datahub_app.command("trace")
def datahub_trace(
    urn: Annotated[str, typer.Option(help="Exact changed DataHub entity URN.")],
    output: Annotated[
        Path | None,
        typer.Option(help="Optional destination for the complete live Context Snapshot."),
    ] = None,
) -> None:
    """Trace critical downstream consumers using genuine MCP calls."""

    provider = DataHubMCPProvider(load_settings())
    try:
        root = asyncio.run(provider.resolve_exact(urn))
    except Exception as exc:
        typer.echo(f"DataHub MCP retrieval failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    if root.kind is not EntityKind.DATASET:
        raise typer.BadParameter("Phase 1 trace root must be a dataset URN")
    try:
        snapshot = asyncio.run(provider.trace_critical_consumers(root))
    except Exception as exc:
        typer.echo(f"DataHub MCP lineage failed: {exc}", err=True)
        raise typer.Exit(code=2) from None
    payload = json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    if output is None:
        typer.echo(payload, nl=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "artifact": str(output),
                "provider": snapshot.provider,
                "context_facts": len(snapshot.facts),
                "lineage_paths": len(snapshot.paths),
                "critical_consumers": len(snapshot.coverage.critical_consumers),
                "active_protections": len(snapshot.protections),
                "coverage": snapshot.coverage.status.value,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    app()
