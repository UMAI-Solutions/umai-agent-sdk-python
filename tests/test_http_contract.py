from __future__ import annotations

import json
import asyncio

import httpx
import pytest

from umai import AgentIdentity, UmaiBlockedError, UmaiClient, UmaiUnavailableError
from umai.stores import MemoryIdentityStore


def registered_identity() -> AgentIdentity:
    identity = AgentIdentity.generate("agent-1")
    identity.tenant_id = "tenant-1"
    identity.environment_id = "dev"
    identity.project_id = "project"
    identity.agent_did = "did:umai:test:agent-1"
    identity.public_key_fingerprint = "sha256:test"
    return identity


def test_start_record_guard_complete_contract() -> None:
    asyncio.run(_start_record_guard_complete_contract())


async def _start_record_guard_complete_contract() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        seen.append({"path": request.url.path, "body": body})
        if request.url.path == "/api/v1/agent-runs":
            return httpx.Response(
                200,
                json={
                    "tenant_id": "tenant-1",
                    "environment_id": "dev",
                    "project_id": "project",
                    "run_id": body["run_id"],
                    "agent_id": "agent-1",
                    "agent_did": "did:umai:test:agent-1",
                    "status": "RUNNING",
                },
            )
        if request.url.path.endswith("/steps"):
            return httpx.Response(
                200,
                json={
                    "run_id": "run-1",
                    "step_id": body["step_id"],
                    "sequence": 1,
                    "event_type": body["event_type"],
                    "status": body["status"],
                    "agent_id": "agent-1",
                    "agent_did": "did:umai:test:agent-1",
                },
            )
        if request.url.path.endswith("/guard"):
            assert body["input"]["language"] is None
            assert body["agent_context"]["signature"]
            return httpx.Response(
                200,
                json={
                    "request_id": "req-1",
                    "decision": {
                        "action": "ALLOW",
                        "allowed": True,
                        "severity": "LOW",
                        "reason": "ok",
                    },
                    "latency_ms": 1,
                    "errors": [],
                },
            )
        if request.method == "PATCH":
            return httpx.Response(
                200,
                json={
                    "tenant_id": "tenant-1",
                    "environment_id": "dev",
                    "project_id": "project",
                    "run_id": "run-1",
                    "agent_id": "agent-1",
                    "agent_did": "did:umai:test:agent-1",
                    "status": body["status"],
                },
            )
        return httpx.Response(404, json={"error": {"type": "NOT_FOUND", "message": "missing"}})

    client = UmaiClient(
        endpoint="https://umai.example",
        api_key="uk_test",
        transport=httpx.MockTransport(handler),
    )
    agent = client.agent("agent-1", identity_store=MemoryIdentityStore(registered_identity()))
    run = await agent.start_run(run_id="run-1", guardrail_id="gr-1")
    step = await agent.record_step(run_id=run.run_id, step_id="step-1", event_type="agent_start")
    guard = await agent.guard(
        guardrail_id="gr-1",
        phase="PRE_LLM",
        run_id=run.run_id,
        step_id="guard-1",
        messages=[{"role": "user", "content": "hello"}],
        phase_focus="LAST_USER_MESSAGE",
    )
    completed = await agent.complete_run(run.run_id)
    assert step.step_id == "step-1"
    assert guard.decision.action == "ALLOW"
    assert completed.status == "COMPLETED"
    assert [item["path"] for item in seen] == [
        "/api/v1/agent-runs",
        "/api/v1/agent-runs/run-1/steps",
        "/api/v1/guardrails/gr-1/guard",
        "/api/v1/agent-runs/run-1",
    ]


def test_guard_block_raises_typed_error() -> None:
    asyncio.run(_guard_block_raises_typed_error())


async def _guard_block_raises_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "request_id": "req-1",
                "decision": {
                    "action": "BLOCK",
                    "allowed": False,
                    "severity": "HIGH",
                    "reason": "blocked",
                },
                "latency_ms": 1,
                "errors": [],
            },
        )

    agent = UmaiClient(
        endpoint="https://umai.example",
        api_key="uk_test",
        transport=httpx.MockTransport(handler),
    ).agent("agent-1", identity_store=MemoryIdentityStore(registered_identity()))
    with pytest.raises(UmaiBlockedError):
        await agent.guard(
            guardrail_id="gr-1",
            phase="PRE_LLM",
            run_id="run-1",
            step_id="step-1",
            messages=[{"role": "user", "content": "hello"}],
            phase_focus="LAST_USER_MESSAGE",
        )


def test_unavailable_fail_open_returns_warning_decision() -> None:
    asyncio.run(_unavailable_fail_open_returns_warning_decision())


async def _unavailable_fail_open_returns_warning_decision() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    agent = UmaiClient(
        endpoint="https://umai.example",
        api_key="uk_test",
        fail_closed=False,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    ).agent("agent-1", identity_store=MemoryIdentityStore(registered_identity()))
    result = await agent.guard(
        guardrail_id="gr-1",
        phase="PRE_LLM",
        run_id="run-1",
        step_id="step-1",
        messages=[{"role": "user", "content": "hello"}],
        phase_focus="LAST_USER_MESSAGE",
    )
    assert result.decision.allowed is True
    assert result.decision.action == "ALLOW_WITH_WARNINGS"


def test_unavailable_fail_closed_raises() -> None:
    asyncio.run(_unavailable_fail_closed_raises())


async def _unavailable_fail_closed_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    agent = UmaiClient(
        endpoint="https://umai.example",
        api_key="uk_test",
        max_retries=0,
        transport=httpx.MockTransport(handler),
    ).agent("agent-1", identity_store=MemoryIdentityStore(registered_identity()))
    with pytest.raises(UmaiUnavailableError):
        await agent.guard(
            guardrail_id="gr-1",
            phase="PRE_LLM",
            run_id="run-1",
            step_id="step-1",
            messages=[{"role": "user", "content": "hello"}],
            phase_focus="LAST_USER_MESSAGE",
        )
