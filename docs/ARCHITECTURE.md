# System Architecture & Technical Specification: TrustOps v1.0

## 1. End-to-End Platform Topology

TrustOps decouples **YAML-driven policy configuration** from the **stateless verification pipeline** and **cryptographic audit ledger**.

```mermaid
flowchart LR
    subgraph Config["1. Externalized Policy Layer"]
        Y[configs/fintech_lending_policy.yaml\nCONSUMER_KYC vs. SME_KYB Profiles]
    end

    subgraph Intake["2. Upstream Intake"]
        A[Lending Portal / OCR Pipeline] -->|POST /v1/verify| B(FastAPI Gateway)
    end

    subgraph Engine["3. TrustOps Core Verification Engine"]
        B --> C[Structured Extraction Gateway\nOpenAI Structured Outputs / Offline Parser]
        Y -.-> D[10-Rule Deterministic Guardrails\nPOL-001 to POL-010]
        Y -.-> E[Dual-Track Confidence Scorer\n35% LLM + 20% OCR + 30% Name + 15% Schema]
        C --> D
        C --> E
        D --> F{Risk-Tiered State Machine}
        E --> F
    end

    subgraph Routing["4. Execution & HITL Triage"]
        F -->|Conf >= Gate & 0 Flags| G[AUTO_APPROVED\nInstant STP Webhook]
        F -->|Ambiguous or MED/HIGH Flag| H[HITL_TIER_1_REVIEW\nStreamlit Reviewer Workbench]
        F -->|Conf < Floor or CRITICAL Flag| I[HARD_BLOCK_ESCALATED\nSenior Compliance Queue]
        H -->|POST /v1/review/decision| J[Human Override & Justification]
        I -->|POST /v1/review/decision| J
    end

    subgraph Audit["5. Cryptographic Governance"]
        F -.->|SHA-256 Chained Event| K[(Tamper-Evident Audit Ledger\ndata/audit_log.jsonl)]
        J -.->|SHA-256 Chained Event| K
    end
```

---

## 2. Module Boundaries & Responsibilities

| Layer | File Path | Architectural Role |
| :--- | :--- | :--- |
| **Policy Configuration** | `configs/fintech_lending_policy.yaml` | Externalizes confidence weights, track-specific thresholds (`0.90` vs `0.93`), SLA targets, sancion lists, and unit-cost assumptions. |
| **Data Contracts** | `src/schemas.py` | Defines strict Pydantic v2 models for dual-track intake, extracted profiles, UBO arrays, policy flags, and audit records. |
| **Extraction Gateway** | `src/extractor.py` | Supports live `gpt-4o-mini` Structured Outputs (`TRUSTOPS_LIVE_LLM=1`) and a deterministic zero-key parser for reproducible CI/CD runs. |
| **Guardrail & State Machine** | `src/guardrails.py` | Evaluates rules `POL-001` through `POL-010`, computes the weighted confidence score, and assigns the routing tier and SLA timer. |
| **Cryptographic Audit** | `src/audit.py` | Append-only JSON-L logger chaining each event via SHA-256 (`prev_hash` $\rightarrow$ `event_hash`) with full chain verification (`verify_chain_integrity()`). |
| **Pipeline Orchestrator** | `src/pipeline.py` | Coordinates verification execution, manages in-memory HITL queues, and commits operator overrides. |
| **REST Microservice** | `src/main.py` | FastAPI service exposing `/v1/verify`, `/v1/review-queue`, `/v1/review/{case_id}/decision`, `/v1/audit-trail/{case_id}`, `/v1/config`, `/v1/metrics`, and `/health`. |
| **Reviewer Workbench** | `ui/app.py` | 4-tab Streamlit operational console for live intake simulation, HITL triage, SHA-256 ledger inspection, and benchmark telemetry. |

---

## 3. Tamper-Evident SHA-256 Audit Chain Specification

To satisfy **SOC 2 Type II** and **ISO/IEC 27001** non-repudiation controls, every event $i$ computes its cryptographic digest over canonical sorted JSON:

$$H_i = \text{SHA256}\left(\text{CanonicalJSON}(\text{event\_id}_i, \text{timestamp}_i, \text{case\_id}_i, \text{workflow\_type}_i, \text{actor}_i, \text{decision}_i, \text{payload}_i, H_{i-1})\right)$$

where $H_0 = \text{"0"}^{64}$ is the genesis hash. Any unauthorized database modification of a historical decision, confidence score, or reviewer note invalidates $H_i$ and breaks the chain link for $H_{i+1}$, immediately alerting platform monitors on `GET /health`.
