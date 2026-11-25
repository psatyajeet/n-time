import json
import unittest
from pathlib import Path

from device.muni_logic import (
    arrival_pair_texts,
    eta_text,
    parse_iso_seconds,
    parse_remaining_seconds,
)

FIXTURE = Path(__file__).parent / "fixtures" / "stop_monitoring.json"


class DeviceLogicTests(unittest.TestCase):
    def test_timestamp_offsets_match(self):
        self.assertEqual(
            parse_iso_seconds("2025-01-02T00:00:00Z"),
            parse_iso_seconds("2025-01-01T17:00:00-07:00"),
        )

    def test_parses_same_two_arrivals_as_laptop(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([240, 720], parse_remaining_seconds(payload, "38"))

    def test_counts_from_response_time_when_vehicle_record_is_old(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        delivery = payload["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"]
        for recorded in ("2025-01-01T23:57:00Z", "1970-01-01T00:00:00Z", None):
            for visit in delivery["MonitoredStopVisit"]:
                visit["RecordedAtTime"] = recorded
            self.assertEqual([240, 720], parse_remaining_seconds(payload, "38"))

    def test_truncates_partial_minutes(self):
        self.assertEqual("DUE 2", eta_text([59, 145]))
        self.assertEqual("1", eta_text([145], age_seconds=60))

    def test_arrival_pair_countdown(self):
        self.assertEqual(("2:30", "10"), arrival_pair_texts([150, 600]))
        self.assertEqual(("2:25", "9"), arrival_pair_texts([150, 600], age_seconds=5))
        self.assertEqual(("DUE", "10"), arrival_pair_texts([30, 600]))
        self.assertEqual(("9:50", ""), arrival_pair_texts([-31, 600], age_seconds=10))
        self.assertEqual(("--", ""), arrival_pair_texts([]))


if __name__ == "__main__":
    unittest.main()
