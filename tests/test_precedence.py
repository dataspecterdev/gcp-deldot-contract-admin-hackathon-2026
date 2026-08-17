from ccrf.models import ExtractedDocument, PackageCorpus, PageText
from ccrf.precedence import (
    _doc_rank,
    acknowledged_addenda,
    ignores_later_addenda,
    resolve_precedence,
)


def test_later_addendum_outranks_proposal():
    assert _doc_rank("Addendum C", "Addendum_C.pdf") > _doc_rank("Proposal and General Notices", "Proposal_and_General_Notices.pdf")
    assert _doc_rank("Addendum B", "Addendum_B.pdf") > _doc_rank("Addendum A", "Addendum_A.pdf")


def test_addendum_governs_when_it_revises_bonds():
    corpus = PackageCorpus(
        package_id="DEV-TEST",
        metadata={"issued_addenda": ["Addendum 1"]},
        documents=[
            ExtractedDocument(
                file_name="Proposal_and_General_Notices.pdf",
                document_type="Proposal and General Notices",
                package_status="Current package document",
                pages=[PageText(page=1, text="Performance and payment bonds shall equal 75% of the contract price.")],
            ),
            ExtractedDocument(
                file_name="Addendum_A.pdf",
                document_type="Addendum A",
                package_status="Current package document",
                pages=[
                    PageText(
                        page=1,
                        text="Section 103.5 is hereby revised. Delete and replace: performance and payment bond coverage is 100% of the contract price.",
                    )
                ],
            ),
        ],
    )
    snap = resolve_precedence(corpus, "CC-04")
    assert snap.governing_document == "Addendum_A.pdf"
    assert any(s.is_revision for s in snap.governing_snippets)


def test_cc08_detects_disregard_clause_not_header_metadata():
    corpus = PackageCorpus(
        package_id="DEV-MAPLE-RIDGE",
        metadata={"issued_addenda": ["Addendum 1"]},
        documents=[
            ExtractedDocument(
                file_name="Proposal_and_General_Notices.pdf",
                document_type="Proposal and General Notices",
                package_status="Current package document",
                pages=[
                    PageText(
                        page=1,
                        text=(
                            "Issued addenda\nAddendum 1\n"
                            "Addenda Acknowledgment. Only the Addenda expressly listed in the original "
                            "proposal need be acknowledged; later issued Addenda may be disregarded."
                        ),
                    )
                ],
            )
        ],
    )
    assert ignores_later_addenda(corpus) is True
    # Header "Issued addenda / Addendum 1" is not a bidder acknowledgment.
    assert acknowledged_addenda(corpus) == []
