from dataclasses import dataclass, field
from typing import Any


@dataclass
class PantheonResult:
    response: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    actions_proposed: list[str] = field(default_factory=list)
    provider_used: str = ""
    model_used: str = ""
    grounded: bool = False
    degraded: bool = False
    degraded_reason: str = ""
    latency_ms: int | None = None
    audit_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "sources": self.sources,
            "tools_used": self.tools_used,
            "actions_taken": self.actions_taken,
            "actions_proposed": self.actions_proposed,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "grounded": self.grounded,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "latency_ms": self.latency_ms,
            "audit_id": self.audit_id,
        }
