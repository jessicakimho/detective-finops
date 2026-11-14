"""Verify fixture contracts independently of the future anomaly engine."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from data.generator import generate


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)

    def read_csv(self, name):
        with (self.output / name).open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def test_default_month_has_expected_cost_and_unique_instance_billing(self):
        manifest = generate(self.output)
        billing = self.read_csv("billing.csv")
        telemetry = self.read_csv("dcgm_telemetry.csv")
        self.assertEqual(len(billing), 1440)
        self.assertEqual(len(telemetry), 11520)
        billing_keys = [(r["resource_id"], r["timestamp"]) for r in billing]
        self.assertEqual(len(set(billing_keys)), len(billing))
        gpu_groups = Counter((r["resource_id"], r["timestamp"]) for r in telemetry)
        self.assertEqual(set(gpu_groups), set(billing_keys))
        self.assertEqual(set(gpu_groups.values()), {8})
        gpu_keys = {(r["resource_id"], r["timestamp"], r["gpu_index"]) for r in telemetry}
        self.assertEqual(len(gpu_keys), len(telemetry))
        self.assertEqual(sum(Decimal(r["cost_usd"]) for r in billing), Decimal("47188.80"))
        truth = manifest["ground_truth"]
        self.assertEqual(truth["idle_instance_hours"], 456)
        self.assertEqual(truth["idle_compute_cost_usd"], "14943.12")
        self.assertEqual(truth["eligible_12h_instance_hours"], 444)
        self.assertEqual(truth["eligible_12h_compute_cost_usd"], "14549.88")
        self.assertEqual(sum(i["hours"] for i in truth["idle_intervals"]), 456)
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), manifest)

    def test_schedule_memory_and_healthy_control_are_reflected_in_telemetry(self):
        # Monday through Sunday, covering overnight, business hours, and a weekend.
        generate(self.output, days=7)
        rows = self.read_csv("dcgm_telemetry.csv")
        idle_keys = set()
        for row in rows:
            current = datetime.fromisoformat(row["timestamp"])
            expected_idle = row["resource_id"].endswith("1") and (
                current.weekday() in (5, 6) or current.hour in (*range(6), *range(18, 24))
            )
            memory = int(row["vram_used_mb"])
            capacity = int(row["vram_total_mb"])
            self.assertGreater(memory, capacity / 2)
            self.assertLessEqual(memory, capacity)
            if expected_idle:
                idle_keys.add((row["resource_id"], row["timestamp"]))
                self.assertEqual(int(row["sm_utilization"]), 0)
                self.assertEqual(int(row["tensor_core_active"]), 0)
                self.assertEqual(int(row["requests_per_second"]), 0)
            else:
                self.assertGreaterEqual(int(row["tensor_core_active"]), 25)
                self.assertGreater(int(row["requests_per_second"]), 0)
        # Five 12-hour weekday idle periods plus two full idle weekend days.
        self.assertEqual(len(idle_keys), 108)

    def test_same_configuration_produces_byte_identical_files(self):
        generate(self.output, days=2, seed=7)
        first = {p.name: p.read_bytes() for p in self.output.iterdir()}
        generate(self.output, days=2, seed=7)
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.output.iterdir()})
        generate(self.output, days=2, seed=8)
        self.assertNotEqual(first["dcgm_telemetry.csv"], (self.output / "dcgm_telemetry.csv").read_bytes())
        self.assertEqual(first["billing.csv"], (self.output / "billing.csv").read_bytes())

    def test_custom_period_rate_and_clipped_intervals(self):
        manifest = generate(
            self.output, days=1, start_date=date(2026, 11, 7), hourly_rate=Decimal("1.25"),
        )
        self.assertEqual(manifest["start"], "2026-11-07T00:00:00Z")
        self.assertEqual(manifest["end_exclusive"], "2026-11-08T00:00:00Z")
        self.assertEqual(manifest["ground_truth"]["idle_compute_cost_usd"], "30.00")
        self.assertEqual(manifest["ground_truth"]["eligible_12h_instance_hours"], 24)
        weekday = generate(self.output, days=1)
        self.assertEqual(weekday["ground_truth"]["idle_instance_hours"], 12)
        self.assertEqual(weekday["ground_truth"]["eligible_12h_instance_hours"], 0)

    def test_invalid_parameters_do_not_create_output(self):
        target = self.output / "not-created"
        for days in (0, -1, 367):
            with self.subTest(days=days), self.assertRaises(ValueError):
                generate(target, days=days)
        for rate in ("0", "-1", "NaN", "Infinity", "0.001", "1000001"):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                generate(target, hourly_rate=Decimal(rate))
        self.assertFalse(target.exists())

    def test_cli_generates_files_and_rejects_invalid_arguments(self):
        script = Path(__file__).resolve().parents[1] / "data" / "generator.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--output-dir", str(self.output), "--days", "1"],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("Billing rows: 48", completed.stdout)
        failed = subprocess.run(
            [sys.executable, str(script), "--days", "0"], capture_output=True, text=True,
        )
        self.assertEqual(failed.returncode, 2)
        self.assertIn("days must be between", failed.stderr)
        invalid_rate = subprocess.run(
            [sys.executable, str(script), "--hourly-rate", "not-a-number"],
            capture_output=True, text=True,
        )
        self.assertEqual(invalid_rate.returncode, 2)
        self.assertIn("hourly rate must be a decimal number", invalid_rate.stderr)


if __name__ == "__main__":
    unittest.main()

