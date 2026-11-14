"""Generate normalized synthetic billing, DCGM-like telemetry, and ground truth.

Only the Python standard library is required. All timestamps and the workload
schedule use UTC. Billing is per instance-hour; telemetry is per GPU-hour.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_START = date(2026, 11, 2)
DEFAULT_RATE = Decimal("32.77")  # Illustrative fixture rate, NOT an AWS quote.
GPU_COUNT = 8
VRAM_TOTAL_MB = 40960  # Binary MiB; legacy DCGM-style column name retained.
BILLING_FIELDS = (
    "timestamp", "interval_end", "provider", "account_id", "region",
    "resource_id", "instance_type", "service", "environment", "usage_hours",
    "hourly_rate_usd", "cost_usd", "currency", "pricing_source",
)
TELEMETRY_FIELDS = (
    "timestamp", "provider", "account_id", "region", "resource_id", "gpu_index",
    "gpu_uuid", "sm_utilization", "tensor_core_active", "vram_used_mb",
    "vram_total_mb", "requests_per_second",
)


@dataclass(frozen=True)
class Resource:
    resource_id: str
    service: str
    scenario: str
    terraform_address: str | None = None


RESOURCES = (
    Resource(
        "i-00000000000000001", "recommendation-llm", "idle_inference",
        "aws_instance.recommendation_inference",
    ),
    Resource("i-00000000000000002", "healthy-inference", "healthy_control"),
)


def timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_idle(value: datetime) -> bool:
    """Inference receives traffic weekdays 06:00 through 17:59 UTC."""
    return value.weekday() >= 5 or value.hour < 6 or value.hour >= 18


def money(value: Decimal) -> str:
    return format(value, ".2f")


def generate(
    output_dir: Path,
    *,
    days: int = 30,
    start_date: date = DEFAULT_START,
    seed: int = 42,
    hourly_rate: Decimal = DEFAULT_RATE,
) -> dict:
    """Write a deterministic dataset and return its serializable manifest.

    The manifest is test ground truth, never an input to anomaly detection.
    Files with the standard output names are replaced on subsequent runs.
    """
    if not 1 <= days <= 366:
        raise ValueError("days must be between 1 and 366")
    if (
        not hourly_rate.is_finite()
        or hourly_rate <= 0
        or hourly_rate > Decimal("1000000")
        or hourly_rate != hourly_rate.quantize(Decimal("0.01"))
    ):
        raise ValueError("hourly_rate must be positive USD with at most two decimal places")

    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=days)
    rng = random.Random(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    intervals: list[dict] = []
    idle_start: datetime | None = None
    idle_hours = 0

    with (
        (output_dir / "billing.csv").open("w", newline="", encoding="utf-8") as billing,
        (output_dir / "dcgm_telemetry.csv").open("w", newline="", encoding="utf-8") as dcgm,
    ):
        billing_writer = csv.DictWriter(billing, fieldnames=BILLING_FIELDS)
        telemetry_writer = csv.DictWriter(dcgm, fieldnames=TELEMETRY_FIELDS)
        billing_writer.writeheader()
        telemetry_writer.writeheader()

        for hour in range(days * 24):
            current = start + timedelta(hours=hour)
            idle = is_idle(current)
            if idle:
                idle_hours += 1
                if idle_start is None:
                    idle_start = current
            elif idle_start is not None:
                intervals.append(idle_interval(idle_start, current, hourly_rate))
                idle_start = None

            for resource in RESOURCES:
                identity = {
                    "timestamp": timestamp(current),
                    "provider": "aws",
                    "account_id": "000000000000",
                    "region": "us-east-1",
                    "resource_id": resource.resource_id,
                }
                billing_writer.writerow({
                    **identity,
                    "interval_end": timestamp(current + timedelta(hours=1)),
                    "instance_type": "p4d.24xlarge",
                    "service": resource.service,
                    "environment": "demo",
                    "usage_hours": 1,
                    "hourly_rate_usd": money(hourly_rate),
                    "cost_usd": money(hourly_rate),
                    "currency": "USD",
                    "pricing_source": "synthetic-illustrative-v1",
                })
                resource_idle = idle and resource.scenario == "idle_inference"
                for gpu_index in range(GPU_COUNT):
                    telemetry_writer.writerow({
                        **identity,
                        "gpu_index": gpu_index,
                        "gpu_uuid": f"GPU-demo-{resource.resource_id}-{gpu_index}",
                        "sm_utilization": 0 if resource_idle else rng.randint(45, 85),
                        "tensor_core_active": 0 if resource_idle else rng.randint(25, 65),
                        "vram_used_mb": rng.randint(28672, 32768),
                        "vram_total_mb": VRAM_TOTAL_MB,
                        "requests_per_second": 0 if resource_idle else rng.randint(10, 100),
                    })

    if idle_start is not None:
        intervals.append(idle_interval(idle_start, end, hourly_rate))
    eligible_hours = sum(item["hours"] for item in intervals if item["eligible_12h_window"])
    manifest = {
        "schema_version": 1,
        "synthetic": True,
        "seed": seed,
        "start": timestamp(start),
        "end_exclusive": timestamp(end),
        "days": days,
        "timezone": "UTC",
        "sampling_interval_seconds": 3600,
        "telemetry_semantics": "one hourly aggregate per physical GPU; percentages 0-100",
        "vram_unit": "MiB (binary), despite legacy _mb column suffix",
        "pricing": {
            "source": "synthetic-illustrative-v1",
            "is_live_quote": False,
            "currency": "USD",
            "hourly_instance_rate_usd": money(hourly_rate),
            "excludes": ["EBS", "network", "tax", "discounts", "commitments"],
        },
        "resources": [
            {
                "resource_id": resource.resource_id,
                "service": resource.service,
                "scenario": resource.scenario,
                "terraform_address": resource.terraform_address,
                "instance_type": "p4d.24xlarge",
                "gpu_count": GPU_COUNT,
                "vram_per_gpu_mb": VRAM_TOTAL_MB,
            }
            for resource in RESOURCES
        ],
        "row_counts": {
            "billing": days * 24 * len(RESOURCES),
            "telemetry": days * 24 * len(RESOURCES) * GPU_COUNT,
        },
        "ground_truth": {
            "resource_id": RESOURCES[0].resource_id,
            "idle_schedule": "weekends and weekdays outside [06:00, 18:00) UTC",
            "idle_intervals": intervals,
            "idle_instance_hours": idle_hours,
            "idle_compute_cost_usd": money(hourly_rate * idle_hours),
            "eligible_12h_instance_hours": eligible_hours,
            "eligible_12h_compute_cost_usd": money(hourly_rate * eligible_hours),
            "total_billed_compute_usd": money(hourly_rate * days * 24 * len(RESOURCES)),
            "note": "Injected idle cost is potential waste, not guaranteed recoverable savings. "
                    "Intervals shorter than 12h at dataset boundaries cannot meet the rule.",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return manifest


def idle_interval(start: datetime, end: datetime, rate: Decimal) -> dict:
    hours = int((end - start).total_seconds() / 3600)
    return {
        "start": timestamp(start),
        "end_exclusive": timestamp(end),
        "hours": hours,
        "cost_usd": money(rate * hours),
        "eligible_12h_window": hours >= 12,
    }


def parse_rate(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("hourly rate must be a decimal number") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "generated")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hourly-rate", type=parse_rate, default=DEFAULT_RATE)
    args = parser.parse_args()
    try:
        manifest = generate(
            args.output_dir, days=args.days, start_date=args.start_date,
            seed=args.seed, hourly_rate=args.hourly_rate,
        )
    except (ValueError, InvalidOperation, OverflowError) as exc:
        parser.error(str(exc))
    truth = manifest["ground_truth"]
    print(f"Generated {manifest['days']} days in {args.output_dir.resolve()}")
    print(f"Billing rows: {manifest['row_counts']['billing']:,}")
    print(f"Telemetry rows: {manifest['row_counts']['telemetry']:,}")
    print(f"Injected idle instance-hours: {truth['idle_instance_hours']}")
    print(f"Illustrative idle compute cost: ${truth['idle_compute_cost_usd']}")
    print("Phase 1 only: detection, LLM calls, and infrastructure changes are not executed.")


if __name__ == "__main__":
    main()

