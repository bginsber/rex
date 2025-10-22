"""RexLit CLI application with Typer."""

import os
from pathlib import Path
from typing import Annotated

import typer

from rexlit import __version__
from rexlit.config import Settings, get_settings, set_settings

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


def require_online(settings: Settings, online_flag: bool, feature_name: str) -> None:
    """Check if online mode is enabled, exit if not.

    Args:
        settings: Current settings instance
        online_flag: Value of --online CLI flag
        feature_name: Name of feature requiring online mode
    """
    is_online = settings.online or bool(os.getenv("REXLIT_ONLINE")) or online_flag

    if not is_online:
        typer.secho(
            f"\n{feature_name} requires online mode.\n"
            f"Enable with: --online flag or REXLIT_ONLINE=1\n"
            f"Aborting.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=2)


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
    from rexlit.audit.ledger import AuditLedger
    from rexlit.ingest.discover import discover_documents

    settings = get_settings()

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initialize audit ledger
    ledger = AuditLedger(settings.get_audit_path()) if settings.audit_enabled else None

    # Discover and ingest documents using streaming pattern
    typer.secho(f"Discovering documents in {path}...", fg=typer.colors.BLUE)

    # Collect documents for processing
    import json

    document_count = 0
    sha256_hashes = []

    # Clear manifest file if it exists
    if manifest:
        open(manifest, "w").close()

    # Process documents as stream
    for doc_meta in discover_documents(path, recursive=recursive):
        document_count += 1
        sha256_hashes.append(doc_meta.sha256)

        # Write to manifest if requested
        if manifest:
            # Open in append mode for streaming writes
            with open(manifest, "a") as f:
                f.write(json.dumps(doc_meta.model_dump(mode="json")) + "\n")

    typer.secho(f"Found {document_count} documents", fg=typer.colors.GREEN)

    if manifest:
        typer.secho(f"Manifest written to {manifest}", fg=typer.colors.GREEN)

    # Log to audit ledger
    if ledger:
        ledger.log(
            operation="ingest",
            inputs=[str(path)],
            outputs=sha256_hashes,
            args={"watch": watch, "recursive": recursive},
        )

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
) -> None:
    """Build search index from documents."""
    from rexlit.index.build import build_index

    settings = get_settings()

    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"Building index from {path}...", fg=typer.colors.BLUE)
    index_dir = settings.get_index_dir()

    count = build_index(path, index_dir, rebuild=rebuild)
    typer.secho(f"Indexed {count} documents to {index_dir}", fg=typer.colors.GREEN)


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
) -> None:
    """Search the index."""
    import json

    from rexlit.index.search import search_index

    settings = get_settings()
    index_dir = settings.get_index_dir()

    if not index_dir.exists():
        typer.secho(
            "Error: Index not found. Run 'rexlit index build' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    results = search_index(index_dir, query, limit=limit)

    if json_output:
        typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
    else:
        typer.secho(f"Found {len(results)} results for '{query}':", fg=typer.colors.BLUE)
        for i, result in enumerate(results, 1):
            typer.echo(f"\n{i}. {result.path} (score: {result.score:.2f})")
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

    if provider == "deepseek":
        require_online(settings, online, "DeepSeek OCR")

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

    from rexlit.audit.ledger import AuditLedger

    settings = get_settings()
    audit_path = settings.get_audit_path()

    if not audit_path.exists():
        typer.secho("No audit ledger found", fg=typer.colors.YELLOW)
        return

    ledger = AuditLedger(audit_path)
    entries = ledger.read_all()

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
    from rexlit.audit.ledger import AuditLedger

    settings = get_settings()
    audit_path = settings.get_audit_path()

    if not audit_path.exists():
        typer.secho("No audit ledger found", fg=typer.colors.YELLOW)
        return

    ledger = AuditLedger(audit_path)
    if ledger.verify():
        typer.secho("Audit ledger is valid", fg=typer.colors.GREEN)
    else:
        typer.secho("Audit ledger integrity check failed", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
