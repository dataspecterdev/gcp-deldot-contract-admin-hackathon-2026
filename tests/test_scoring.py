from ccrf.models import ExtractedDocument, Finding, PackageCorpus, PageText
from ccrf.pipeline import (
    _apply_deterministic_overrides,
    _downrank_shorthand_flag,
    _upgrade_cc14_from_corpus,
)
from ccrf.precedence import resolve_precedence


def _finding(**kwargs) -> Finding:
    values = dict(
        document_id="DEV-TEST",
        requirement_id="CC-12",
        applicability_decision="APPLIES",
        applicability_reason="baseline",
        predicted_label="FLAG",
        severity="High",
        governing_document="General_Conditions.pdf",
        draft_location="General_Conditions.pdf",
        draft_evidence="Alleged changes require follow-up documentation within the stated period.",
        reference_id="CC-12",
        reference_location="DelDOT 104.3",
        reference_evidence="7 calendar days",
        explanation="omits 7 days",
        confidence=0.9,
        recommended_human_action="Review",
    )
    values.update(kwargs)
    return Finding(**values)


def test_shorthand_stated_period_is_downranked():
    finding = _downrank_shorthand_flag(_finding())
    assert finding.predicted_label == "NO_FLAG"


def test_shorthand_gate_keeps_5_percent_flag():
    finding = _downrank_shorthand_flag(
        _finding(
            requirement_id="CC-02",
            draft_evidence="Proposal guaranty shall equal five percent (5%) of the total bid price.",
        )
    )
    assert finding.predicted_label == "FLAG"


def test_cc14_upgrade_from_80_percent_page():
    corpus = PackageCorpus(
        package_id="DEV-STONE-CREEK",
        metadata={"subcontracting_planned": "Yes"},
        documents=[
            ExtractedDocument(
                file_name="General_Conditions.pdf",
                document_type="General Conditions",
                package_status="Current",
                pages=[
                    PageText(
                        page=1,
                        text="Up to eighty percent (80%) of the work may be subcontracted without approval.",
                    )
                ],
            )
        ],
    )
    finding = _upgrade_cc14_from_corpus(
        _finding(requirement_id="CC-14", predicted_label="NO_FLAG", draft_evidence="silent"),
        corpus,
    )
    assert finding.predicted_label == "FLAG"
    assert "80%" in finding.draft_evidence


def test_cc08_override_does_not_flag_empty_ack_without_disregard():
    corpus = PackageCorpus(
        package_id="DEV-RIVERBEND",
        metadata={"issued_addenda": ["Addendum 1"]},
        documents=[
            ExtractedDocument(
                file_name="Proposal_and_General_Notices.pdf",
                document_type="Proposal and General Notices",
                package_status="Current",
                pages=[PageText(page=1, text="Issued addenda: Addendum 1.")],
            )
        ],
    )
    snap = resolve_precedence(corpus, "CC-08")
    finding = _apply_deterministic_overrides(
        _finding(requirement_id="CC-08", predicted_label="FLAG", document_id="DEV-RIVERBEND"),
        corpus,
        snap,
    )
    assert finding.predicted_label == "NO_FLAG"
