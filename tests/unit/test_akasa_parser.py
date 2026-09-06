"""Unit tests for AkasaResponseParser and AkasaCollector."""

import asyncio
from datetime import date
import json
from pathlib import Path
import unittest

from apex.collectors.akasa import AkasaCollector, AkasaResponseParser
from apex.models.fare import BookingWindow, FareObservation

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "observations"
    / "akasa_response_sample.json"
)


class TestAkasaParser(unittest.TestCase):
    """Test suite for Akasa Air response parser and collector."""

    def setUp(self):
        self.parser = AkasaResponseParser(non_stop_only=True)
        with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
            self.sample_payload = f.read()

    def test_normalize_flight_number(self):
        self.assertEqual(AkasaResponseParser.normalize_flight_number("QP-1101"), "QP-1101")
        self.assertEqual(AkasaResponseParser.normalize_flight_number("QP1101"), "QP-1101")
        self.assertEqual(AkasaResponseParser.normalize_flight_number("1101"), "QP-1101")
        self.assertEqual(AkasaResponseParser.normalize_flight_number("  qp-202 "), "QP-202")

    def test_parse_sample_fixture_success(self):
        observations = self.parser.parse(
            raw_payload=self.sample_payload,
            origin="DEL",
            destination="BOM",
            travel_date=date(2026, 9, 20),
            window_label="T+15",
        )

        self.assertEqual(len(observations), 3)
        flight_numbers = [obs.flight_identity.flight_number for obs in observations]
        self.assertIn("QP-1101", flight_numbers)
        self.assertIn("QP-1105", flight_numbers)

        for obs in observations:
            self.assertIsInstance(obs, FareObservation)
            self.assertEqual(obs.flight_identity.airline_iata, "QP")
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

    def test_akasa_collector_execution(self):
        collector = AkasaCollector()
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                collector.collect_route("DEL", "BOM", date(2026, 9, 20), "T+15")
            )
            self.assertGreater(len(res.observations), 0)
            self.assertEqual(res.observations[0].flight_identity.airline_iata, "QP")
            self.assertEqual(res.execution_meta["origin"], "DEL")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
