from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ccrf.apply import decide_applicability
from ccrf.config import REQUIREMENT_IDS, REPO_ROOT
from ccrf.evidence import evidence_supported
from ccrf.extract import extract_package
from ccrf.ingest import discover_packages, load_checklist, load_severity_guidance
from ccrf.models import Finding, PackageCorpus
from ccrf.precedence import (
    _cc14_is_concrete,
    fhwa_physically_included,
    ignores_later_addenda,
    resolve_precedence,
)
from ccrf.blend import upgrade_from_rag_recall
from ccrf.rag import rag_enabled, retrieve_snippets
from ccrf.review import inapplicable_finding, review_requirement


def _checklist_path() -> Path:
    return REPO_ROOT / "References" / "Reference_Checklist.csv"


def _severity_path() -> Path:
    return REPO_ROOT / "Evaluation" / "Severity_Guidance.csv"


def _to_finding(
    package_id: str,
    checklist,
    applicability: str,
    reason: str,
    snapshot,
    model_out: dict[str, Any],
    corpus: PackageCorpus,
) -> Finding:
    label = str(model_out.get("predicted_label") or "NO_FLAG")
    if label not in {"FLAG", "NO_FLAG"}:
        label = "NO_FLAG"
    severity = str(model_out.get("severity") or "Info")
    quote = str(model_out.get("draft_evidence") or "")
    loc = str(model_out.get("draft_location") or snapshot.governing_document)
    conf = float(model_out.get("confidence") or 0.5)
    action = str(model_out.get("recommended_human_action") or "Review")
    if action not in {"Review", "Confirm", "No action"}:
        action = "Review"

    evidence_text = corpus.full_text()
    if label == "FLAG" and not evidence_supported(quote, evidence_text):
        label = "NO_FLAG"
        severity = "Info"
        conf = min(conf, 0.35)
        explanation = (
            "Down-ranked to NO_FLAG: draft_evidence was not found in the package text. "
            + str(model_out.get("explanation") or "")
        )
    else:
        explanation = str(model_out.get("explanation") or "")

    if label == "NO_FLAG":
        severity = "Info"
        if action == "Review" and conf < 0.5:
            action = "Confirm"

    return Finding(
        document_id=package_id,
        requirement_id=checklist.requirement_id,
        applicability_decision=applicability,
        applicability_reason=reason,
        predicted_label=label,
        severity=severity,
        governing_document=snapshot.governing_document,
        draft_location=loc,
        draft_evidence=quote,
        reference_id=checklist.requirement_id,
        reference_location=checklist.section,
        reference_evidence=checklist.challenge_reference_rule,
        explanation=explanation.strip(),
        confidence=max(0.0, min(1.0, conf)),
        recommended_human_action=action,
    )


SHORTHAND_QUOTE_RE = re.compile(
    r"(the stated period|the reference period|reference timing|"
    r"required proof of insurance|within the reference|"
    r"same priority sequence|order of precedence supplied|"
    r"right to audit and record retention)",
    re.IGNORECASE,
)
MATERIAL_QUOTE_RE = re.compile(
    r"("
    r"\b5\s*%\b|\b5 percent\b|\b80\s*%\b|eighty percent|"
    r"\b25\s*%\b|\b75\s*%\b|\$10,000|"
    r"45 calendar|45 days|60 day|30 calendar|"
    r"1 year|one year|optional|"
    r"after work begins|oral direction|"
    r"automatic|"
    r"does not apply|"
    r"later issued addenda may be disregarded|"
    r"fhwa-1273"
    r")",
    re.IGNORECASE,
)


def _downrank_shorthand_flag(finding: Finding) -> Finding:
    if finding.predicted_label != "FLAG" or finding.applicability_decision != "APPLIES":
        return finding
    quote = finding.draft_evidence or ""
    if SHORTHAND_QUOTE_RE.search(quote) and not MATERIAL_QUOTE_RE.search(quote):
        finding.predicted_label = "NO_FLAG"
        finding.severity = "Info"
        finding.confidence = min(finding.confidence, 0.4)
        finding.recommended_human_action = "No action"
        finding.explanation = (
            "Down-ranked to NO_FLAG: draft_evidence is challenge shorthand/equivalent "
            "wording, not a different concrete number or process. " + finding.explanation
        )
    return finding


def _upgrade_cc14_from_corpus(finding: Finding, corpus: PackageCorpus) -> Finding:
    if finding.requirement_id != "CC-14" or finding.applicability_decision != "APPLIES":
        return finding
    if finding.predicted_label == "FLAG":
        return finding
    for doc in corpus.documents:
        for page in doc.pages:
            if not _cc14_is_concrete(page.text):
                continue
            finding.predicted_label = "FLAG"
            finding.severity = "High"
            finding.recommended_human_action = "Review"
            finding.confidence = max(finding.confidence, 0.9)
            finding.governing_document = doc.file_name
            finding.draft_location = f"{doc.file_name} p.{page.page}"
            finding.draft_evidence = page.text.strip()[:500]
            finding.explanation = (
                "Concrete 80% subcontracting weakening is present in the package and "
                "was not restored by a later Addendum. " + finding.explanation
            )
            return finding
    return finding


