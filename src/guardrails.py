"""Deterministic 10-Rule Policy Engine, Dual-Track Confidence Scorer & State Machine."""
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Tuple, Dict, Any
from src.schemas import (
    VerificationIntakeRequest,
    ExtractedEntityProfile,
    PolicyFlag,
    RiskSeverity,
    ConfidenceBreakdown,
    RoutingDecision,
    WorkflowType,
)

DEFAULT_CONFIG_PATH = Path("configs/fintech_lending_policy.yaml")

DEFAULT_POLICY_CONFIG: Dict[str, Any] = {
    "reference_domain": "fintech_digital_lending",
    "schema_version": "1.0.0",
    "confidence_weights": {
        "llm_extraction": 0.35,
        "ocr_fidelity": 0.20,
        "entity_match": 0.30,
        "schema_completeness": 0.15,
    },
    "workflow_profiles": {
        "CONSUMER_KYC": {
            "description": "Individual Consumer Micro-Loan Identity & Income Verification",
            "auto_approval_threshold": 0.90,
            "hard_block_floor": 0.65,
            "target_sla_minutes": {
                "AUTO_APPROVED": 0,
                "HITL_TIER_1_REVIEW": 60,
                "HARD_BLOCK_ESCALATED": 30,
            },
            "illustrative_unit_economics_usd": {
                "legacy_manual_cost": 6.50,
                "automated_stp_cost": 0.12,
                "hitl_assisted_cost": 1.85,
            },
        },
        "SME_KYB": {
            "description": "SME Merchant Credit Line Corporate Registry, Tax & UBO Verification",
            "auto_approval_threshold": 0.93,
            "hard_block_floor": 0.70,
            "target_sla_minutes": {
                "AUTO_APPROVED": 0,
                "HITL_TIER_1_REVIEW": 240,
                "HARD_BLOCK_ESCALATED": 60,
            },
            "illustrative_unit_economics_usd": {
                "legacy_manual_cost": 18.00,
                "automated_stp_cost": 0.25,
                "hitl_assisted_cost": 4.20,
            },
        },
    },
    "compliance_lists": {
        "sanctioned_jurisdictions": ["KP", "IR", "SY", "MM", "RU"],
        "enhanced_due_diligence_jurisdictions": ["VG", "KY", "PA", "BZ"],
        "minimum_id_length": 6,
        "entity_similarity_threshold_high_risk": 0.55,
        "entity_similarity_threshold_medium_risk": 0.78,
        "reference_verification_date": "2026-11-01",
    },
}

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+all\s+previous\s+instructions",
    r"system\s+override",
    r"auto[\s_-]*approve\s+this",
    r"set\s+confidence\s+to\s+1\.0",
    r"bypass\s+compliance",
]


def load_policy_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load externalized YAML policy configuration (with zero-dependency fallback)."""
    if config_path.exists():
        try:
            import yaml
            return yaml.safe_load(config_path.read_text())
        except ImportError:
            return DEFAULT_POLICY_CONFIG
    return DEFAULT_POLICY_CONFIG


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute normalized sequence similarity between declared and extracted names."""
    clean_a = re.sub(r"[^a-z0-9]", "", name_a.lower())
    clean_b = re.sub(r"[^a-z0-9]", "", name_b.lower())
    if not clean_a or not clean_b:
        return 0.0
    return round(SequenceMatcher(None, clean_a, clean_b).ratio(), 4)


