"""Unit tests for IndiGoResponseParser and IndiGoCollector adapter."""

import asyncio
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import unittest

from apex.collectors.indigo import IndiGoCollector, IndiGoResponseParser
from apex.models.fare import BookingWindow, FareObservation

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "observations"
    / "indigo_response_sample.json"
)


class TestIndiGoParser(unittest.TestCase):
    """Test suite for IndiGo response parser and collector."""

    def setUp(self):
        self.parser = IndiGoResponseParser(non_stop_only=True)
        with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
            self.sample_payload = f.read()

    def test_normalize_flight_number(self):
        self.assertEqual(IndiGoResponseParser.normalize_flight_number("6E-2054"), "6E-2054")
        self.assertEqual(IndiGoResponseParser.normalize_flight_number("6E2054"), "6E-2054")
        self.assertEqual(IndiGoResponseParser.normalize_flight_number("2054"), "6E-2054")
        self.assertEqual(IndiGoResponseParser.normalize_flight_number("  6e-101 "), "6E-101")

    def test_parse_sample_fixture_success(self):
        travel_date = date(2026, 9, 19)
        observations = self.parser.parse(
            raw_payload=self.sample_payload,
            origin="DEL",
            destination="BOM",
            travel_date=travel_date,
            window_label="T+15",
        )

        # In sample: 6E-2054 has 2 fares (Saver, FlexiPlus), 6E-5128 has 1 fare (Saver).
        # 6E-301 has 1 stop, so it must be filtered out when non_stop_only=True.
        self.assertEqual(len(observations), 3)

        flight_numbers = [obs.flight_identity.flight_number for obs in observations]
        self.assertIn("6E-2054", flight_numbers)
        self.assertIn("6E-5128", flight_numbers)
        self.assertNotIn("6E-301", flight_numbers)

        for obs in observations:
            self.assertIsInstance(obs, FareObservation)
            self.assertEqual(obs.flight_identity.origin_iata, "DEL")
            self.assertEqual(obs.flight_identity.destination_iata, "BOM")
            self.assertEqual(obs.flight_identity.stops, 0)
            self.assertTrue(obs.flight_identity.is_nonstop)
            self.assertEqual(obs.booking_dimension.booking_window, BookingWindow.T_PLUS_15)
            self.assertEqual(obs.booking_dimension.advance_days, 15)
            self.assertEqual(obs.booking_dimension.cabin_class, "economy")
            self.assertEqual(obs.fare_breakdown.currency, "INR")

            # Mathematical accounting integrity
            sum_parts = (
                obs.fare_breakdown.base_fare
                + obs.fare_breakdown.taxes
                + obs.fare_breakdown.fees
            )
            self.assertEqual(obs.fare_breakdown.total_payable_fare, sum_parts)

            # Cryptographic raw hash integrity
            self.assertEqual(len(obs.raw_audit.raw_hash), 64)

    def test_parse_with_stops_allowed(self):
        lenient_parser = IndiGoResponseParser(non_stop_only=False)
        observations = lenient_parser.parse(
            raw_payload=self.sample_payload,
            origin="DEL",
            destination="BOM",
            travel_date=date(2026, 9, 19),
            window_label="T+15",
        )
        # Should now include 6E-301 (1 stop)
        self.assertEqual(len(observations), 4)
        flight_numbers = [obs.flight_identity.flight_number for obs in observations]
        self.assertIn("6E-301", flight_numbers)

    def test_parse_malformed_json_raises_error(self):
        with self.assertRaises(json.JSONDecodeError):
            self.parser.parse(
                raw_payload="NOT_JSON",
                origin="DEL",
                destination="BOM",
                travel_date=date(2026, 9, 19),
                window_label="T+15",
            )

    def test_indigo_collector_with_mock_transport(self):
        async def mock_transport(origin: str, dest: str, d: date, w: str) -> str:
            return self.sample_payload

        collector = IndiGoCollector(transport=mock_transport)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                collector.collect_route("DEL", "BOM", date(2026, 9, 19), "T+15")
            )
            self.assertEqual(len(result.observations), 3)
            self.assertEqual(result.execution_meta["origin"], "DEL")
            self.assertEqual(result.execution_meta["destination"], "BOM")
            self.assertEqual(result.raw_hash, result.observations[0].raw_audit.raw_hash)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
