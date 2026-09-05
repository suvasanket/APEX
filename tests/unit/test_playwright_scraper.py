"""Unit tests for PlaywrightIndiGoCollector."""

import asyncio
from datetime import date
import unittest
from unittest.mock import AsyncMock, patch

from apex.collectors.base import BaseCollector, CircuitBreakerState
from apex.collectors.playwright_scraper import PlaywrightIndiGoCollector


class TestPlaywrightScraper(unittest.TestCase):
    """Test suite for PlaywrightIndiGoCollector interface and heuristics."""

    def setUp(self):
        self.collector = PlaywrightIndiGoCollector(headless=True)

    def test_collector_hierarchy(self):
        self.assertIsInstance(self.collector, BaseCollector)
        self.assertEqual(self.collector.name, "PlaywrightIndiGoCollector")
        self.assertEqual(self.collector.source_code, "indigo_direct")

    def test_heuristic_flight_search_response(self):
        # Valid cases
        self.assertTrue(
            PlaywrightIndiGoCollector._is_flight_search_response(
                "https://www.goindigo.in/flightSearch/search", "application/json"
            )
        )
        self.assertTrue(
            PlaywrightIndiGoCollector._is_flight_search_response(
                "https://www.goindigo.in/booking/availability", "application/json;charset=utf-8"
            )
        )

        # Invalid cases
        self.assertFalse(
            PlaywrightIndiGoCollector._is_flight_search_response(
                "https://www.goindigo.in/static/js/main.js", "application/javascript"
            )
        )
        self.assertFalse(
            PlaywrightIndiGoCollector._is_flight_search_response(
                "https://www.goindigo.in/home.html", "text/html"
            )
        )

    def test_mocked_live_search_success(self):
        sample_json = '{"data": {"journeys": [{"flights": [{"flightNumber": "6E-2054", "departureTime": "2026-09-20T06:00:00Z", "arrivalTime": "2026-09-20T08:15:00Z", "stops": 0, "isNonStop": true, "fares": [{"fareFamily": "Saver", "baseFare": 3800, "taxes": 450, "fees": 282, "totalFare": 4532}]}]}]}}'

        with patch.object(
            self.collector,
            "_intercept_live_search",
            new_callable=AsyncMock,
        ) as mock_intercept:
            obs = self.collector.parser.parse(
                sample_json, "DEL", "BOM", date(2026, 9, 20), "T+15"
            )
            mock_intercept.return_value = (sample_json, obs)

            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(
                    self.collector.collect_route("DEL", "BOM", date(2026, 9, 20), "T+15")
                )
                self.assertEqual(len(res.observations), 1)
                self.assertEqual(res.observations[0].flight_identity.flight_number, "6E-2054")
                self.assertEqual(self.collector.circuit_breaker.state, CircuitBreakerState.CLOSED)
            finally:
                loop.close()


if __name__ == "__main__":
    unittest.main()
