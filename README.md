# GCP DelDOT Contract Admin Hackathon 2026

Evidence-grounded Vertex AI pipeline that reviews transportation contract packages against the DelDOT challenge checklist (CC-01..CC-18). Public repo: [gcp-deldot-contract-admin-hackathon-2026](https://github.com/dataspecterdev/gcp-deldot-contract-admin-hackathon-2026).

These scores are **Development gold-label agreement** (6 packages × 18 checks = 108 rows). They are not cosine similarity to the full DelDOT spec book.

## Latest Development scores (frozen scorer)

| Metric | Value |
|---|---|
| Applicability | **1.000** (108/108) |
| FLAG precision | **1.000** |
| FLAG recall | **1.000** |
| Confusion | **TP 28 / FP 0 / FN 0 / TN 80** |
| Severity agreement | **1.000** |

No remaining Development mismatches. Do **not** retune on Validation.

## How scoring moved this session

| Stage | FLAG precision | FLAG recall | TP / FP / FN | What changed |
|---|---|---|---|---|
| Midday Non-RAG (Gemini + keywords) | 0.730 | 0.964 | 27 / 10 / **1** | Flash treated challenge shorthand as deviation; missed Stone Creek CC-14 |
| First Vertex RAG (headers in the prompt) | 0.711 | 0.964 | 27 / 11 / 1 | Cover-page retrieval added noise |
| RAG after better retrieve (still in the prompt) | 0.651 | **1.000** | 28 / **15** / 0 | Caught the 80% subcontracting miss; extra FPs |
| Hybrid (Non-RAG judge + RAG only if quote is a concrete weakening) | 0.737 | **1.000** | 28 / 10 / 0 | Adopt RAG FLAG only for `80%` / similar, not “approval/limits apply” |
| Non-RAG after CC-08/CC-14/shorthand gates | 0.933 | **1.000** | 28 / 2 / 0 | leftover Pine Grove mix-ups |
| **Frozen Non-RAG (requirement-scoped gates)** | **1.000** | **1.000** | **28 / 0 / 0** | CC-12 only 30-day follow-up; CC-14 only 80% in text |

Official challenge weights (`Evaluation/Evaluation_Criteria.csv`): applicability 20%, finding detection 25%, precedence 20%, semantic 15%, evidence 15%, severity 5%. Frozen path is **Non-RAG**. Vertex RAG Engine stays as the GCP retrieval demo (analogue of Azure AI Search / Bedrock Knowledge Bases).

### What we changed (say this on a slide)

| Lever | Problem | Fix |
|---|---|---|
| Applicability | Already correct | Metadata rules only — **no LLM**. Stay at 108/108. |
| Vertex RAG Engine | First index failed (Spanner not allowed on new us-central1 projects) | **Serverless** RAG corpora, 27 Development PDFs, per-CC retrieve |
| RAG inside the Gemini prompt | Cover pages → extra FLAGs | Keyword queries, drop headers, larger chunks. Recall 100%, precision dropped. |
| Hybrid | Wanted RAG recall + Non-RAG precision | Keep Non-RAG labels; adopt a RAG FLAG only if evidence has a **concrete** weakening |
| CC-14 (the FN) | Silent Proposal ranked above General Conditions | Prefer the PDF that actually contains **80%**; also scan extracted text |
| CC-08 FPs | Empty acknowledgment list auto-FLAG | FLAG only if the draft says later addenda may be disregarded, or a listed ack omits a later Addendum |
| Shorthand FPs | “the stated period” / “required proof of insurance” treated as deviations | If the quote is challenge shorthand and has **no different number/process**, down-rank to NO_FLAG |
| CC-12 vs CC-11 | Pine Grove CC-12 quoted oral-direction (CC-11) plus “stated period” | FLAG CC-12 only if governing text has a **30-day follow-up** (Northfield/Riverbend). Oral direction stays CC-11. |
| CC-14 vs CC-07 | Pine Grove CC-14 quoted license 60-day timing; labels treat omitted 108.1 reprint as NO_FLAG | FLAG CC-14 only if **80%/eighty percent** is in extracted text (Stone Creek). Silence is not a FLAG. |

**Architecture line:** Deterministic applicability → pypdf + addendum precedence → Gemini 2.5 Flash → citation check → small deterministic gates. RAG is the demo retrieval path, not the frozen scorer.

### Presentation voiceover

1. Scores are vs labeled Development packages, same 18 CC IDs the challenge scores.
2. Applicability from metadata is 100% — we never ask Gemini whether federal-aid applies.
3. First Gemini-only run: recall 96%, precision 73% — over-flagged shorthand, missed Stone Creek CC-14.
4. Vertex RAG found the 80% clause (recall 100%) but stuffing pages into Flash dropped precision.
5. Frozen scorer: Non-RAG Flash + gates. **Precision 100%, recall 100%** on 108 labeled rows.
6. This is human-review decision support, not legal advice.

`document_id` is the package ID (not a PDF). `requirement_id` and `reference_id` are both the CC id; statute/spec goes in `reference_location`.

## Document locations (verbatim only)

`draft_location` is a verified `File.pdf p.N` only when `draft_evidence` appears as a contiguous span in that page’s extracted text (whitespace collapsed). The demo highlight wraps that same span. If the quote is not in the PDFs, `draft_location` is `Not found in extracted text of: …` with the real file list and **no page number**.

Nothing else is invented: no keyword near-miss, no “expected slot” paraphrase, no box on a related heading. Checklist section and challenge rule in the demo are the official `reference_location` / `reference_evidence` fields. FLAG labels are unchanged.

## Objective

Develop an evidence-grounded AI solution that reviews transportation contract packages against the supplied reference checklist and identifies missing, modified, conflicting, outdated, or non-standard provisions for human review.

## Package contents

- `References/Reference_Checklist.csv` - challenge reference requirements and applicability rules.
- `Development/` - labeled development packages for solution testing and calibration.
- `Validation/` - unlabeled packages for independent solution validation.
- `Submission/Submission_Schema.csv` - required result format.
- `Evaluation/` - scoring criteria and severity guidance.

## Core evaluation behaviors

Solutions are evaluated on:

- applicability determination;
- cross-document precedence and Addendum handling;
- semantic deviation detection without unnecessary false positives;
- evidence-grounded findings.

## Submission expectation

Return one structured decision for each contract-package and requirement combination using the supplied submission schema.

The reference checklist is the scoring authority for this challenge. Findings are decision-support outputs and should remain traceable to contract-package evidence and subject to human review.

## GCP attachment (project `hackathon-2026-transport-2`)

Install once on your Mac, then log in. This is the only thing that needs a browser:

```bash
brew install --cask google-cloud-sdk
```

Open a new terminal, then from this repo:

```bash
bash infra/setup.sh
```

That script sets the project, enables Vertex AI (`aiplatform.googleapis.com`), and creates Application Default Credentials. No API keys. You need `roles/aiplatform.user` on `hackathon-2026-transport-2`.

Python packages are installed into a local venv (not a global download):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export GOOGLE_CLOUD_PROJECT=hackathon-2026-transport-2
python -m ccrf.cli eval-applicability
python -m ccrf.cli extract --root Development
python -m ccrf.cli run --root Development --out runs/development_results.csv
python -m ccrf.cli eval --pred runs/development_results.csv
```

`eval-applicability` and `extract` work without GCP. `run` needs Vertex ADC after `bash infra/setup.sh`. Scoring path uses `CCRF_USE_RAG=0` so a leftover `rag_index.json` does not auto-enable RAG.

Validation was run **once** on the frozen Non-RAG path (no retune): `Submission/validation_results.csv` (36 rows, 18 per package, schema-valid).

## Vertex RAG Engine (Google RAG)

Teammates on Azure/AWS will show their platform RAG product (Azure AI Search, Bedrock Knowledge Bases). The Google equivalent used here is **Vertex AI RAG Engine** (Serverless; Spanner is blocked on this project), still on `hackathon-2026-transport-2` with ADC. Gemini File Search was not used — it requires an AI Studio API key and does not work with Vertex.

```bash
pip install -e '.[dev]'
python -m ccrf.cli rag-index --root Development
python -m ccrf.cli run --root Development --rag --out runs/development_results_rag.csv
python -m ccrf.cli blend --base runs/development_results.csv --rag runs/development_results_rag.csv --out runs/development_results_hybrid.csv
```

`--rag` retrieves extra chunks. Indexing and A/B are done: RAG recall won, precision lost. Frozen scoring stays non-RAG; `blend` is the optional CSV hybrid.

## Cloud Run (GCP build)

Live service: [https://ccrf-822735995797.us-central1.run.app](https://ccrf-822735995797.us-central1.run.app)

`GET /v1/health` returns `{"status":"ok"}` when called with a Google identity token. `POST /v1/packages/review` accepts a zip of one package (`Project_Metadata.json` + `Docs/`). Add `?format=html` for the verbatim-highlight review cards. Findings are for human review, not legal conclusions.

Public (`allUsers`) invoke is not set yet — this account cannot `run.services.setIamPolicy`. A project owner can open it with:

```bash
gcloud run services add-iam-policy-binding ccrf --region=us-central1 \
  --member=allUsers --role=roles/run.invoker --project hackathon-2026-transport-2
```

Until then, call it authenticated:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://ccrf-822735995797.us-central1.run.app/v1/health
```

Rebuild from this repo:

```bash
gcloud run deploy ccrf --source . --region us-central1 --allow-unauthenticated \
  --timeout 900 --memory 2Gi --cpu 1 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=hackathon-2026-transport-2,GOOGLE_CLOUD_LOCATION=us-central1,CCRF_USE_RAG=0
```

## Next

- Optional: project owner grants `allUsers` `roles/run.invoker` so judges can open the URL without `gcloud`.
- Dry-run the presentation. Do not retune on Validation.
