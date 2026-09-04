"""Canonical FareObservation data contract for APEX."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class BookingWindow(str, Enum):
    """Standard 5 booking windows for domestic observation."""

    T_PLUS_1 = "T+1"
    T_PLUS_7 = "T+7"
    T_PLUS_15 = "T+15"
    T_PLUS_30 = "T+30"
    T_PLUS_45 = "T+45"


class ObservationStatus(str, Enum):
    """Observation availability status."""

    AVAILABLE = "AVAILABLE"
    SOLD_OUT = "SOLD_OUT"
    UNAVAILABLE = "UNAVAILABLE"


class SourceType(str, Enum):
    """Type of collection source."""

    AIRLINE_DIRECT = "airline_direct"
    OTA = "ota"


class ImmutableBase(BaseModel):
    """Base model enforcing immutability and strict serialization."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class SourceInfo(ImmutableBase):
    """Collection source provenance."""

    source_code: str = Field(
        ...,
        description="Scraper/collector source identifier (e.g. indigo_direct)",
        min_length=1,
    )
    source_type: SourceType = Field(
        ...,
        description="Source category: airline_direct or ota",
    )
    collection_run_id: str = Field(
        ...,
        description="UUID/identifier of the execution run",
        min_length=1,
    )


class FlightIdentity(ImmutableBase):
    """Immutable physical flight identity."""

    airline_iata: str = Field(
        ...,
        description="2-character IATA airline code (e.g. 6E, AI, QP, SG)",
        pattern=r"^[A-Z0-9]{2}$",
    )
    flight_number: str = Field(
        ...,
        description="Flight number code (e.g. 6E-2054, AI-102)",
        min_length=3,
        max_length=10,
    )
    origin_iata: str = Field(
        ...,
        description="3-letter IATA origin airport code (e.g. DEL)",
        pattern=r"^[A-Z]{3}$",
    )
    destination_iata: str = Field(
        ...,
        description="3-letter IATA destination airport code (e.g. BOM)",
        pattern=r"^[A-Z]{3}$",
    )
    departure_datetime: datetime = Field(
        ...,
        description="Scheduled departure timestamp in UTC",
    )
    arrival_datetime: datetime = Field(
        ...,
        description="Scheduled arrival timestamp in UTC",
    )
    stops: int = Field(
        default=0,
        ge=0,
        description="Number of intermediate stops (0 for non-stop)",
    )
    is_nonstop: bool = Field(
        default=True,
        description="Flag indicating non-stop service",
    )

    @model_validator(mode="after")
    def validate_flight_route_and_times(self) -> "FlightIdentity":
        if self.origin_iata == self.destination_iata:
            raise ValueError(
                f"Origin and destination cannot be identical: {self.origin_iata}"
            )
        if self.departure_datetime >= self.arrival_datetime:
            raise ValueError(
                f"Departure time ({self.departure_datetime.isoformat()}) must be strictly "
                f"before arrival time ({self.arrival_datetime.isoformat()})"
            )
        expected_nonstop = self.stops == 0
        if self.is_nonstop != expected_nonstop:
            raise ValueError(
                f"Inconsistent is_nonstop ({self.is_nonstop}) with stops count ({self.stops})"
            )
        return self


class BookingDimension(ImmutableBase):
    """Booking advance and cabin dimensions."""

    booking_window: BookingWindow = Field(
        ...,
        description="Observation lead-time window (T+1, T+7, T+15, T+30, T+45)",
    )
    advance_days: int = Field(
        ...,
        ge=0,
        description="Exact number of days prior to departure",
    )
    cabin_class: Literal["economy"] = Field(
        default="economy",
        description="Cabin class, strictly 'economy' for V1 index standard",
    )
    fare_family: str = Field(
        ...,
        description="Airline fare tier name (e.g. Saver, Standard, Flexi)",
        min_length=1,
    )

    @field_validator("cabin_class", mode="before")
    @classmethod
    def normalize_cabin_class(cls, v: str) -> str:
        if isinstance(v, str) and v.lower() == "economy":
            return "economy"
        raise ValueError("Cabin class must be 'economy'")