def evaluate_policy_guardrails(
    intake: VerificationIntakeRequest,
    extracted: ExtractedEntityProfile,
    config: Dict[str, Any] = None,
) -> List[PolicyFlag]:
    """
    Execute 10 deterministic compliance rules (POL-001 through POL-010).
    Deterministic policy rules always supersede probabilistic LLM confidence scores.
    """
    cfg = config or load_policy_config()
    lists = cfg["compliance_lists"]
    sanctioned_set = set(lists["sanctioned_jurisdictions"])
    min_id_len = int(lists.get("minimum_id_length", 6))
    ref_date = str(lists.get("reference_verification_date", "2026-11-01"))

    flags: List[PolicyFlag] = []

    # POL-001: Adversarial Prompt Injection / Instruction Override
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, intake.raw_document_text, re.IGNORECASE):
            flags.append(
                PolicyFlag(
                    rule_id="POL-001",
                    rule_name="Adversarial Prompt Injection Detected",
                    severity=RiskSeverity.CRITICAL,
                    description=f"Untrusted document text contains instruction-override pattern matching '{pattern}'.",
                    field_reference="raw_document_text",
                )
            )
            break

    # POL-002: OFAC / FATF Sanctioned Jurisdiction Match
    if (
        extracted.extracted_jurisdiction.upper() in sanctioned_set
        or intake.declared_jurisdiction.upper() in sanctioned_set
    ):
        flags.append(
            PolicyFlag(
                rule_id="POL-002",
                rule_name="Sanctioned Jurisdiction Match (OFAC/FATF)",
                severity=RiskSeverity.CRITICAL,
                description=(
                    f"Declared ({intake.declared_jurisdiction}) or extracted ({extracted.extracted_jurisdiction}) "
                    "jurisdiction is on the restricted sanctions list."
                ),
                field_reference="extracted_jurisdiction",
            )
        )

    # POL-003: Cross-Field Jurisdiction Mismatch
    if intake.declared_jurisdiction.upper() != extracted.extracted_jurisdiction.upper():
        flags.append(
            PolicyFlag(
                rule_id="POL-003",
                rule_name="Declared vs. Extracted Jurisdiction Mismatch",
                severity=RiskSeverity.HIGH,
                description=(
                    f"Applicant declared jurisdiction '{intake.declared_jurisdiction}' but document "
                    f"evidence indicates '{extracted.extracted_jurisdiction}'."
                ),
                field_reference="extracted_jurisdiction",
            )
        )

    # POL-004: Missing or Malformed Primary Identification / Registration Number
    if not extracted.primary_id_number or len(extracted.primary_id_number.strip()) < min_id_len:
        flags.append(
            PolicyFlag(
                rule_id="POL-004",
                rule_name="Missing or Malformed Primary ID / Registration Number",
                severity=RiskSeverity.HIGH,
                description=(
                    f"Primary ID/Registration number is missing or shorter than minimum policy length ({min_id_len} chars)."
                ),
                field_reference="primary_id_number",
            )
        )

    # POL-005: Applicant / Legal Entity Name Discrepancy
    similarity = compute_name_similarity(intake.applicant_name, extracted.extracted_name)
    med_thresh = float(lists.get("entity_similarity_threshold_medium_risk", 0.78))
    high_thresh = float(lists.get("entity_similarity_threshold_high_risk", 0.55))
    if similarity < med_thresh:
        flags.append(
            PolicyFlag(
                rule_id="POL-005",
                rule_name="Applicant / Entity Name Discrepancy",
                severity=RiskSeverity.MEDIUM if similarity >= high_thresh else RiskSeverity.HIGH,
                description=(
                    f"Declared name '{intake.applicant_name}' diverges from extracted name "
                    f"'{extracted.extracted_name}' (similarity={similarity:.2f} < {med_thresh})."
                ),
                field_reference="extracted_name",
            )
        )

    # SME_KYB Specific Corporate Governance Rules (POL-006, POL-007, POL-008, POL-009)
    if intake.workflow_type == WorkflowType.SME_KYB:
        total_ubo_pct = sum(u.ownership_pct for u in extracted.ubos)
        if not extracted.ubos:
            flags.append(
                PolicyFlag(
                    rule_id="POL-006",
                    rule_name="Missing Ultimate Beneficial Owner (UBO) Disclosure",
                    severity=RiskSeverity.MEDIUM,
                    description="SME_KYB policy requires at least one disclosed UBO (>25% control); none extracted.",
                    field_reference="ubos",
                )
            )
        elif total_ubo_pct > 100.01:
            flags.append(
                PolicyFlag(
                    rule_id="POL-007",
                    rule_name="Invalid UBO Ownership Sum (>100%)",
                    severity=RiskSeverity.HIGH,
                    description=f"Extracted UBO ownership percentages sum to {total_ubo_pct:.1f}%, exceeding 100.0%.",
                    field_reference="ubos",
                )
            )

        for ubo in extracted.ubos:
            if ubo.pep_flagged:
                flags.append(
                    PolicyFlag(
                        rule_id="POL-008",
                        rule_name="Politically Exposed Person (PEP) Identified",
                        severity=RiskSeverity.HIGH,
                        description=f"Beneficial owner '{ubo.full_name}' is flagged as a Politically Exposed Person.",
                        field_reference="ubos",
                    )
                )
            if ubo.nationality.upper() in sanctioned_set:
                flags.append(
                    PolicyFlag(
                        rule_id="POL-009",
                        rule_name="Sanctioned Beneficial Owner Nationality",
                        severity=RiskSeverity.CRITICAL,
                        description=f"UBO '{ubo.full_name}' holds nationality in a sanctioned jurisdiction ({ubo.nationality}).",
                        field_reference="ubos",
                    )
                )

    # POL-010: Expired Verification Document
    if extracted.document_expiry_date and extracted.document_expiry_date < ref_date:
        flags.append(
            PolicyFlag(
                rule_id="POL-010",
                rule_name="Expired Verification Document",
                severity=RiskSeverity.HIGH,
                description=(
                    f"Document expiry date ({extracted.document_expiry_date}) is prior to the reference "
                    f"verification date ({ref_date})."
                ),
                field_reference="document_expiry_date",
            )
        )

    return flags


