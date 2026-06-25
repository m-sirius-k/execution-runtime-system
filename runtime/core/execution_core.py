from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec
from runtime.storage import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_token(token_id: str, spec_id: str, verify_key: Ed25519PublicKey) -> bool:
    row = db.get_approval_token(token_id)
    if row is None:
        return False
    if row["used_flag"]:
        return False
    if row["spec_id"] != spec_id:
        return False
    return crypto.verify(verify_key, bytes.fromhex(row["signature"]), row["spec_hash"])


def execute(spec: TaskSpec, token_id: str, verify_key: Ed25519PublicKey, run) -> dict:
    """Pure executor: decides nothing beyond token validity. `run` is the
    deterministic, side-effect-isolated callable that performs spec.intent.

    Token consumption is claimed atomically (claim_token) so concurrent
    executions against the same token cannot both pass — only one caller
    ever wins, eliminating the validate-then-mark race window.
    """
    execution_id = str(uuid.uuid4())
    timestamp = _now()

    if not validate_token(token_id, spec.spec_id, verify_key):
        db.append_execution_log(execution_id, spec.spec_id, token_id, "", "REJECTED", timestamp)
        return {"execution_id": execution_id, "status": "REJECTED", "result": None}

    if not db.claim_token(token_id):
        db.append_execution_log(execution_id, spec.spec_id, token_id, "", "REJECTED", timestamp)
        return {"execution_id": execution_id, "status": "REJECTED", "result": None}

    result = run(spec.intent, spec.params)

    db.append_execution_log(execution_id, spec.spec_id, token_id, str(result), "success", timestamp)
    return {"execution_id": execution_id, "status": "success", "result": result}
