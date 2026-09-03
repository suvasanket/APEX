"""Unit tests for FareObservation domain model and data contract."""

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

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


class TestFareSpec(unittest.TestCase):
    """Test suite for FareObservation schema compliance and validation."""

    def setUp(self) -> None:
        self.raw_payload = '{"flights": [{"flightNo": "6E-2054", "price": 4532}]}'
        self.raw_audit = RawAudit.create(self.raw_payload)

        self.valid_data = {
            "observation_id": "obs-del-bom-20260903-001",
            "collection_timestamp": datetime(2026, 9, 3, 10, 0, 0, tzinfo=timezone.utc),
            "source_info": SourceInfo(
                source_code="indigo_direct",
                source_type=SourceType.AIRLINE_DIRECT,
                collection_run_id="run-20260903-1000",
            ),
            "flight_identity": FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 6, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 8, 15, 0, tzinfo=timezone.utc),
                stops=0,
                is_nonstop=True,
            ),
            "booking_dimension": BookingDimension(
                booking_window=BookingWindow.T_PLUS_15,
                advance_days=15,
                cabin_class="economy",
                fare_family="Saver",
            ),
            "fare_breakdown": FareBreakdown(
                currency="INR",
                base_fare=Decimal("3800.00"),
                taxes=Decimal("450.00"),
                fees=Decimal("282.00"),
                total_payable_fare=Decimal("4532.00"),
            ),
            "raw_audit": self.raw_audit,
            "status": ObservationStatus.AVAILABLE,
        }

    def test_valid_fare_observation_instantiation(self) -> None:
        """Verify that a properly configured observation builds without error."""
        obs = FareObservation(**self.valid_data)
        self.assertEqual(obs.observation_id, "obs-del-bom-20260903-001")
        self.assertEqual(obs.flight_identity.origin_iata, "DEL")
        self.assertEqual(obs.flight_identity.destination_iata, "BOM")
        self.assertEqual(obs.fare_breakdown.currency, "INR")
        self.assertEqual(obs.fare_breakdown.total_payable_fare, Decimal("4532.00"))
        self.assertTrue(obs.flight_identity.is_nonstop)

    def test_rejection_of_negative_fares(self) -> None:
        """Verify that negative base fare, taxes, fees, or total raise ValidationError."""
        # Negative base fare
        with self.assertRaises(ValidationError):
            FareBreakdown(
                currency="INR",
                base_fare=Decimal("-100.00"),
                taxes=Decimal("50.00"),
                fees=Decimal("50.00"),
                total_payable_fare=Decimal("0.00"),
            )

        # Negative taxes
        with self.assertRaises(ValidationError):
            FareBreakdown(
                currency="INR",
                base_fare=Decimal("100.00"),
                taxes=Decimal("-50.00"),
                fees=Decimal("50.00"),
                total_payable_fare=Decimal("100.00"),
            )

        # Negative fees
        with self.assertRaises(ValidationError):
            FareBreakdown(
                currency="INR",
                base_fare=Decimal("100.00"),
                taxes=Decimal("50.00"),
                fees=Decimal("-50.00"),
                total_payable_fare=Decimal("100.00"),
            )

    def test_rejection_of_non_inr_currency(self) -> None:
        """Verify that currency must strictly be INR."""
        with self.assertRaises(ValidationError):
            FareBreakdown(
                currency="USD",  # type: ignore[arg-type]
                base_fare=Decimal("1000.00"),
                taxes=Decimal("200.00"),
                fees=Decimal("50.00"),
                total_payable_fare=Decimal("1250.00"),
            )

    def test_rejection_of_mismatched_total_fare(self) -> None:
        """Verify that total_payable_fare must equal base_fare + taxes + fees."""
        with self.assertRaises(ValidationError):
            FareBreakdown(
                currency="INR",
                base_fare=Decimal("1000.00"),
                taxes=Decimal("200.00"),
                fees=Decimal("50.00"),
                total_payable_fare=Decimal("1500.00"),  # Expected 1250.00
            )

    def test_rejection_of_departure_after_arrival(self) -> None:
        """Verify departure time must be strictly before arrival time."""
        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                stops=0,
                is_nonstop=True,
            )

    def test_rejection_of_identical_origin_and_destination(self) -> None:
        """Verify origin and destination airport codes cannot be identical."""
        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="DEL",
                departure_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
                stops=0,
                is_nonstop=True,
            )

    def test_rejection_of_invalid_iata_codes(self) -> None:
        """Verify IATA airport codes must be exactly 3 uppercase letters."""
        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="del",  # Lowercase
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
            )

        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DELHI",  # 5 characters
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
            )

    def test_is_nonstop_consistency_with_stops(self) -> None:
        """Verify that is_nonstop matches stops == 0."""
        # Non-stop flagged True, but stops = 1
        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc),
                stops=1,
                is_nonstop=True,
            )

        # Non-stop flagged False, but stops = 0
        with self.assertRaises(ValidationError):
            FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime=datetime(2026, 9, 18, 8, 0, 0, tzinfo=timezone.utc),
                arrival_datetime=datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc),
                stops=0,
                is_nonstop=False,
            )

    def test_rejection_of_non_economy_cabin(self) -> None:
        """Verify that cabin class must be economy."""
        with self.assertRaises(ValidationError):
            BookingDimension(
                booking_window=BookingWindow.T_PLUS_15,
                advance_days=15,
                cabin_class="business",  # type: ignore[arg-type]
                fare_family="Flexi",
            )

    def test_immutability(self) -> None:
        """Verify that FareObservation instances cannot be modified after instantiation."""
        obs = FareObservation(**self.valid_data)
        with self.assertRaises(ValidationError):
            obs.observation_id = "mutated-id"  # type: ignore[misc]

    def test_raw_audit_hash_validation(self) -> None:
        """Verify raw_hash must match SHA-256 of raw_payload."""
        # Incorrect raw hash
        with self.assertRaises(ValidationError):
            RawAudit(
                raw_payload='{"test": 123}',
                raw_hash="0000000000000000000000000000000000000000000000000000000000000000",
            )

        # Helper correctly hashes
        audit = RawAudit.create("sample data")
        self.assertEqual(len(audit.raw_hash), 64)
        self.assertEqual(audit.raw_payload, "sample data")

    def test_json_roundtrip(self) -> None:
        """Verify serialization and deserialization to/from JSON."""
        obs = FareObservation(**self.valid_data)
        serialized_json = obs.model_dump_json()
        deserialized = FareObservation.model_validate_json(serialized_json)
        self.assertEqual(obs.observation_id, deserialized.observation_id)
        self.assertEqual(obs.fare_breakdown.total_payable_fare, deserialized.fare_breakdown.total_payable_fare)


    def test_booking_window_offsets(self) -> None:
        """Verify window offset calculation helper."""
        from datetime import date
        from apex.models.fare import (
            calculate_observation_target_date,
            get_window_offset,
        )

        self.assertEqual(get_window_offset("T+1"), 1)
        self.assertEqual(get_window_offset("T+7"), 7)
        self.assertEqual(get_window_offset("T+15"), 15)
        self.assertEqual(get_window_offset("T+30"), 30)
        self.assertEqual(get_window_offset("T+45"), 45)

        base_d = date(2026, 9, 1)
        self.assertEqual(calculate_observation_target_date(base_d, "T+1"), date(2026, 9, 2))
        self.assertEqual(calculate_observation_target_date(base_d, "T+15"), date(2026, 9, 16))

    def test_valid_fixture_file(self) -> None:
        """Verify the canonical valid_fare.json fixture passes contract validation."""
        fixture_path = Path("tests/fixtures/observations/valid_fare.json")
        self.assertTrue(fixture_path.exists(), f"Fixture file not found at {fixture_path}")

        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        obs = FareObservation.model_validate(data)
        self.assertEqual(obs.flight_identity.origin_iata, "DEL")
        self.assertEqual(obs.flight_identity.destination_iata, "BOM")
        self.assertEqual(obs.fare_breakdown.currency, "INR")
        self.assertEqual(obs.fare_breakdown.total_payable_fare, Decimal("4532.00"))
        self.assertTrue(obs.flight_identity.is_nonstop)

    def test_invalid_fixtures_file(self) -> None:
        """Verify all cases in invalid_fares.json raise ValidationError."""
        fixture_path = Path("tests/fixtures/observations/invalid_fares.json")
        self.assertTrue(fixture_path.exists(), f"Fixture file not found at {fixture_path}")

        with open(fixture_path, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

        self.assertGreaterEqual(len(test_cases), 5)
        for case in test_cases:
            with self.subTest(msg=case["description"]):
                with self.assertRaises(ValidationError, msg=f"Failed to reject invalid case: {case['description']}"):
                    FareObservation.model_validate(case["payload"])


if __name__ == "__main__":
    unittest.main()


