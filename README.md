# TrustOps (v1.0): Enterprise AI Policy & HITL Verification Gateway

[![Release: v1.0.0 Reference Architecture](https://img.shields.io/badge/Release-v1.0.0_Reference_Architecture-0A66C2)](#)
[![Safety Gate: 0.00% False Auto-Approval](https://img.shields.io/badge/Safety_Eval-0.00%25_False_Auto_Approval-2EA44F)](#)
[![Compliance: SHA-256 Hash-Chained Audit](https://img.shields.io/badge/Audit_Ledger-SHA256_Tamper_Evident-6F42C1)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Author:** Sumeet S Sharma — Senior Product Manager (B2B SaaS, Internal Platforms & Applied AI)

---

## Executive Overview

In regulated B2B SaaS and FinTech onboarding workflows, scaling AI automation is rarely bottlenecked by raw LLM extraction capability—it is bottlenecked by **compliance liability, uncalibrated confidence scores, and audit fragility**.

**TrustOps v1.0** is an open-source reference architecture and functional microservice platform distilled from enterprise trust-orchestration production learnings. It demonstrates how platform product teams govern AI-assisted document verification across a **Dual-Track FinTech Digital Lending** implementation (`CONSUMER_KYC` micro-loans and `SME_KYB` merchant credit lines):

1. **Pluggable Dual-Track Risk Profiles (`configs/fintech_lending_policy.yaml`):** Externalizes confidence weights, auto-approval thresholds (`0.90` for low-ticket Consumer KYC vs. `0.93` for higher-risk SME Merchant KYB), SLA timers, and unit-cost models into a declarative YAML layer.
2. **Schema-Constrained Extraction Gateway (`src/extractor.py`):** Enforces strict Pydantic v2 contracts (`ExtractedEntityProfile`) via live **OpenAI Structured Outputs** (`TRUSTOPS_LIVE_LLM=1`) alongside a zero-key deterministic offline parser for reproducible CI/CD benchmarking.
3. **10-Rule Deterministic Compliance Guardrail Engine (`src/guardrails.py`):** Evaluates extracted profiles against ten deterministic rules (`POL-001` through `POL-010`) covering OFAC/FATF sanctions, cross-field jurisdiction mismatches, ID format validation, entity name similarity, UBO ownership sum validation, PEP flags, expired documents, and adversarial prompt injections. Deterministic flags always override model confidence.
4. **Audit-Ready HITL Reviewer Workbench & SHA-256 Ledger (`ui/app.py`, `src/audit.py`):** Routes ambiguous applications to a 4-tab Streamlit console pairing extracted JSON with verbatim source quotes, logging every automated decision and human override into a tamper-evident **SHA-256 hash-chained audit trail** aligned with **SOC 2 Type II**, **ISO 27001**, **GDPR Article 22**, and the **EU AI Act**.

---

## Repository Structure

```text
trustops-hitl-gateway/
├── configs/
│   └── fintech_lending_policy.yaml  # Externalized dual-track risk thresholds, SLAs & unit economics
├── docs/
│   ├── PRD.md                       # Complete Enterprise Product Requirements Document
│   ├── ARCHITECTURE.md              # System topology, Mermaid diagrams & SHA-256 audit spec
│   ├── METRICS_FRAMEWORK.md         # CI/CD Eval Gates vs. Production Operational ROI Framework
│   └── openapi-spec.yaml            # OpenAPI 3.0.3 REST contract
├── evals/
│   ├── golden_dataset.json          # 30 synthetic test cases (15 Consumer KYC + 15 SME KYB)
│   ├── run_evals.py                 # Automated CI/CD evaluation & safety benchmark script
│   └── eval_results.md              # Generated evaluation scorecard & confusion matrix
├── src/
│   ├── schemas.py                   # Pydantic v2 data contracts
│   ├── extractor.py                 # OpenAI Structured Outputs + Deterministic offline parser
│   ├── guardrails.py                # 10 compliance rules, confidence scorer & routing state machine
│   ├── audit.py                     # Tamper-evident SHA-256 hash-chained audit logger
│   ├── pipeline.py                  # End-to-end verification & HITL orchestration engine
│   └── main.py                      # FastAPI microservice (/v1/verify, /v1/review-queue, /v1/config)
├── ui/
│   └── app.py                       # 4-Tab Streamlit Reviewer Workbench & Governance Console
├── tests/
│   └── test_pipeline.py             # Automated pytest suite verifying dual-track routing & audit chain
├── Makefile                         # Developer workflow shortcuts (make eval, make test, make api, make ui)
├── LICENSE                          # MIT License
└── requirements.txt                 # Python package dependencies
```

---

## Reference Evaluation Benchmark (`evals/eval_results.md`)

Running `PYTHONPATH=. python3 evals/run_evals.py` validates the default FinTech Lending policy configuration against all 30 synthetic Golden Dataset scenarios (clean filings, degraded OCR scans, UBO/PEP flags, and adversarial prompt injections):

| Metric Category | Release-Gate KPI | Target Gate | Reference Dataset Result | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Critical Safety** | **False Auto-Approval Rate (FAAR)** | **0.00%** | **0.00%** (0/18) | **PASS** |
| **Decision Quality** | **Dual-Track Routing Tier Match** | >= 95.0% | **100.00%** (30/30) | **PASS** |
| **Determinism** | **Pydantic v2 Schema Adherence** | 100.0% | **100.00%** (30/30) | **PASS** |
| **Compliance** | **Audit Chain SHA-256 Integrity** | 100.0% | **100.00%** (30/30 hashes) | **PASS** |

> *Note on Reference Metrics:* The table above reflects automated CI/CD release-gate verification on the 30-case synthetic dataset bundled in this repository. See [`docs/METRICS_FRAMEWORK.md`](docs/METRICS_FRAMEWORK.md) for how adopting teams map these technical release gates to production operational KPIs (cycle time, reviewer AHT, and unit cost).

---

## Quickstart Guide (Runs Out-of-the-Box Without API Keys)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the 30-Case Evaluation Harness
```bash
PYTHONPATH=. python3 evals/run_evals.py
```

### 3. Run the Automated Pytest Suite
```bash
PYTHONPATH=. pytest tests/ -v
```

### 4. Launch the Interactive HITL Reviewer Workbench
```bash
PYTHONPATH=. streamlit run ui/app.py
```

### 5. Launch the FastAPI Microservice
```bash
PYTHONPATH=. uvicorn src.main:app --reload --port 8000
# Open Swagger UI at http://localhost:8000/docs
```

*(Optional)* To switch from the deterministic offline extractor to live OpenAI Structured Outputs:
```bash
export OPENAI_API_KEY="sk-..."
export TRUSTOPS_LIVE_LLM=1
```
