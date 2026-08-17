from ccrf.blend import blend_rows, has_concrete_weakening, upgrade_from_rag_recall
from ccrf.models import Finding, Snippet


def _finding(label: str) -> Finding:
    return Finding(
        document_id="DEV-STONE-CREEK",
        requirement_id="CC-14",
        applicability_decision="APPLIES",
        applicability_reason="subcontracting_planned=Yes",
        predicted_label=label,
        severity="Info",
        governing_document="Proposal_and_General_Notices.pdf",
        draft_location="Proposal_and_General_Notices.pdf",
        draft_evidence="silent",
        reference_id="CC-14",
        reference_location="108.1",
        reference_evidence="50%",
        explanation="keyword path",
        confidence=0.4,
        recommended_human_action="No action",
    )


def test_concrete_weakening_detects_80_percent():
    assert has_concrete_weakening("Up to eighty percent (80%) of the work may be subcontracted")
    assert not has_concrete_weakening(
        "Subcontracting. Required Department approval/limits apply and the prime remains responsible."
    )


def test_upgrade_from_rag_recall_only_on_80_percent_clause():
    finding = upgrade_from_rag_recall(
        _finding("NO_FLAG"),
        [
            Snippet(
                file_name="General_Conditions.pdf",
                document_type="Vertex RAG",
                page=1,
                text="Up to eighty percent (80%) of the work may be subcontracted without approval.",
            )
        ],
    )
    assert finding.predicted_label == "FLAG"
    assert "80%" in finding.draft_evidence


def test_blend_prefers_non_rag_flag_and_skips_shorthand_rag_flag():
    base = {"predicted_label": "NO_FLAG", "draft_evidence": "silent", "explanation": "", "severity": "Info"}
    rag_fp = {
        "predicted_label": "FLAG",
        "draft_evidence": "Required Department approval/limits apply",
        "explanation": "omits 50%",
        "severity": "High",
    }
    assert blend_rows(base, rag_fp)["predicted_label"] == "NO_FLAG"
    rag_tp = {
        "predicted_label": "FLAG",
        "draft_evidence": "Up to eighty percent (80%) of the work may be subcontracted",
        "explanation": "80% weakening",
        "severity": "High",
        "draft_location": "General_Conditions.pdf",
        "recommended_human_action": "Review",
        "confidence": "0.90",
    }
    hybrid = blend_rows(base, rag_tp)
    assert hybrid["predicted_label"] == "FLAG"
    assert "80%" in hybrid["draft_evidence"]
