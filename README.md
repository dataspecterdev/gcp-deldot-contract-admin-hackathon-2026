# GCP DelDOT Contract Admin Hackathon 2026

Evidence-grounded Vertex AI pipeline that reviews transportation contract packages against the DelDOT challenge checklist (CC-01..CC-18).

## Latest Development scores

| Run | Applicability | FLAG precision | FLAG recall | Confusion |
|---|---|---|---|---|
| Keyword / pypdf (no RAG) | 1.000 | 0.730 | 0.964 | TP 27 / FP 10 / FN 1 / TN 70 |
| Vertex RAG Engine | 1.000 | 0.711 | 0.964 | TP 27 / FP 11 / FN 1 / TN 69 |

RAG is indexed and retrieves, but it did not beat the non-RAG judge on this labeled set (one extra false positive; Stone Creek CC-14 is still a miss). Keep keyword fallback. Use `--rag` for the multi-cloud demo, not as the frozen scorer until precision recovers.


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

`eval-applicability` and `extract` work without GCP. `run` needs Vertex ADC after `bash infra/setup.sh`. Do not score Validation until Development FLAG precision/recall are acceptable.

## Vertex RAG Engine (Google RAG)

Teammates on Azure/AWS will show their platform RAG product (Azure AI Search, Bedrock Knowledge Bases). The Google equivalent used here is **Vertex AI RAG Engine**, still on project `hackathon-2026-transport-2` with ADC. Gemini File Search was not used — it requires an AI Studio API key and does not work with Vertex.

```bash
pip install -e '.[dev]'
python -m ccrf.cli rag-index --root Development
python -m ccrf.cli run --root Development --rag --out runs/development_results.csv
```

Indexing uploads the challenge PDFs into a Vertex RAG corpus per package. `--rag` retrieves extra chunks into the Gemini judge. If RAG is unavailable, keyword/pypdf retrieval still runs.
