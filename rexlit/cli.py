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
from rexlit.bootstrap import bootstrap_application
from rexlit.config import get_settings, set_settings
from rexlit.utils.methods import sanitize_argv
from rexlit.utils.offline import OfflineModeGate
from rexlit.index.search import search_by_hash

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
        exclude_extensions={".pdf"},
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
    import json

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
        typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
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
    import json

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
        typer.echo(json.dumps(payload, indent=2))
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
    import json

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
        typer.echo(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
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

    This command uses the self-hosted gpt-oss-safeguard-20b model to classify
    documents for privilege. All processing is offline (no network calls).

    Privacy note: Full reasoning chain is hashed, not logged. Only redacted
    summaries appear in audit logs.

    Example:
        rexlit privilege classify email001.txt
        rexlit privilege classify --threshold 0.80 --reasoning-effort high doc.pdf
    """
    import json

    from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter
    from rexlit.app.privilege_service import PrivilegeReviewService

    container = bootstrap_application()

    # Determine model path
    if model_path is None:
        model_path = container.settings.get_privilege_model_path()
        if model_path is None:
            typer.secho(
                "❌ Privilege model not found. Install gpt-oss-safeguard-20b or configure "
                "privilege_model_path in settings.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    # Load policy
    try:
        policy_path = container.settings.get_privilege_policy_path(stage=1)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize adapter
    try:
        adapter = PrivilegeSafeguardAdapter(
            model_path=model_path,
            policy_path=policy_path,
            log_full_cot=container.settings.privilege_log_full_cot,
            cot_vault_path=container.settings.get_privilege_cot_vault_path(),
            vault_key_path=container.settings.get_privilege_cot_vault_key_path(),
            timeout_seconds=container.settings.privilege_timeout_seconds,
            circuit_breaker_threshold=container.settings.privilege_circuit_breaker_threshold,
        )
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
    typer.secho(f"🔍 Classifying {file_path.name}...", fg=typer.colors.CYAN)
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
        typer.echo(json.dumps(decision.model_dump(mode="json"), indent=2))
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
) -> None:
    """Classify document with detailed explanation (verbose mode).

    This command is identical to `classify` but always uses high reasoning effort
    and displays the full (redacted) reasoning summary.

    Example:
        rexlit privilege explain email001.txt
    """
    import json

    from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter
    from rexlit.app.privilege_service import PrivilegeReviewService

    container = bootstrap_application()

    # Determine model path
    if model_path is None:
        model_path = container.settings.get_privilege_model_path()
        if model_path is None:
            typer.secho(
                "❌ Privilege model not found. Install gpt-oss-safeguard-20b or configure "
                "privilege_model_path in settings.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)

    # Load policy
    try:
        policy_path = container.settings.get_privilege_policy_path(stage=1)
    except FileNotFoundError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize adapter
    try:
        adapter = PrivilegeSafeguardAdapter(
            model_path=model_path,
            policy_path=policy_path,
            log_full_cot=container.settings.privilege_log_full_cot,
            cot_vault_path=container.settings.get_privilege_cot_vault_path(),
            vault_key_path=container.settings.get_privilege_cot_vault_key_path(),
            timeout_seconds=container.settings.privilege_timeout_seconds,
            circuit_breaker_threshold=container.settings.privilege_circuit_breaker_threshold,
        )
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
    typer.secho(f"🔍 Explaining privilege classification for {file_path.name}...", fg=typer.colors.CYAN)
    typer.secho("   (Using high reasoning effort for detailed analysis)", fg=typer.colors.CYAN)

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


if __name__ == "__main__":
    app()
