"""RexLit CLI application with Typer."""

from pathlib import Path
from typing import Annotated

import typer

from rexlit import __version__
from rexlit.bootstrap import bootstrap_application
from rexlit.config import get_settings, set_settings
from rexlit.utils.offline import OfflineModeGate

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
) -> None:
    """Ingest documents from path and extract metadata."""
    container = bootstrap_application()

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Discovering documents in {path}...", fg=typer.colors.BLUE)
    manifest_path = manifest.resolve() if manifest else None
    result = container.pipeline.run(
        path,
        manifest_path=manifest_path,
        recursive=recursive,
    )

    typer.secho(f"Found {len(result.documents)} documents", fg=typer.colors.GREEN)

    for stage in result.stages:
        color = typer.colors.GREEN if stage.status == "completed" else typer.colors.YELLOW
        typer.secho(f"[{stage.status}] {stage.name}", fg=color)

    if result.notes:
        for note in result.notes:
            typer.secho(f"NOTE: {note}", fg=typer.colors.YELLOW)

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
    settings = container.settings
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
    except FileNotFoundError:
        typer.secho(
            "Error: Index not found. Run 'rexlit index build' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

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


# OCR subcommand (Phase 2)
ocr_app = typer.Typer(help="OCR processing")
app.add_typer(ocr_app, name="ocr")


@ocr_app.command("run")
def ocr_run(
    path: Annotated[Path, typer.Argument(help="Path to document or directory")],
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="OCR provider: tesseract, paddle, deepseek"),
    ] = "tesseract",
    online: Annotated[
        bool,
        typer.Option("--online", help="Enable online OCR (DeepSeek)"),
    ] = False,
) -> None:
    """Run OCR on documents."""
    settings = get_settings()

    if online and not settings.online:
        settings.online = True
        set_settings(settings)

    gate = OfflineModeGate.from_settings(settings)

    if provider == "deepseek":
        require_online(gate, "DeepSeek OCR")

    typer.secho(f"OCR not yet implemented (provider: {provider})", fg=typer.colors.YELLOW)


# Audit subcommand
audit_app = typer.Typer(help="Audit ledger management")
app.add_typer(audit_app, name="audit")


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


if __name__ == "__main__":
    app()
