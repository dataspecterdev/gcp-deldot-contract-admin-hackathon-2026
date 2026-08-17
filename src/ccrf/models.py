from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentRef:
    file_name: str
    document_type: str
    package_status: str
    path: Path


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class ExtractedDocument:
    file_name: str
    document_type: str
    package_status: str
    pages: list[PageText]


@dataclass
class PackageCorpus:
    package_id: str
    metadata: dict[str, Any]
    documents: list[ExtractedDocument]

    def full_text(self) -> str:
        chunks = []
        for doc in self.documents:
            for page in doc.pages:
                chunks.append(page.text)
        return "\n".join(chunks)

    def document_text(self, file_name: str) -> str:
        for doc in self.documents:
            if doc.file_name == file_name:
                return "\n".join(p.text for p in doc.pages)
        return ""


@dataclass
class Snippet:
    file_name: str
    document_type: str
    page: int
    text: str
    is_revision: bool = False


@dataclass
class PrecedenceSnapshot:
    requirement_id: str
    governing_document: str
    governing_snippets: list[Snippet] = field(default_factory=list)
    superseded_snippets: list[Snippet] = field(default_factory=list)
    rag_snippets: list[Snippet] = field(default_factory=list)
    hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChecklistRow:
    requirement_id: str
    name: str
    reference_source: str
    section: str
    applicability_rule: str
    review_expectation: str
    severity_guidance: str
    challenge_reference_rule: str


@dataclass
class Finding:
    document_id: str
    requirement_id: str
    applicability_decision: str
    applicability_reason: str
    predicted_label: str
    severity: str
    governing_document: str
    draft_location: str
    draft_evidence: str
    reference_id: str
    reference_location: str
    reference_evidence: str
    explanation: str
    confidence: float
    recommended_human_action: str

    def as_row(self) -> dict[str, str]:
        return {
            "document_id": self.document_id,
            "requirement_id": self.requirement_id,
            "applicability_decision": self.applicability_decision,
            "applicability_reason": self.applicability_reason,
            "predicted_label": self.predicted_label,
            "severity": self.severity,
            "governing_document": self.governing_document,
            "draft_location": self.draft_location,
            "draft_evidence": self.draft_evidence,
            "reference_id": self.reference_id,
            "reference_location": self.reference_location,
            "reference_evidence": self.reference_evidence,
            "explanation": self.explanation,
            "confidence": f"{self.confidence:.2f}",
            "recommended_human_action": self.recommended_human_action,
        }
