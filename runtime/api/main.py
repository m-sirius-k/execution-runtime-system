from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from runtime.core import execution_core
from runtime.gate import approval_gate
from runtime.gate.approval_gate import HumanConfirmationEvent
from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec, TaskSpecRejected
from runtime.storage import db

app = FastAPI(title="Execution Runtime System", version="1.0")

_signing_key, _verify_key = crypto.load_or_create_keypair()


def _identity_run(intent: str, params: dict):
    """Placeholder deterministic executor — replace with real task dispatch."""
    return {"intent": intent, "params": params}


class TaskSpecIn(BaseModel):
    issued_by: str
    intent: str
    params: dict = {}


class ApproveIn(BaseModel):
    spec_id: str
    confirmed: bool
    human_identity: str


class ExecuteIn(BaseModel):
    spec_id: str
    token_id: str


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.post("/task-spec")
def create_task_spec(payload: TaskSpecIn):
    spec = TaskSpec(
        spec_id=str(uuid.uuid4()),
        issued_by=payload.issued_by,
        issued_at=datetime.now(timezone.utc).isoformat(),
        intent=payload.intent,
        params=payload.params,
    )
    try:
        spec.validate()
    except TaskSpecRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    db.insert_task_spec(spec)
    return {"spec_id": spec.spec_id, "issued_at": spec.issued_at}


def _load_spec(spec_id: str) -> TaskSpec:
    row = db.get_task_spec(spec_id)
    if row is None:
        raise HTTPException(status_code=404, detail="spec not found")
    return TaskSpec(
        spec_id=row["spec_id"],
        issued_by=row["issued_by"],
        issued_at=row["issued_at"],
        intent=row["intent"],
        params=json.loads(row["params_json"]),
    )


@app.post("/approve")
def approve_task_spec(payload: ApproveIn):
    spec = _load_spec(payload.spec_id)

    event = HumanConfirmationEvent(confirmed=payload.confirmed, human_identity=payload.human_identity)
    try:
        token = approval_gate.approve(spec, event, _signing_key)
    except approval_gate.ApprovalRejected as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return token


@app.post("/execute")
def execute_task(payload: ExecuteIn):
    spec = _load_spec(payload.spec_id)
    return execution_core.execute(spec, payload.token_id, _verify_key, _identity_run)
