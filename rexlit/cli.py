"""RexLit CLI application with Typer."""

import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import click
import typer
from typer import Context as TyperContext

from rexlit import __version__
from rexlit.app.ports.stamp import BatesStampRequest
from rexlit.app.privilege_service import PrivilegePolicyManager
from rexlit.bootstrap import bootstrap_application
from rexlit.config import get_settings, set_settings
from rexlit.index.search import search_by_hash
from rexlit.utils.methods import sanitize_argv
from rexlit.utils.offline import OfflineModeGate
from rexlit.utils.paths import validate_input_root, validate_output_root

if TYPE_CHECKING:
    from rexlit.app.ports import OCRPort
    from rexlit.app.ports.ocr import OCRResult
    from rexlit.bootstrap import ApplicationContainer

app = typer.Typer(
    name="rexlit",
    help="Offline-first UNIX litigation SDK/CLI for e-discovery and deadline management",
    add_completion=True,
    no_args_is_help=True,
)
highlight_app = typer.Typer(help="Highlight planning and validation")
app.add_typer(highlight_app, name="highlight")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        typer.echo(f"RexLit version {__version__}")
        raise typer.Exit()


def require_online(gate: OfflineModeGate, feature_name: str) -> None:
    """Enforce that ``feature_name`` may only run in online mode."""

    try:
        gate.require(feature_name)
    except RuntimeError as exc:
        typer.secho(f"\n{exc}\nAborting.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=2) from exc


def _resolve_invocation_tokens() -> list[str]:
    """Reconstruct CLI invocation using Typer context for audit logging."""

    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return list(sys.argv)

    chain: list[TyperContext] = []
    current: TyperContext | None = cast(TyperContext, ctx)
    while current is not None:
        chain.append(current)
        parent = getattr(current, "parent", None)
        current = cast(TyperContext | None, parent)
    chain.reverse()

    tokens: list[str] = []
    if chain:
        command_path = chain[-1].command_path or ""
        if command_path:
            tokens.extend(command_path.split())

    for context in chain:
        command = context.command
        if command is None:
            continue

        params = context.params
        for param in command.params:
            name = param.name
            if name not in params:
                continue
            value = params[name]
            default = getattr(param, "default", None)

            if isinstance(param, click.Argument):
                if value is None:
                    continue
                if getattr(param, "multiple", False) or isinstance(value, (list, tuple, set)):
                    tokens.extend(str(item) for item in value)
                else:
                    tokens.append(str(value))
                continue

            if isinstance(param, click.Option):
                opts = param.opts or param.secondary_opts
                if not opts:
                    continue
                flag = opts[-1]  # Prefer long-form flag when available
                if isinstance(value, bool):
                    if value != default and value:
                        tokens.append(flag)
                    elif value != default and not value and param.secondary_opts:
                        tokens.append(param.secondary_opts[-1])
                    continue
                if value is None:
                    continue
                if (
                    not getattr(param, "multiple", False)
                    and default is not None
                    and value == default
                ):
                    continue
                if getattr(param, "multiple", False) or isinstance(value, (list, tuple, set)):
                    for item in value:
                        tokens.extend([flag, str(item)])
                else:
                    tokens.extend([flag, str(value)])

    return tokens


def _parse_rgb_hex(value: str) -> tuple[float, float, float]:
    color = value.strip().lstrip("#")
    if len(color) != 6:
        raise ValueError("Color must be a 6-digit hexadecimal string")
    try:
        components = tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError as exc:  # pragma: no cover - handled by CLI validation
        raise ValueError("Invalid hexadecimal color value") from exc
    return components  # type: ignore[return-value]


def _collect_pdf_documents(container, source: Path) -> list:
    records = []
    for record in container.discovery_port.discover(source, recursive=True):
        extension = getattr(record, "extension", "").lower()
        if extension == ".pdf":
            records.append(record)
    return records


@highlight_app.command("plan")
def highlight_plan(
    input_path: Annotated[
        Path,
        typer.Argument(help="Document to analyze for highlights", exists=True, resolve_path=True),
    ],
    output_plan: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination for encrypted highlight plan (defaults to <file>.highlight-plan.enc)",
        ),
    ] = None,
    concepts: Annotated[
        str | None,
        typer.Option(
            "--concepts",
            help="Comma-separated list of concept types to detect",
        ),
    ] = None,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            help="Confidence threshold for concept detection",
        ),
    ] = 0.5,
) -> None:
    """Generate a highlight plan for the provided document."""

    container = bootstrap_application()
    service = container.highlight_service
    gate = container.offline_gate

    if service.concept.requires_online():
        require_online(gate, "Highlight concept detection")

    resolved_input = input_path.expanduser()
    resolved_output = (
        output_plan.expanduser()
        if output_plan is not None
        else Path.cwd() / f"{resolved_input.stem}.highlight-plan.enc"
    )

    safe_input = validate_input_root(resolved_input, [Path.cwd()])
    safe_output = validate_output_root(resolved_output, [Path.cwd()])

    concept_list = [entry.strip() for entry in concepts.split(",")] if concepts else None

    plan = service.plan(
        safe_input,
        safe_output,
        concepts=concept_list,
        threshold=threshold,
        allowed_input_roots=[Path.cwd()],
        allowed_output_roots=[Path.cwd()],
    )

    typer.secho(f"✅ Highlight plan created: {safe_output}", fg=typer.colors.GREEN)
    typer.echo(f"   Plan ID: {plan.plan_id}")
    typer.echo(f"   Highlights: {len(plan.highlights)}")


@highlight_app.command("validate")
def highlight_validate(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Encrypted highlight plan", exists=True, resolve_path=True),
    ],
    document_path: Annotated[
        Path,
        typer.Argument(help="Document to validate against", exists=True, resolve_path=True),
    ],
) -> None:
    """Validate a highlight plan against a document hash."""

    container = bootstrap_application()
    service = container.highlight_service
    gate = container.offline_gate

    safe_document = validate_input_root(document_path.expanduser(), [Path.cwd()])
    if service.concept.requires_online():
        require_online(gate, "Highlight concept detection")
    plan_valid = service.validate_plan(
        plan_path.expanduser(),
        safe_document,
        allowed_input_roots=[Path.cwd()],
    )

    if plan_valid:
        typer.secho("✅ Highlight plan is valid for the provided document.", fg=typer.colors.GREEN)
    else:
        typer.secho("❌ Highlight plan validation failed.", fg=typer.colors.RED)


@highlight_app.command("export")
def highlight_export(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Encrypted highlight plan", exists=True, resolve_path=True),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination for exported highlights JSON",
        ),
    ],
    format: Annotated[
        Literal["json", "heatmap"],
        typer.Option(
            "--format",
            "-f",
            help="Export format (json for UI payload, heatmap for scroll bar)",
        ),
    ] = "json",
) -> None:
    """Export highlight plan to UI-friendly JSON."""

    container = bootstrap_application()
    service = container.highlight_service

    exported = service.export(plan_path.expanduser(), output.expanduser(), format=format)
    typer.secho(f"✅ Exported highlights to {exported}", fg=typer.colors.GREEN)


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
    online: Annotated[
        bool,
        typer.Option("--online", help="Enable online features (API calls)"),
    ] = False,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Override data directory"),
    ] = None,
) -> None:
    """RexLit - Offline-first UNIX litigation SDK/CLI."""
    # Update settings with CLI flags
    settings = get_settings()
    if online:
        settings.online = True
    if data_dir:
        settings.data_dir = data_dir
    set_settings(settings)


