# GCP DelDOT Contract Admin Hackathon 2026

Evidence-grounded Vertex AI pipeline that reviews transportation contract packages against the DelDOT challenge checklist (CC-01..CC-18). Public repo: [gcp-deldot-contract-admin-hackathon-2026](https://github.com/dataspecterdev/gcp-deldot-contract-admin-hackathon-2026).

These scores are **Development gold-label agreement** (6 packages × 18 checks = 108 rows). They are not cosine similarity to the full DelDOT spec book.

## Latest Development scores (frozen scorer)

| Metric | Value |
|---|---|
| Applicability | **1.000** (108/108) |
| FLAG precision | **0.933** |
| FLAG recall | **1.000** |
| Confusion | **TP 28 / FP 2 / FN 0 / TN 78** |
| Severity agreement | **0.981** |

Remaining mismatches: Pine Grove CC-12 and CC-14 only. Do **not** retune on Validation.

## How scoring moved this session

| Stage | FLAG precision | FLAG recall | TP / FP / FN | What changed |
|---|---|---|---|---|
| Midday Non-RAG (Gemini + keywords) | 0.730 | 0.964 | 27 / 10 / **1** | Flash treated challenge shorthand as deviation; missed Stone Creek CC-14 |
| First Vertex RAG (headers in the prompt) | 0.711 | 0.964 | 27 / 11 / 1 | Cover-page retrieval added noise |
| RAG after better retrieve (still in the prompt) | 0.651 | **1.000** | 28 / **15** / 0 | Caught the 80% subcontracting miss; extra FPs |
| Hybrid (Non-RAG judge + RAG only if quote is a concrete weakening) | 0.737 | **1.000** | 28 / 10 / 0 | Adopt RAG FLAG only for `80%` / similar, not “approval/limits apply” |
| **Frozen Non-RAG scoring** | **0.933** | **1.000** | **28 / 2 / 0** | CC-08/CC-14 gates + shorthand down-rank |

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

**Architecture line:** Deterministic applicability → pypdf + addendum precedence → Gemini 2.5 Flash → citation check → small deterministic gates. RAG is the demo retrieval path, not the frozen scorer.

### Presentation voiceover

1. Scores are vs labeled Development packages, same 18 CC IDs the challenge scores.
2. Applicability from metadata is 100% — we never ask Gemini whether federal-aid applies.
3. First Gemini-only run: recall 96%, precision 73% — over-flagged shorthand, missed Stone Creek CC-14.
4. Vertex RAG found the 80% clause (recall 100%) but stuffing pages into Flash dropped precision.
5. Frozen scorer: Non-RAG Flash + gates. **Precision 93%, recall 100%** on 108 rows.
6. This is human-review decision support, not legal advice.

`document_id` is the package ID (not a PDF). `requirement_id` and `reference_id` are both the CC id; statute/spec goes in `reference_location`.

## Document locations: cite found issues; do not invent pages for missing text

**Yes, point reviewers at the issue — the schema already requires it.** `draft_location` and `draft_evidence` are required for FLAG, and evidence/citation is 15% of the official score. We already emit `File.pdf p.N` plus a quote when the weakening **is in the package**.

**Do not build a “missing-section highlighter” that pretends an absent clause has a page.** Absence has no bbox. For missing items (e.g. FHWA-1273 not physically attached), the useful output is:

- files searched / governing document that only *incorporates by reference*;
- expected slot (“should be in Proposal / as an attachment”);
- optional **near-miss** quote (related language that is not the requirement);
- `reference_location` for the spec/statute we compared against.

Skip PDF overlays / bounding boxes this week. File + page + quote already satisfies the CSV and the demo. If we polish locations later, only add search-scope + expected-slot language for missing FLAGs.

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

`eval-applicability` and `extract` work without GCP. `run` needs Vertex ADC after `bash infra/setup.sh`. Do not score Validation until Development is frozen (it is frozen at the table above). Scoring path uses `CCRF_USE_RAG=0` so a leftover `rag_index.json` does not auto-enable RAG.

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

The same review engine is a public demo API. From this repo (needs `gcloud` auth on `hackathon-2026-transport-2`):

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project hackathon-2026-transport-2
gcloud run deploy ccrf --source . --region us-central1 --allow-unauthenticated \
  --timeout 900 --memory 2Gi --cpu 1 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=hackathon-2026-transport-2,GOOGLE_CLOUD_LOCATION=us-central1,CCRF_USE_RAG=0
```

`POST /v1/packages/review` accepts a zip of one package (`Project_Metadata.json` + `Docs/`). `GET /v1/health` is the probe. Findings are for human review, not legal conclusions. Enabling Cloud Run APIs / IAM for the default SA may need an explicit org-policy exemption.

## Next

- Optional: last two Pine Grove FPs; then freeze harder.
- Run Validation once (`Mill_Creek`, `Oak_Hollow`); do not retune.
- Deploy Cloud Run after APIs are enabled.
- Do not build PDF page overlays for missing clauses.
