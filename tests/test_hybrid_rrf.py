from __future__ import annotations

from pathlib import Path

from rexlit.index.search import SearchResult, hybrid_search_index


def test_hybrid_rrf_fusion_orders_by_rrf(monkeypatch, tmp_path: Path) -> None:
    # Lexical ranks: A(1), B(2), C(3)
    lex = [
        SearchResult(path="a.txt", sha256="A", custodian=None, doctype=None, score=3.0, lexical_score=3.0, dense_score=None, strategy="lexical", snippet=None, metadata=None),  # noqa: E501
        SearchResult(path="b.txt", sha256="B", custodian=None, doctype=None, score=2.0, lexical_score=2.0, dense_score=None, strategy="lexical", snippet=None, metadata=None),  # noqa: E501
        SearchResult(path="c.txt", sha256="C", custodian=None, doctype=None, score=1.0, lexical_score=1.0, dense_score=None, strategy="lexical", snippet=None, metadata=None),  # noqa: E501
    ]
    # Dense ranks: B(1), C(2), A(3)
    den = [
        SearchResult(path="b.txt", sha256="B", custodian=None, doctype=None, score=0.9, lexical_score=None, dense_score=0.9, strategy="dense", snippet=None, metadata=None),  # noqa: E501
        SearchResult(path="c.txt", sha256="C", custodian=None, doctype=None, score=0.8, lexical_score=None, dense_score=0.8, strategy="dense", snippet=None, metadata=None),  # noqa: E501
        SearchResult(path="a.txt", sha256="A", custodian=None, doctype=None, score=0.7, lexical_score=None, dense_score=0.7, strategy="dense", snippet=None, metadata=None),  # noqa: E501
    ]

    monkeypatch.setattr("rexlit.index.search.search_index", lambda *a, **k: lex)
    monkeypatch.setattr(
        "rexlit.index.search.dense_search_index",
        lambda *a, **k: (den, {"latency_ms": 1.0, "usage": {}}),
    )

    results, telemetry = hybrid_search_index(tmp_path, "query", limit=3, fusion_k=60)

    # Compute expected RRF scores
    def rrf(rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)

    expected_scores = {
        "A": rrf(1) + rrf(3),  # lex rank 1 + dense rank 3
        "B": rrf(2) + rrf(1),
        "C": rrf(3) + rrf(2),
    }

    # Sort expected by score desc
    expected_order = sorted(expected_scores.items(), key=lambda x: x[1], reverse=True)
    got_order = [r.sha256 for r in results]
    assert got_order == [doc for doc, _ in expected_order]
    assert telemetry["fusion"] == "rrf"
