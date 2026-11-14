# Implementation plan

## Phase 1: local fixtures (implemented)

- Generate 30 days of normalized AWS billing and DCGM-like telemetry as CSV.
- Include an inference node idle overnight/weekends with its model still loaded,
  and a continuously busy control node.
- Record deterministic ground truth, disjoint idle intervals, and Decimal costs.
- Provide a tagged Terraform inspection target, architecture diagrams, local
  commands, a dependency-free container, and integrity tests.

Acceptance: identical configuration produces identical bytes; billing keys are
unique; every billed hour has eight GPU samples; injected idle hours and costs
match independently specified expectations. The demo requires no credentials,
cloud resources, real GPU, model download, or network after runtime setup.

## Phase 2: deterministic detection (next)

Add DuckDB and SQL rules under `src/engine/`. Validate identity and complete
hourly coverage; aggregate physical GPUs to the node before joining billing.
Define the node rule explicitly: all GPUs keep over 50% VRAM occupied and each
GPU averages less than 5% tensor activity over 12 consecutive complete hours.
This conservative definition avoids hiding a busy GPU in a node-wide average.
Flag eligible windows, union overlapping billed hours, and emit strict anomaly
JSON with cost provenance. Never load the ground-truth manifest into the engine.

Acceptance: recover eligible injected hours without flagging the healthy control;
prove exact cost attribution, threshold boundaries, no duplicate charges, and
correct handling of missing or duplicate samples. Add those tests as
`tests/test_anomalies.py` when the engine exists.

## Phase 3: evidence-backed recommendations

Add Pydantic models, a Terraform parser, dated pricing/spec snapshots, an offline
recommendation adapter, and one optional cloud LLM SDK. Supply only findings and
relevant configuration to the model. Validate memory and capacity constraints;
calculate savings and token charges deterministically. Record observed idle
cost separately from projected and eventually realized savings. An instance
change is only one remedy; scheduling may preserve necessary GPU memory.

## Phase 4: controlled remediation

Generate a constrained edit on a new branch. Run `terraform fmt`, initialize the
provider without a remote backend, and run `terraform validate`. Record the
diff and results. Validation checks syntax/schema, not deployment or inference
performance. Prepare an optional GitHub PR with evidence, assumptions, monthly
savings, and agent costs. Applying infrastructure stays a separate decision.

## Execution modes

`make demo` is the stable offline entry point. Today it generates fixtures; each
later phase will extend it to run the completed local pipeline without requiring
API keys. Live LLM/PR actions will be explicit opt-ins.

`make prod` is reserved and exits unsuccessfully today. It must not quietly run
synthetic data as a production workload. Before implementing it, define live
source configuration, durable storage/jobs, authentication, least-privilege
credentials, approval policy, monitoring, and deployment checks. It will invoke
the same core pipeline with production adapters; deployment remains a distinct
operation.

Start production with AWS: S3 for datasets, RDS PostgreSQL for state, ECS/Fargate
for API/workers, SQS for jobs, and EventBridge for scheduling. Add a FastAPI API
and application database when persistent runs and asynchronous job submission
are implemented. Add a dashboard when findings are available. GCP ingestion and
larger analytics infrastructure should follow a demonstrated need.

