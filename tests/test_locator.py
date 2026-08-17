from ccrf.locator import attach_locator, find_verbatim_anchor
from ccrf.models import ExtractedDocument, Finding, PackageCorpus, PageText


def _corpus() -> PackageCorpus:
    return PackageCorpus(
        package_id="DEV-HARBOR-CROSSING",
        metadata={"federal_aid": "Yes"},
        documents=[
            ExtractedDocument(
                file_name="Proposal_and_General_Notices.pdf",
                document_type="Proposal and General Notices",
                package_status="Current",
                pages=[
                    PageText(
                        page=1,
                        text=(
                            "Federal requirements. FHWA-1273 is incorporated by reference. "
                            "No FHWA-1273 attachment is included in this package. "
                            "Proposal Guaranty shall equal five percent (5%) of the total bid price."
                        ),
                    )
                ],
            )
        ],
    )


def _finding(**kwargs) -> Finding:
    values = dict(
        document_id="DEV-HARBOR-CROSSING",
        requirement_id="CC-01",
        applicability_decision="APPLIES",
        applicability_reason="federal_aid=Yes",
        predicted_label="FLAG",
        severity="Critical",
        governing_document="Proposal_and_General_Notices.pdf",
        draft_location="Proposal_and_General_Notices.pdf",
        draft_evidence="FHWA-1273 is incorporated by reference.",
        reference_id="CC-01",
        reference_location="FHWA-1273 I.1",
        reference_evidence="must be physically included",
        explanation="No FHWA-1273 attachment is included in this package.",
        confidence=0.95,
        recommended_human_action="Review",
    )
    values.update(kwargs)
    return Finding(**values)


def test_verbatim_quote_is_pinned_to_the_page_it_appears_on():
    finding = attach_locator(_finding(), _corpus())
    assert finding.predicted_label == "FLAG"
    assert finding.locator["quote_found_in_extracted_text"] is True
    assert finding.draft_location == "Proposal_and_General_Notices.pdf p.1"
    assert "Nearest" not in finding.draft_location
    assert "expected:" not in finding.draft_location.lower()
    span = finding.locator["anchors"][0]["matched_span"]
    assert "FHWA-1273 is incorporated by reference." in span
    excerpt = finding.locator["anchors"][0]["verbatim_excerpt"]
    assert span in excerpt
    assert "<mark>" in finding.locator["anchors"][0]["highlight_html"]
    assert "locator" not in finding.as_row()


def test_unlocated_quote_does_not_invent_a_page_or_near_miss():
    finding = attach_locator(
        _finding(draft_evidence="This sentence does not appear anywhere in the PDFs at all."),
        _corpus(),
    )
    assert finding.predicted_label == "FLAG"
    assert finding.locator["quote_found_in_extracted_text"] is False
    assert finding.locator["anchors"] == []
    assert finding.draft_location.startswith("Not found in extracted text of:")
    assert "p." not in finding.draft_location
    assert find_verbatim_anchor(_corpus(), "bonded waffle clause XYZ-9999") is None


def test_weakening_quote_uses_only_the_page_text():
    quote = "Proposal Guaranty shall equal five percent (5%) of the total bid price."
    finding = attach_locator(
        _finding(requirement_id="CC-02", draft_evidence=quote),
        _corpus(),
    )
    assert finding.draft_location == "Proposal_and_General_Notices.pdf p.1"
    assert quote in finding.locator["anchors"][0]["matched_span"]
    assert "80%" not in finding.locator["anchors"][0]["verbatim_excerpt"]
