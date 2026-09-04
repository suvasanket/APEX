"""Offline-first Mock Collector emitting synthetic FareObservation objects from recorded fixtures."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Optional
import uuid

from apex.collectors.base import BaseCollector, CollectorResult
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
    get_window_offset,
)

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "tests"
    / "fixtures"
    / "observations"
    / "valid_fare.json"
)


class MockCollector(BaseCollector):
    """Mock collector generating valid FareObservations offline without live network access."""

    def __init__(
        self,
        name: str = "MockCollector",
        source_code: str = "mock_direct",
        fixture_path: Optional[Path | str] = None,
        simulate_failure: bool = False,
        simulate_empty: bool = False,
    ):
        super().__init__(
            name=name,
            source_code=source_code,
            min_delay_seconds=0.0,
            max_requests_per_minute=1000,
        )
        self.fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE_PATH
        self.simulate_failure = simulate_failure
        self.simulate_empty = simulate_empty

    def _generate_synthetic_flight(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        window_label: str,
        flight_idx: int = 1,
    ) -> tuple[FareObservation, dict[str, Any]]:
        """Generate a single deterministic FareObservation and its raw dictionary."""
        window = BookingWindow(window_label)
        advance_days = get_window_offset(window)
        flight_number = f"6E-{2000 + flight_idx}"

        # Standard schedule: departure at 06:00 + idx*3 hours, duration 2h15m
        dep_time = time(hour=min(23, 6 + (flight_idx - 1) * 3), minute=0)
        dep_dt = datetime.combine(travel_date, dep_time).replace(tzinfo=timezone.utc)
        arr_dt = dep_dt + timedelta(hours=2, minutes=15)

        # Realistic fare components scaled by window
        # Closer to departure = higher fare
        base_multiplier = Decimal(str(max(1.0, 3.5 - (advance_days * 0.05))))
        base_fare = (Decimal("3000.00") * base_multiplier).quantize(Decimal("0.01"))
        taxes = (base_fare * Decimal("0.12")).quantize(Decimal("0.01"))  # 12% GST/fees
        fees = Decimal("282.00")
        total_fare = (base_fare + taxes + fees).quantize(Decimal("0.01"))

        raw_dict = {
            "flight_number": flight_number,
            "origin": origin,
            "destination": destination,
            "departure": dep_dt.isoformat(),
            "arrival": arr_dt.isoformat(),
            "fare_family": "Saver",
            "base_fare": float(base_fare),
            "taxes": float(taxes),
            "fees": float(fees),
            "total_payable_fare": float(total_fare),
        }
        raw_payload = json.dumps(raw_dict, sort_keys=True)
        raw_audit = RawAudit.create(raw_payload)

        run_id = f"run-mock-{travel_date.strftime('%Y%m%d')}-{window_label}"
        obs_id = f"obs-{flight_number.lower()}-{origin.lower()}-{destination.lower()}-{travel_date.strftime('%Y%m%d')}-{window_label.lower().replace('+', '')}"

        obs = FareObservation(
            observation_id=obs_id,
            collection_timestamp=datetime.now(timezone.utc),
            source_info=SourceInfo(
                source_code=self.source_code,
                source_type=SourceType.AIRLINE_DIRECT,
                collection_run_id=run_id,
            ),
            flight_identity=FlightIdentity(
                airline_iata="6E",
                flight_number=flight_number,
                origin_iata=origin,
                destination_iata=destination,
                departure_datetime=dep_dt,
                arrival_datetime=arr_dt,
                stops=0,
                is_nonstop=True,
            ),
            booking_dimension=BookingDimension(
                booking_window=window,
                advance_days=advance_days,
                cabin_class="economy",
                fare_family="Saver",
            ),
            fare_breakdown=FareBreakdown(
                currency="INR",
                base_fare=base_fare,
                taxes=taxes,
                fees=fees,
                total_payable_fare=total_fare,
            ),
            raw_audit=raw_audit,
            status=ObservationStatus.AVAILABLE,
        )
        return obs, raw_dict

    async def collect_route(
        self, origin: str, destination: str, travel_date: date, window_label: str
    ) -> CollectorResult:
        """Emulate collecting observations for origin-destination pair."""
        self.circuit_breaker.can_execute()

        if self.simulate_failure:
            self.circuit_breaker.record_failure()
            raise ConnectionError(f"Simulated network timeout for {origin}->{destination}")

        if self.simulate_empty:
            self.circuit_breaker.record_success()
            empty_payload = json.dumps({"flights": []})
            return CollectorResult.create(
                observations=[],
                raw_payload=empty_payload,
                execution_meta={
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date.isoformat(),
                    "window": window_label,
                    "mock": True,
                    "empty": True,
                },
            )

        # Generate 3 non-stop flights across the day
        observations = []
        raw_flights = []
        for idx in range(1, 4):
            obs, raw_dict = self._generate_synthetic_flight(
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                window_label=window_label,
                flight_idx=idx,
            )
            observations.append(obs)
            raw_flights.append(raw_dict)

        full_payload = json.dumps(
            {
                "origin": origin,
                "destination": destination,
                "date": travel_date.isoformat(),
                "window": window_label,
                "flights": raw_flights,
            },
            sort_keys=True,
        )

        self.circuit_breaker.record_success()
        return CollectorResult.create(
            observations=observations,
            raw_payload=full_payload,
            execution_meta={
                "origin": origin,
                "destination": destination,
                "travel_date": travel_date.isoformat(),
                "window": window_label,
                "mock": True,
                "count": len(observations),
            },
        )
