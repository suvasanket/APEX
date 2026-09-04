"""Unit tests for BaseCollector interface, CollectorResult, and CircuitBreaker."""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import time
import unittest

from apex.collectors.base import (
    BaseCollector,
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitBreakerState,
    CollectorResult,
)
from apex.models.fare import (
    BookingDimension,
    BookingWindow,
    FareBreakdown,
    FareObservation,
    FlightIdentity,
    ObservationStatus,
    RawAudit,
    SourceInfo,
    SourceType,
)


class TestCollectorBase(unittest.TestCase):
    """Test suite verifying Collector base interfaces and data structures."""

    def _create_sample_observation(self, payload: str = '{"test": 1}') -> FareObservation:
        audit = RawAudit.create(payload)
        return FareObservation(
            observation_id="OBS-TEST-001",
            collection_timestamp=datetime.now(timezone.utc),
            source_info=SourceInfo(
                source_code="test_collector",
                source_type=SourceType.AIRLINE_DIRECT,
                collection_run_id="RUN-TEST-001",
            ),
            flight_identity=FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 20, 6, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 20, 8, 15, tzinfo=timezone.utc),
                stops=0,
                is_nonstop=True,
            ),
            booking_dimension=BookingDimension(
                booking_window=BookingWindow.T_PLUS_15,
                advance_days=15,
                cabin_class="economy",
                fare_family="Saver",
            ),
            fare_breakdown=FareBreakdown(
                currency="INR",
                base_fare=Decimal("4500.00"),
                taxes=Decimal("650.00"),
                fees=Decimal("250.00"),
                total_payable_fare=Decimal("5400.00"),
            ),
            raw_audit=audit,
            status=ObservationStatus.AVAILABLE,
        )

    def test_collector_result_creation_and_hash_computation(self):
        payload = '{"flights": [{"flight": "6E-2054", "price": 5400}]}'
        obs = self._create_sample_observation(payload)

        result = CollectorResult.create(
            observations=[obs],
            raw_payload=payload,
            execution_meta={"http_status": 200, "duration_ms": 120},
        )
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.raw_payload, payload)
        self.assertEqual(len(result.raw_hash), 64)
        self.assertEqual(result.execution_meta["http_status"], 200)

    def test_collector_result_hash_mismatch_fails(self):
        payload = '{"test": true}'
        with self.assertRaises(ValueError):
            CollectorResult(
                observations=[],
                raw_payload=payload,
                raw_hash="a" * 64,  # incorrect hash
                execution_meta={},
            )

    def test_circuit_breaker_transitions(self):
        cb = CircuitBreaker(service_name="test_service", failure_threshold=3, recovery_timeout_seconds=0.1)
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)
        self.assertTrue(cb.can_execute())

        # 1st failure
        cb.record_failure()
        self.assertEqual(cb.consecutive_failures, 1)
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

        # 2nd failure
        cb.record_failure()
        self.assertEqual(cb.consecutive_failures, 2)
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

        # 3rd failure trips breaker
        cb.record_failure()
        self.assertEqual(cb.consecutive_failures, 3)
        self.assertEqual(cb.state, CircuitBreakerState.OPEN)

        # Calling can_execute raises CircuitBreakerOpenException
        with self.assertRaises(CircuitBreakerOpenException) as ctx:
            cb.can_execute()
        self.assertIn("Circuit breaker is OPEN", str(ctx.exception))

        # Sleep past recovery timeout
        time.sleep(0.12)
        self.assertEqual(cb.state, CircuitBreakerState.HALF_OPEN)
        self.assertTrue(cb.can_execute())

        # Success resets to CLOSED
        cb.record_success()
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)
        self.assertEqual(cb.consecutive_failures, 0)

    def test_circuit_breaker_sync_decorator(self):
        cb = CircuitBreaker(service_name="sync_service", failure_threshold=2, recovery_timeout_seconds=0.1)

        @cb
        def fragile_func(succeed: bool):
            if not succeed:
                raise RuntimeError("Network error")
            return "OK"

        self.assertEqual(fragile_func(True), "OK")
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

        with self.assertRaises(RuntimeError):
            fragile_func(False)
        self.assertEqual(cb.consecutive_failures, 1)

        with self.assertRaises(RuntimeError):
            fragile_func(False)
        self.assertEqual(cb.state, CircuitBreakerState.OPEN)

        # Next call blocked by breaker
        with self.assertRaises(CircuitBreakerOpenException):
            fragile_func(True)

    def test_circuit_breaker_async_decorator(self):
        cb = CircuitBreaker(service_name="async_service", failure_threshold=2, recovery_timeout_seconds=0.1)

        @cb
        async def async_fragile(succeed: bool):
            await asyncio.sleep(0.01)
            if not succeed:
                raise ConnectionResetError("Connection dropped")
            return "SUCCESS"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self.assertEqual(loop.run_until_complete(async_fragile(True)), "SUCCESS")
            with self.assertRaises(ConnectionResetError):
                loop.run_until_complete(async_fragile(False))
            with self.assertRaises(ConnectionResetError):
                loop.run_until_complete(async_fragile(False))
            self.assertEqual(cb.state, CircuitBreakerState.OPEN)
            with self.assertRaises(CircuitBreakerOpenException):
                loop.run_until_complete(async_fragile(True))
        finally:
            loop.close()

    def test_base_collector_subclass_contract(self):
        # Cannot instantiate ABC directly
        with self.assertRaises(TypeError):
            BaseCollector("Test", "test_source")  # type: ignore

        # Concrete implementation
        class ConcreteCollector(BaseCollector):
            async def collect_route(
                self, origin: str, destination: str, travel_date: date, window_label: str
            ) -> CollectorResult:
                payload = '{"status": "ok"}'
                return CollectorResult.create(
                    observations=[],
                    raw_payload=payload,
                    execution_meta={"origin": origin, "dest": destination},
                )

        collector = ConcreteCollector("TestCollector", "test_src")
        self.assertEqual(collector.name, "TestCollector")
        self.assertEqual(collector.source_code, "test_src")
        self.assertEqual(collector.circuit_breaker.state, CircuitBreakerState.CLOSED)

        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                collector.collect_route("DEL", "BOM", date(2026, 9, 20), "T+15")
            )
            self.assertEqual(res.execution_meta["origin"], "DEL")
            self.assertEqual(res.execution_meta["dest"], "BOM")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
