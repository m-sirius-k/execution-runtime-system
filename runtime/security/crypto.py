from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

PRIVATE_KEY_PATH = Path(__file__).parent / "keypair.pem"
PUBLIC_KEY_PATH = Path(__file__).parent / "keypair.pub"


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def _write_keypair(private_key: Ed25519PrivateKey) -> None:
    PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PUBLIC_KEY_PATH.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def _load_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PATH.read_bytes(), password=None
    )
    return private_key, private_key.public_key()


def load_or_create_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Loads the persisted signing keypair, generating it only on first run.

    Once keypair.pem exists it is never regenerated — the trust root for all
    previously issued tokens depends on this key staying fixed.
    """
    if PRIVATE_KEY_PATH.exists():
        return _load_keypair()
    private_key, public_key = generate_keypair()
    _write_keypair(private_key)
    return private_key, public_key


def sign(private_key: Ed25519PrivateKey, payload_hash_hex: str) -> bytes:
    return private_key.sign(bytes.fromhex(payload_hash_hex))


def verify(public_key: Ed25519PublicKey, signature: bytes, payload_hash_hex: str) -> bool:
    try:
        public_key.verify(signature, bytes.fromhex(payload_hash_hex))
        return True
    except InvalidSignature:
        return False
