from ccrf.models import Snippet
from ccrf.rag import (
    build_retrieval_query,
    merge_rag_snippets,
    rag_enabled,
    snippet_relevant,
    strip_boilerplate,
)


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


def test_strip_boilerplate_keeps_clause_text():
    raw = (
        "CONTRACT CLAUSE RISK FLAGGING - SAMPLE CONTRACT DOCUMENT\n"
        "DEV-STONE-CREEK | FOR EVALUATION USE ONLY Page 1\n"
        "Eighty percent (80%) of the work may be subcontracted without written consent."
    )
    cleaned = strip_boilerplate(raw)
    assert "80%" in cleaned
    assert "SAMPLE CONTRACT DOCUMENT" not in cleaned
    assert snippet_relevant(cleaned, "CC-14") is True


def test_header_only_chunk_is_not_relevant_for_cc14():
    header = (
        "CONTRACT CLAUSE RISK FLAGGING - SAMPLE CONTRACT DOCUMENT\n"
        "PROPOSAL AND GENERAL NOTICES\n"
        "Federal aid Yes\n"
        "Assumed contract value $28,750,000"
    )
    assert snippet_relevant(strip_boilerplate(header), "CC-14") is False


def test_retrieval_query_uses_keywords_not_package_boilerplate():
    query = build_retrieval_query("CC-14", "Subcontracting", "prime performs no less than 50%")
    assert "CC-14" in query
    assert "subcontract" in query
    assert "contract clause addendum special provisions" not in query

