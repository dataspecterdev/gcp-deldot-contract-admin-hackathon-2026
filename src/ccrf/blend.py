"""Hybrid scorer: Non-RAG Gemini precision + RAG recall for concrete weakenings."""

from __future__ import annotations

import re
from typing import Iterable

from ccrf.models import Finding, Snippet

# Distinctive number/process changes RAG is good at surfacing. Shorthand
# ("approval/limits apply", "the stated period") does not match.
CONCRETE_WEAKENING_RE = re.compile(
    r"(eighty percent|\b80\s*%\b|"
    r"later issued addenda may be disregarded|"
    r"automatically extends|"
    r"\$10,000|"
    r"domestic-content requirements do not apply)",
    re.IGNORECASE,
)


def has_concrete_weakening(text: str) -> bool:
    return bool(CONCRETE_WEAKENING_RE.search(text or ""))


def upgrade_from_rag_recall(finding: Finding, rag_snips: Iterable[Snippet]) -> Finding:
    """Keep Non-RAG NO_FLAG unless RAG found a live concrete weakening."""
    if finding.predicted_label == "FLAG":
        return finding
    if finding.applicability_decision != "APPLIES":
        return finding
    for snip in rag_snips:
        if not has_concrete_weakening(snip.text):
            continue
        finding.predicted_label = "FLAG"
        finding.severity = "High"
        finding.recommended_human_action = "Review"
        finding.confidence = max(finding.confidence, 0.85)
        finding.draft_location = f"{snip.file_name} p.{snip.page}"
        finding.draft_evidence = snip.text[:500]
        finding.explanation = (
            "RAG recall upgrade: Vertex RAG retrieved a concrete weakening "
            "that keyword/pypdf governing snippets missed. " + finding.explanation
        )
        return finding
    return finding


def blend_rows(base: dict[str, str], rag: dict[str, str]) -> dict[str, str]:
    """Prefer Non-RAG labels; take RAG FLAG only when evidence is a concrete weakening."""
    out = dict(base)
    if (base.get("predicted_label") or "") == "FLAG":
        return out
    if (rag.get("predicted_label") or "") != "FLAG":
        return out
    blob = " ".join(
        [
            rag.get("draft_evidence") or "",
            rag.get("explanation") or "",
        ]
    )
    if not has_concrete_weakening(blob):
        return out
    out["predicted_label"] = "FLAG"
    out["severity"] = rag.get("severity") or "High"
    out["draft_location"] = rag.get("draft_location") or out.get("draft_location") or ""
    out["draft_evidence"] = rag.get("draft_evidence") or out.get("draft_evidence") or ""
    out["explanation"] = (
        "Hybrid recall: kept Non-RAG precision, adopted RAG FLAG on concrete weakening. "
        + (rag.get("explanation") or "")
    )
    out["recommended_human_action"] = rag.get("recommended_human_action") or "Review"
    out["confidence"] = rag.get("confidence") or out.get("confidence") or "0.85"
    return out