def _apply_deterministic_overrides(
    finding: Finding,
    corpus: PackageCorpus,
    snapshot,
) -> Finding:
    rid = finding.requirement_id
    if rid == "CC-01" and finding.applicability_decision == "APPLIES":
        if not fhwa_physically_included(corpus):
            finding.predicted_label = "FLAG"
            finding.severity = "Critical"
            finding.recommended_human_action = "Review"
            finding.confidence = max(finding.confidence, 0.9)
            if "fhwa" not in finding.explanation.lower():
                finding.explanation = (
                    "FHWA-1273 is applicable (federal-aid=Yes) but Document_Index does not "
                    "show a physically included attachment. " + finding.explanation
                )
    if rid == "CC-08" and finding.applicability_decision == "APPLIES":
        issued = [str(x) for x in (corpus.metadata.get("issued_addenda") or [])]
        acknowledged = [str(x) for x in (snapshot.hints.get("acknowledged_addenda") or [])]
        ignores = bool(snapshot.hints.get("ignores_later_addenda")) or ignores_later_addenda(corpus)
        missing = sorted(set(issued) - set(acknowledged)) if issued else []
        partial = bool(issued and acknowledged and missing)
        if ignores or partial:
            finding.predicted_label = "FLAG"
            finding.severity = "High"
            finding.recommended_human_action = "Review"
            finding.confidence = max(finding.confidence, 0.85)
            finding.explanation = (
                f"Issued addenda {issued} vs acknowledged {acknowledged}; "
                f"ignores_later={ignores}; missing {missing}. " + finding.explanation
            )
        else:
            finding.predicted_label = "NO_FLAG"
            finding.severity = "Info"
            finding.recommended_human_action = "No action"
            finding.explanation = (
                "CC-08: issued addenda without an explicit 'later issued Addenda may be "
                "disregarded' clause (and without a partial acknowledgment that omits a "
                "later Addendum) is NO_FLAG. " + finding.explanation
            )
    return finding


def review_package(package_dir: Path, client: Any | None = None) -> list[Finding]:
    corpus = extract_package(package_dir)
    checklist = load_checklist(_checklist_path())
    severity_guide = load_severity_guidance(_severity_path())
    findings: list[Finding] = []
    for rid in REQUIREMENT_IDS:
        row = checklist[rid]
        decision, reason = decide_applicability(rid, corpus.metadata)
        if decision == "DOES_NOT_APPLY":
            print(f"{corpus.package_id} {rid} skip DOES_NOT_APPLY", flush=True)
            findings.append(inapplicable_finding(corpus.package_id, row, reason, corpus.metadata))
            continue
        if client is None:
            raise RuntimeError(
                "Vertex AI client required for APPLIES rows. Run bash infra/setup.sh "
                "and export GOOGLE_CLOUD_PROJECT=hackathon-2026-transport-2"
            )
        snapshot = resolve_precedence(corpus, rid)
        rag_hits: list = []
        if rag_enabled():
            rag_hits = retrieve_snippets(
                corpus.package_id,
                rid,
                checklist_name=row.name,
                challenge_rule=row.challenge_reference_rule,
            )
            snapshot.hints["vertex_rag"] = bool(rag_hits)
            snapshot.rag_snippets = []
            print(
                f"{corpus.package_id} {rid} gemini rag_kept={len(rag_hits)}",
                flush=True,
            )
        else:
            print(f"{corpus.package_id} {rid} gemini", flush=True)
        model_out = review_requirement(client, corpus, row, snapshot, severity_guide)
        finding = _to_finding(
            corpus.package_id, row, decision, reason, snapshot, model_out, corpus
        )
        finding = _downrank_shorthand_flag(finding)
        finding = _apply_deterministic_overrides(finding, corpus, snapshot)
        finding = _upgrade_cc14_from_corpus(finding, corpus)
        finding = upgrade_from_rag_recall(finding, rag_hits)
        findings.append(finding)
    if len(findings) != 18:
        raise RuntimeError(f"Expected 18 rows, got {len(findings)} for {corpus.package_id}")
    print(f"finished {corpus.package_id} ({len(findings)} rows)", flush=True)
    return findings


def review_root(root: Path, client: Any | None = None) -> list[Finding]:
    all_findings: list[Finding] = []
    for package_dir in discover_packages(root):
        all_findings.extend(review_package(package_dir, client=client))
    return all_findings
