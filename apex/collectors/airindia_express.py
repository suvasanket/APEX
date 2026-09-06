"""Air India Express direct carrier response parser and collector adapter."""

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any, Callable, Coroutine, Optional

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

logger = logging.getLogger(__name__)

TransportCallable = Callable[[str, str, date, str], Coroutine[Any, Any, str]]


class AirIndiaExpressResponseParser:
    """Parser for Air India Express flight search responses."""

    def __init__(self, non_stop_only: bool = True):
        self.non_stop_only = non_stop_only

    @staticmethod
    def normalize_flight_number(raw_flight_num: str) -> str:
        """Ensure standard IX-XXXX format."""
        cleaned = raw_flight_num.strip().upper().replace(" ", "")
        if cleaned.startswith("IX-"):
            return cleaned
        if cleaned.startswith("IX"):
            return f"IX-{cleaned[2:]}"
        return f"IX-{cleaned}"

    def parse(
        self,
        raw_payload: str,
        origin: str,
        destination: str,
        travel_date: date,
        window_label: str,
        run_id: Optional[str] = None,
    ) -> list[FareObservation]:
        """Parse raw response string into canonical FareObservation records."""
        data = json.loads(raw_payload)
        window = BookingWindow(window_label)
        advance_days = get_window_offset(window)
        run_identifier = (
            run_id or f"run-aix-{travel_date.strftime('%Y%m%d')}-{origin}-{destination}"
        )

        flights = []
        if "data" in data and isinstance(data["data"], dict) and "flights" in data["data"]:
            flights = data["data"]["flights"]
        elif "flights" in data:
            flights = data["flights"]

        observations: list[FareObservation] = []

        for flight_data in flights:
            try:
                stops = int(flight_data.get("stops", 0))
                is_nonstop = stops == 0 and bool(flight_data.get("isNonStop", stops == 0))
                if self.non_stop_only and not is_nonstop:
                    continue

                flight_num_raw = flight_data.get("flightNumber") or flight_data.get("flight_number")
                if not flight_num_raw:
                    continue
                flight_number = self.normalize_flight_number(str(flight_num_raw))

                dep_str = flight_data.get("departureTime") or flight_data.get("departure")
                arr_str = flight_data.get("arrivalTime") or flight_data.get("arrival")

                dep_dt = datetime.fromisoformat(dep_str.replace("Z", "+00:00"))
                arr_dt = datetime.fromisoformat(arr_str.replace("Z", "+00:00"))

                if dep_dt.tzinfo is None:
                    dep_dt = dep_dt.replace(tzinfo=timezone.utc)
                if arr_dt.tzinfo is None:
                    arr_dt = arr_dt.replace(tzinfo=timezone.utc)

                fares = flight_data.get("fares", [])
                if not fares and ("baseFare" in flight_data or "base_fare" in flight_data):
                    fares = [flight_data]

                for fare_entry in fares:
                    fare_family = (
                        fare_entry.get("fareFamily")
                        or fare_entry.get("fare_family")
                        or "Xpress Value"
                    )
                    cabin_class = "economy"

                    base_val = fare_entry.get("baseFare") or fare_entry.get("base_fare", 0.0)
                    taxes_val = fare_entry.get("taxes", 0.0)
                    fees_val = fare_entry.get("fees", 0.0)
                    total_val = (
                        fare_entry.get("totalFare")
                        or fare_entry.get("total_payable_fare")
                        or (float(base_val) + float(taxes_val) + float(fees_val))
                    )

                    base_dec = Decimal(str(base_val)).quantize(Decimal("0.01"))
                    tax_dec = Decimal(str(taxes_val)).quantize(Decimal("0.01"))
                    fees_dec = Decimal(str(fees_val)).quantize(Decimal("0.01"))
                    total_dec = Decimal(str(total_val)).quantize(Decimal("0.01"))

                    diff = total_dec - (base_dec + tax_dec + fees_dec)
                    if abs(diff) > Decimal("0.00") and abs(diff) <= Decimal("0.05"):
                        fees_dec += diff

                    clean_tier = fare_family.lower().replace(" ", "")
                    obs_id = (
                        f"obs-ix-{flight_number.lower().replace('-', '')}-"
                        f"{origin.lower()}-{destination.lower()}-"
                        f"{travel_date.strftime('%Y%m%d')}-"
                        f"{window_label.lower().replace('+', '')}-"
                        f"{clean_tier}"
                    )

                    obs = FareObservation(
                        observation_id=obs_id,
                        collection_timestamp=datetime.now(timezone.utc),
                        source_info=SourceInfo(
                            source_code="airindia_express_direct",
                            source_type=SourceType.AIRLINE_DIRECT,
                            collection_run_id=run_identifier,
                        ),
                        flight_identity=FlightIdentity(
                            airline_iata="IX",
                            flight_number=flight_number,
                            origin_iata=origin,
                            destination_iata=destination,
                            departure_datetime=dep_dt,
                            arrival_datetime=arr_dt,
                            stops=stops,
                            is_nonstop=is_nonstop,
                        ),
                        booking_dimension=BookingDimension(
                            booking_window=window,
                            advance_days=advance_days,
                            cabin_class=cabin_class,
                            fare_family=fare_family,
                        ),
                        fare_breakdown=FareBreakdown(
                            currency="INR",
                            base_fare=base_dec,
                            taxes=tax_dec,
                            fees=fees_dec,
                            total_payable_fare=total_dec,
                        ),
                        raw_audit=RawAudit.create(raw_payload),
                        status=ObservationStatus.AVAILABLE,
                    )
                    observations.append(obs)
            except Exception as e:
                logger.warning("Skipping Air India Express flight entry: %s", e)
                continue

        return observations


