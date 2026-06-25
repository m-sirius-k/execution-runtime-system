from __future__ import annotations

from typing import Any


def detect_divergence(intent: dict[str, Any], execution: dict[str, Any]) -> str:
    """Compares what was intended against what actually executed.

    This is read-only: it never alters execution state, only classifies it.
    Severity order (most severe wins): CRITICAL > HIGH > MEDIUM > OK.
    """
    if intent.get("task") != execution.get("task"):
        return "CRITICAL"

    expected_state = intent.get("expected_state")
    if expected_state is not None and expected_state != execution.get("final_state"):
        return "HIGH"

    if execution.get("warnings"):
        return "MEDIUM"

    return "OK"
