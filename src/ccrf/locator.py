"""Pin findings to pages using only verbatim extracted text.

A file + page is reported only when draft_evidence appears as a contiguous
span in that page (whitespace collapsed). No keyword near-miss, no invented
expected-slot copy, no highlight of text that did not match.
"""

from __future__ import annotations

import html
import re
from typing import Any

from ccrf.models import Finding, PackageCorpus, PrecedenceSnapshot
from ccrf.precedence import fhwa_physically_included

_MIN_QUOTE = 12


def _collapse_map(text: str) -> tuple[str, list[int]]:
    collapsed: list[str] = []
    raw_at: list[int] = []
    prev_space = True
    for i, ch in enumerate(text or ""):
        if ch.isspace():
            if not prev_space:
                collapsed.append(" ")
                raw_at.append(i)
            prev_space = True
            continue
        collapsed.append(ch)
        raw_at.append(i)
        prev_space = False
    while collapsed and collapsed[0] == " ":
        collapsed.pop(0)
        raw_at.pop(0)
    while collapsed and collapsed[-1] == " ":
        collapsed.pop()
        raw_at.pop()
    return "".join(collapsed), raw_at


def _clip_raw(raw: str, start: int, end: int, radius: int = 140) -> str:
    lo = max(0, start - radius)
    hi = min(len(raw), end + radius)
    return raw[lo:hi]


def find_verbatim_anchor(corpus: PackageCorpus, quote: str) -> dict[str, Any] | None:
    q = re.sub(r"\s+", " ", (quote or "").strip())
    if len(q) < _MIN_QUOTE:
        return None
    q_lower = q.lower()
    for doc in corpus.documents:
        for page in doc.pages:
            raw = page.text or ""
            collapsed, raw_at = _collapse_map(raw)
            if not collapsed or not raw_at:
                continue
            idx = collapsed.lower().find(q_lower)
            if idx < 0:
                continue
            end = idx + len(q)
            if end > len(raw_at):
                continue
            raw_start = raw_at[idx]
            raw_end = raw_at[end - 1] + 1
            matched = raw[raw_start:raw_end]
            excerpt = _clip_raw(raw, raw_start, raw_end)
            escaped_excerpt = html.escape(excerpt)
            escaped_match = html.escape(matched)
            if escaped_match and escaped_match in escaped_excerpt:
                highlight_html = escaped_excerpt.replace(
                    escaped_match, f"<mark>{escaped_match}</mark>", 1
                )
            else:
                highlight_html = escaped_excerpt
            return {
                "file_name": doc.file_name,
                "page": page.page,
                "verbatim_excerpt": excerpt,
                "matched_span": matched,
                "highlight_html": highlight_html,
            }
    return None


def attach_locator(
    finding: Finding,
    corpus: PackageCorpus,
    snapshot: PrecedenceSnapshot | None = None,
) -> Finding:
    """Verify location against extracted pages. Never changes FLAG labels."""
    del snapshot  # scoring already finished; locator does not re-judge
    files = [doc.file_name for doc in corpus.documents]
    anchor = find_verbatim_anchor(corpus, finding.draft_evidence)
    index_has_fhwa = (
        fhwa_physically_included(corpus) if finding.requirement_id == "CC-01" else None
    )

    if anchor:
        finding.draft_location = f"{anchor['file_name']} p.{anchor['page']}"
        locator_anchor = {
            "file_name": anchor["file_name"],
            "page": anchor["page"],
            "verbatim_excerpt": anchor["verbatim_excerpt"],
            "matched_span": anchor["matched_span"],
            "highlight_html": anchor["highlight_html"],
        }
        anchors = [locator_anchor]
        quote_found = True
    else:
        finding.draft_location = (
            "Not found in extracted text of: " + (", ".join(files) if files else "(no PDFs)")
        )
        anchors = []
        quote_found = False

    finding.locator = {
        "quote_found_in_extracted_text": quote_found,
        "files_in_package": files,
        "fhwa_physically_included": index_has_fhwa,
        "anchors": anchors,
        "reference_location": finding.reference_location,
        "reference_evidence": finding.reference_evidence,
    }
    return finding
