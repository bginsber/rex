from __future__ import annotations

from pathlib import Path

from rexlit.bootstrap import TantivyIndexAdapter
from rexlit.config import Settings
from rexlit.index.search import SearchResult


def test_tantivy_adapter_hybrid_search_delegates_when_online(temp_dir: Path, monkeypatch) -> None:
    settings = Settings(data_dir=temp_dir, online=True)
    adapter = TantivyIndexAdapter(settings)

    fused = SearchResult(
        path="doc.txt",
        sha256="sha-1",
        custodian=None,
        doctype="txt",
        score=1.23,
        dense_score=0.9,
        lexical_score=0.5,
        strategy="hybrid",
        snippet=None,
        metadata=None,
    )

    # Patch hybrid function (adapter imports symbol at call time)
    monkeypatch.setattr(
        "rexlit.index.search.hybrid_search_index",
        lambda *args, **kwargs: ([fused], {"fusion": "rrf"}),
    )

    results = adapter.search("query", limit=1, mode="hybrid")
    assert len(results) == 1
    assert results[0].strategy == "hybrid"


def test_tantivy_adapter_lexical_search_delegates(temp_dir: Path, monkeypatch) -> None:
    cfg_dir = temp_dir / "cfg"
    settings = Settings(data_dir=temp_dir, config_dir=cfg_dir)
    adapter = TantivyIndexAdapter(settings)

    expected = SearchResult(
        path="doc.txt",
        sha256="sha",
        custodian=None,
        doctype=None,
        score=1.0,
        lexical_score=1.0,
        dense_score=None,
        strategy="lexical",
        snippet=None,
        metadata=None,
    )

    calls: dict[str, object] = {}

    def fake_lexical(index_dir: Path, query: str, limit: int) -> list[SearchResult]:
        calls["index_dir"] = index_dir
        calls["query"] = query
        calls["limit"] = limit
        return [expected]

    monkeypatch.setattr("rexlit.bootstrap.lexical_search_index", fake_lexical)

    results = adapter.search("needle")

    assert results == [expected]
    assert calls["query"] == "needle"
    assert calls["limit"] == 10
    assert calls["index_dir"] == settings.get_index_dir()


def test_tantivy_adapter_dense_search_respects_cli_overrides(
    temp_dir: Path, monkeypatch
) -> None:
    cfg_dir = temp_dir / "cfg"
    settings = Settings(data_dir=temp_dir, config_dir=cfg_dir, online=True)
    adapter = TantivyIndexAdapter(settings)

    sentinel_embedder = object()
    safe_calls: list[tuple[str | None, str | None]] = []
    dense_call: dict[str, object] = {}

    def fake_safe_init(
        offline_gate, *, api_key: str | None = None, api_base: str | None = None
    ) -> object:
        safe_calls.append((api_key, api_base))
        return sentinel_embedder

    def fake_dense_search_index(
        index_dir: Path,
        query: str,
        *,
        limit: int,
        dim: int,
        api_key: str | None,
        api_base: str | None,
        embedder,
        vector_store,
    ) -> tuple[list[SearchResult], dict[str, object]]:
        dense_call["api_key"] = api_key
        dense_call["api_base"] = api_base
        dense_call["embedder"] = embedder
        dense_call["limit"] = limit
        dense_call["dim"] = dim
        return (
            [
                SearchResult(
                    path="doc.txt",
                    sha256="sha",
                    custodian=None,
                    doctype=None,
                    score=0.5,
                    lexical_score=None,
                    dense_score=0.5,
                    strategy="dense",
                    snippet=None,
                    metadata=None,
                )
            ],
            {},
        )

    monkeypatch.setattr("rexlit.bootstrap._safe_init_embedder", fake_safe_init)
    monkeypatch.setattr("rexlit.bootstrap.dense_search_index", fake_dense_search_index)

    results = adapter.search(
        "needle",
        mode="dense",
        api_key="override-key",
        api_base="https://override",
    )

    assert results and results[0].strategy == "dense"
    assert safe_calls == [("override-key", "https://override")]
    assert dense_call["api_key"] == "override-key"
    assert dense_call["api_base"] == "https://override"
    assert dense_call["embedder"] is sentinel_embedder


def test_tantivy_adapter_dense_build_respects_cli_overrides(
    temp_dir: Path, monkeypatch
) -> None:
    cfg_dir = temp_dir / "cfg"
    settings = Settings(data_dir=temp_dir, config_dir=cfg_dir, online=True)
    adapter = TantivyIndexAdapter(settings)

    source_dir = temp_dir / "docs"
    source_dir.mkdir()

    sentinel_embedder = object()
    safe_calls: list[tuple[str | None, str | None]] = []
    dense_build_call: dict[str, object] = {}

    def fake_safe_init(
        offline_gate, *, api_key: str | None = None, api_base: str | None = None
    ) -> object:
        safe_calls.append((api_key, api_base))
        return sentinel_embedder

    def fake_build_index(
        source: Path,
        index_dir: Path,
        *,
        rebuild: bool = False,
        dense_collector: list[dict] | None = None,
        **kwargs,
    ) -> int:
        if dense_collector is not None:
            dense_collector.append(
                {
                    "identifier": "doc-1",
                    "path": str(source / "doc1.txt"),
                    "sha256": "sha-1",
                    "custodian": None,
                    "doctype": "txt",
                    "text": "hello world",
                }
            )
        return 1

    def fake_build_dense_index(
        dense_documents,
        *,
        index_dir: Path,
        dim: int,
        batch_size: int,
        api_key: str | None,
        api_base: str | None,
        embedder,
        vector_store,
        ledger,
    ) -> None:
        dense_build_call["documents"] = list(dense_documents)
        dense_build_call["api_key"] = api_key
        dense_build_call["api_base"] = api_base
        dense_build_call["embedder"] = embedder
        dense_build_call["index_dir"] = index_dir
        dense_build_call["dim"] = dim
        dense_build_call["batch_size"] = batch_size
        return None

    monkeypatch.setattr("rexlit.bootstrap._safe_init_embedder", fake_safe_init)
    monkeypatch.setattr("rexlit.bootstrap.build_index", fake_build_index)
    monkeypatch.setattr("rexlit.bootstrap.build_dense_index", fake_build_dense_index)

    count = adapter.build(
        source_dir,
        dense=True,
        dense_api_key="override-key",
        dense_api_base="https://override",
        dense_dim=256,
        dense_batch_size=8,
    )

    assert count == 1
    assert safe_calls == [("override-key", "https://override")]
    assert dense_build_call["api_key"] == "override-key"
    assert dense_build_call["api_base"] == "https://override"
    assert dense_build_call["embedder"] is sentinel_embedder
    assert dense_build_call["documents"][0]["text"] == "hello world"
