from ccrf.models import Snippet
from ccrf.rag import merge_rag_snippets, rag_enabled


def test_merge_dedupes_rag_and_keyword_snippets():
    keyword = [
        Snippet(
            file_name="Special_Provisions.pdf",
            document_type="Special Provisions",
            page=1,
            text="Perform no less than 50 percent of total original contract price with the contractor's own organization.",
        )
    ]
    rag = [
        Snippet(
            file_name="Special_Provisions.pdf",
            document_type="Vertex RAG",
            page=0,
            text="Perform no less than 50 percent of total original contract price with the contractor's own organization. Extra.",
        ),
        Snippet(
            file_name="Addendum_A.pdf",
            document_type="Vertex RAG",
            page=0,
            text="Eighty percent (80%) of the work may be subcontracted without written consent.",
        ),
    ]
    merged = merge_rag_snippets(keyword, rag)
    assert len(merged) == 2
    assert any("80%" in s.text for s in merged)


def test_rag_disabled_unless_flag_or_index(monkeypatch, tmp_path):
    monkeypatch.delenv("CCRF_USE_RAG", raising=False)
    monkeypatch.setattr("ccrf.rag.INDEX_PATH", tmp_path / "missing.json")
    assert rag_enabled() is False
    monkeypatch.setenv("CCRF_USE_RAG", "1")
    assert rag_enabled() is True
