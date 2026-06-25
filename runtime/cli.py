"""Manual-trigger execution entrypoint for the GitHub Actions agent workflow.

This script assumes it only runs after a human has already passed a GitHub
Environment protection approval gate (the human approval event). It performs
exactly one Task Spec -> Approval Gate -> Execution Core -> Result cycle and
exits. It does not loop, does not self-trigger, and does not bypass the
single-use token model used by the rest of the runtime.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runtime.core import execution_core
from runtime.gate import approval_gate
from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec, TaskSpecRejected
from runtime.storage import db


def _identity_run(intent: str, params: dict):
    return {"intent": intent, "params": params}


def main() -> int:
    intent = os.environ.get("TASK_INTENT")
    human_identity = os.environ.get("HUMAN_IDENTITY")
    params_raw = os.environ.get("TASK_PARAMS", "{}")

    if not intent or not human_identity:
        print("TASK_INTENT and HUMAN_IDENTITY are required", file=sys.stderr)
        return 1

    try:
        params = json.loads(params_raw)
    except json.JSONDecodeError as exc:
        print(f"TASK_PARAMS is not valid JSON: {exc}", file=sys.stderr)
        return 1

    db.init_db()

    spec = TaskSpec(
        spec_id=str(uuid.uuid4()),
        issued_by=human_identity,
        issued_at=datetime.now(timezone.utc).isoformat(),
        intent=intent,
        params=params,
    )

    try:
        spec.validate()
    except TaskSpecRejected as exc:
        print(f"REJECTED at Task Spec validation: {exc}", file=sys.stderr)
        return 1

    db.insert_task_spec(spec)

    # Reaching this line means the GitHub Environment protection gate already
    # required an explicit human approval before this job started. That gate
    # IS the human confirmation event — this script does not grant approval
    # on its own and cannot run unattended.
    signing_key, verify_key = crypto.load_or_create_keypair()
    event = approval_gate.HumanConfirmationEvent(confirmed=True, human_identity=human_identity)
    try:
        token = approval_gate.approve(spec, event, signing_key)
    except approval_gate.ApprovalRejected as exc:
        print(f"REJECTED at Approval Gate: {exc}", file=sys.stderr)
        return 1

    result = execution_core.execute(spec, token["token_id"], verify_key, _identity_run)

    print(json.dumps({"spec_id": spec.spec_id, "token_id": token["token_id"], **result}, indent=2))

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("### Execution Result\n")
            fh.write(f"- spec_id: `{spec.spec_id}`\n")
            fh.write(f"- issued_by: `{human_identity}`\n")
            fh.write(f"- status: `{result['status']}`\n")
            fh.write(f"- result: `{result['result']}`\n")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
