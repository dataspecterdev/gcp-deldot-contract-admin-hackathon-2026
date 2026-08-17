from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ccrf.config import CONFIG_DIR, REQUIREMENT_IDS


def load_rules(path: Path | None = None) -> dict[str, Any]:
    path = path or (CONFIG_DIR / "applicability_rules.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _yes(value: Any) -> bool:
    return str(value).strip().lower() == "yes"


def decide_applicability(
    requirement_id: str,
    metadata: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (APPLIES|DOES_NOT_APPLY, reason). Never calls an LLM."""
    rules = rules or load_rules()
    if requirement_id not in REQUIREMENT_IDS:
        raise KeyError(requirement_id)

    always = set(rules.get("always_apply") or [])
    if requirement_id in always:
        return "APPLIES", "Baseline DelDOT proposal/contract requirement applies to this package."

    equals_yes = rules.get("metadata_equals_yes") or {}
    if requirement_id in equals_yes:
        field = equals_yes[requirement_id]
        if _yes(metadata.get(field)):
            return "APPLIES", f"Project metadata {field}=Yes triggers {requirement_id}."
        return "DOES_NOT_APPLY", f"Project metadata {field} is not Yes; {requirement_id} does not apply."

    list_fields = rules.get("nonempty_list_field") or {}
    if requirement_id in list_fields:
        field = list_fields[requirement_id]
        values = metadata.get(field) or []
        if isinstance(values, str):
            values = [values] if values.strip() else []
        if values:
            return "APPLIES", f"Project metadata {field} is non-empty ({len(values)} issued); {requirement_id} applies."
        return "DOES_NOT_APPLY", f"Project metadata {field} is empty; {requirement_id} does not apply."

    raise KeyError(f"No applicability rule for {requirement_id}")
