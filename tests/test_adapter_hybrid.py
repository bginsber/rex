from __future__ import annotations

from pathlib import Path

from rexlit.bootstrap import TantivyIndexAdapter
from rexlit.config import Settings
from rexlit.index.search import SearchResult


def test_tantivy_adapter_hybrid_search_delegates_when_online(
    temp_dir: Path, monkeypatch
) -> None:
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
