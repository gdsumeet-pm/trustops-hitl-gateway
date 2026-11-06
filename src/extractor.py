"""Structured Extraction Gateway (Supports Live OpenAI Structured Outputs + Deterministic Offline Parser)."""
import os
import re
from typing import List
from src.schemas import VerificationIntakeRequest, ExtractedEntityProfile, UBOEntry


def _deterministic_offline_extract(intake: VerificationIntakeRequest) -> ExtractedEntityProfile:
    """
    Deterministic parser for zero-key CI/CD benchmarking, unit testing, and live interview demos.
    """
    text = intake.raw_document_text

    name_match = re.search(r"(?:NAME|ENTITY_NAME):\s*([^\n|]+)", text)
    extracted_name = name_match.group(1).strip() if name_match else intake.applicant_name

    id_match = re.search(r"(?:ID_NO|PAN|REG_NO):\s*([^\n|]+)", text)
    primary_id = id_match.group(1).strip() if id_match else None
    if primary_id in ("NONE", "NULL", "N/A", ""):
        primary_id = None

    jur_match = re.search(r"JURISDICTION:\s*([A-Z]{2})", text)
    jurisdiction = jur_match.group(1).strip() if jur_match else intake.declared_jurisdiction

    iss_match = re.search(r"(?:ISS_DATE|INC_DATE):\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text)
    iss_date = iss_match.group(1).strip() if iss_match else None

    exp_match = re.search(r"EXP_DATE:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text)
    exp_date = exp_match.group(1).strip() if exp_match else None

    addr_match = re.search(r"ADDRESS:\s*([^\n|]+)", text)
    address = addr_match.group(1).strip() if addr_match else None

    conf_match = re.search(r"MODEL_CONF:\s*([0-9.]+)", text)
    model_conf = float(conf_match.group(1)) if conf_match else min(0.98, intake.ocr_quality_score + 0.03)

    ubos: List[UBOEntry] = []
    for ubo_m in re.finditer(r"UBO:\s*([^,]+),([0-9.]+),([A-Z]{2}),(True|False)", text):
        ubos.append(
            UBOEntry(
                full_name=ubo_m.group(1).strip(),
                ownership_pct=float(ubo_m.group(2)),
                nationality=ubo_m.group(3).strip(),
                pep_flagged=(ubo_m.group(4) == "True"),
            )
        )

    snippets = {
        "extracted_name": f"NAME: {extracted_name}",
        "primary_id_number": f"ID_NO: {primary_id or 'MISSING'}",
        "extracted_jurisdiction": f"JURISDICTION: {jurisdiction}",
    }

    return ExtractedEntityProfile(
        extracted_name=extracted_name,
        primary_id_number=primary_id,
        issuance_or_incorporation_date=iss_date,
        document_expiry_date=exp_date,
        extracted_jurisdiction=jurisdiction,
        registered_address=address,
        ubos=ubos,
        extraction_confidence=model_conf,
        source_snippets=snippets,
    )


def extract_entity_profile(intake: VerificationIntakeRequest) -> ExtractedEntityProfile:
    """
    Extract structured KYC/KYB profile from unstructured document text.
    Uses OpenAI Structured Outputs when TRUSTOPS_LIVE_LLM=1 and OPENAI_API_KEY is set;
    otherwise uses the deterministic offline parser for reproducible evaluation runs.
    """
    if os.getenv("TRUSTOPS_LIVE_LLM") == "1" and os.getenv("OPENAI_API_KEY"):
        from openai import OpenAI

        client = OpenAI()
        completion = client.beta.chat.completions.parse(
            model=os.getenv("TRUSTOPS_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an enterprise FinTech KYC/KYB extraction engine. Extract the entity "
                        "profile strictly from the provided document text. Never fabricate missing fields."
                    ),
                },
                {"role": "user", "content": intake.raw_document_text},
            ],
            response_format=ExtractedEntityProfile,
            temperature=0.0,
        )
        return completion.choices[0].message.parsed

    return _deterministic_offline_extract(intake)
