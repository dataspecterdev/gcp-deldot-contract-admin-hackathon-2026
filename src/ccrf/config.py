from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
PROMPTS_DIR = REPO_ROOT / "prompts"
CACHE_DIR = Path(os.environ.get("CCRF_CACHE_DIR", REPO_ROOT / ".cache" / "extracted"))

GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "hackathon-2026-transport-2")
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

REQUIREMENT_IDS = [f"CC-{i:02d}" for i in range(1, 19)]

SUBMISSION_FIELDS = [
    "document_id",
    "requirement_id",
    "applicability_decision",
    "applicability_reason",
    "predicted_label",
    "severity",
    "governing_document",
    "draft_location",
    "draft_evidence",
    "reference_id",
    "reference_location",
    "reference_evidence",
    "explanation",
    "confidence",
    "recommended_human_action",
]
