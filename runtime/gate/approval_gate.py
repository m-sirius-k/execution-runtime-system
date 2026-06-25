from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec
from runtime.storage import db


class ApprovalRejected(Exception):
    pass


@dataclass
class HumanConfirmationEvent:
    confirmed: bool
    human_identity: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def approve(spec: TaskSpec, human_event: HumanConfirmationEvent,
            signing_key: Ed25519PrivateKey) -> dict:
    """Converts a validated TaskSpec + human confirmation into an approval_token.

    This function does not judge intent, does not interpret params, and does
    not generate rejection reasoning beyond a fixed reject signal — it only
    transforms an external human event into a bound, signed token.
    """
    spec.validate()

    if not human_event.confirmed:
        raise ApprovalRejected("human confirmation absent")

    spec_hash = crypto.sha256_hex(spec.binding_payload())
    signature = crypto.sign(signing_key, spec_hash)
    issued_at = _now()
    token_id = str(uuid.uuid4())

    scope = {
        "spec_id": spec.spec_id,
        "execution_mode": "single_use",
        "expires_at": None,
    }

    db.insert_approval_token(
        token_id=token_id,
        spec_id=spec.spec_id,
        spec_hash=spec_hash,
        signature_hex=signature.hex(),
        scope=scope,
        issued_at=issued_at,
    )

    return {
        "token_id": token_id,
        "spec_binding_hash": spec_hash,
        "human_signature": signature.hex(),
        "scope": scope,
        "issued_at": issued_at,
    }
