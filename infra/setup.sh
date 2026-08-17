#!/usr/bin/env bash
# Attach this repo to GCP project hackathon-2026-transport-2 (Vertex AI / ADC).
# Run from the repo root, in a normal Terminal window (needs a browser):
#   bash infra/setup.sh
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-hackathon-2026-transport-2}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

echo "==> GCP project: ${PROJECT_ID}"
echo "==> Region:      ${LOCATION}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo
  echo "gcloud is not installed. On this Mac:"
  echo "  brew install --cask gcloud-cli"
  echo "Then open a new terminal and re-run: bash infra/setup.sh"
  exit 1
fi

ACTIVE="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || true)"
if [[ -z "${ACTIVE}" ]]; then
  echo
  echo "==> No Google account is logged into gcloud yet."
  echo "    A browser window will open. Sign in with the Google account that"
  echo "    was added to project ${PROJECT_ID} (not a random personal Gmail"
  echo "    unless that address is on the project)."
  echo
  gcloud auth login --update-adc
else
  echo "==> Already logged in as ${ACTIVE}"
fi

echo "==> Setting active project"
gcloud config set project "${PROJECT_ID}"

echo "==> Enable Vertex AI (Gemini + RAG Engine)"
gcloud services enable aiplatform.googleapis.com --project "${PROJECT_ID}"

# Phase 2 (run later, after Development scoring is locked):
# gcloud services enable documentai.googleapis.com run.googleapis.com --project "${PROJECT_ID}"

if [[ ! -f "${HOME}/.config/gcloud/application_default_credentials.json" ]]; then
  echo "==> Application Default Credentials for local Python (browser again)"
  gcloud auth application-default login
fi

gcloud auth application-default set-quota-project "${PROJECT_ID}" || true

echo
echo "Logged in as: $(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
echo "Project:      $(gcloud config get-value project)"
echo
echo "Then:"
echo "  source .venv/bin/activate"
echo "  export GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
echo "  python -m ccrf.cli rag-index --root Development"
echo "  python -m ccrf.cli run --root Development --rag --out runs/development_results.csv"
