import os
import sys
import tempfile
import threading
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runtime.core import execution_core
from runtime.gate import approval_gate
from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec, TaskSpecRejected
from runtime.storage import db


def setup_module(_module):
    db.DB_PATH = type(db.DB_PATH)(tempfile.mkstemp(suffix=".db")[1])
    db.init_db()


def _spec(spec_id, **overrides):
    base = dict(
        spec_id=spec_id,
        issued_by="human-1",
        issued_at=datetime.now(timezone.utc).isoformat(),
        intent="noop",
        params={},
    )
    base.update(overrides)
    return TaskSpec(**base)


def _approved(spec_id):
    spec = _spec(spec_id)
    db.insert_task_spec(spec)
    private_key, public_key = crypto.generate_keypair()
    event = approval_gate.HumanConfirmationEvent(confirmed=True, human_identity="human-1")
    token = approval_gate.approve(spec, event, private_key)
    return spec, token, public_key


def _log_count(spec_id):
    with db.connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM execution_log WHERE spec_id = ?", (spec_id,)
        ).fetchone()["c"]


def test_tc01_normal_execution():
    spec, token, public_key = _approved("tc01")
    result = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    assert result["status"] == "success"
    assert _log_count("tc01") == 1


def test_tc02_unapproved_execution_rejected():
    spec = _spec("tc02")
    db.insert_task_spec(spec)
    private_key, _ = crypto.generate_keypair()
    event = approval_gate.HumanConfirmationEvent(confirmed=False, human_identity="human-1")
    try:
        approval_gate.approve(spec, event, private_key)
        assert False, "expected rejection"
    except approval_gate.ApprovalRejected:
        pass


def test_tc03_invalid_task_spec_rejected():
    spec = _spec("tc03", params={"decision_logic": "always_allow"})
    try:
        spec.validate()
        assert False, "expected rejection"
    except TaskSpecRejected:
        pass


def test_tc04_mocka_contamination_rejected():
    spec = _spec("tc04", intent="call MoCKA judgment")
    try:
        spec.validate()
        assert False, "expected rejection"
    except TaskSpecRejected:
        pass


def test_tc05_token_replay_rejected():
    spec, token, public_key = _approved("tc05")
    first = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    second = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    assert first["status"] == "success"
    assert second["status"] == "REJECTED"
    assert _log_count("tc05") == 2


def test_tc06_tampered_signature_rejected():
    spec, token, public_key = _approved("tc06")
    tampered = bytes.fromhex(token["human_signature"])
    tampered = bytes([tampered[0] ^ 0xFF]) + tampered[1:]
    with db.connect() as conn:
        conn.execute(
            "UPDATE approval_token SET signature = ? WHERE token_id = ?",
            (tampered.hex(), token["token_id"]),
        )
    result = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    assert result["status"] == "REJECTED"


def test_concurrent_executions_single_winner():
    spec, token, public_key = _approved("tc-concurrent")
    results = []
    lock = threading.Lock()

    def worker():
        r = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
        with lock:
            results.append(r["status"])

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("success") == 1, f"expected exactly one success, got {results}"
    assert results.count("REJECTED") == 9
    assert _log_count("tc-concurrent") == 10


def test_audit_log_append_only_enforced():
    spec, token, public_key = _approved("tc-audit")
    execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")

    import sqlite3

    try:
        with db.connect() as conn:
            conn.execute(
                "UPDATE execution_log SET status = 'tampered' WHERE spec_id = ?", ("tc-audit",)
            )
        assert False, "expected update to be blocked"
    except sqlite3.IntegrityError:
        pass

    try:
        with db.connect() as conn:
            conn.execute("DELETE FROM execution_log WHERE spec_id = ?", ("tc-audit",))
        assert False, "expected delete to be blocked"
    except sqlite3.IntegrityError:
        pass


if __name__ == "__main__":
    setup_module(None)
    test_tc01_normal_execution()
    test_tc02_unapproved_execution_rejected()
    test_tc03_invalid_task_spec_rejected()
    test_tc04_mocka_contamination_rejected()
    test_tc05_token_replay_rejected()
    test_tc06_tampered_signature_rejected()
    test_concurrent_executions_single_winner()
    test_audit_log_append_only_enforced()
    print("all e2e tests passed")
