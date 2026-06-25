# Execution Runtime System v1.0

Closed-loop governance system finalized. No further structural modifications.

## Overview
Execution Runtime System is a deterministic execution framework that enforces:
- Human-only approval initiation
- Immutable Task Specification
- Single-use execution tokens
- Fully isolated execution core

MoCKA is explicitly excluded and has no dependency or reference.

---

## Architecture

Human → Task Spec → Approval Gate → Execution Core → Output Layer

---

## Core Principles

- No automatic approval
- No decision logic inside Task Spec
- No re-evaluation in Execution Core
- Single-use execution tokens only
- Append-only audit logs

---

## Tech Stack

- Python 3.11+
- FastAPI
- SQLite
- SHA-256
- Ed25519

---

## Security Model

- Token replay prevention (single-use enforcement)
- Signature-based approval binding
- Immutable audit logs (DB-level enforcement)

---

## API Endpoints

- POST /task-spec
- POST /approve
- POST /execute

---

## Running

```
pip install -r requirements.txt
uvicorn runtime.api.main:app --reload --port 8000
```

Tests:

```
python tests/test_runtime.py
python tests/test_e2e.py
```

---

## Status

v1.0-runtime-final
FULLY IMPLEMENTED AND VERIFIED

---

## License

MIT — see [LICENSE](LICENSE)
