"""Core Orchestration Pipeline Combining Extraction, 10-Rule Guardrails, Dual-Track Routing & Audit."""
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from src.schemas import (
    VerificationIntakeRequest,
    VerificationResponse,
    RoutingDecision,
    HumanReviewSubmission,
    AuditLogEntry,
)
from src.extractor import extract_entity_profile
from src.guardrails import (
    load_policy_config,
    evaluate_policy_guardrails,
    calculate_confidence,
    determine_routing,
    DEFAULT_CONFIG_PATH,
)
from src.audit import TamperEvidentAuditLogger


class TrustOpsPipeline:
    """Enterprise Dual-Track KYC/KYB Verification & HITL Orchestration Engine."""

    def __init__(
        self,
        audit_log_path: Path = Path("data/audit_log.jsonl"),
        config_path: Path = DEFAULT_CONFIG_PATH,
    ):
        self.audit_logger = TamperEvidentAuditLogger(log_path=audit_log_path)
        self.config_path = config_path
        self.config = load_policy_config(config_path)
        self.review_queue: Dict[str, VerificationResponse] = {}
        self.completed_cases: Dict[str, VerificationResponse] = {}

    def verify_case(self, intake: VerificationIntakeRequest) -> VerificationResponse:
        start_ns = time.perf_counter_ns()

        # Step 1: Schema-Constrained Extraction
        extracted = extract_entity_profile(intake)

        # Step 2: Deterministic 10-Rule Policy Evaluation
        flags = evaluate_policy_guardrails(intake, extracted, self.config)

        # Step 3: Dual-Track Multi-Dimensional Confidence Calculation
        confidence = calculate_confidence(intake, extracted, self.config)

        # Step 4: Risk-Tiered State Machine Routing
        routing, target_sla_mins = determine_routing(
            intake.workflow_type, confidence, flags, self.config
        )

        latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
        timestamp_utc = datetime.now(timezone.utc).isoformat()

        # Step 5: Immutable Cryptographic Audit Logging
        audit_entry = self.audit_logger.log_event(
            case_id=intake.case_id,
            workflow_type=intake.workflow_type.value,
            actor="TRUSTOPS_AI_GATEWAY_V1",
            event_type="AUTOMATED_VERIFICATION_DECISION",
            decision=routing.value,
            payload_summary={
                "applicant_name": intake.applicant_name,
                "composite_confidence": confidence.composite_score,
                "applied_auto_threshold": confidence.applied_auto_threshold,
                "flag_codes": [f.rule_id for f in flags],
                "target_sla_minutes": target_sla_mins,
                "latency_ms": latency_ms,
            },
        )

        response = VerificationResponse(
            case_id=intake.case_id,
            workflow_type=intake.workflow_type,
            timestamp_utc=timestamp_utc,
            routing_decision=routing,
            composite_confidence=confidence.composite_score,
            confidence_breakdown=confidence,
            extracted_profile=extracted,
            policy_flags=flags,
            target_sla_minutes=target_sla_mins,
            audit_event_hash=audit_entry.event_hash,
            processing_latency_ms=latency_ms,
        )

        if routing in (
            RoutingDecision.HITL_TIER_1_REVIEW,
            RoutingDecision.HARD_BLOCK_ESCALATED,
        ):
            self.review_queue[intake.case_id] = response
        else:
            self.completed_cases[intake.case_id] = response

        return response

    def submit_human_review(self, submission: HumanReviewSubmission) -> AuditLogEntry:
        """Process human reviewer decision, record overrides, and append to SHA-256 audit chain."""
        case = self.review_queue.pop(submission.case_id, None)
        wf_type = case.workflow_type.value if case else "UNKNOWN"
        if case:
            self.completed_cases[submission.case_id] = case

        return self.audit_logger.log_event(
            case_id=submission.case_id,
            workflow_type=wf_type,
            actor=f"HUMAN_REVIEWER:{submission.reviewer_id}",
            event_type="HITL_MANUAL_DECISION",
            decision=submission.action.value,
            payload_summary={
                "override_fields": submission.override_fields or {},
                "reviewer_notes": submission.reviewer_notes,
                "review_duration_seconds": submission.review_duration_seconds,
            },
        )
