from __future__ import annotations

import json
from typing import Any

from ccrf.config import CONFIG_DIR, GEMINI_MODEL, GCP_LOCATION, GCP_PROJECT, PROMPTS_DIR
from ccrf.models import ChecklistRow, Finding, PackageCorpus, PrecedenceSnapshot

FINDING_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "predicted_label": {"type": "STRING", "enum": ["FLAG", "NO_FLAG"]},
        "severity": {"type": "STRING", "enum": ["Critical", "High", "Medium", "Low", "Info"]},
        "draft_location": {"type": "STRING"},
        "draft_evidence": {"type": "STRING"},
        "explanation": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "recommended_human_action": {"type": "STRING", "enum": ["Review", "Confirm", "No action"]},
    },
    "required": [
        "predicted_label",
        "severity",
        "draft_location",
        "draft_evidence",
        "explanation",
        "confidence",
        "recommended_human_action",
    ],
}


def _system_prompt() -> str:
    return (PROMPTS_DIR / "review_system.txt").read_text(encoding="utf-8")


def load_official_baselines() -> dict:
    import yaml

    path = CONFIG_DIR / "official_baselines.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def official_excerpt_block(requirement_id: str) -> str:
    row = load_official_baselines().get(requirement_id) or {}
    excerpt = (row.get("excerpt") or "").strip()
    chunks: list[str] = []
    if excerpt:
        source = row.get("source") or ""
        url = row.get("url") or ""
        extra = f" ({url})" if url else ""
        chunks.append(f"Official source excerpt [{source}]{extra}:\n{excerpt}\n")
    from ccrf.statute import retrieve_statute_excerpt

    statute = retrieve_statute_excerpt(requirement_id)
    if statute:
        chunks.append(statute)
    return "\n".join(chunks)


def _format_snippets(title: str, snapshot: PrecedenceSnapshot, which: str) -> str:
    if which == "governing":
        items = snapshot.governing_snippets
    elif which == "superseded":
        items = snapshot.superseded_snippets
    else:
        items = snapshot.rag_snippets
    if not items:
        return f"{title}: (none retrieved)\n"
    lines = [f"{title}:"]
    for snip in items:
        loc = f"{snip.file_name} p.{snip.page}"
        flag = " [REVISION LANGUAGE]" if snip.is_revision else ""
        lines.append(f"- {loc}{flag}: {snip.text}")
    return "\n".join(lines)


def build_user_prompt(
    corpus: PackageCorpus,
    checklist: ChecklistRow,
    snapshot: PrecedenceSnapshot,
    severity_guide: str,
) -> str:
    meta = json.dumps(corpus.metadata, indent=2)
    hints = json.dumps(snapshot.hints, indent=2)
    return f"""Package {corpus.package_id}
Requirement {checklist.requirement_id}: {checklist.name}

Challenge_Reference_Rule (scoring authority):
{checklist.challenge_reference_rule}

{official_excerpt_block(checklist.requirement_id)}
Review_Expectation:
{checklist.review_expectation}

Reference location: {checklist.reference_source} / {checklist.section}
Severity_Guidance for this requirement: {checklist.severity_guidance}

Challenge severity taxonomy:
{severity_guide}

Project_Metadata.json:
{meta}

Deterministic hints (do not ignore):
{hints}

Governing document after addendum/precedence resolution: {snapshot.governing_document}

{_format_snippets("CONTROLLING snippets", snapshot, "governing")}

{_format_snippets("VERTEX RAG RETRIEVED snippets (Google RAG Engine; treat as extra evidence, still obey addendum precedence)", snapshot, "rag")}

{_format_snippets("SUPERSEDED earlier snippets (do not flag these if controlling text restored the requirement)", snapshot, "superseded")}

Return one JSON object. Quote draft_evidence from CONTROLLING snippets when possible.
"""


def get_client(project: str | None = None, location: str | None = None):
    from google import genai

    return genai.Client(
        vertexai=True,
        project=project or GCP_PROJECT,
        location=location or GCP_LOCATION,
    )


def review_requirement(
    client: Any,
    corpus: PackageCorpus,
    checklist: ChecklistRow,
    snapshot: PrecedenceSnapshot,
    severity_guide: str,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    from google.genai import types

    prompt = build_user_prompt(corpus, checklist, snapshot, severity_guide)
    response = client.models.generate_content(
        model=model or GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_system_prompt(),
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=FINDING_SCHEMA,
        ),
    )
    text = response.text or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "predicted_label": "NO_FLAG",
            "severity": "Info",
            "draft_location": snapshot.governing_document,
            "draft_evidence": "",
            "explanation": "Model returned unparseable JSON; defaulting to NO_FLAG.",
            "confidence": 0.2,
            "recommended_human_action": "Review",
        }


def inapplicable_finding(
    package_id: str,
    checklist: ChecklistRow,
    reason: str,
    metadata: dict[str, Any],
) -> Finding:
    evidence = json.dumps(
        {k: metadata.get(k) for k in (
            "federal_aid",
            "buy_america_baba_applicable",
            "issued_addenda",
            "subcontracting_planned",
            "claim_event",
            "delay_event",
            "changed_work_event",
        )},
        ensure_ascii=True,
    )
    return Finding(
        document_id=package_id,
        requirement_id=checklist.requirement_id,
        applicability_decision="DOES_NOT_APPLY",
        applicability_reason=reason,
        predicted_label="NO_FLAG",
        severity="Info",
        governing_document="Project_Metadata.json",
        draft_location="Project_Metadata.json",
        draft_evidence=evidence,
        reference_id=checklist.requirement_id,
        reference_location=f"{checklist.section}",
        reference_evidence=checklist.challenge_reference_rule,
        explanation=reason,
        confidence=1.0,
        recommended_human_action="No action",
    )
