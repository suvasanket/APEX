"""Unit tests for RouteBasketOrchestrator."""

import asyncio
from datetime import date
import unittest

from apex.collectors.mock import MockCollector
from apex.collectors.orchestrator import (
    CollectionTask,
    RouteBasketOrchestrator,
    RouteDefinition,
)


class TestRouteBasketOrchestrator(unittest.TestCase):
    """Test suite for RouteBasketOrchestrator matrix execution."""

    def setUp(self):
        self.mock_collector = MockCollector()
        self.orchestrator = RouteBasketOrchestrator(collector=self.mock_collector)

    def test_load_routes_and_windows(self):
        routes = self.orchestrator.routes
        self.assertEqual(len(routes), 5)
        total_weight = sum(r.weight for r in routes)
        self.assertAlmostEqual(total_weight, 1.0, places=5)

        windows = self.orchestrator.windows
        self.assertEqual(len(windows), 5)
        window_ids = [w.window_id for w in windows]
        self.assertListEqual(window_ids, ["T+1", "T+7", "T+15", "T+30", "T+45"])

    def test_get_route_and_window(self):
        route = self.orchestrator.get_route("del-bom")
        self.assertEqual(route.origin_iata, "DEL")
        self.assertEqual(route.destination_iata, "BOM")

        with self.assertRaises(KeyError):
            self.orchestrator.get_route("UNKNOWN-ROUTE")

        window = self.orchestrator.get_window("T+15")
        self.assertEqual(window.offset_days, 15)

        with self.assertRaises(KeyError):
            self.orchestrator.get_window("T+999")

    def test_generate_full_matrix(self):
        base_date = date(2026, 9, 5)
        tasks = self.orchestrator.generate_matrix(collection_date=base_date)
        # 5 routes x 5 booking windows = 25 collection tasks
        self.assertEqual(len(tasks), 25)

        # Check target date offsets
        del_bom_t15 = [
            t for t in tasks if t.route.route_id == "DEL-BOM" and t.window.window_id == "T+15"
        ][0]
        self.assertEqual(del_bom_t15.target_date, date(2026, 9, 20))
        self.assertEqual(del_bom_t15.task_id, "DEL-BOM_T+15_20260920")

    def test_generate_filtered_matrix(self):
        tasks = self.orchestrator.generate_matrix(
            route_ids=["DEL-BOM", "BLR-HYD"],
            window_ids=["T+1", "T+7"],
        )
        self.assertEqual(len(tasks), 4)

    def test_execute_task_with_mock_collector(self):
        task = self.orchestrator.generate_matrix(
            route_ids=["DEL-BOM"],
            window_ids=["T+15"],
            collection_date=date(2026, 9, 5),
        )[0]

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.orchestrator.execute_task(task))
            self.assertEqual(len(result.observations), 3)
            self.assertEqual(result.execution_meta["origin"], "DEL")
            self.assertEqual(result.execution_meta["destination"], "BOM")
            self.assertEqual(result.execution_meta["window"], "T+15")
        finally:
            loop.close()

    def test_execute_matrix_with_mock_collector(self):
        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(
                self.orchestrator.execute_matrix(
                    route_ids=["DEL-BOM", "BOM-BLR"],
                    window_ids=["T+1", "T+7"],
                    collection_date=date(2026, 9, 5),
                )
            )
            self.assertEqual(len(results), 4)
            for res in results:
                self.assertGreater(len(res.observations), 0)
                self.assertEqual(len(res.raw_hash), 64)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