class FareBreakdown(ImmutableBase):
    """Breakdown of fare components in INR."""

    currency: Literal["INR"] = Field(
        default="INR",
        description="Monetary currency code, strictly 'INR'",
    )
    base_fare: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Base airline passenger fare (>= 0)",
    )
    taxes: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Government, GST, and security taxes (>= 0)",
    )
    fees: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Airport development, user fees, and surcharges (>= 0)",
    )
    total_payable_fare: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Total all-in customer payable fare (base_fare + taxes + fees)",
    )

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v != "INR":
            raise ValueError(f"Currency must be 'INR', got: {v}")
        return "INR"

    @model_validator(mode="after")
    def validate_total_sum(self) -> "FareBreakdown":
        computed_sum = self.base_fare + self.taxes + self.fees
        if abs(self.total_payable_fare - computed_sum) > Decimal("0.01"):
            raise ValueError(
                f"total_payable_fare ({self.total_payable_fare}) does not match "
                f"sum of components ({computed_sum} = {self.base_fare} + {self.taxes} + {self.fees})"
            )
        return self


class RawAudit(ImmutableBase):
    """Provenance audit trail preserving raw scraper response and cryptographic hash."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
    )

    raw_payload: str = Field(
        ...,
        description="Exact raw unmutated payload snippet from collection source",
        min_length=1,
    )
    raw_hash: str = Field(
        ...,
        description="SHA-256 hex digest of raw_payload",
        pattern=r"^[a-f0-9]{64}$",
    )

    @classmethod
    def create(cls, raw_payload: str) -> "RawAudit":
        """Convenience constructor that automatically computes SHA-256."""
        computed_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        return cls(raw_payload=raw_payload, raw_hash=computed_hash)

    @model_validator(mode="after")
    def verify_hash(self) -> "RawAudit":
        expected_hash = hashlib.sha256(self.raw_payload.encode("utf-8")).hexdigest()
        if self.raw_hash.lower() != expected_hash:
            raise ValueError(
                f"raw_hash does not match SHA-256 of raw_payload: "
                f"expected {expected_hash}, got {self.raw_hash}"
            )
        return self


class FareObservation(ImmutableBase):
    """Canonical immutable observation emitted by scrapers and consumed by APEX pipeline."""

    observation_id: str = Field(
        ...,
        description="Unique identifier for the observation (UUID / prefixed string)",
        min_length=1,
    )
    collection_timestamp: datetime = Field(
        ...,
        description="Collection execution timestamp in UTC",
    )
    source_info: SourceInfo
    flight_identity: FlightIdentity
    booking_dimension: BookingDimension
    fare_breakdown: FareBreakdown
    raw_audit: RawAudit
    status: ObservationStatus = Field(
        default=ObservationStatus.AVAILABLE,
        description="Availability status of the fare",
    )


WINDOW_OFFSETS: dict[BookingWindow, int] = {
    BookingWindow.T_PLUS_1: 1,
    BookingWindow.T_PLUS_7: 7,
    BookingWindow.T_PLUS_15: 15,
    BookingWindow.T_PLUS_30: 30,
    BookingWindow.T_PLUS_45: 45,
}


def get_window_offset(window: BookingWindow | str) -> int:
    """Return integer advance offset days for a given booking window."""
    w = BookingWindow(window) if isinstance(window, str) else window
    return WINDOW_OFFSETS[w]


def calculate_observation_target_date(
    collection_date: date | datetime, window: BookingWindow | str
) -> date:
    """Calculate flight departure target date from collection date and booking window."""
    base_date = collection_date.date() if isinstance(collection_date, datetime) else collection_date
    offset = get_window_offset(window)
    return base_date + timedelta(days=offset)

