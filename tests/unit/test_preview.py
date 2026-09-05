"""Unit tests for Live Preview Viewer."""

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from apex.collectors.preview import (
    export_verification_artifacts,
    format_observation_table,
    run_cli_preview,
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


class TestPreview(unittest.TestCase):
    """Test suite for live preview and reporting."""

    def _sample_obs(self) -> FareObservation:
        payload = '{"test": 1}'
        return FareObservation(
            observation_id="OBS-TEST",
            collection_timestamp=date(2026, 9, 5),
            source_info=SourceInfo(
                source_code="test_src",
                source_type=SourceType.AIRLINE_DIRECT,
                collection_run_id="RUN-1",
            ),
            flight_identity=FlightIdentity(
                airline_iata="6E",
                flight_number="6E-2054",
                origin_iata="DEL",
                destination_iata="BOM",
                departure_datetime="2026-09-20T06:00:00Z",
                arrival_datetime="2026-09-20T08:15:00Z",
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
                base_fare=Decimal("3800.00"),
                taxes=Decimal("450.00"),
                fees=Decimal("282.00"),
                total_payable_fare=Decimal("4532.00"),
            ),
            raw_audit=RawAudit.create(payload),
            status=ObservationStatus.AVAILABLE,
        )

    def test_format_observation_table(self):
        obs = self._sample_obs()
        table_str = format_observation_table(
            route_id="DEL-BOM",
            window_id="T+15",
            travel_date=date(2026, 9, 20),
            observations=[obs],
            raw_hash="a" * 64,
            source_name="TestCollector",
        )
        self.assertIn("DEL-BOM", table_str)
        self.assertIn("6E-2054", table_str)
        self.assertIn("3800.00", table_str)
        self.assertIn("4532.00", table_str)
        self.assertIn("VERIFICATION INSTRUCTIONS", table_str)

    def test_export_artifacts(self):
        obs = self._sample_obs()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            txt_file, json_file = export_verification_artifacts(
                route_id="DEL-BOM",
                window_id="T+15",
                travel_date=date(2026, 9, 20),
                observations=[obs],
                raw_payload='{"raw": true}',
                raw_hash="b" * 64,
                source_name="TestCollector",
                output_dir=tmp_path,
            )
            self.assertTrue(txt_file.exists())
            self.assertTrue(json_file.exists())
            self.assertIn("6E-2054", txt_file.read_text(encoding="utf-8"))
            self.assertEqual(json_file.read_text(encoding="utf-8"), '{"raw": true}')

    def test_run_cli_preview_mock(self):
        loop = asyncio.new_event_loop()
        try:
            # Running CLI preview in mock mode completes successfully
            loop.run_until_complete(
                run_cli_preview(
                    route_id="DEL-BLR",
                    window_id="T+7",
                    source="mock",
                    export=False,
                )
            )
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
