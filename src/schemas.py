"""Pydantic v2 Data Contracts for TrustOps v1.0 Dual-Track Verification & HITL Gateway."""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WorkflowType(str, Enum):
    CONSUMER_KYC = "CONSUMER_KYC"
    SME_KYB = "SME_KYB"


class RoutingDecision(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    HITL_TIER_1_REVIEW = "HITL_TIER_1_REVIEW"
    HARD_BLOCK_ESCALATED = "HARD_BLOCK_ESCALATED"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UBOEntry(BaseModel):
    full_name: str = Field(..., description="Full legal name of Ultimate Beneficial Owner")
    ownership_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of ownership")
    nationality: str = Field(..., description="ISO-2 country code of nationality")
    pep_flagged: bool = Field(default=False, description="Politically Exposed Person indicator")


class VerificationIntakeRequest(BaseModel):
    case_id: str = Field(..., description="Unique onboarding or loan application ID")
    workflow_type: WorkflowType = Field(..., description="Risk profile track: CONSUMER_KYC or SME_KYB")
    applicant_name: str = Field(..., description="Declared consumer full name or SME legal business name")
    declared_jurisdiction: str = Field(..., description="Declared ISO-2 country code")
    document_type: str = Field(..., description="Document class (e.g., PAN_CARD, NATIONAL_ID, CERTIFICATE_OF_INCORPORATION)")
    raw_document_text: str = Field(..., description="Unstructured OCR text from uploaded verification document")
    ocr_quality_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Upstream OCR engine quality score")
    requested_credit_limit_usd: Optional[float] = Field(default=1000.0, ge=0.0, description="Requested micro-loan or merchant credit line")


class ExtractedEntityProfile(BaseModel):
    extracted_name: str = Field(..., description="Individual or legal entity name extracted from document")
    primary_id_number: Optional[str] = Field(None, description="Government ID, Tax/PAN ID, or Corporate Registration Number")
    issuance_or_incorporation_date: Optional[str] = Field(None, description="Date of issuance or incorporation (YYYY-MM-DD)")
    document_expiry_date: Optional[str] = Field(None, description="Document expiry date if applicable (YYYY-MM-DD)")
    extracted_jurisdiction: str = Field(..., description="ISO-2 country code extracted from document")
    registered_address: Optional[str] = Field(None, description="Extracted residential or registered corporate address")
    ubos: List[UBOEntry] = Field(default_factory=list, description="Extracted Ultimate Beneficial Owners (mandatory for SME_KYB)")
    extraction_confidence: float = Field(..., ge=0.0, le=1.0, description="Model field-level extraction confidence")
    source_snippets: Dict[str, str] = Field(default_factory=dict, description="Verbatim source evidence quotes per field")


class PolicyFlag(BaseModel):
    rule_id: str = Field(..., description="Deterministic policy rule identifier (POL-001 to POL-010)")
    rule_name: str = Field(..., description="Human-readable compliance rule name")
    severity: RiskSeverity = Field(..., description="Severity level governing state machine routing")
    description: str = Field(..., description="Detailed explanation for human reviewer and audit log")
    field_reference: Optional[str] = Field(None, description="Schema field that triggered the rule")


class ConfidenceBreakdown(BaseModel):
    llm_extraction_score: float = Field(..., ge=0.0, le=1.0)
    ocr_fidelity_score: float = Field(..., ge=0.0, le=1.0)
    entity_match_score: float = Field(..., ge=0.0, le=1.0)
    schema_completeness_score: float = Field(..., ge=0.0, le=1.0)
    composite_score: float = Field(..., ge=0.0, le=1.0)
    applied_auto_threshold: float = Field(..., ge=0.0, le=1.0)
    applied_hard_block_floor: float = Field(..., ge=0.0, le=1.0)


class VerificationResponse(BaseModel):
    case_id: str
    workflow_type: WorkflowType
    timestamp_utc: str
    routing_decision: RoutingDecision
    composite_confidence: float
    confidence_breakdown: ConfidenceBreakdown
    extracted_profile: ExtractedEntityProfile
    policy_flags: List[PolicyFlag]
    target_sla_minutes: int
    audit_event_hash: str
    processing_latency_ms: float


class ReviewerAction(str, Enum):
    APPROVE = "APPROVE"
    OVERRIDE_AND_APPROVE = "OVERRIDE_AND_APPROVE"
    REJECT = "REJECT"
    ESCALATE_COMPLIANCE = "ESCALATE_COMPLIANCE"


class HumanReviewSubmission(BaseModel):
    case_id: str
    reviewer_id: str = Field(..., description="Authenticated operator or underwriter ID")
    action: ReviewerAction
    override_fields: Optional[Dict[str, Any]] = Field(default=None, description="Corrected fields if overridden by human reviewer")
    reviewer_notes: str = Field(..., min_length=5, description="Mandatory audit justification for GDPR Art. 22 / SOC 2")
    review_duration_seconds: int = Field(default=180, ge=1)


class AuditLogEntry(BaseModel):
    event_id: str
    timestamp_utc: str
    case_id: str
    workflow_type: str
    actor: str
    event_type: str
    decision: str
    payload_summary: Dict[str, Any]
    prev_hash: str
    event_hash: str
