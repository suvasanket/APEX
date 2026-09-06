"""Unit tests for Multi-Carrier Registry."""

import unittest

from apex.collectors.airindia import AirIndiaCollector
from apex.collectors.airindia_express import AirIndiaExpressCollector
from apex.collectors.akasa import AkasaCollector
from apex.collectors.base import BaseCollector
from apex.collectors.indigo import IndiGoCollector
from apex.collectors.registry import (
    create_carrier_collector,
    get_all_carrier_collectors,
    get_carrier_metadata,
    get_supported_carriers,
    resolve_carrier_code,
)
from apex.collectors.spicejet import SpiceJetCollector


class TestCarrierRegistry(unittest.TestCase):
    """Test suite verifying domestic non-OTA carrier registry."""

    def test_get_supported_carriers(self):
        carriers = get_supported_carriers()
        self.assertEqual(len(carriers), 5)
        codes = {c.iata_code for c in carriers}
        self.assertSetEqual(codes, {"6E", "AI", "IX", "QP", "SG"})

    def test_resolve_carrier_code(self):
        self.assertEqual(resolve_carrier_code("6E"), "6E")
        self.assertEqual(resolve_carrier_code("indigo"), "6E")
        self.assertEqual(resolve_carrier_code("AI"), "AI")
        self.assertEqual(resolve_carrier_code("Air India"), "AI")
        self.assertEqual(resolve_carrier_code("IX"), "IX")
        self.assertEqual(resolve_carrier_code("Akasa"), "QP")
        self.assertEqual(resolve_carrier_code("SpiceJet"), "SG")

        with self.assertRaises(KeyError):
            resolve_carrier_code("UNKNOWN_AIRLINE")

    def test_create_carrier_collector(self):
        c_6e = create_carrier_collector("6E")
        self.assertIsInstance(c_6e, IndiGoCollector)
        self.assertEqual(c_6e.source_code, "indigo_direct")

        c_ai = create_carrier_collector("AI")
        self.assertIsInstance(c_ai, AirIndiaCollector)
        self.assertEqual(c_ai.source_code, "airindia_direct")

        c_qp = create_carrier_collector("QP")
        self.assertIsInstance(c_qp, AkasaCollector)

        c_ix = create_carrier_collector("IX")
        self.assertIsInstance(c_ix, AirIndiaExpressCollector)

        c_sg = create_carrier_collector("SG")
        self.assertIsInstance(c_sg, SpiceJetCollector)

    def test_get_all_carrier_collectors(self):
        all_collectors = get_all_carrier_collectors()
        self.assertEqual(len(all_collectors), 5)
        for code, coll in all_collectors.items():
            self.assertIsInstance(coll, BaseCollector)


if __name__ == "__main__":
    unittest.main()
