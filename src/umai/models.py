from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

GuardrailPhase = Literal[
    "PRE_LLM",
    "POST_LLM",
    "TOOL_INPUT",
    "TOOL_OUTPUT",
    "MCP_REQUEST",
    "MCP_RESPONSE",
    "MEMORY_WRITE",
]

GuardrailAction = Literal[
    "ALLOW",
    "BLOCK",
    "FLAG",
    "ALLOW_WITH_MODIFICATIONS",
    "ALLOW_WITH_WARNINGS",
    "STEP_UP_APPROVAL",
]

AgentRunStatus = Literal["RUNNING", "COMPLETED", "FAILED", "CANCELED", "TIMEOUT"]
AgentStepStatus = Literal["RECORDED", "RUNNING", "COMPLETED", "FAILED", "BLOCKED", "WARNED"]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class InputArtifact(BaseModel):
    artifact_type: Literal[
        "TOOL_INPUT",
        "TOOL_OUTPUT",
        "MCP_REQUEST",
        "MCP_RESPONSE",
        "MEMORY_WRITE",
        "CUSTOM",
    ] = "CUSTOM"
    name: str | None = None
    payload_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputPayload(BaseModel):
    messages: list[ChatMessage | dict[str, str]]
    phase_focus: Literal["LAST_USER_MESSAGE", "LAST_ASSISTANT_MESSAGE"]
    content_type: Literal["text", "markdown", "json"] = "text"
    language: str | None = None
    artifacts: list[InputArtifact | dict[str, Any]] = Field(default_factory=list)


class AgentContext(BaseModel):
    agent_id: str
    agent_did: str
    nonce: str
    signed_at: str
    signature: str
    run_id: str | None = None
    step_id: str | None = None
    parent_step_id: str | None = None
    public_key_fingerprint: str | None = None


class GuardDecision(BaseModel):
    action: GuardrailAction
    allowed: bool
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    reason: str


class TriggeringPolicy(BaseModel):
    policy_id: str
    type: str
    status: str


class GuardResponse(BaseModel):
    request_id: str
    decision: GuardDecision
    category: str | None = None
    triggering_policy: TriggeringPolicy | None = None
    output_modifications: dict[str, Any] | None = None
    latency_ms: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class AgentRun(BaseModel):
    tenant_id: str
    environment_id: str
    project_id: str
    run_id: str
    agent_id: str
    agent_did: str
    guardrail_id: str | None = None
    status: str
    decision_action: str | None = None
    decision_severity: str | None = None
    trust_score: float | None = None
    trust_tier: str | None = None
    summary: dict[str, Any] | None = None
    started_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None


class AgentStep(BaseModel):
    run_id: str
    step_id: str
    parent_step_id: str | None = None
    sequence: int
    event_type: str
    phase: str | None = None
    status: str
    agent_id: str
    agent_did: str
    action: str | None = None
    resource_type: str | None = None
    resource_name: str | None = None
    decision_action: str | None = None
    decision_severity: str | None = None
    decision_reason: str | None = None
    policy_id: str | None = None
    matched_rule_id: str | None = None
    latency_ms: float | None = None
    payload_summary: str | None = None
    metadata: dict[str, Any] | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    prev_step_hash: str | None = None
    step_hash: str | None = None
    created_at: dt.datetime | None = None

