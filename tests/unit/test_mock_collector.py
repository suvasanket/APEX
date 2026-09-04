"""Unit tests for MockCollector offline generation and fixture simulation."""

import asyncio
from datetime import date
from decimal import Decimal
import unittest

from apex.collectors.base import CircuitBreakerState
from apex.collectors.mock import MockCollector
from apex.models.fare import BookingWindow, FareObservation


class TestMockCollector(unittest.TestCase):
    """Test suite for MockCollector offline pipeline validation."""

    def setUp(self):
        self.collector = MockCollector()

    def test_collect_route_del_bom_t15(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self.collector.collect_route(
                    origin="DEL",
                    destination="BOM",
                    travel_date=date(2026, 9, 20),
                    window_label="T+15",
                )
            )
            self.assertEqual(len(result.observations), 3)
            self.assertEqual(result.execution_meta["origin"], "DEL")
            self.assertEqual(result.execution_meta["destination"], "BOM")

            for obs in result.observations:
                self.assertIsInstance(obs, FareObservation)
                self.assertEqual(obs.flight_identity.origin_iata, "DEL")
                self.assertEqual(obs.flight_identity.destination_iata, "BOM")
                self.assertTrue(obs.flight_identity.is_nonstop)
                self.assertEqual(obs.booking_dimension.booking_window, BookingWindow.T_PLUS_15)
                self.assertEqual(obs.booking_dimension.advance_days, 15)
                self.assertEqual(obs.fare_breakdown.currency, "INR")

                # Accounting invariant
                expected_total = (
                    obs.fare_breakdown.base_fare
                    + obs.fare_breakdown.taxes
                    + obs.fare_breakdown.fees
                )
                self.assertEqual(obs.fare_breakdown.total_payable_fare, expected_total)
        finally:
            loop.close()

    def test_all_five_booking_windows(self):
        loop = asyncio.new_event_loop()
        windows = ["T+1", "T+7", "T+15", "T+30", "T+45"]
        try:
            for w in windows:
                result = loop.run_until_complete(
                    self.collector.collect_route(
                        origin="BLR",
                        destination="DEL",
                        travel_date=date(2026, 9, 25),
                        window_label=w,
                    )
                )
                self.assertGreater(len(result.observations), 0)
                for obs in result.observations:
                    self.assertEqual(obs.booking_dimension.booking_window.value, w)
        finally:
            loop.close()

    def test_simulate_empty_flag(self):
        empty_collector = MockCollector(simulate_empty=True)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                empty_collector.collect_route(
                    origin="DEL",
                    destination="CCU",
                    travel_date=date(2026, 9, 20),
                    window_label="T+7",
                )
            )
            self.assertEqual(len(result.observations), 0)
            self.assertTrue(result.execution_meta["empty"])
        finally:
            loop.close()

    def test_simulate_failure_trips_circuit_breaker(self):
        fail_collector = MockCollector(simulate_failure=True)
        fail_collector.circuit_breaker.failure_threshold = 2
        loop = asyncio.new_event_loop()
        try:
            with self.assertRaises(ConnectionError):
                loop.run_until_complete(
                    fail_collector.collect_route(
                        origin="BOM",
                        destination="BLR",
                        travel_date=date(2026, 9, 20),
                        window_label="T+1",
                    )
                )
            self.assertEqual(fail_collector.circuit_breaker.consecutive_failures, 1)

            with self.assertRaises(ConnectionError):
                loop.run_until_complete(
                    fail_collector.collect_route(
                        origin="BOM",
                        destination="BLR",
                        travel_date=date(2026, 9, 20),
                        window_label="T+1",
                    )
                )
            self.assertEqual(fail_collector.circuit_breaker.state, CircuitBreakerState.OPEN)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
