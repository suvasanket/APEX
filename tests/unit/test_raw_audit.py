"""Unit tests for cryptographic payload hashing and raw audit trail."""

import hashlib
import unittest

from apex.collectors.audit import (
    InMemoryRawPayloadStore,
    compute_raw_hash,
    create_raw_audit,
    verify_raw_hash,
)
from apex.models.fare import RawAudit


class TestRawAudit(unittest.TestCase):
    """Test suite for payload SHA-256 provenance hashing and storage."""

    def test_compute_raw_hash_deterministic(self):
        sample = '{"airline": "6E", "flight": "6E-2054", "price": 4532}'
        expected = hashlib.sha256(sample.encode("utf-8")).hexdigest()
        digest = compute_raw_hash(sample)
        self.assertEqual(digest, expected)
        self.assertEqual(len(digest), 64)

    def test_compute_raw_hash_bytes(self):
        sample_bytes = b"Raw binary stream data 12345"
        expected = hashlib.sha256(sample_bytes).hexdigest()
        self.assertEqual(compute_raw_hash(sample_bytes), expected)

    def test_compute_raw_hash_invalid_type(self):
        with self.assertRaises(TypeError):
            compute_raw_hash(12345)  # type: ignore

    def test_verify_raw_hash_valid_and_tampered(self):
        sample = '{"status": "CONFIRMED", "seats": 5}'
        valid_hash = hashlib.sha256(sample.encode("utf-8")).hexdigest()

        # Valid match
        self.assertTrue(verify_raw_hash(sample, valid_hash))
        self.assertTrue(verify_raw_hash(sample, valid_hash.upper()))

        # Tampered payload (1 character difference)
        tampered_sample = '{"status": "CONFIRMED", "seats": 4}'
        self.assertFalse(verify_raw_hash(tampered_sample, valid_hash))

        # Invalid hash format
        self.assertFalse(verify_raw_hash(sample, "tooshort"))
        self.assertFalse(verify_raw_hash(sample, ""))

    def test_create_raw_audit_model(self):
        payload = '{"route": "DEL-BOM", "date": "2026-09-20"}'
        audit = create_raw_audit(payload)
        self.assertIsInstance(audit, RawAudit)
        self.assertEqual(audit.raw_payload, payload)
        self.assertEqual(audit.raw_hash, compute_raw_hash(payload))

    def test_in_memory_raw_payload_store(self):
        store = InMemoryRawPayloadStore()
        payload1 = '{"flight": "6E-2054"}'
        payload2 = '{"flight": "6E-5128"}'

        h1 = store.put(payload1)
        h2 = store.put(payload2)

        self.assertEqual(store.count(), 2)
        self.assertTrue(store.contains(h1))
        self.assertTrue(store.contains(h2))
        self.assertFalse(store.contains("nonexistenthash" * 4))

        self.assertEqual(store.get(h1), payload1)
        self.assertEqual(store.get(h2), payload2)
        self.assertTrue(store.verify_integrity(h1))
        self.assertTrue(store.verify_integrity(h2))


if __name__ == "__main__":
    unittest.main()
