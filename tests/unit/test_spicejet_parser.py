"""Unit tests for SpiceJetResponseParser and SpiceJetCollector."""

import asyncio
from datetime import date
import json
from pathlib import Path
import unittest

from apex.collectors.spicejet import SpiceJetCollector, SpiceJetResponseParser
from apex.models.fare import BookingWindow, FareObservation

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "observations"
    / "spicejet_response_sample.json"
)


class TestSpiceJetParser(unittest.TestCase):
    """Test suite for SpiceJet response parser and collector."""

    def setUp(self):
        self.parser = SpiceJetResponseParser(non_stop_only=True)
        with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
            self.sample_payload = f.read()

    def test_normalize_flight_number(self):
        self.assertEqual(SpiceJetResponseParser.normalize_flight_number("SG-8169"), "SG-8169")
        self.assertEqual(SpiceJetResponseParser.normalize_flight_number("SG8169"), "SG-8169")
        self.assertEqual(SpiceJetResponseParser.normalize_flight_number("8169"), "SG-8169")
        self.assertEqual(SpiceJetResponseParser.normalize_flight_number("  sg-404 "), "SG-404")

    def test_parse_sample_fixture_success(self):
        observations = self.parser.parse(
            raw_payload=self.sample_payload,
            origin="DEL",
            destination="BOM",
            travel_date=date(2026, 9, 20),
            window_label="T+15",
        )

        self.assertEqual(len(observations), 2)
        flight_numbers = [obs.flight_identity.flight_number for obs in observations]
        self.assertIn("SG-8169", flight_numbers)
        self.assertIn("SG-8709", flight_numbers)

        for obs in observations:
            self.assertIsInstance(obs, FareObservation)
            self.assertEqual(obs.flight_identity.airline_iata, "SG")
            self.assertEqual(obs.flight_identity.origin_iata, "DEL")
            self.assertEqual(obs.flight_identity.destination_iata, "BOM")
            self.assertEqual(obs.flight_identity.stops, 0)
            self.assertTrue(obs.flight_identity.is_nonstop)
            self.assertEqual(obs.booking_dimension.booking_window, BookingWindow.T_PLUS_15)
            self.assertEqual(obs.booking_dimension.cabin_class, "economy")
            self.assertEqual(obs.fare_breakdown.currency, "INR")

            # Mathematical accounting invariant
            computed_total = (
                obs.fare_breakdown.base_fare
                + obs.fare_breakdown.taxes
                + obs.fare_breakdown.fees
            )
            self.assertEqual(obs.fare_breakdown.total_payable_fare, computed_total)
            self.assertEqual(len(obs.raw_audit.raw_hash), 64)

    def test_spicejet_collector_execution(self):
        collector = SpiceJetCollector()
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                collector.collect_route("DEL", "BOM", date(2026, 9, 20), "T+15")
            )
            self.assertGreater(len(res.observations), 0)
            self.assertEqual(res.observations[0].flight_identity.airline_iata, "SG")
            self.assertEqual(res.execution_meta["origin"], "DEL")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
