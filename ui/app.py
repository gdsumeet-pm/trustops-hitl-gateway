"""Streamlit Reviewer Workbench & AI Governance Console for TrustOps v1.0."""
import json
from pathlib import Path
import streamlit as st
from src.schemas import (
    VerificationIntakeRequest,
    WorkflowType,
    HumanReviewSubmission,
    ReviewerAction,
)
from src.pipeline import TrustOpsPipeline

st.set_page_config(
    page_title="TrustOps v1.0 | Enterprise AI Policy & HITL Verification Gateway",
    layout="wide",
)

if "pipeline" not in st.session_state:
    pipeline = TrustOpsPipeline()
    golden_path = Path("evals/golden_dataset.json")
    if golden_path.exists() and len(pipeline.review_queue) == 0 and len(pipeline.completed_cases) == 0:
        cases = json.loads(golden_path.read_text())
        # Pre-seed a balanced sample of Consumer KYC and SME KYB cases
        for item in cases[:8] + cases[15:25]:
            payload = {k: v for k, v in item.items() if k not in ("category", "expected_routing")}
            req = VerificationIntakeRequest(**payload)
            pipeline.verify_case(req)
    st.session_state.pipeline = pipeline

pipeline: TrustOpsPipeline = st.session_state.pipeline

st.title("TrustOps v1.0: Enterprise AI Policy & HITL Verification Gateway")
st.caption(
    "Open-Source Reference Architecture | Dual-Track FinTech Lending (Consumer Micro-Loan KYC & SME Merchant KYB) | "
    "10-Rule Deterministic Guardrails | SHA-256 Cryptographic Audit Ledger"
)

tab1, tab2, tab3, tab4 = st.tabs([
    "1. Live Dual-Track Intake & Guardrail Inspector",
    "2. Human-in-the-Loop (HITL) Reviewer Workbench",
    "3. Tamper-Evident SHA-256 Audit Ledger",
    "4. Reference Config & Evaluation Telemetry",
])

with tab1:
    st.subheader("Simulate Unstructured Document Intake (Consumer KYC vs. SME KYB)")
    col1, col2 = st.columns(2)
    with col1:
        wf_type = st.selectbox(
            "Select Risk Profile Track (from configs/fintech_lending_policy.yaml)",
            [WorkflowType.SME_KYB.value, WorkflowType.CONSUMER_KYC.value],
        )
        case_id = st.text_input("Transaction / Case ID", value="KYB-LIVE-901")
        applicant_name = st.text_input("Declared Applicant / Business Name", value="Orion MedTech Systems Ltd")
        declared_jur = st.text_input("Declared ISO-2 Jurisdiction", value="GB")
        doc_type = st.text_input("Document Type", value="CERTIFICATE_OF_INCORPORATION")
        ocr_score = st.slider("Upstream OCR Fidelity Score", 0.35, 1.00, 0.94, 0.01)
        raw_text = st.text_area(
            "Raw OCR Document Payload",
            height=190,
            value=(
                "ENTITY_NAME: Orion MedTech Systems Ltd\n"
                "REG_NO: NONE\n"
                "JURISDICTION: GB\n"
                "INC_DATE: 2021-05-14\n"
                "EXP_DATE: 2029-05-14\n"
                "ADDRESS: 100 Bishopsgate, London\n"
                "MODEL_CONF: 0.92\n"
                "UBO: Dr. Aris Thorne,65.0,GB,False"
            ),
        )
        if st.button("Execute TrustOps Verification Pipeline", type="primary"):
            req = VerificationIntakeRequest(
                case_id=case_id,
                workflow_type=WorkflowType(wf_type),
                applicant_name=applicant_name,
                declared_jurisdiction=declared_jur,
                document_type=doc_type,
                ocr_quality_score=ocr_score,
                raw_document_text=raw_text,
            )
            res = pipeline.verify_case(req)
            st.session_state.last_result = res

    with col2:
        if "last_result" in st.session_state:
            res = st.session_state.last_result
            st.markdown(f"### Routing Decision: `{res.routing_decision.value}`")
            st.metric(
                "Composite Confidence Score",
                f"{res.composite_confidence:.4f}",
                f"Track Gate: {res.confidence_breakdown.applied_auto_threshold:.2f} | Target SLA: {res.target_sla_minutes} mins",
            )
            st.json(res.confidence_breakdown.model_dump())
            if res.policy_flags:
                st.warning(f"Triggered Deterministic Policy Flags ({len(res.policy_flags)})")
                for f in res.policy_flags:
                    st.markdown(f"- **`{f.rule_id}` [{f.severity.value}]**: {f.rule_name} — {f.description}")
            else:
                st.success("Zero Policy Guardrail Violations Detected.")

with tab2:
    st.subheader("Pending Human Review Queue (Tier-1 Triage & Compliance Escalations)")
    queue_items = list(pipeline.review_queue.values())
    if not queue_items:
        st.info("No pending cases in the HITL Review Queue.")
    else:
        selected_id = st.selectbox(
            "Select Flagged Case for Operator Triage",
            [f"{c.case_id} ({c.workflow_type.value} -> {c.routing_decision.value})" for c in queue_items],
        )
        raw_case_id = selected_id.split(" ")[0]
        active_case = pipeline.review_queue[raw_case_id]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Extracted Structured Profile & Verbatim Snippets")
            st.json(active_case.extracted_profile.model_dump())
        with c2:
            st.markdown("#### Triggered Guardrails & Operator Decision Console")
            for f in active_case.policy_flags:
                st.error(f"**{f.rule_id} [{f.severity.value}]**: {f.description}")
            reviewer_id = st.text_input("Authenticated Operator ID", value="sr.reviewer@enterprise.io")
            action = st.selectbox("Operator Action", [a.value for a in ReviewerAction])
            override_id = st.text_input("Override Primary ID / Registration Number (Optional)", value="")
            notes = st.text_area(
                "Mandatory Audit Justification Notes (GDPR Art. 22 / SOC 2)",
                value="Verified primary registry extract manually; secondary documentary evidence attached.",
            )
            if st.button("Commit Decision to SHA-256 Cryptographic Audit Log"):
                sub = HumanReviewSubmission(
                    case_id=raw_case_id,
                    reviewer_id=reviewer_id,
                    action=ReviewerAction(action),
                    override_fields={"primary_id_number": override_id} if override_id else None,
                    reviewer_notes=notes,
                    review_duration_seconds=240,
                )
                pipeline.submit_human_review(sub)
                st.success(f"Case {raw_case_id} resolved and appended to SHA-256 hash chain.")
                st.rerun()

with tab3:
    st.subheader("Immutable SHA-256 Hash-Chained Audit Ledger")
    valid, count, status = pipeline.audit_logger.verify_chain_integrity()
    st.metric("Cryptographic Chain Integrity Status", status, f"{count} Events Verified (Valid={valid})")
    events = [e.model_dump() for e in pipeline.audit_logger.get_events()]
    st.dataframe(events, use_container_width=True)

with tab4:
    st.subheader("Externalized Reference Policy Configuration & Benchmark Telemetry")
    st.markdown("#### Active YAML Policy (`configs/fintech_lending_policy.yaml`)")
    st.json(pipeline.config)
    eval_report = Path("evals/eval_results.md")
    if eval_report.exists():
        st.markdown("---")
        st.markdown(eval_report.read_text())
