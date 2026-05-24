"""Pydantic schemas. Mirror the OSS RepairEvent shape on the ingest side
and shape the dashboard responses on the read side.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

EventType = Literal[
    "attempt_start",
    "attempt_failed",
    "propose_start",
    "propose_chunk",
    "propose_complete",
    "install_success",
    "install_failed",
    "cache_hit",
    "cache_miss",
    "safety_violation",
    "verify_success",
    "repair_succeeded",
    "repair_exhausted",
]

RunStatus = Literal["in_progress", "succeeded", "exhausted"]


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class IngestEvent(BaseModel):
    """Single event as sent by the OSS ControlPlaneClient."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=8, max_length=64)
    ts: datetime
    run_key: str = Field(..., min_length=1, max_length=128)
    type: EventType
    function_name: str = Field(..., min_length=1, max_length=300)
    module_name: str | None = Field(default=None, max_length=300)
    attempt_number: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestBatch(BaseModel):
    events: list[IngestEvent] = Field(..., min_length=1, max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    duplicates: int
    runs: list[uuid.UUID]


# ---------------------------------------------------------------------------
# Read (audit log)
# ---------------------------------------------------------------------------


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    function_name: str
    module_name: str | None
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None
    attempts: int


class EventRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    type: EventType
    attempt_number: int | None
    payload: dict[str, Any]


class RunDetail(RunSummary):
    final_error: str | None
    final_source: str | None
    events: list[EventRecord]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    sent: bool = True


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyCondition(BaseModel):
    """A single condition. Multiple conditions on a rule are AND-ed."""

    model_config = ConfigDict(extra="forbid")

    field: Literal["type", "function_name", "module_name", "error_message", "attempt_number"]
    op: Literal["eq", "ne", "contains", "regex", "gte", "lte"]
    value: str | int


class PolicyRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    enabled: bool = True
    priority: int = 100
    conditions: list[PolicyCondition] = Field(default_factory=list)
    action: Literal["allow", "block", "notify"] = "notify"


class PolicyRuleOut(PolicyRuleIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PolicyEvaluateRequest(BaseModel):
    event: IngestEvent


class PolicyDecision(BaseModel):
    action: Literal["allow", "block", "notify"] = "allow"
    matched_rule_id: uuid.UUID | None = None
    matched_rule_name: str | None = None
