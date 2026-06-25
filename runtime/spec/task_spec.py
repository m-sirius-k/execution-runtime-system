from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_KEYS = {
    "if", "condition", "branch",
    "decision", "rule", "policy",
    "judgment_logic", "decision_structure",
    "source_system", "auto_generated",
}

FORBIDDEN_VALUE_PATTERN = re.compile(r"mocka", re.IGNORECASE)


class TaskSpecRejected(Exception):
    pass


def _scan_for_contamination(obj: Any, path: str = "params") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower()
            if any(forbidden in key_lower for forbidden in FORBIDDEN_KEYS):
                raise TaskSpecRejected(f"forbidden key '{key}' at {path}.{key}")
            if isinstance(value, str) and FORBIDDEN_VALUE_PATTERN.search(value):
                raise TaskSpecRejected(f"forbidden value at {path}.{key}")
            _scan_for_contamination(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _scan_for_contamination(item, f"{path}[{index}]")


@dataclass
class TaskSpec:
    spec_id: str
    issued_by: str
    issued_at: str
    intent: str
    params: dict = field(default_factory=dict)
    approval_token: str | None = None

    def validate(self) -> None:
        if not self.spec_id or not self.issued_by or not self.issued_at or not self.intent:
            raise TaskSpecRejected("missing required field")
        if FORBIDDEN_VALUE_PATTERN.search(self.intent):
            raise TaskSpecRejected("forbidden value in intent")
        _scan_for_contamination(self.params)

    def binding_payload(self) -> str:
        return f"{self.spec_id}{self.issued_by}{self.issued_at}"
