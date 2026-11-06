# Product Requirements Document (PRD): TrustOps v1.0 — AI Policy & HITL Verification Gateway

| Document Metadata | Details |
| :--- | :--- |
| **Product Name** | TrustOps — Enterprise AI Policy & Human-in-the-Loop (HITL) Verification Gateway |
| **Release Version** | v1.0.0 (Open-Source Reference Architecture) |
| **Author / Owner** | Sumeet S Sharma — Senior Product Manager (B2B SaaS, Internal Platforms & Applied AI) |
| **Reference Domain** | Dual-Track FinTech Digital Lending (`CONSUMER_KYC` Micro-Loans & `SME_KYB` Merchant Credit Lines) |
| **Regulatory Alignment** | SOC 2 Type II, ISO/IEC 27001, GDPR Article 22, EU AI Act (High-Risk Annex III Human Oversight) |

---

## 1. Executive Context & Architectural Provenance

**TrustOps v1.0** is an open-source reference architecture distilled from production learnings delivering shared B2B SaaS trust orchestration and KYC/KYB verification platforms at enterprise scale.

In regulated onboarding and digital lending platforms, product teams face a structural trade-off between **unit economics** and **compliance liability**:
1. **Unconstrained LLM Extraction Creates Compliance Liability:** Autonomous LLMs hallucinate over degraded OCR scans, misread corporate ownership structures, or fall victim to adversarial prompt injections embedded in uploaded PDFs—leading to **False Auto-Approvals** of sanctioned or fraudulent entities.
2. **Uncalibrated Confidence Scores Destroy Unit Economics:** When compliance teams cannot trust model confidence scores, they revert to 100% manual review. On a $500 consumer micro-loan, a $6.50 manual review cost erodes contribution margin; on SME merchant credit lines, manual review queues cause multi-day onboarding delays and frequent SLA breaches.
3. **Standard Application Logs Fail Regulatory Audits:** Conventional database rows can be mutated post-hoc and fail to provide tamper-evident proof of *why* an AI approved an application or *which human operator* overrode a compliance flag under GDPR Article 22 and the EU AI Act.

---

## 2. Reference Architecture Separation of Concerns

To serve as an authentic, reusable blueprint rather than a single hardcoded app, TrustOps separates the **Core Platform Engine** from the **Pluggable Domain Configuration**:

* **Layer 1 — Core Reusable Platform Gateway (`src/`):** Domain-agnostic FastAPI microservice enforcing Pydantic v2 data contracts, a dual-mode extraction gateway (OpenAI Structured Outputs + deterministic zero-key parser), a 10-rule compliance engine (`POL-001` through `POL-010`), a multi-dimensional confidence state machine, a 4-tab Streamlit Reviewer Workbench, and an append-only SHA-256 hash-chained audit ledger.
* **Layer 2 — Pluggable Reference Policy (`configs/fintech_lending_policy.yaml`):** Externalized YAML configuration modeling a dual-track **FinTech Digital Lending** platform:
  * **Track A (`CONSUMER_KYC`):** Individual micro-loans ($100–$1,500) optimized for high Straight-Through Processing (auto-approval gate $\ge 0.90$, Tier-1 HITL SLA: 60 mins).
  * **Track B (`SME_KYB`):** SME merchant credit lines ($10,000–$250,000) requiring stricter corporate registry, tax ID, and Ultimate Beneficial Owner (UBO) verification (auto-approval gate $\ge 0.93$, Tier-1 HITL SLA: 240 mins).

---

## 3. Multi-Dimensional Confidence Model & State Machine

Rather than trusting raw LLM token probabilities alone, TrustOps computes a weighted **Composite Confidence Score ($C_{comp}$)** governed by `configs/fintech_lending_policy.yaml`:

$$C_{comp} = 0.35 \cdot C_{LLM} + 0.20 \cdot C_{OCR} + 0.30 \cdot S_{entity\_match} + 0.15 \cdot S_{completeness}$$

| Routing State | Trigger Condition | Consumer KYC SLA | SME KYB SLA | Downstream Action |
| :--- | :--- | :---: | :---: | :--- |
| **`AUTO_APPROVED`** | $C_{comp} \ge T_{auto}$ **AND** Zero Policy Flags | **0 mins** | **0 mins** | Straight-through approval webhook emitted |
| **`HITL_TIER_1_REVIEW`** | $T_{block} \le C_{comp} < T_{auto}$ **OR** `MEDIUM`/`HIGH` Flag | **60 mins** | **240 mins** | Routed to Reviewer Workbench with source snippets |
| **`HARD_BLOCK_ESCALATED`** | $C_{comp} < T_{block}$ **OR** `CRITICAL` Flag | **30 mins** | **60 mins** | Immediate freeze; escalated to Senior Compliance |

*(Reference defaults: $T_{auto} = 0.90, T_{block} = 0.65$ for `CONSUMER_KYC`; $T_{auto} = 0.93, T_{block} = 0.70$ for `SME_KYB`.)*

---

## 4. Deterministic 10-Rule Compliance Guardrail Catalog (`src/guardrails.py`)

Deterministic rules execute in Python after extraction and **always supersede** probabilistic confidence scores:

| Rule ID | Rule Name | Applies To | Severity | Deterministic Trigger Condition |
| :--- | :--- | :---: | :---: | :--- |
| **`POL-001`** | Adversarial Prompt Injection | Both Tracks | `CRITICAL` | Regex match for instruction-override attacks inside raw OCR text |
| **`POL-002`** | Sanctioned Jurisdiction Match | Both Tracks | `CRITICAL` | Declared or extracted ISO-2 country in OFAC/FATF restricted list (`KP, IR, SY, MM, RU`) |
| **`POL-003`** | Cross-Field Jurisdiction Mismatch | Both Tracks | `HIGH` | Declared onboarding country $\neq$ extracted document jurisdiction |
| **`POL-004`** | Missing/Malformed Primary ID | Both Tracks | `HIGH` | Primary ID / Registration number missing or $< 6$ characters |
| **`POL-005`** | Applicant / Entity Name Discrepancy | Both Tracks | `MEDIUM`/`HIGH` | Normalized sequence similarity between declared and extracted name $< 0.78$ |
| **`POL-006`** | Missing UBO Disclosure | `SME_KYB` | `MEDIUM` | Zero Ultimate Beneficial Owners extracted from corporate filing |
| **`POL-007`** | Invalid UBO Ownership Sum | `SME_KYB` | `HIGH` | Sum of extracted UBO ownership percentages $> 100.0\%$ |
| **`POL-008`** | Politically Exposed Person (PEP) | `SME_KYB` | `HIGH` | Any extracted UBO flagged as PEP (`pep_flagged == True`) |
| **`POL-009`** | Sanctioned UBO Nationality | `SME_KYB` | `CRITICAL` | Any extracted UBO holds nationality in a sanctioned jurisdiction |
| **`POL-010`** | Expired Verification Document | Both Tracks | `HIGH` | Document expiry date prior to reference verification date (`2026-11-01`) |

---

## 5. Non-Functional Requirements (NFRs) & Regulatory Safeguards

1. **Zero Silent Schema Failures:** 100% of verification responses validate against Pydantic v2 contracts (`VerificationResponse`).
2. **GDPR Article 22 & EU AI Act Human Oversight:** No adverse rejection is executed autonomously by the model; all ambiguous or flagged applications require human intervention with mandatory audit justification notes (`min_length=5`).
3. **Cryptographic Non-Repudiation:** Every automated decision and human review action is recorded in an append-only JSON-L ledger chained via SHA-256 (`prev_hash` $\rightarrow$ `event_hash`).