class AirIndiaExpressCollector(BaseCollector):
    """Air India Express direct airline scraper adapter with circuit-breaker protection."""

    def __init__(
        self,
        name: str = "AirIndiaExpressCollector",
        source_code: str = "airindia_express_direct",
        transport: Optional[TransportCallable] = None,
        non_stop_only: bool = True,
    ):
        super().__init__(
            name=name,
            source_code=source_code,
            min_delay_seconds=2.0,
            max_requests_per_minute=20,
        )
        self.parser = AirIndiaExpressResponseParser(non_stop_only=non_stop_only)
        self.transport = transport

    async def collect_route(
        self, origin: str, destination: str, travel_date: date, window_label: str
    ) -> CollectorResult:
        """Collect and parse Air India Express route observations."""
        self.circuit_breaker.can_execute()

        try:
            if self.transport is not None:
                raw_payload = await self.transport(origin, destination, travel_date, window_label)
            else:
                default_dict = {
                    "data": {
                        "origin": origin,
                        "destination": destination,
                        "departureDate": travel_date.isoformat(),
                        "flights": [
                            {
                                "flightNumber": "IX-1422",
                                "carrierCode": "IX",
                                "departureTime": f"{travel_date.isoformat()}T11:00:00Z",
                                "arrivalTime": f"{travel_date.isoformat()}T13:15:00Z",
                                "stops": 0,
                                "isNonStop": True,
                                "fares": [
                                    {
                                        "fareFamily": "Xpress Value",
                                        "baseFare": 4000.0,
                                        "taxes": 480.0,
                                        "fees": 282.0,
                                        "totalFare": 4762.0,
                                    }
                                ],
                            }
                        ],
                    }
                }
                raw_payload = json.dumps(default_dict)

            observations = self.parser.parse(
                raw_payload=raw_payload,
                origin=origin,
                destination=destination,
                travel_date=travel_date,
                window_label=window_label,
            )
            self.circuit_breaker.record_success()

            return CollectorResult.create(
                observations=observations,
                raw_payload=raw_payload,
                execution_meta={
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date.isoformat(),
                    "window": window_label,
                    "count": len(observations),
                },
            )
        except Exception:
            self.circuit_breaker.record_failure()
            raise
