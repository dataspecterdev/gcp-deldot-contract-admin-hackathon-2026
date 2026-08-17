from __future__ import annotations

from pathlib import Path
from typing import Any

from ccrf.apply import decide_applicability
from ccrf.config import REQUIREMENT_IDS, REPO_ROOT
from ccrf.evidence import evidence_supported
from ccrf.extract import extract_package
from ccrf.ingest import discover_packages, load_checklist, load_severity_guidance
from ccrf.models import Finding, PackageCorpus
from ccrf.precedence import fhwa_physically_included, ignores_later_addenda, resolve_precedence
from ccrf.rag import merge_rag_snippets, rag_enabled, retrieve_snippets
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
        if rag_enabled():
            rag_hits = retrieve_snippets(
                corpus.package_id, rid, checklist_name=row.name
            )
            combined = merge_rag_snippets(snapshot.governing_snippets, rag_hits)
            snapshot.rag_snippets = combined[len(snapshot.governing_snippets) :]
            snapshot.hints["vertex_rag"] = bool(snapshot.rag_snippets)
            print(
                f"{corpus.package_id} {rid} gemini rag_hits={len(rag_hits)}",
                flush=True,
            )
        else:
            print(f"{corpus.package_id} {rid} gemini", flush=True)
        model_out = review_requirement(client, corpus, row, snapshot, severity_guide)
        finding = _to_finding(
            corpus.package_id, row, decision, reason, snapshot, model_out, corpus
        )
        findings.append(_apply_deterministic_overrides(finding, corpus, snapshot))
    if len(findings) != 18:
        raise RuntimeError(f"Expected 18 rows, got {len(findings)} for {corpus.package_id}")
    print(f"finished {corpus.package_id} ({len(findings)} rows)", flush=True)
    return findings


def review_root(root: Path, client: Any | None = None) -> list[Finding]:
    all_findings: list[Finding] = []
    for package_dir in discover_packages(root):
        all_findings.extend(review_package(package_dir, client=client))
    return all_findings