# Ingest subcommand
ingest_app = typer.Typer(help="Document ingest and extraction")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("run")
def ingest_run(
    path: Annotated[Path, typer.Argument(help="Path to document or directory")],
    manifest: Annotated[
        Path | None,
        typer.Option("--manifest", "-m", help="Output manifest file (JSONL)"),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch directory for new documents"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", "-r", help="Recursively scan directories"),
    ] = True,
    impact_report: Annotated[
        Path | None,
        typer.Option("--impact-report", help="Generate JSON impact discovery summary (Sedona-aligned)"),
    ] = None,
    methods_appendix: Annotated[
        Path | None,
        typer.Option("--methods-appendix", help="Generate JSON methods appendix (cooperation)")
    ] = None,
    review_docs_per_hour_low: Annotated[
        int,
        typer.Option("--review-docs-per-hour-low", help="Low estimate for document review rate"),
    ] = 50,
    review_docs_per_hour_high: Annotated[
        int,
        typer.Option("--review-docs-per-hour-high", help="High estimate for document review rate"),
    ] = 150,
    review_cost_low: Annotated[
        float,
        typer.Option("--review-cost-low", help="Low hourly cost estimate (USD)"),
    ] = 75.0,
    review_cost_high: Annotated[
        float,
        typer.Option("--review-cost-high", help="High hourly cost estimate (USD)"),
    ] = 200.0,
    skip_plan_validation: Annotated[
        bool,
        typer.Option(
            "--skip-plan-validation",
            help="Skip redaction plan provenance validation (useful when sample data is mismatched).",
        ),
    ] = False,
    skip_redaction: Annotated[
        bool,
        typer.Option("--skip-redaction", help="Skip redaction planning stage."),
    ] = False,
    skip_bates: Annotated[
        bool,
        typer.Option("--skip-bates", help="Skip Bates planning stage."),
    ] = False,
    skip_pack: Annotated[
        bool,
        typer.Option("--skip-pack", help="Skip pack/archive creation stage."),
    ] = False,
    skip_pdf: Annotated[
        bool,
        typer.Option("--skip-pdf", help="Ignore PDF files during discovery."),
    ] = False,
) -> None:
    """Ingest documents from path and extract metadata."""
    container = bootstrap_application()
    # Log sanitized CLI invocation
    try:
        tokens = _resolve_invocation_tokens()
        container.ledger_port.log(
            operation="cli.invoke",
            inputs=[str(Path.cwd())],
            outputs=[],
            args={"command_line": sanitize_argv(tokens)},
        )
    except Exception:
        pass

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Validate review parameter ranges before running pipeline
    if review_docs_per_hour_low <= 0 or review_docs_per_hour_high <= 0:
        typer.secho(
            "Error: Review docs-per-hour values must be greater than zero.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if review_docs_per_hour_low > review_docs_per_hour_high:
        typer.secho(
            "Error: --review-docs-per-hour-low cannot exceed --review-docs-per-hour-high.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if review_cost_low < 0 or review_cost_high < 0:
        typer.secho(
            "Error: Review cost estimates must be non-negative.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    if review_cost_low > review_cost_high:
        typer.secho(
            "Error: --review-cost-low cannot exceed --review-cost-high.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    typer.secho(f"Discovering documents in {path}...", fg=typer.colors.BLUE)
    manifest_path = manifest.resolve() if manifest else None
    result = container.pipeline.run(
        path,
        manifest_path=manifest_path,
        recursive=recursive,
        exclude_extensions={".pdf"} if skip_pdf else None,
        validate_redaction_plans=not skip_plan_validation,
        skip_redaction=skip_redaction,
        skip_bates=skip_bates,
        skip_pack=skip_pack,
    )

    typer.secho(f"Found {len(result.documents)} documents", fg=typer.colors.GREEN)

    for stage in result.stages:
        color = typer.colors.GREEN if stage.status == "completed" else typer.colors.YELLOW
        typer.secho(f"[{stage.status}] {stage.name}", fg=color)

    if result.notes:
        for note in result.notes:
            typer.secho(f"NOTE: {note}", fg=typer.colors.YELLOW)

    # Generate impact report if requested
    if impact_report:
        impact_report = impact_report.resolve()

        allowed_root = result.manifest_path.parent.resolve()
        try:
            impact_report.relative_to(allowed_root)
        except ValueError:
            typer.secho(
                f"Error: Impact report path must reside within {allowed_root}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from None

        impact_report.parent.mkdir(parents=True, exist_ok=True)

        # Extract discovered_count from discover stage
        discovered_count = None
        for stage in result.stages:
            if stage.name == "discover" and stage.metrics:
                discovered_count = stage.metrics.get("discovered_count")
                break

        # Build report
        report = container.report_service.build_impact_report(
            result.manifest_path,
            discovered_count=discovered_count,
            stages=result.stages,
            review_rate_low=review_docs_per_hour_low,
            review_rate_high=review_docs_per_hour_high,
            cost_low=review_cost_low,
            cost_high=review_cost_high,
        )

        # Write atomically
        container.report_service.write_impact_report(impact_report, report)
        typer.secho(f"Impact report written to {impact_report}", fg=typer.colors.BLUE)

    # Generate methods appendix if requested
    if methods_appendix:
        appendix_path = methods_appendix.resolve()

        allowed_root = result.manifest_path.parent.resolve()
        try:
            appendix_path.relative_to(allowed_root)
        except ValueError:
            typer.secho(
                f"Error: Methods appendix path must reside within {allowed_root}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1) from None

        appendix_path.parent.mkdir(parents=True, exist_ok=True)
        appendix = container.report_service.build_methods_appendix(
            result.manifest_path, stages=result.stages
        )
        container.report_service.write_methods_appendix(appendix_path, appendix)
        typer.secho(f"Methods appendix written to {appendix_path}", fg=typer.colors.BLUE)

    if watch:
        typer.secho("Watch mode not yet implemented", fg=typer.colors.YELLOW)


# Index subcommand
index_app = typer.Typer(help="Search index management")
app.add_typer(index_app, name="index")


@index_app.command("build")
def index_build(
    path: Annotated[Path, typer.Argument(help="Path to document directory")],
    rebuild: Annotated[
        bool,
        typer.Option("--rebuild", help="Rebuild index from scratch"),
    ] = False,
    dense: Annotated[
        bool,
        typer.Option(
            "--dense",
            help="Also build Kanon 2 dense embeddings (requires --online or REXLIT_ONLINE=1).",
        ),
    ] = False,
    dim: Annotated[
        int,
        typer.Option("--dim", help="Dense embedding dimension (Matryoshka)", min=256),
    ] = 768,
    dense_batch: Annotated[
        int,
        typer.Option("--dense-batch", help="Batch size for embedding requests", min=1),
    ] = 32,
    isaacus_api_key: Annotated[
        str | None,
        typer.Option("--isaacus-api-key", help="Override ISAACUS_API_KEY environment variable"),
    ] = None,
    isaacus_api_base: Annotated[
        str | None,
        typer.Option("--isaacus-api-base", help="Isaacus self-host base URL"),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", help="Number of worker processes", min=1),
    ] = None,
) -> None:
    """Build search index from documents."""
    container = bootstrap_application()
    settings = container.settings

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Building index from {path}...", fg=typer.colors.BLUE)
    index_dir = settings.get_index_dir()

    if dense:
        require_online(container.offline_gate, "Dense indexing")

    try:
        count = container.index_port.build(  # type: ignore[attr-defined]
            path,
            rebuild=rebuild,
            dense=dense,
            dense_dim=dim,
            dense_batch_size=dense_batch,
            dense_api_key=isaacus_api_key,
            dense_api_base=isaacus_api_base,
            max_workers=workers,
        )
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    typer.secho(f"Indexed {count} documents to {index_dir}", fg=typer.colors.GREEN)

    if dense:
        dense_path = index_dir / "dense" / f"kanon2_{dim}.hnsw"
        if dense_path.exists():
            typer.secho(f"Dense index stored at {dense_path}", fg=typer.colors.BLUE)
        else:
            typer.secho(
                "Dense index skipped (no eligible textual content).", fg=typer.colors.YELLOW
            )


@index_app.command("search")
def index_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum results to return"),
    ] = 10,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Search mode: lexical, dense, or hybrid",
            case_sensitive=False,
        ),
    ] = "lexical",
    dim: Annotated[
        int,
        typer.Option("--dim", help="Dense embedding dimension", min=256),
    ] = 768,
    isaacus_api_key: Annotated[
        str | None,
        typer.Option("--isaacus-api-key", help="Override ISAACUS_API_KEY environment variable"),
    ] = None,
    isaacus_api_base: Annotated[
        str | None,
        typer.Option("--isaacus-api-base", help="Isaacus self-host base URL"),
    ] = None,
) -> None:
    """Search the index."""

    container = bootstrap_application()
    # Log sanitized CLI invocation
    try:
        tokens = _resolve_invocation_tokens()
        container.ledger_port.log(
            operation="cli.invoke",
            inputs=[str(Path.cwd())],
            outputs=[],
            args={"command_line": sanitize_argv(tokens)},
        )
    except Exception:
        pass
    mode_normalized = mode.lower()

    if mode_normalized not in {"lexical", "dense", "hybrid"}:
        typer.secho(
            "Invalid mode. Choose from 'lexical', 'dense', or 'hybrid'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    if not query.strip():
        typer.secho("Error: Query cannot be empty", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if mode_normalized in {"dense", "hybrid"}:
        require_online(container.offline_gate, f"{mode_normalized} search")

    try:
        results = container.index_port.search(  # type: ignore[call-arg]
            query,
            limit=limit,
            mode=mode_normalized,
            dim=dim,
            api_key=isaacus_api_key,
            api_base=isaacus_api_base,
        )
        # Log query parameters to audit ledger for methods appendix
        try:
            container.ledger_port.log(
                operation="index.search",
                inputs=[],
                outputs=[],
                args={
                    "query": query,
                    "mode": mode_normalized,
                    "limit": limit,
                    "dim": dim,
                },
            )
        except Exception:
            pass
    except FileNotFoundError as exc:
        typer.secho(
            "Error: Index not found. Run 'rexlit index build' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "search_results",
                1,
                query=query,
                mode=mode_normalized,
                total_hits=len(results),
                results=[r.model_dump(mode="json") for r in results],
            )
        )
        return

    if not results:
        typer.secho("No results found", fg=typer.colors.YELLOW)
        return

    typer.secho(
        f"Found {len(results)} {mode_normalized} results for '{query}':",
        fg=typer.colors.BLUE,
    )
    for i, result in enumerate(results, 1):
        score_repr = f"{result.score:.2f}"
        components: list[str] = []
        strategy = getattr(result, "strategy", "lexical")
        lexical_score = getattr(result, "lexical_score", None)
        dense_score = getattr(result, "dense_score", None)

        if strategy != "lexical" and lexical_score is not None:
            components.append(f"lex={lexical_score:.2f}")
        if dense_score is not None:
            components.append(f"dense={dense_score:.2f}")
        if components:
            score_repr += f" ({', '.join(components)})"

        typer.echo(f"\n{i}. {result.path} [{strategy}] (score: {score_repr})")
        if result.snippet:
            typer.echo(f"   {result.snippet}")


@index_app.command("get")
def index_get(
    sha256: Annotated[str, typer.Argument(help="Document SHA-256 hash")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output metadata as JSON"),
    ] = False,
) -> None:
    """Retrieve document metadata by SHA-256 hash."""

    container = bootstrap_application()
    try:
        result = search_by_hash(container.settings.get_index_dir(), sha256)
    except FileNotFoundError as exc:
        typer.secho(
            "Error: Index not found. Run 'rexlit index build' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if result is None:
        typer.secho(
            f"No document found for SHA-256 {sha256}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    payload = result.model_dump(mode="json")
    if "file_path" not in payload:
        payload["file_path"] = payload.get("path")

    if json_output:
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "document_metadata",
                1,
                **payload,
            )
        )
        return

    typer.echo(f"Path: {payload.get('file_path')}")
    typer.echo(f"SHA-256: {result.sha256}")
    typer.echo(f"Custodian: {result.custodian or 'unknown'}")
    typer.echo(f"Doctype: {result.doctype or 'unknown'}")


# Report subcommand
report_app = typer.Typer(help="Report generation utilities")
app.add_typer(report_app, name="report")


@report_app.command("methods")
def report_methods(
    manifest: Annotated[Path, typer.Argument(help="Path to manifest JSONL")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output methods JSON path")],
) -> None:
    """Generate a Methods Appendix from existing manifest + audit ledger."""
    container = bootstrap_application()

    # Log sanitized CLI invocation
    try:
        tokens = _resolve_invocation_tokens()
        container.ledger_port.log(
            operation="cli.invoke",
            inputs=[str(Path.cwd())],
            outputs=[],
            args={"command_line": sanitize_argv(tokens)},
        )
    except Exception:
        pass

    if not manifest.exists():
        typer.secho(f"Error: Manifest not found: {manifest}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    output = output.resolve()

    allowed_root = manifest.resolve().parent
    try:
        output.relative_to(allowed_root)
    except ValueError:
        typer.secho(
            f"Error: Output path must reside within {allowed_root}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from None

    output.parent.mkdir(parents=True, exist_ok=True)
    appendix = container.report_service.build_methods_appendix(manifest)
    container.report_service.write_methods_appendix(output, appendix)
    typer.secho(f"Methods appendix written to {output}", fg=typer.colors.BLUE)


# Bates subcommand
bates_app = typer.Typer(help="Bates numbering utilities")
app.add_typer(bates_app, name="bates")


@bates_app.command("stamp")
def bates_stamp(
    path: Annotated[Path, typer.Argument(help="PDF file or directory to stamp")],
    prefix: Annotated[str, typer.Option("--prefix", "-p", help="Bates prefix (e.g. 'ABC')")],
    width: Annotated[
        int,
        typer.Option("--width", "-w", help="Zero-pad width for numeric portion", min=1),
    ] = 7,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination directory or PDF for stamped output"),
    ] = None,
    font_size: Annotated[int, typer.Option("--font-size", help="Font size in points", min=6)] = 10,
    color: Annotated[str, typer.Option("--color", help="RGB hex color (e.g. '000000')") ] = "000000",
    position: Annotated[
        Literal["bottom-right", "bottom-center", "top-right"],
        typer.Option("--position", help="Stamp placement"),
    ] = "bottom-right",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview assignments without stamping")]
    = False,
) -> None:
    """Apply Bates numbers to PDF documents with layout-aware placement."""

    container = bootstrap_application()
    resolved_path = path.resolve()

    if not resolved_path.exists():
        typer.secho(f"Error: Path not found: {resolved_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        rgb = _parse_rgb_hex(color)
    except ValueError as exc:
        typer.secho(f"Invalid color value: {color} ({exc})", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    documents = _collect_pdf_documents(container, resolved_path)

    if resolved_path.is_file() and not documents:
        typer.secho("Input file must be a PDF for stamping", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not documents:
        typer.secho("No PDF documents discovered for stamping", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    plan = container.bates_planner.plan_with_families(
        documents,
        prefix=prefix,
        width=width,
        separator="",
    )

    record_by_sha = {record.sha256: record for record in documents}
    ordered_documents = list(plan.get("ordered_documents", []))

    if dry_run:
        preview_labels: list[str] = []
        current_number = 1
        total_pages = 0
        for entry in ordered_documents:
            sha256 = str(entry.get("sha256"))
            record = record_by_sha.get(sha256)
            if record is None:
                continue
            page_count = container.bates_stamper.get_page_count(Path(record.path))
            total_pages += page_count
            for _ in range(page_count):
                if len(preview_labels) < 5:
                    preview_labels.append(f"{prefix}{current_number:0{width}d}")
                current_number += 1

        typer.secho("✓ Dry-run preview", fg=typer.colors.GREEN)
        typer.echo(f"  Documents: {plan['total_documents']}")
        typer.echo(f"  Total pages: {total_pages}")
        typer.echo(f"  Prefix: {prefix}")
        typer.echo(f"  Position: {position}")
        if preview_labels:
            typer.echo("\n  First labels:")
            for idx, label in enumerate(preview_labels, start=1):
                typer.echo(f"    {idx}. {label}")
            remaining = max(total_pages - len(preview_labels), 0)
            if remaining:
                typer.echo(f"    … and {remaining} more")
        raise typer.Exit(code=0)

    if resolved_path.is_dir():
        output_root = (output.resolve() if output else (resolved_path / "stamped")).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
    else:
        output_root = None
        if output is None:
            destination = resolved_path.with_name(
                f"{resolved_path.stem}_stamped{resolved_path.suffix}"
            )
        else:
            destination = output.resolve()
            if destination.is_dir():
                destination = destination / resolved_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)

    current_number = 1
    total_pages = 0
    manifest_records: list[dict[str, Any]] = []

    for entry in ordered_documents:
        sha256 = str(entry.get("sha256"))
        record = record_by_sha.get(sha256)
        if record is None:
            continue

        input_path = Path(record.path)
        if output_root is not None:
            relative_path = input_path.relative_to(resolved_path)
            output_path = (output_root / relative_path).with_suffix(input_path.suffix)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = destination

        request = BatesStampRequest(
            input_path=input_path,
            output_path=output_path,
            prefix=prefix,
            start_number=current_number,
            width=width,
            position=position,
            font_size=font_size,
            color=rgb,
            background=True,
        )

        result = container.bates_stamper.stamp(request)
        total_pages += result.pages_stamped
        current_number = result.end_number + 1

        output_hash = container.storage_port.compute_hash(result.output_path)
        manifest_records.append(
            {
                "input_path": str(result.input_path),
                "output_path": str(result.output_path),
                "sha256": record.sha256,
                "family_id": entry.get("family_id"),
                "prefix": result.prefix,
                "width": result.width,
                "start_number": result.start_number,
                "end_number": result.end_number,
                "start_label": result.start_label,
                "end_label": result.end_label,
                "pages_stamped": result.pages_stamped,
                "coordinates": [coord.model_dump(mode="json") for coord in result.coordinates],
                "output_sha256": output_hash,
            }
        )

    if not manifest_records:
        typer.secho("No PDFs were stamped.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    manifest_parent = (
        output_root if output_root is not None else destination.parent
    )
    manifest_path = manifest_parent / "bates_manifest.jsonl"
    container.storage_port.write_jsonl(manifest_path, iter(manifest_records))

    typer.secho(
        f"✓ Stamped {total_pages} pages across {len(manifest_records)} document(s)",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  Manifest: {manifest_path}")
    if output_root is not None:
        typer.echo(f"  Output directory: {output_root}")
    else:
        typer.echo(f"  Output file: {destination}")


@bates_app.command("verify")
def bates_verify(
    plan: Annotated[
        Path | None,
        typer.Argument(help="Path to bates_plan.jsonl (defaults to data dir)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
) -> None:
    """Verify Bates registry integrity.

    Checks the Bates plan file for:
    - Required fields (document, sha256, bates_id)
    - Duplicate Bates IDs or SHA-256 hashes
    - Missing source files
    - Hash mismatches (file modified after planning)
    """
    container = bootstrap_application()

    from rexlit.utils.bates_verify import verify_bates_registry

    if plan is None:
        plan_path = container.settings.get_data_dir() / "bates" / "bates_plan.jsonl"
    else:
        plan_path = plan.resolve()

    is_valid, errors = verify_bates_registry(plan_path)

    if json_output:
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "bates_verification",
                1,
                plan_path=str(plan_path),
                valid=is_valid,
                error_count=len(errors),
                errors=errors,
            )
        )
    else:
        if is_valid:
            typer.secho(f"Bates registry verified: {plan_path}", fg=typer.colors.GREEN)
        else:
            typer.secho(
                f"Bates registry verification failed ({len(errors)} errors):",
                fg=typer.colors.RED,
                err=True,
            )
            for error in errors:
                typer.echo(f"  - {error}", err=True)

    if not is_valid:
        raise typer.Exit(code=1)


# Production subcommand
produce_app = typer.Typer(help="Production load file exports")
app.add_typer(produce_app, name="produce")


@produce_app.command("create")
def produce_create(
    path: Annotated[Path, typer.Argument(help="Directory containing stamped PDFs")],
    name: Annotated[str, typer.Option("--name", "-n", help="Production set name")],
    format: Annotated[
        Literal["dat", "opticon"],
        typer.Option("--format", "-f", help="Production load file format"),
    ] = "dat",
    bates_prefix: Annotated[
        str,
        typer.Option("--bates", help="Expected Bates prefix for validation"),
    ] = "",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for production set"),
    ] = None,
) -> None:
    """Generate DAT or Opticon production files from stamped documents."""

    container = bootstrap_application()
    resolved_path = path.resolve()

    if not resolved_path.exists() or not resolved_path.is_dir():
        typer.secho(f"Error: Directory not found: {resolved_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        result = container.pack_service.create_production(
            resolved_path,
            name=name,
            format=format,
            bates_prefix=bates_prefix,
            output_dir=output.resolve() if output is not None else None,
        )
    except (FileNotFoundError, ValueError, NotImplementedError) as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"✓ Production set created: {result['output_path']}", fg=typer.colors.GREEN)
    typer.echo(f"  Documents: {result['document_count']}")
    typer.echo(f"  Format: {format.upper()}")


# Rules subcommand
rules_app = typer.Typer(help="Rules and deadline calculations")
app.add_typer(rules_app, name="rules")


@rules_app.command("calc")
def rules_calc(
    jurisdiction: Annotated[
        Literal["TX", "FL"],
        typer.Option("--jurisdiction", "-j", help="Jurisdiction"),
    ],
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Triggering event (e.g. 'served_petition')"),
    ],
    date: Annotated[
        str,
        typer.Option("--date", "-d", help="Base date (YYYY-MM-DD)"),
    ],
    service_method: Annotated[
        Literal["personal", "mail", "eservice"],
        typer.Option("--service", "-s", help="Service method"),
    ] = "personal",
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Show calculation trace"),
    ] = False,
    ics_output: Annotated[
        Path | None,
        typer.Option("--ics", help="Export deadlines to an ICS calendar file"),
    ] = None,
) -> None:
    """Calculate litigation deadlines for Texas or Florida civil rules."""

    container = bootstrap_application()

    try:
        base_date = datetime.fromisoformat(date)
    except ValueError as exc:
        typer.secho(f"Invalid date format: {date}. Use YYYY-MM-DD.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"\n📅 {jurisdiction} Rules Calculator", fg=typer.colors.BLUE, bold=True)

    try:
        deadlines = container.rules_engine.calculate_deadline(
            jurisdiction=jurisdiction,
            event=event,
            base_date=base_date,
            service_method=service_method,
            explain=explain,
        )
    except ValueError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"   Event: {event}", fg=typer.colors.CYAN)
    typer.secho(f"   Base date: {base_date.strftime('%Y-%m-%d')}", fg=typer.colors.CYAN)
    typer.secho(f"   Service: {service_method}\n", fg=typer.colors.CYAN)

    deadline_items = deadlines.get("deadlines", {})
    if not deadline_items:
        typer.secho("No deadlines defined for this event.", fg=typer.colors.YELLOW)
    else:
        for name, info in deadline_items.items():
            typer.secho(f"  ✓ {name}", fg=typer.colors.GREEN, bold=True)
            deadline_dt = datetime.fromisoformat(info["date"])
            typer.echo(f"    Date:   {deadline_dt.strftime('%A, %B %d, %Y @ %H:%M')}")
            typer.echo(f"    Rule:   {info['cite']}")
            if explain and info.get("trace"):
                typer.echo(f"    Calc:   {info['trace']}")
            if info.get("notes"):
                typer.echo(f"    Notes:  {info['notes']}")
            if info.get("last_reviewed"):
                typer.echo(f"    Reviewed: {info['last_reviewed']}")
            typer.echo()

    if ics_output is not None:
        output_path = ics_output.resolve()
        typer.secho("📋 Exporting to ICS...", fg=typer.colors.BLUE)
        from rexlit.rules.export import export_deadlines_to_ics

        export_deadlines_to_ics(deadlines, output_path)
        typer.secho(f"✓ Calendar exported: {output_path}", fg=typer.colors.GREEN)
        typer.echo("   Drag-drop into Calendar app to import")


# OCR subcommand (Phase 2)
ocr_app = typer.Typer(help="OCR processing")
app.add_typer(ocr_app, name="ocr")


@ocr_app.command("run")
def ocr_run(
    path: Annotated[Path, typer.Argument(help="Path to PDF, image, or directory")],
    provider: Annotated[
        Literal["tesseract", "paddle"],
        typer.Option("--provider", "-p", help="OCR provider"),
    ] = "tesseract",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output text file or directory"),
    ] = None,
    preflight: Annotated[
        bool,
        typer.Option("--preflight/--no-preflight", help="Analyze pages before OCR"),
    ] = True,
    language: Annotated[
        str,
        typer.Option("--language", "-l", help="OCR language code"),
    ] = "eng",
    online: Annotated[
        bool,
        typer.Option("--online", help="Enable online OCR providers"),
    ] = False,
    show_confidence: Annotated[
        bool,
        typer.Option("--confidence", help="Show OCR confidence scores"),
    ] = False,
) -> None:
    """Run OCR on documents with preflight optimisation."""
    settings = get_settings()
    if online and not settings.online:
        settings.online = True
        set_settings(settings)

    container = bootstrap_application(settings)

    if provider not in container.ocr_providers:
        typer.secho(
            f"Error: OCR provider '{provider}' not available. "
            f"Options: {', '.join(sorted(container.ocr_providers))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    ocr_adapter = container.ocr_providers[provider]

    try:
        container.offline_gate.ensure_supported(
            feature=f"{provider} OCR",
            requires_online=ocr_adapter.is_online(),
        )
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=2) from exc

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    resolved = path.resolve()
    typer.secho(f"🔍 OCR provider: {provider}", fg=typer.colors.BLUE)

    with _override_preflight(ocr_adapter, preflight):
        if resolved.is_file():
            success = _ocr_single_file(
                resolved,
                ocr_adapter,
                output,
                language,
                show_confidence,
                container,
                provider,
            )
            if not success:
                raise typer.Exit(code=1)
        elif resolved.is_dir():
            _ocr_directory(
                resolved,
                ocr_adapter,
                output,
                language,
                show_confidence,
                container,
                provider,
            )
        else:
            typer.secho(
                f"Error: Not a file or directory: {resolved}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)


def _ocr_single_file(
    path: Path,
    ocr_adapter: "OCRPort",
    output: Path | None,
    language: str,
    show_confidence: bool,
    container: "ApplicationContainer",
    provider: str,
    *,
    output_override: Path | None = None,
    display_label: str | None = None,
) -> bool:
    label = display_label or path.name
    typer.secho(f"\n📄 {label}", fg=typer.colors.CYAN)

    try:
        result, elapsed = _execute_ocr(ocr_adapter, path, language)
    except Exception as exc:  # pragma: no cover - surfaces to CLI
        typer.secho(f"  ✗ OCR failed: {exc}", fg=typer.colors.RED)
        return False

    output_path = _write_output_text(result, output, path, output_override)

    typer.secho(
        f"  ✓ {result.page_count} pages | {len(result.text):,} chars | {elapsed:.2f}s",
        fg=typer.colors.GREEN,
    )
    if show_confidence:
        typer.echo(f"  Confidence: {result.confidence:.1%}")

    _log_ocr_event(container, path, provider, result, elapsed, output_path)
    return True


def _ocr_directory(
    directory: Path,
    ocr_adapter: "OCRPort",
    output: Path | None,
    language: str,
    show_confidence: bool,
    container: "ApplicationContainer",
    provider: str,
) -> None:
    resolved_root = directory.resolve()
    allowed_suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

    files: list[Path] = []
    for candidate in sorted(resolved_root.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in allowed_suffixes:
            continue
        try:
            resolved_candidate = candidate.resolve(strict=True)
        except FileNotFoundError:
            typer.secho(f"Skipping vanished file: {candidate}", fg=typer.colors.YELLOW)
            continue
        try:
            resolved_candidate.relative_to(resolved_root)
        except ValueError:
            typer.secho(
                f"Skipping {candidate}: resolves outside {resolved_root}",
                fg=typer.colors.YELLOW,
            )
            continue
        files.append(resolved_candidate)

    if not files:
        typer.secho("No OCR-compatible files found in directory.", fg=typer.colors.YELLOW)
        return

    output_dir = None
    if output is not None:
        output_dir = output.expanduser()
        if output_dir.exists() and not output_dir.is_dir():
            typer.secho(
                "Output path must be a directory when processing multiple files.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        output_dir.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = 0
    total = len(files)

    for idx, file_path in enumerate(files, 1):
        try:
            relative = file_path.relative_to(resolved_root)
        except ValueError:
            relative = file_path.name

        typer.echo(f"\n[{idx}/{total}] {relative}")

        target_output = None
        if output_dir is not None:
            target_output = (output_dir / Path(relative)).with_suffix(".txt")

        ok = _ocr_single_file(
            file_path,
            ocr_adapter,
            None,
            language,
            show_confidence,
            container,
            provider,
            output_override=target_output,
            display_label=str(relative),
        )

        if ok:
            successes += 1
        else:
            failures += 1

    typer.echo(f"\n{'=' * 60}")
    typer.secho(f"✓ Success: {successes}/{total}", fg=typer.colors.GREEN)
    if failures:
        typer.secho(f"✗ Failures: {failures}/{total}", fg=typer.colors.RED)


def _execute_ocr(
    ocr_adapter: "OCRPort",
    path: Path,
    language: str,
) -> tuple["OCRResult", float]:
    started = time.monotonic()
    result = ocr_adapter.process_document(path, language=language)
    elapsed = time.monotonic() - started
    return result, elapsed


def _write_output_text(
    result: "OCRResult",
    output: Path | None,
    source_path: Path,
    output_override: Path | None,
) -> Path | None:
    target = output_override
    if target is None and output is not None:
        target = _resolve_output_target(output, source_path)

    if target is None:
        return None

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.text, encoding="utf-8")
    typer.secho(f"  ➜ Saved: {target}", fg=typer.colors.BLUE)
    return target


def _resolve_output_target(base_output: Path, source_path: Path) -> Path:
    base = base_output.expanduser()
    if base.exists():
        if base.is_dir():
            return base / f"{source_path.stem}.txt"
        return base

    if base.suffix:
        base.parent.mkdir(parents=True, exist_ok=True)
        return base

    base.mkdir(parents=True, exist_ok=True)
    return base / f"{source_path.stem}.txt"


def _log_ocr_event(
    container: "ApplicationContainer",
    source: Path,
    provider: str,
    result: "OCRResult",
    elapsed: float,
    output_path: Path | None,
) -> None:
    outputs = [str(output_path)] if output_path else []
    try:
        container.ledger_port.log(
            operation="ocr.process",
            inputs=[str(source)],
            outputs=outputs,
            args={
                "provider": provider,
                "language": result.language,
                "page_count": result.page_count,
                "text_length": len(result.text),
                "confidence": round(result.confidence, 4),
                "elapsed_seconds": round(elapsed, 4),
            },
        )
    except Exception as exc:  # pragma: no cover - logging failures should not stop OCR
        typer.secho(f"⚠️  Audit log failure: {exc}", fg=typer.colors.YELLOW)


@contextmanager
def _override_preflight(ocr_adapter: "OCRPort", enabled: bool):
    if not hasattr(ocr_adapter, "preflight"):
        yield
        return

    typed_adapter = cast(Any, ocr_adapter)
    original = typed_adapter.preflight
    try:
        typed_adapter.preflight = enabled
        yield
    finally:
        typed_adapter.preflight = original


# Audit subcommand
audit_app = typer.Typer(help="Audit ledger management")
app.add_typer(audit_app, name="audit")


def _parse_comma_list(raw: str) -> list[str]:
    parts = [item.strip() for item in raw.split(",")]
    return [item for item in parts if item]


redaction_app = typer.Typer(help="PII redaction planning and application")
app.add_typer(redaction_app, name="redaction")


@redaction_app.command("plan")
def redaction_plan(
    input_path: Annotated[
        Path,
        typer.Argument(help="PDF to scan for PII", exists=True, resolve_path=True),
    ],
    output_plan: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination for encrypted plan (defaults to <file>.redaction-plan.enc)"),
    ] = None,
    pii_types: Annotated[
        str,
        typer.Option(
            "--pii-types",
            help="Comma-separated list of entity types (e.g. SSN,EMAIL,PHONE)",
        ),
    ] = "SSN,EMAIL,PHONE,CREDIT_CARD",
) -> None:
    """Generate a redaction plan for the provided document."""

    container = bootstrap_application()
    service = container.redaction_service

    resolved_input = input_path.expanduser()
    resolved_output = (
        output_plan.expanduser()
        if output_plan is not None
        else Path.cwd() / f"{resolved_input.stem}.redaction-plan.enc"
    )
    entities = [entry.upper() for entry in _parse_comma_list(pii_types)]

    plan = service.plan(
        resolved_input,
        resolved_output,
        pii_types=entities or None,
    )

    typer.secho(f"✅ Redaction plan created: {resolved_output}", fg=typer.colors.GREEN)
    typer.echo(f"   Plan ID: {plan.plan_id}")
    typer.echo(f"   Findings: {len(plan.redactions)}")


@redaction_app.command("apply")
def redaction_apply(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Encrypted redaction plan", exists=True, resolve_path=True),
    ],
    output_dir: Annotated[
        Path,
        typer.Argument(help="Directory to write redacted PDFs"),
    ],
    preview: Annotated[
        bool,
        typer.Option("--preview", help="Only report how many redactions would apply"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Apply even if the source hash differs from the plan"),
    ] = False,
) -> None:
    """Apply a previously generated redaction plan."""

    container = bootstrap_application()
    service = container.redaction_service

    resolved_output = output_dir.expanduser()
    count = service.apply(plan_path, resolved_output, preview=preview, force=force)

    if preview:
        typer.secho(f"🔍 Preview: {count} redactions would be applied", fg=typer.colors.CYAN)
    else:
        typer.secho(f"✅ Applied {count} redactions to {resolved_output}", fg=typer.colors.GREEN)


@audit_app.command("show")
def audit_show(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
    tail: Annotated[
        int | None,
        typer.Option("--tail", "-n", help="Show last N entries"),
    ] = None,
) -> None:
    """Show audit ledger entries."""

    container = bootstrap_application()

    if not container.audit_service.is_enabled():
        typer.secho("No audit ledger found", fg=typer.colors.YELLOW)
        return

    entries = container.audit_service.get_entries()

    if not entries:
        typer.secho("No audit ledger entries found", fg=typer.colors.YELLOW)
        return

    if tail:
        entries = entries[-tail:]

    if json_output:
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "audit_log",
                1,
                total_entries=len(entries),
                entries=[e.model_dump(mode="json") for e in entries],
            )
        )
    else:
        for entry in entries:
            typer.echo(f"{entry.timestamp} | {entry.operation} | {entry.inputs}")


@audit_app.command("verify")
def audit_verify() -> None:
    """Verify audit ledger integrity."""
    container = bootstrap_application()

    if not container.audit_service.is_enabled():
        typer.secho("No audit ledger found", fg=typer.colors.YELLOW)
        return

    valid, error = container.audit_service.verify()

    if valid:
        typer.secho("Audit ledger is valid", fg=typer.colors.GREEN)
        return

    message = error or "Audit ledger integrity check failed"
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


# Privilege subcommand
privilege_app = typer.Typer(help="Privilege classification and review")
app.add_typer(privilege_app, name="privilege")


# Privilege policy subcommands
policy_app = typer.Typer(help="Privilege policy management")
privilege_app.add_typer(policy_app, name="policy")


def _resolve_stage(stage: int) -> int:
    if stage not in (1, 2, 3):
        raise typer.BadParameter("Stage must be 1, 2, or 3.")
    return stage


def _policy_error(exc: Exception) -> "NoReturn":
    message = str(exc)
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from exc


@policy_app.command("list")
def privilege_policy_list(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return policy metadata as JSON"),
    ] = False,
) -> None:
    """List available privilege policy templates."""
    import json as _json

    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    policies = manager.list_policies()

    if json_output:
        typer.echo(_json.dumps([policy.to_dict() for policy in policies], indent=2))
        return

    for policy in policies:
        status = "missing" if not policy.exists else policy.source
        typer.secho(
            f"Stage {policy.stage} ({policy.stage_name}): {status}",
            fg=typer.colors.GREEN if policy.exists else typer.colors.YELLOW,
        )
        typer.echo(f"  Path: {policy.path}")
        if policy.exists:
            typer.echo(f"  SHA256: {policy.sha256}")
            typer.echo(f"  Size: {policy.size_bytes} bytes")
            if policy.modified_at:
                typer.echo(f"  Modified: {policy.modified_at.isoformat()}")


@policy_app.command("show")
def privilege_policy_show(
    stage: Annotated[
        int,
        typer.Option(
            "--stage",
            "-s",
            min=1,
            max=3,
            help="Policy stage to display",
        ),
    ] = 1,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return policy text and metadata as JSON"),
    ] = False,
) -> None:
    """Display the policy template for a given stage."""
    import json as _json

    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    try:
        metadata, text = manager.show_policy(_resolve_stage(stage))
    except (FileNotFoundError, ValueError) as exc:
        _policy_error(exc)

    if json_output:
        payload = metadata.to_dict()
        payload["text"] = text
        typer.echo(_json.dumps(payload, indent=2))
        return

    typer.secho(f"Stage {metadata.stage} ({metadata.stage_name})", bold=True)
    typer.echo(f"Path: {metadata.path}")
    typer.echo()
    typer.echo(text)


@policy_app.command("edit")
def privilege_policy_edit(
    stage: Annotated[
        int,
        typer.Option(
            "--stage",
            "-s",
            min=1,
            max=3,
            help="Policy stage to edit",
        ),
    ] = 1,
    editor: Annotated[
        str | None,
        typer.Option("--editor", help="Override $EDITOR for this edit session"),
    ] = None,
) -> None:
    """Open the policy template in $EDITOR and persist changes."""
    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    target_stage = _resolve_stage(stage)
    try:
        edit_path = manager.prepare_edit_path(target_stage)
    except (FileNotFoundError, ValueError) as exc:
        _policy_error(exc)

    initial_text = ""
    if edit_path.exists():
        initial_text = edit_path.read_text(encoding="utf-8")

    typer.secho(f"Editing Stage {target_stage} policy at {edit_path}", fg=typer.colors.BLUE)
    updated_text = typer.edit(initial_text, editor=editor)

    if updated_text is None:
        typer.secho("Edit cancelled. Policy not modified.", fg=typer.colors.YELLOW)
        return

    if not updated_text.endswith("\n"):
        updated_text += "\n"

    if updated_text == initial_text:
        typer.secho("No changes detected. Policy remains unchanged.", fg=typer.colors.YELLOW)
        return

    metadata = manager.save_policy_from_text(
        target_stage,
        updated_text,
        source="editor",
        command_args=_resolve_invocation_tokens(),
    )
    typer.secho(
        f"Policy updated: Stage {metadata.stage} ({metadata.stage_name})",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Path: {metadata.path}")
    typer.echo(f"SHA256: {metadata.sha256}")


@policy_app.command("diff")
def privilege_policy_diff(
    other: Annotated[
        Path,
        typer.Argument(help="Path to compare against", exists=True, dir_okay=False, readable=True),
    ],
    stage: Annotated[
        int,
        typer.Option(
            "--stage",
            "-s",
            min=1,
            max=3,
            help="Policy stage to diff",
        ),
    ] = 1,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return diff output as JSON payload"),
    ] = False,
) -> None:
    """Show diff between current policy and another file."""
    import json as _json

    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    try:
        diff_text = manager.diff_with_file(_resolve_stage(stage), other)
    except (FileNotFoundError, ValueError) as exc:
        _policy_error(exc)

    if json_output:
        typer.echo(_json.dumps({"diff": diff_text}, indent=2))
        return

    if not diff_text.strip():
        typer.secho("Policies are identical.", fg=typer.colors.GREEN)
        return

    typer.echo(diff_text)


@policy_app.command("apply")
def privilege_policy_apply(
    stage: Annotated[
        int,
        typer.Option(
            "--stage",
            "-s",
            min=1,
            max=3,
            help="Policy stage to update",
        ),
    ] = 1,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file",
            "-f",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Source file containing updated policy text",
        ),
    ] = None,
    stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read updated policy text from STDIN"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return update metadata as JSON"),
    ] = False,
) -> None:
    """Apply policy changes from file or STDIN."""
    import json as _json

    if stdin and file is not None:
        raise typer.BadParameter("Use either --stdin or --file, not both.")
    if not stdin and file is None:
        raise typer.BadParameter("Provide --file or --stdin to update policy.")

    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    target_stage = _resolve_stage(stage)
    command_tokens = _resolve_invocation_tokens()

    try:
        if stdin:
            updated_text = sys.stdin.read()
            if not updated_text.endswith("\n"):
                updated_text += "\n"
            metadata = manager.save_policy_from_text(
                target_stage,
                updated_text,
                source="stdin",
                command_args=command_tokens,
            )
        else:
            assert file is not None
            metadata = manager.apply_from_file(
                target_stage,
                file,
                command_args=command_tokens,
            )
    except (FileNotFoundError, ValueError) as exc:
        _policy_error(exc)

    if json_output:
        typer.echo(_json.dumps(metadata.to_dict(), indent=2))
        return

    typer.secho(
        f"Policy updated from {'STDIN' if stdin else file}: Stage {metadata.stage} ({metadata.stage_name})",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Path: {metadata.path}")
    typer.echo(f"SHA256: {metadata.sha256}")


@policy_app.command("validate")
def privilege_policy_validate(
    stage: Annotated[
        int,
        typer.Option(
            "--stage",
            "-s",
            min=1,
            max=3,
            help="Policy stage to validate",
        ),
    ] = 1,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Return validation report as JSON"),
    ] = False,
) -> None:
    """Run structural validation on the policy template."""
    import json as _json

    container = bootstrap_application()
    manager = PrivilegePolicyManager(container.settings, container.ledger_port)
    try:
        result = manager.validate_policy(_resolve_stage(stage))
    except (FileNotFoundError, ValueError) as exc:
        _policy_error(exc)

    if json_output:
        typer.echo(_json.dumps(result, indent=2))
        return

    if result["passed"]:
        typer.secho(
            f"Policy Stage {result['stage']} ({result['stage_name']}) passed validation.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Policy Stage {result['stage']} ({result['stage_name']}) failed validation.",
            fg=typer.colors.RED,
        )
        typer.echo("Errors:")
        for error in result["errors"]:
            typer.echo(f"  - {error}")