def calculate_confidence(
    intake: VerificationIntakeRequest,
    extracted: ExtractedEntityProfile,
    config: Dict[str, Any] = None,
) -> ConfidenceBreakdown:
    """Calculate weighted multi-dimensional confidence score configured per workflow track."""
    cfg = config or load_policy_config()
    weights = cfg["confidence_weights"]
    profile_cfg = cfg["workflow_profiles"][intake.workflow_type.value]

    entity_match = compute_name_similarity(intake.applicant_name, extracted.extracted_name)

    if intake.workflow_type == WorkflowType.SME_KYB:
        mandatory_fields = [
            bool(extracted.extracted_name),
            bool(extracted.primary_id_number),
            bool(extracted.issuance_or_incorporation_date),
            bool(extracted.extracted_jurisdiction),
            bool(extracted.registered_address),
            len(extracted.ubos) > 0,
        ]
    else:
        mandatory_fields = [
            bool(extracted.extracted_name),
            bool(extracted.primary_id_number),
            bool(extracted.issuance_or_incorporation_date),
            bool(extracted.extracted_jurisdiction),
            bool(extracted.registered_address),
        ]

    completeness = round(sum(mandatory_fields) / float(len(mandatory_fields)), 4)

    composite = round(
        weights["llm_extraction"] * extracted.extraction_confidence
        + weights["ocr_fidelity"] * intake.ocr_quality_score
        + weights["entity_match"] * entity_match
        + weights["schema_completeness"] * completeness,
        4,
    )

    return ConfidenceBreakdown(
        llm_extraction_score=round(extracted.extraction_confidence, 4),
        ocr_fidelity_score=round(intake.ocr_quality_score, 4),
        entity_match_score=entity_match,
        schema_completeness_score=completeness,
        composite_score=composite,
        applied_auto_threshold=float(profile_cfg["auto_approval_threshold"]),
        applied_hard_block_floor=float(profile_cfg["hard_block_floor"]),
    )


def determine_routing(
    workflow_type: WorkflowType,
    confidence: ConfidenceBreakdown,
    flags: List[PolicyFlag],
    config: Dict[str, Any] = None,
) -> Tuple[RoutingDecision, int]:
    """
    Deterministic Risk-Tiered State Machine:
    - CRITICAL flag OR composite < hard_block_floor -> HARD_BLOCK_ESCALATED
    - HIGH/MEDIUM flag OR composite < auto_approval_threshold -> HITL_TIER_1_REVIEW
    - Zero flags AND composite >= auto_approval_threshold -> AUTO_APPROVED
    """
    cfg = config or load_policy_config()
    profile_cfg = cfg["workflow_profiles"][workflow_type.value]
    slas = profile_cfg["target_sla_minutes"]

    severities = {f.severity for f in flags}

    if RiskSeverity.CRITICAL in severities or confidence.composite_score < confidence.applied_hard_block_floor:
        return RoutingDecision.HARD_BLOCK_ESCALATED, int(slas["HARD_BLOCK_ESCALATED"])

    if (
        RiskSeverity.HIGH in severities
        or RiskSeverity.MEDIUM in severities
        or confidence.composite_score < confidence.applied_auto_threshold
    ):
        return RoutingDecision.HITL_TIER_1_REVIEW, int(slas["HITL_TIER_1_REVIEW"])

    return RoutingDecision.AUTO_APPROVED, int(slas["AUTO_APPROVED"])
