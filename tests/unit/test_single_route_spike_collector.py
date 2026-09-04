"""End-to-End Single Route DEL-BOM T+15 Spike verification test."""

import asyncio
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from apex.collectors.indigo import IndiGoCollector
from apex.models.fare import (
    BookingWindow,
    FareObservation,
    calculate_observation_target_date,
    get_window_offset,
)

SAMPLE_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "observations"
    / "indigo_response_sample.json"
)


class TestSingleRouteSpikeCollector(unittest.TestCase):
    """End-to-End verification of single route DEL->BOM at T+15."""

    def test_del_bom_t15_spike_run(self):
        # Target route DEL -> BOM at T+15
        collection_date = date(2026, 9, 4)
        travel_date = calculate_observation_target_date(collection_date, BookingWindow.T_PLUS_15)
        self.assertEqual(travel_date, date(2026, 9, 19))
        self.assertEqual(get_window_offset(BookingWindow.T_PLUS_15), 15)

        with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
            sample_payload = f.read()

        async def route_transport(origin: str, dest: str, d: date, w: str) -> str:
            self.assertEqual(origin, "DEL")
            self.assertEqual(dest, "BOM")
            self.assertEqual(d, travel_date)
            self.assertEqual(w, "T+15")
            return sample_payload

        collector = IndiGoCollector(transport=route_transport)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                collector.collect_route(
                    origin="DEL",
                    destination="BOM",
                    travel_date=travel_date,
                    window_label="T+15",
                )
            )

            # Result assertions
            self.assertGreater(len(result.observations), 0)
            self.assertEqual(len(result.raw_hash), 64)
            self.assertEqual(result.execution_meta["origin"], "DEL")
            self.assertEqual(result.execution_meta["destination"], "BOM")

            for obs in result.observations:
                # Type contract
                self.assertIsInstance(obs, FareObservation)

                # Flight identity
                self.assertEqual(obs.flight_identity.origin_iata, "DEL")
                self.assertEqual(obs.flight_identity.destination_iata, "BOM")
                self.assertEqual(obs.flight_identity.stops, 0)
                self.assertTrue(obs.flight_identity.is_nonstop)

                # Booking dimension
                self.assertEqual(obs.booking_dimension.booking_window, BookingWindow.T_PLUS_15)
                self.assertEqual(obs.booking_dimension.advance_days, 15)
                self.assertEqual(obs.booking_dimension.cabin_class, "economy")

                # Fare breakdown accounting integrity
                parts_sum = (
                    obs.fare_breakdown.base_fare
                    + obs.fare_breakdown.taxes
                    + obs.fare_breakdown.fees
                )
                self.assertEqual(obs.fare_breakdown.total_payable_fare, parts_sum)
                self.assertEqual(obs.fare_breakdown.currency, "INR")

                # Cryptographic raw provenance
                self.assertEqual(obs.raw_audit.raw_hash, result.raw_hash)

                # Valid JSON serialization conforming to schema
                dumped_json = obs.model_dump_json()
                loaded = json.loads(dumped_json)
                self.assertEqual(loaded["flight_identity"]["origin_iata"], "DEL")
                self.assertEqual(loaded["flight_identity"]["destination_iata"], "BOM")
                self.assertEqual(loaded["booking_dimension"]["booking_window"], "T+15")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
