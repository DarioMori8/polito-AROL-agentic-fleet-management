import sys
import unittest
from pathlib import Path

from fastapi import HTTPException


SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

import load_dataset  # noqa: E402
import main  # noqa: E402


class OperationalEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not main.DB_PATH.is_file():
            load_dataset.main(load_dataset.DEFAULT_SOURCE)

    def test_health_is_bounded_and_includes_latest_snapshot(self):
        result = main.machine_health("MCH-0007", 24)

        self.assertEqual(result["window"]["from"], "2026-08-04T00:00")
        self.assertEqual(result["window"]["to"], "2026-08-04T23:00")
        self.assertEqual(result["telemetry"]["snapshots"], 24)
        self.assertEqual(result["latest"]["timestamp"], "2026-08-04T23:00")
        self.assertEqual(
            sum(row["hours"] for row in result["operational_statuses"]), 24
        )

    def test_telemetry_explicit_date_overrides_rolling_window(self):
        result = main.search_telemetry(
            "MCH-0001", 1, "2026-08-03", "2026-08-03", None, 5
        )

        self.assertEqual(result["summary"]["matched_snapshots"], 24)
        self.assertEqual(len(result["results"]), 5)
        self.assertTrue(
            all(row["timestamp"].startswith("2026-08-03") for row in result["results"])
        )

    def test_alarm_search_never_crosses_machine(self):
        result = main.search_alarms(
            "MCH-0007", 720, None, None, None, "Open", None, 100
        )

        self.assertGreater(result["summary"]["matched_alarms"], 0)
        self.assertTrue(all(row["status"] == "Open" for row in result["results"]))
        alarm_ids = {row["alarm_id"] for row in result["results"]}
        self.assertIn("ALM-0228", alarm_ids)
        self.assertNotIn("ALM-0260", alarm_ids)  # belongs to MCH-0008

    def test_maintenance_preserves_ticket_without_alarm(self):
        result = main.search_maintenance_tickets(
            "MCH-0007", None, None, "Open", None, None, 50
        )

        self.assertTrue(
            any(row["alarm_id"] is None for row in result["results"]),
            "LEFT/nullable alarm relationships must not be dropped",
        )

    def test_invalid_timestamp_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            main.search_telemetry(
                "MCH-0001", 24, "not-a-date", None, None, 5
            )
        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