@privilege_app.command("classify")
def privilege_classify(
    file_path: Annotated[
        Path,
        typer.Argument(help="Document file to classify (text, PDF, or DOCX)", exists=True),
    ],
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Confidence threshold (0.0-1.0)"),
    ] = 0.75,
    reasoning_effort: Annotated[
        str,
        typer.Option(
            "--reasoning-effort",
            "-r",
            help="Reasoning effort: low, medium, high, or dynamic",
        ),
    ] = "dynamic",
    model_path: Annotated[
        Path | None,
        typer.Option("--model-path", help="Override model path"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Classify a document for attorney-client privilege.

    This command uses Groq Cloud API (if online) or self-hosted gpt-oss-safeguard-20b
    model to classify documents for privilege.

    Privacy note: Full reasoning chain is hashed, not logged. Only redacted
    summaries appear in audit logs.

    Example:
        rexlit privilege classify email001.txt
        rexlit privilege classify --threshold 0.80 --reasoning-effort high doc.pdf
    """

    from rexlit.app.privilege_service import PrivilegeReviewService
    from rexlit.bootstrap import _create_privilege_reasoning_adapter

    container = bootstrap_application()

    # Determine model path (for fallback to Safeguard adapter)
    if model_path is None:
        model_path = container.settings.get_privilege_model_path()

    # Load policy
    try:
        policy_path = container.settings.get_privilege_policy_path(stage=1)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize adapter (prefer Groq if online, fall back to Safeguard)
    try:
        adapter = _create_privilege_reasoning_adapter(
            container.settings,
            model_path=model_path,
            policy_path=policy_path,
        )
        if adapter is None:
            typer.secho(
                "❌ No privilege adapter available. Install gpt-oss-safeguard-20b or configure "
                "GROQ_API_KEY with --online flag.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"❌ Failed to initialize privilege adapter: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize service
    service = PrivilegeReviewService(
        safeguard_adapter=adapter,
        ledger_port=container.ledger_port,
        pattern_skip_threshold=container.settings.privilege_pattern_skip_threshold,
        pattern_escalate_threshold=container.settings.privilege_pattern_escalate_threshold,
    )

    # Read document text
    try:
        # Use extract_document which handles all file types (text, PDF, DOCX, images)
        from rexlit.ingest.extract import extract_document

        extracted = extract_document(file_path)
        text = extracted.text
    except Exception as e:
        typer.secho(f"❌ Failed to read document: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Classify
    if not json_output:
        typer.secho(
            f"🔍 Classifying {file_path.name}...",
            fg=typer.colors.CYAN,
            err=True,
        )
    try:
        decision = service.review_document(
            doc_id=str(file_path),
            text=text,
            threshold=threshold,
        )
    except Exception as e:
        typer.secho(f"❌ Classification failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Output results
    if json_output:
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "privilege_decision",
                1,
                document=str(file_path),
                **decision.model_dump(mode="json"),
            )
        )
    else:
        if decision.labels:
            label_str = ", ".join(decision.labels)
            color = typer.colors.YELLOW if decision.is_privileged else typer.colors.GREEN
            typer.secho(f"✓ Labels: {label_str}", fg=color)
        else:
            typer.secho("✓ Non-privileged", fg=typer.colors.GREEN)

        typer.echo(f"  Confidence: {decision.confidence:.2f}")
        typer.echo(f"  Needs Review: {decision.needs_review}")
        typer.echo(f"  Reasoning Hash: {decision.reasoning_hash[:16]}...")
        typer.echo(f"  Summary: {decision.reasoning_summary[:100]}...")

        if decision.error_message:
            typer.secho(f"  ⚠️  Error: {decision.error_message}", fg=typer.colors.YELLOW)


@privilege_app.command("explain")
def privilege_explain(
    file_path: Annotated[
        Path,
        typer.Argument(help="Document file to explain", exists=True),
    ],
    model_path: Annotated[
        Path | None,
        typer.Option("--model-path", help="Override model path"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Classify document with detailed explanation (verbose mode).

    This command is identical to `classify` but always uses high reasoning effort
    and displays the full (redacted) reasoning summary.

    Example:
        rexlit privilege explain email001.txt
    """
    import json

    from rexlit.app.privilege_service import PrivilegeReviewService
    from rexlit.bootstrap import _create_privilege_reasoning_adapter

    container = bootstrap_application()

    # Determine model path (for fallback to Safeguard adapter)
    if model_path is None:
        model_path = container.settings.get_privilege_model_path()

    # Load policy
    try:
        policy_path = container.settings.get_privilege_policy_path(stage=1)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize adapter (prefer Groq if online, fall back to Safeguard)
    try:
        adapter = _create_privilege_reasoning_adapter(
            container.settings,
            model_path=model_path,
            policy_path=policy_path,
        )
        if adapter is None:
            typer.secho(
                "❌ No privilege adapter available. Install gpt-oss-safeguard-20b or configure "
                "GROQ_API_KEY with --online flag.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"❌ Failed to initialize privilege adapter: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize service
    service = PrivilegeReviewService(
        safeguard_adapter=adapter,
        ledger_port=container.ledger_port,
    )

    # Read document text
    try:
        # Use extract_document which handles all file types (text, PDF, DOCX, images)
        from rexlit.ingest.extract import extract_document

        extracted = extract_document(file_path)
        text = extracted.text
    except Exception as e:
        typer.secho(f"❌ Failed to read document: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Classify with high reasoning effort
    if not json_output:
        typer.secho(
            f"🔍 Explaining privilege classification for {file_path.name}...",
            fg=typer.colors.CYAN,
            err=True,
        )
        typer.secho(
            "   (Using high reasoning effort for detailed analysis)",
            fg=typer.colors.CYAN,
            err=True,
        )

    try:
        decision = service.review_document(
            doc_id=str(file_path),
            text=text,
            threshold=0.75,
            force_llm=True,  # Always use LLM with high effort
        )
    except Exception as e:
        typer.secho(f"❌ Classification failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(decision.model_dump(mode="json"), indent=2))
        return

    # Display detailed results
    typer.echo()
    typer.secho("═" * 80, fg=typer.colors.CYAN)
    typer.secho("PRIVILEGE CLASSIFICATION REPORT", fg=typer.colors.CYAN, bold=True)
    typer.secho("═" * 80, fg=typer.colors.CYAN)
    typer.echo()

    typer.secho(f"Document: {file_path}", bold=True)
    typer.echo()

    if decision.labels:
        label_str = ", ".join(decision.labels)
        color = typer.colors.YELLOW if decision.is_privileged else typer.colors.GREEN
        typer.secho(f"Classification: {label_str}", fg=color, bold=True)
    else:
        typer.secho("Classification: NON-PRIVILEGED", fg=typer.colors.GREEN, bold=True)

    typer.echo(f"Confidence: {decision.confidence:.2%}")
    typer.echo(f"Needs Review: {'Yes' if decision.needs_review else 'No'}")
    typer.echo(f"Model: {decision.model_version}")
    typer.echo(f"Policy: {decision.policy_version}")
    typer.echo(f"Reasoning Effort: {decision.reasoning_effort}")
    typer.echo()

    typer.secho("Reasoning Summary:", bold=True)
    typer.echo(f"  {decision.reasoning_summary}")
    typer.echo()

    typer.secho("Privacy Note:", fg=typer.colors.YELLOW)
    typer.echo(f"  Reasoning Hash: {decision.reasoning_hash}")
    typer.echo(
        f"  Full CoT Stored: {'Yes' if decision.full_reasoning_available else 'No (hashed only)'}"
    )
    typer.echo()

    if decision.error_message:
        typer.secho("⚠️  Errors/Warnings:", fg=typer.colors.YELLOW)
        typer.echo(f"  {decision.error_message}")
        typer.echo()

@app.command("doctor")
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show additional diagnostic information"),
    ] = False,
) -> None:
    """Run health checks and report system status.

    Verifies that RexLit is properly configured and can run core operations.
    Useful for troubleshooting first-run issues and validating production setups.

    Example:
        rexlit doctor
        rexlit doctor --json
        rexlit doctor --verbose
    """
    import shutil
    import platform
    from rexlit import __version__
    from rexlit.config import get_settings

    checks: list[dict[str, str | bool]] = []
    all_passed = True

    def add_check(name: str, passed: bool, message: str, suggestion: str = "") -> None:
        nonlocal all_passed
        if not passed:
            all_passed = False
        checks.append({
            "name": name,
            "passed": passed,
            "message": message,
            "suggestion": suggestion,
        })

    # 1. Python version
    py_version = platform.python_version()
    py_ok = sys.version_info >= (3, 11)
    add_check(
        "python_version",
        py_ok,
        f"Python {py_version}",
        "RexLit requires Python 3.11+" if not py_ok else "",
    )

    # 2. RexLit version
    add_check(
        "rexlit_installed",
        True,
        f"RexLit {__version__}",
        "",
    )

    # 3. Data directory
    try:
        settings = get_settings()
        data_dir = settings.get_data_dir()
        data_dir_exists = data_dir.exists()
        data_dir_writable = data_dir_exists and data_dir.is_dir()
        if data_dir_writable:
            try:
                test_file = data_dir / ".doctor_test"
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError):
                data_dir_writable = False

        add_check(
            "data_directory",
            data_dir_writable,
            f"Data directory: {data_dir}" + (" (writable)" if data_dir_writable else ""),
            f"Create or fix permissions: mkdir -p {data_dir}" if not data_dir_writable else "",
        )
    except Exception as e:
        add_check(
            "data_directory",
            False,
            f"Failed to resolve data directory: {e}",
            "Check REXLIT_HOME or REXLIT_DATA_DIR environment variables",
        )
        settings = None

    # 4. Index status
    if settings:
        try:
            index_dir = settings.get_index_dir()
            index_exists = index_dir.exists() and (index_dir / "meta.json").exists()
            if index_exists:
                # Count indexed documents via metadata cache
                cache_path = index_dir / ".metadata_cache.json"
                if cache_path.exists():
                    import json as _json
                    try:
                        cache = _json.loads(cache_path.read_text(encoding="utf-8"))
                        doc_count = cache.get("total_documents", "unknown")
                        add_check(
                            "search_index",
                            True,
                            f"Search index: {doc_count} documents indexed",
                            "",
                        )
                    except Exception:
                        add_check("search_index", True, "Search index exists", "")
                else:
                    add_check("search_index", True, "Search index exists (no metadata cache)", "")
            else:
                add_check(
                    "search_index",
                    False,
                    "No search index found",
                    "Build with: rexlit index build <documents-path>",
                )
        except Exception as e:
            add_check("search_index", False, f"Index check failed: {e}", "")

    # 5. Audit ledger
    if settings:
        try:
            audit_path = settings.get_audit_path()
            audit_ok = audit_path.exists() and audit_path.stat().st_size > 0
            if audit_ok:
                # Try to verify integrity
                container = bootstrap_application(settings)
                valid, error = container.audit_service.verify()
                if valid:
                    add_check("audit_ledger", True, f"Audit ledger: {audit_path} (verified)", "")
                else:
                    add_check(
                        "audit_ledger",
                        False,
                        f"Audit ledger integrity failed: {error}",
                        "Regenerate audit ledger from trusted manifests",
                    )
            else:
                add_check(
                    "audit_ledger",
                    True,  # Not having an audit log is OK for first run
                    "No audit ledger yet (will be created on first operation)",
                    "",
                )
        except Exception as e:
            add_check("audit_ledger", False, f"Audit check failed: {e}", "")

    # 6. Tesseract OCR (optional)
    tesseract_path = shutil.which("tesseract")
    if tesseract_path:
        try:
            import subprocess
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            add_check("tesseract_ocr", True, f"Tesseract: {version_line}", "")
        except Exception:
            add_check("tesseract_ocr", True, f"Tesseract found: {tesseract_path}", "")
    else:
        add_check(
            "tesseract_ocr",
            True,  # Optional, so still "pass" but with note
            "Tesseract not installed (OCR features unavailable)",
            "Install with: brew install tesseract (macOS) or apt install tesseract-ocr",
        )

    # 7. API connectivity check hint (if verbose)
    if verbose and settings:
        add_check(
            "api_hint",
            True,
            "API: Start with 'cd api && REXLIT_HOME=$PWD bun run index.ts'",
            "",
        )

    # Output results
    if json_output:
        import json as _json
        from rexlit.utils.cli_output import json_response

        typer.echo(
            json_response(
                "doctor_report",
                1,
                all_passed=all_passed,
                checks=checks,
            )
        )
    else:
        typer.echo()
        typer.secho("🩺 RexLit Doctor", fg=typer.colors.CYAN, bold=True)
        typer.secho("=" * 40, fg=typer.colors.CYAN)
        typer.echo()

        for check in checks:
            icon = "✓" if check["passed"] else "✗"
            color = typer.colors.GREEN if check["passed"] else typer.colors.RED
            typer.secho(f"  {icon} {check['message']}", fg=color)
            if check.get("suggestion") and not check["passed"]:
                typer.secho(f"    → {check['suggestion']}", fg=typer.colors.YELLOW)

        typer.echo()
        if all_passed:
            typer.secho("All checks passed! ✓", fg=typer.colors.GREEN, bold=True)
        else:
            typer.secho("Some checks failed. See suggestions above.", fg=typer.colors.RED)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
