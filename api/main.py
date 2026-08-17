"""Cloud Run demo API around the same clause-flagging engine as the CLI."""

from __future__ import annotations

import html
import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from ccrf.ingest import discover_packages
from ccrf.models import Finding
from ccrf.pipeline import review_package
from ccrf.review import get_client

app = FastAPI(
    title="GCP DelDOT Contract Clause Risk Flagging",
    description=(
        "Flags missing, modified, conflicting, or non-standard contract clauses "
        "(CC-01..CC-18) for human review. Decision support only — not legal advice. "
        "Page citations are only verbatim matches of draft_evidence in extracted PDF text."
    ),
    version="0.1.0",
)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/packages/review")
async def review_zip(
    file: UploadFile = File(...),
    format: str = Query("json", description="json or html"),
):
    """Accept a zip of one challenge package (Project_Metadata.json + Docs/)."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip of one contract package")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "pkg"
        root.mkdir()
        zip_path = Path(tmp) / "upload.zip"
        zip_path.write_bytes(raw)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(root)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Not a valid zip file") from exc
        packages = discover_packages(root)
        if not packages:
            raise HTTPException(
                status_code=400,
                detail="Zip must contain a folder with Project_Metadata.json and Docs/",
            )
        client = get_client()
        findings = review_package(packages[0], client=client)
        if format.lower() == "html":
            return HTMLResponse(_demo_html(findings))
        return JSONResponse(_demo_payload(findings))


def _demo_payload(findings: list[Finding]) -> dict:
    flags = [f for f in findings if f.predicted_label == "FLAG"]
    return {
        "document_id": findings[0].document_id if findings else "",
        "disclaimer": "Decision support for human review — not legal advice.",
        "flag_count": len(flags),
        "findings": [f.as_demo() for f in findings],
    }


def _demo_html(findings: list[Finding]) -> str:
    doc_id = html.escape(findings[0].document_id if findings else "")
    cards = []
    for finding in findings:
        if finding.predicted_label != "FLAG":
            continue
        loc = finding.locator or {}
        found = bool(loc.get("quote_found_in_extracted_text"))
        kind = "located" if found else "unlocated"
        searched = ", ".join(html.escape(x) for x in loc.get("files_in_package") or [])
        ref_loc = html.escape(finding.reference_location)
        ref_ev = html.escape(finding.reference_evidence)
        anchors_html = []
        for anchor in loc.get("anchors") or []:
            file_name = html.escape(str(anchor.get("file_name") or ""))
            page = html.escape(str(anchor.get("page") or ""))
            mark = anchor.get("highlight_html") or html.escape(
                str(anchor.get("verbatim_excerpt") or "")
            )
            anchors_html.append(
                f"<div class='anchor'><div class='meta'>{file_name} · p.{page} · verbatim match</div>"
                f"<blockquote>{mark}</blockquote></div>"
            )
        evidence_block = "".join(anchors_html) or (
            "<p class='note'>No verbatim page match — no page is cited.</p>"
        )
        badge = "Located in package" if found else "Quote not in extracted text"
        cards.append(
            f"<article class='card {kind}'>"
            f"<header><span class='rid'>{html.escape(finding.requirement_id)}</span>"
            f"<span class='sev'>{html.escape(finding.severity)}</span>"
            f"<span class='kind'>{badge}</span></header>"
            f"<p class='loc'>{html.escape(finding.draft_location)}</p>"
            f"<p class='slot'><strong>Checklist section:</strong> {ref_loc}</p>"
            f"<p class='slot'><strong>Challenge rule:</strong> {ref_ev}</p>"
            f"{evidence_block}"
            f"<p class='why'>{html.escape(finding.explanation[:500])}</p>"
            f"<p class='files'><strong>Files in package:</strong> {searched}</p>"
            f"</article>"
        )
    body = "".join(cards) or "<p>No FLAG rows.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>CCRF {doc_id}</title>
<style>
body {{ font-family: Georgia, serif; background: #f4f1ea; color: #1b2430; margin: 0; }}
main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px 64px; }}
h1 {{ font-size: 22px; margin-bottom: 6px; }}
.sub {{ color: #5a6570; margin-bottom: 24px; }}
.card {{ background: #fff; border-left: 6px solid #9a3412; padding: 16px 18px; margin: 14px 0; box-shadow: 0 1px 3px #0001; }}
.card.located {{ border-color: #9a3412; }}
.card.unlocated {{ border-color: #7f1d1d; }}
header {{ display: flex; gap: 10px; align-items: baseline; margin-bottom: 8px; }}
.rid {{ font-weight: 700; }}
.kind {{ background: #1b2430; color: #fff; padding: 2px 8px; font-size: 12px; letter-spacing: .02em; }}
blockquote {{ background: #fff8e7; padding: 10px 12px; margin: 8px 0; }}
mark {{ background: #fde68a; padding: 0 2px; }}
.note {{ font-size: 13px; color: #7f1d1d; }}
.meta, .files, .loc {{ font-size: 13px; color: #3d4a57; }}
</style></head>
<body><main>
<h1>Contract clause flags · {doc_id}</h1>
<p class="sub">Human review decision support — not legal advice. Yellow mark is a verbatim span copied from extracted page text. If the quote is not in the PDFs, no page is cited.</p>
{body}
</main></body></html>"""

