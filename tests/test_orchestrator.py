import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runtime.orchestrator.task_orchestrator import task_orchestrator


def test_normalizes_full_input():
    raw = {
        "task": "say hello",
        "context": {"env": "prod"},
        "constraints": {"max_retries": 0},
        "expected_state": "done",
    }
    assert task_orchestrator(raw) == raw


def test_fills_missing_fields_with_defaults():
    raw = {"task": "say hello"}
    result = task_orchestrator(raw)
    assert result == {
        "task": "say hello",
        "context": {},
        "constraints": {},
        "expected_state": None,
    }


def test_does_not_mutate_input():
    raw = {"task": "say hello"}
    task_orchestrator(raw)
    assert raw == {"task": "say hello"}


if __name__ == "__main__":
    test_normalizes_full_input()
    test_fills_missing_fields_with_defaults()
    test_does_not_mutate_input()
    print("all orchestrator tests passed")
