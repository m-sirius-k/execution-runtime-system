import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runtime.gate import approval_gate
from runtime.core import divergence, execution_core
from runtime.security import crypto
from runtime.spec.task_spec import TaskSpec, TaskSpecRejected
from runtime.storage import db


def setup_module(_module):
    db.DB_PATH = type(db.DB_PATH)(tempfile.mkstemp(suffix=".db")[1])
    db.init_db()


def _spec(**overrides):
    base = dict(
        spec_id="spec-1",
        issued_by="human-1",
        issued_at=datetime.now(timezone.utc).isoformat(),
        intent="noop",
        params={},
    )
    base.update(overrides)
    return TaskSpec(**base)


def test_forbidden_key_rejected():
    spec = _spec(params={"decision": "do_it"})
    try:
        spec.validate()
        assert False, "expected rejection"
    except TaskSpecRejected:
        pass


def test_mocka_reference_rejected():
    spec = _spec(intent="reference MoCKA archive")
    try:
        spec.validate()
        assert False, "expected rejection"
    except TaskSpecRejected:
        pass


def test_unconfirmed_human_event_rejected():
    spec = _spec(spec_id="spec-2")
    db.insert_task_spec(spec)
    private_key, _ = crypto.generate_keypair()
    event = approval_gate.HumanConfirmationEvent(confirmed=False, human_identity="human-1")
    try:
        approval_gate.approve(spec, event, private_key)
        assert False, "expected rejection"
    except approval_gate.ApprovalRejected:
        pass


def test_full_path_single_use_token():
    spec = _spec(spec_id="spec-3")
    db.insert_task_spec(spec)
    private_key, public_key = crypto.generate_keypair()
    event = approval_gate.HumanConfirmationEvent(confirmed=True, human_identity="human-1")
    token = approval_gate.approve(spec, event, private_key)

    result = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    assert result["status"] == "success"

    replay = execution_core.execute(spec, token["token_id"], public_key, lambda i, p: "ok")
    assert replay["status"] == "REJECTED"


def test_keypair_persistence_no_regeneration():
    tmp_dir = tempfile.mkdtemp()
    crypto.PRIVATE_KEY_PATH = type(crypto.PRIVATE_KEY_PATH)(tmp_dir) / "keypair.pem"
    crypto.PUBLIC_KEY_PATH = type(crypto.PUBLIC_KEY_PATH)(tmp_dir) / "keypair.pub"

    private_key_1, _ = crypto.load_or_create_keypair()
    bytes_1 = crypto.PRIVATE_KEY_PATH.read_bytes()

    private_key_2, _ = crypto.load_or_create_keypair()
    bytes_2 = crypto.PRIVATE_KEY_PATH.read_bytes()

    assert bytes_1 == bytes_2, "keypair was regenerated on second load"


def test_divergence_ok():
    assert divergence.detect_divergence(
        {"task": "say hello", "expected_state": None},
        {"task": "say hello", "final_state": {"x": 1}, "warnings": None},
    ) == "OK"


def test_divergence_critical_task_mismatch():
    assert divergence.detect_divergence(
        {"task": "say hello", "expected_state": None},
        {"task": "say goodbye", "final_state": None, "warnings": None},
    ) == "CRITICAL"


def test_divergence_high_state_mismatch():
    assert divergence.detect_divergence(
        {"task": "say hello", "expected_state": "done"},
        {"task": "say hello", "final_state": "partial", "warnings": None},
    ) == "HIGH"


def test_divergence_medium_warnings():
    assert divergence.detect_divergence(
        {"task": "say hello", "expected_state": None},
        {"task": "say hello", "final_state": "done", "warnings": ["slow"]},
    ) == "MEDIUM"


if __name__ == "__main__":
    setup_module(None)
    test_forbidden_key_rejected()
    test_mocka_reference_rejected()
    test_unconfirmed_human_event_rejected()
    test_full_path_single_use_token()
    test_keypair_persistence_no_regeneration()
    test_divergence_ok()
    test_divergence_critical_task_mismatch()
    test_divergence_high_state_mismatch()
    test_divergence_medium_warnings()
    print("all tests passed")
