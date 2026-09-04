"""Cryptographic payload provenance and SHA-256 audit hashing utilities."""

import hashlib
import hmac
from typing import Optional, Union

from apex.models.fare import RawAudit


def compute_raw_hash(payload: Union[str, bytes]) -> str:
    """Compute deterministic SHA-256 hex digest for raw scraper payload.

    Payload bytes must never be mutated or trimmed prior to hashing.
    """
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        payload_bytes = payload
    else:
        raise TypeError(f"Payload must be str or bytes, got: {type(payload)}")

    return hashlib.sha256(payload_bytes).hexdigest()


def verify_raw_hash(payload: Union[str, bytes], expected_hash: str) -> bool:
    """Verify raw payload against an expected SHA-256 digest using constant-time comparison."""
    if not expected_hash or len(expected_hash) != 64:
        return False
    computed = compute_raw_hash(payload)
    return hmac.compare_digest(computed.lower(), expected_hash.lower())


def create_raw_audit(payload: str) -> RawAudit:
    """Construct a validated immutable RawAudit record."""
    return RawAudit.create(payload)


class InMemoryRawPayloadStore:
    """In-memory key-value store for raw payloads indexed by SHA-256."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def put(self, payload: str) -> str:
        """Store payload and return its SHA-256 digest."""
        digest = compute_raw_hash(payload)
        self._store[digest] = payload
        return digest

    def get(self, raw_hash: str) -> Optional[str]:
        """Retrieve payload by SHA-256 digest."""
        return self._store.get(raw_hash.lower())

    def contains(self, raw_hash: str) -> bool:
        """Check if payload exists in store."""
        return raw_hash.lower() in self._store

    def verify_integrity(self, raw_hash: str) -> bool:
        """Verify stored payload integrity matches its key hash."""
        payload = self.get(raw_hash)
        if payload is None:
            return False
        return verify_raw_hash(payload, raw_hash)

    def count(self) -> int:
        return len(self._store)
