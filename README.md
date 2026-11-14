# GPU FinOps Detective

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](#install)
[![Status: In development](https://img.shields.io/badge/Status-In%20development-yellow)](docs/PLAN.md)

An AI detective for wasted cloud GPU spending.

Combines billing records with GPU telemetry to find idle AI workloads, explain
unnecessary costs, and propose infrastructure changes with projected savings.
The full workflow will prepare Terraform changes and optional GitHub pull
requests for review.

## Install

Install **Python 3.12 or newer** and clone or download this repository.
GNU Make is optional; Docker is only needed for the container demo.

The current local demo uses the Python standard library. No cloud account,
physical GPU, Terraform installation, or LLM API key is required.

## Quick start

1. Open a terminal in the project folder.
2. Run `make demo` to generate 30 days of sample billing and GPU telemetry.
3. Open `data/generated/` to inspect `billing.csv`, `dcgm_telemetry.csv`, and
   `manifest.json`, which records known idle periods for testing.
4. Run `make test` to verify the data and expected costs.

Without Make:

```sh
python data/generator.py
python -m unittest discover -s tests -v
```

With Docker and Compose:

```sh
docker compose run --build --rm demo
```

The demo runs offline after setup and creates no cloud resources. Rerunning
replaces generated files. Sample prices are illustrative, not live AWS quotes.

## Architecture

Target workflow:

```text
Cloud billing + GPU telemetry
              |
       DuckDB detection rules
              |
       Structured anomalies
              |
 AI agent + pricing + Terraform configuration
              |
 Validated recommendations + savings + LLM cost
              |
 Terraform diff + formatting and validation
              |
     Optional GitHub review PR
```

SQL calculates idle spending; the AI receives findings rather than raw logs.
Recommendations must account for GPU memory and workload requirements. Observed
idle costs and projected savings are tracked separately. Deployment remains a
separate decision.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for Mermaid diagrams.

## Tech stack

- Python with reproducible CSV fixtures for local development
- Docker Compose and GNU Make for local execution
- DuckDB and SQL for anomaly detection (planned)
- Pydantic, a cloud LLM SDK, pricing snapshots, and python-hcl2 for validated
  recommendations and token-cost tracking (planned)
- Terraform CLI, Git, and GitHub integration for remediation proposals (planned)
- FastAPI, PostgreSQL, and background workers for production services (future)

## Roadmap

1. **Synthetic data and sample infrastructure** - implemented.
2. **Idle GPU detection and exact cost attribution** - planned.
3. **AI recommendations, pricing tools, and ROI tracking** - planned.
4. **Terraform changes, validation, and optional GitHub PRs** - planned.

`make demo` will remain the offline entry point as the pipeline grows.
`make prod` is reserved for future production execution and currently exits
with an error.

AWS is the initial target, with GCP support later. Production plans include real
billing exports, DCGM/Prometheus telemetry, S3 storage, managed PostgreSQL,
container workers, durable jobs, and audit records.

See [docs/PLAN.md](docs/PLAN.md) for the implementation and production plan.

## License

MIT. See [LICENSE](LICENSE).
