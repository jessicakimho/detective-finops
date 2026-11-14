# Architecture flow

Solid arrows show the implemented Phase 1 path. Dashed arrows show planned
components. The ground-truth manifest is a test oracle, not detector input.

```mermaid
flowchart TD
    subgraph implemented["Phase 1 - implemented locally"]
        DEMO["make demo / Python CLI / Compose"] --> GEN["Seeded synthetic generator"]
        GEN --> BILL["billing.csv: one row per instance-hour"]
        GEN --> GPU["dcgm_telemetry.csv: one row per GPU-hour"]
        GEN --> TRUTH["manifest.json: injected intervals and exact costs"]
        TF["Sample Terraform: always-on P4d inference node"]
        TEST["Fixture integrity and cost tests"] --> TRUTH
        TEST --> BILL
        TEST --> GPU
    end

    subgraph planned["Phases 2-4 - planned local pipeline"]
        BILL -.-> NORMALIZE["Validate schema, identity, units, and completeness"]
        GPU -.-> NORMALIZE
        NORMALIZE -.-> DUCK["DuckDB: aggregate GPUs before joining instance cost"]
        DUCK -.-> RULE["12h memory/compute rule; deduplicate overlapping hours"]
        RULE -.-> FINDINGS["Structured anomalies and supporting aggregates"]
        FINDINGS -.-> AGENT["Bounded LLM tool loop or offline adapter"]
        PRICE["Dated pricing/spec snapshots"] -.-> AGENT
        TF -.-> HCL["HCL parser"]
        HCL -.-> AGENT
        AGENT -.-> CHECK["Validate plan, capacity constraints, savings, and token cost"]
        CHECK -.-> REPORT["Local evidence and ROI report"]
        CHECK -.-> PATCH["Scoped Terraform edit on a branch"]
        PATCH -.-> VALIDATE["terraform fmt and validate; inspect diff"]
        VALIDATE -.-> PR["Optional GitHub PR for human review"]
    end
```

## Future production boundary

These are design targets; no production resources or connectors exist yet.
Billing remains delayed accounting data even when hardware telemetry is fresh.

```mermaid
flowchart LR
    BILLING["Cloud billing exports"] --> OBJECTS["S3: normalized, versioned datasets"]
    DCGM["DCGM Exporter"] --> PROM["Prometheus"]
    PROM --> INGEST["Telemetry ingestion and hourly rollups"]
    INGEST --> OBJECTS
    TIMER["EventBridge schedule"] --> QUEUE["SQS jobs"]
    QUEUE --> WORKER["Container worker: same detection library"]
    OBJECTS --> WORKER
    WORKER --> DB["RDS PostgreSQL: runs, findings, usage, approvals"]
    API["FastAPI service"] --> DB
    UI["Review dashboard"] --> API
    WORKER --> LLM["Optional cloud LLM"]
    WORKER --> REVIEW["Validated remediation proposal"]
    REVIEW --> GH["GitHub App: reviewable PR"]
```

Keep cloud ingestion, pricing, model calls, and remediation behind separate
interfaces. Raw data stays outside the model context. Detection and cost math
must work with the LLM disabled. Production will add tenant/account isolation,
durable job retries, credentials management, audit records, and operational
monitoring before enabling live execution.

