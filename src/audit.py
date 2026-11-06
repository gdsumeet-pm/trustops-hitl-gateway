"""Tamper-Evident SHA-256 Cryptographic Audit Ledger (SOC 2 Type II / ISO 27001 / GDPR Art. 22)."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.schemas import AuditLogEntry

DEFAULT_AUDIT_PATH = Path("data/audit_log.jsonl")


class TamperEvidentAuditLogger:
    """Append-only JSON-L audit logger using SHA-256 hash chaining."""

    def __init__(self, log_path: Path = DEFAULT_AUDIT_PATH):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("")

    def _get_last_hash(self) -> str:
        lines = [line.strip() for line in self.log_path.read_text().splitlines() if line.strip()]
        if not lines:
            return "0" * 64  # Genesis block hash
        return json.loads(lines[-1])["event_hash"]

    @staticmethod
    def _compute_hash(payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def log_event(
        self,
        case_id: str,
        workflow_type: str,
        actor: str,
        event_type: str,
        decision: str,
        payload_summary: Dict[str, Any],
    ) -> AuditLogEntry:
        prev_hash = self._get_last_hash()
        event_id = f"EVT-{uuid.uuid4().hex[:10].upper()}"
        timestamp_utc = datetime.now(timezone.utc).isoformat()

        hash_input = {
            "event_id": event_id,
            "timestamp_utc": timestamp_utc,
            "case_id": case_id,
            "workflow_type": workflow_type,
            "actor": actor,
            "event_type": event_type,
            "decision": decision,
            "payload_summary": payload_summary,
            "prev_hash": prev_hash,
        }
        event_hash = self._compute_hash(hash_input)
        entry = AuditLogEntry(**hash_input, event_hash=event_hash)

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry

    def get_events(self, case_id: str = None) -> List[AuditLogEntry]:
        lines = [line.strip() for line in self.log_path.read_text().splitlines() if line.strip()]
        entries = [AuditLogEntry(**json.loads(line)) for line in lines]
        if case_id:
            return [e for e in entries if e.case_id == case_id]
        return entries

    def verify_chain_integrity(self) -> Tuple[bool, int, str]:
        """Verify SHA-256 chain integrity across all recorded audit events."""
        entries = self.get_events()
        expected_prev = "0" * 64
        for idx, entry in enumerate(entries):
            if entry.prev_hash != expected_prev:
                return (
                    False,
                    idx,
                    f"Broken chain link at {entry.event_id}: expected prev_hash {expected_prev}, got {entry.prev_hash}",
                )
            hash_input = {
                "event_id": entry.event_id,
                "timestamp_utc": entry.timestamp_utc,
                "case_id": entry.case_id,
                "workflow_type": entry.workflow_type,
                "actor": entry.actor,
                "event_type": entry.event_type,
                "decision": entry.decision,
                "payload_summary": entry.payload_summary,
                "prev_hash": entry.prev_hash,
            }
            if self._compute_hash(hash_input) != entry.event_hash:
                return False, idx, f"Payload tamper detected at event {entry.event_id}"
            expected_prev = entry.event_hash
        return True, len(entries), "CRYPTOGRAPHIC_CHAIN_VERIFIED"
