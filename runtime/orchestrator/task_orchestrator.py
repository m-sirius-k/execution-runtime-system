"""Input normalization layer that sits in front of the frozen governance
pipeline (Task Spec / Approval Gate / Execution Core / Divergence Check /
Audit Issue). This module does not call into, modify, or wire itself into
that pipeline — it only reshapes raw input into a normalized dict.

It does not judge, control, execute, or evaluate anything: formatting only.
"""
from __future__ import annotations

from typing import Any


def task_orchestrator(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": raw.get("task"),
        "context": raw.get("context", {}),
        "constraints": raw.get("constraints", {}),
        "expected_state": raw.get("expected_state"),
    }
