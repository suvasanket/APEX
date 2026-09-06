"""Unit tests for AirIndiaExpressResponseParser and AirIndiaExpressCollector."""

import asyncio
from datetime import date
import json
from pathlib import Path
import unittest

from apex.collectors.airindia_express import (
    AirIndiaExpressCollector,
    AirIndiaExpressResponseParser,
)
from apex.models.fare import BookingWindow, FareObservation

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "observations"
    / "airindia_express_response_sample.json"
)


class TestAirIndiaExpressParser(unittest.TestCase):
    """Test suite for Air India Express response parser and collector."""

    def setUp(self):
        self.parser = AirIndiaExpressResponseParser(non_stop_only=True)
        with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
            self.sample_payload = f.read()

    def test_normalize_flight_number(self):
        self.assertEqual(AirIndiaExpressResponseParser.normalize_flight_number("IX-1422"), "IX-1422")
        self.assertEqual(AirIndiaExpressResponseParser.normalize_flight_number("IX1422"), "IX-1422")
        self.assertEqual(AirIndiaExpressResponseParser.normalize_flight_number("1422"), "IX-1422")
        self.assertEqual(AirIndiaExpressResponseParser.normalize_flight_number("  ix-301 "), "IX-301")

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
        self.assertIn("IX-1422", flight_numbers)
        self.assertIn("IX-1488", flight_numbers)

        for obs in observations:
            self.assertIsInstance(obs, FareObservation)
            self.assertEqual(obs.flight_identity.airline_iata, "IX")
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

    def test_airindia_express_collector_execution(self):
        collector = AirIndiaExpressCollector()
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                collector.collect_route("DEL", "BOM", date(2026, 9, 20), "T+15")
            )
            self.assertGreater(len(res.observations), 0)
            self.assertEqual(res.observations[0].flight_identity.airline_iata, "IX")
            self.assertEqual(res.execution_meta["origin"], "DEL")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
