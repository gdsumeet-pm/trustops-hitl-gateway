"""FastAPI Microservice Exposing TrustOps v1.0 Verification, HITL Queue, Config & Audit Endpoints."""
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from src.schemas import (
    VerificationIntakeRequest,
    VerificationResponse,
    HumanReviewSubmission,
    AuditLogEntry,
)
from src.pipeline import TrustOpsPipeline

app = FastAPI(
    title="TrustOps: Enterprise AI Policy & HITL Verification Gateway",
    description=(
        "Open-Source Reference Architecture for Dual-Track FinTech KYC/KYB Onboarding, "
        "Deterministic Policy Guardrails, Confidence-Tiered Routing, and SHA-256 Audit Trails."
    ),
    version="1.0.0",
)

pipeline = TrustOpsPipeline()


@app.get("/health")
def health_check() -> Dict[str, Any]:
    valid, count, status = pipeline.audit_logger.verify_chain_integrity()
    return {
        "status": "healthy",
        "service": "trustops-hitl-gateway",
        "version": "1.0.0",
        "reference_domain": pipeline.config.get("reference_domain"),
        "audit_chain_valid": valid,
        "audit_events_logged": count,
        "audit_integrity_status": status,
    }


@app.get("/v1/config")
def get_active_policy_config() -> Dict[str, Any]:
    """Return the active YAML-driven risk thresholds, SLA timers, and confidence weights."""
    return pipeline.config


@app.post("/v1/verify", response_model=VerificationResponse)
def verify_onboarding_document(request: VerificationIntakeRequest) -> VerificationResponse:
    """Run unstructured KYC/KYB document through extraction, 10-rule guardrails, and HITL routing."""
    return pipeline.verify_case(request)


@app.get("/v1/review-queue", response_model=List[VerificationResponse])
def get_review_queue() -> List[VerificationResponse]:
    """Retrieve all pending cases routed to Tier-1 HITL Review or Senior Compliance Escalation."""
    return list(pipeline.review_queue.values())


@app.post("/v1/review/{case_id}/decision", response_model=AuditLogEntry)
def record_human_decision(
    case_id: str, submission: HumanReviewSubmission
) -> AuditLogEntry:
    """Submit a human reviewer decision (Approve, Override, Reject, Escalate) with mandatory audit notes."""
    if case_id != submission.case_id:
        raise HTTPException(status_code=400, detail="Path case_id and payload case_id mismatch.")
    return pipeline.submit_human_review(submission)


@app.get("/v1/audit-trail/{case_id}", response_model=List[AuditLogEntry])
def get_case_audit_trail(case_id: str) -> List[AuditLogEntry]:
    """Fetch immutable SHA-256 hash-chained audit events for a specific case."""
    return pipeline.audit_logger.get_events(case_id=case_id)


@app.get("/v1/metrics")
def get_operational_metrics() -> Dict[str, Any]:
    """Return real-time operational SLA and dual-track routing distribution metrics."""
    queued = list(pipeline.review_queue.values())
    completed = list(pipeline.completed_cases.values())
    all_cases = queued + completed
    total = len(all_cases)
    if total == 0:
        return {"total_cases_processed": 0, "straight_through_processing_rate": 0.0}

    auto_count = sum(1 for c in all_cases if c.routing_decision.value == "AUTO_APPROVED")
    hitl_count = sum(1 for c in all_cases if c.routing_decision.value == "HITL_TIER_1_REVIEW")
    block_count = sum(1 for c in all_cases if c.routing_decision.value == "HARD_BLOCK_ESCALATED")

    return {
        "total_cases_processed": total,
        "auto_approved_count": auto_count,
        "hitl_tier_1_count": hitl_count,
        "hard_block_count": block_count,
        "straight_through_processing_rate": round(auto_count / total, 4),
        "pending_review_queue_depth": len(queued),
    }
