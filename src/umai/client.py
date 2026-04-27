from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any, Literal

import httpx

from .crypto import object_hash, public_key_fingerprint, utcnow_rfc3339
from .errors import UmaiBlockedError, UmaiError, UmaiUnavailableError, error_from_response
from .identity import AgentIdentity
from .models import AgentContext, AgentRun, AgentStep, GuardResponse, GuardrailPhase, InputArtifact
from .stores import FileIdentityStore, IdentityStore, MemoryIdentityStore

JsonBody = dict[str, Any]
BodyFactory = Callable[[], JsonBody]


class AsyncRawApi:
    def __init__(self, client: "UmaiClient") -> None:
        self._client = client

    async def get(self, path: str) -> JsonBody:
        return await self._client._request_json("GET", path, lambda: {})

    async def post(self, path: str, *, json: JsonBody) -> JsonBody:
        return await self._client._request_json("POST", path, lambda: json)

    async def patch(self, path: str, *, json: JsonBody) -> JsonBody:
        return await self._client._request_json("PATCH", path, lambda: json)


class SyncRawApi:
    def __init__(self, client: "SyncUmaiClient") -> None:
        self._client = client

    def get(self, path: str) -> JsonBody:
        return self._client._request_json("GET", path, lambda: {})

    def post(self, path: str, *, json: JsonBody) -> JsonBody:
        return self._client._request_json("POST", path, lambda: json)

    def patch(self, path: str, *, json: JsonBody) -> JsonBody:
        return self._client._request_json("PATCH", path, lambda: json)


class UmaiClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        base_url: str | None = None,
        api_key: str,
        timeout: float = 30.0,
        fail_closed: bool = True,
        max_retries: int = 2,
        retry_backoff: float = 0.25,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved = endpoint or base_url
        if not resolved:
            raise ValueError("endpoint is required")
        self.endpoint = resolved.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.fail_closed = fail_closed
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.transport = transport
        self.raw = AsyncRawApi(self)

    def agent(
        self,
        agent_id: str,
        *,
        identity_store: IdentityStore | None = None,
        identity: AgentIdentity | None = None,
        allow_plaintext_private_key: bool = False,
    ) -> "AgentMesh":
        if identity is not None:
            store = MemoryIdentityStore(identity)
        else:
            store = identity_store or FileIdentityStore(
                allow_plaintext_private_key=allow_plaintext_private_key
            )
        return AgentMesh(client=self, agent_id=agent_id, identity_store=store)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Umai-Api-Key": self.api_key,
        }

    async def _request_json(self, method: str, path: str, body_factory: BodyFactory) -> JsonBody:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            body = body_factory()
            try:
                async with httpx.AsyncClient(
                    base_url=self.endpoint,
                    headers=self._headers(),
                    timeout=self.timeout,
                    transport=self.transport,
                ) as http:
                    response = await http.request(method, path, json=body if method != "GET" else None)
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff * (2**attempt))
                    continue
                if response.status_code >= 400:
                    raise error_from_response(response)
                parsed = response.json()
                return parsed if isinstance(parsed, dict) else {"data": parsed}
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff * (2**attempt))
                    continue
                raise UmaiUnavailableError(str(exc), retryable=True) from exc
        raise UmaiUnavailableError(str(last_error or "UMAI request failed"), retryable=True)


class SyncUmaiClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        base_url: str | None = None,
        api_key: str,
        timeout: float = 30.0,
        fail_closed: bool = True,
        max_retries: int = 2,
        retry_backoff: float = 0.25,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved = endpoint or base_url
        if not resolved:
            raise ValueError("endpoint is required")
        self.endpoint = resolved.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.fail_closed = fail_closed
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.transport = transport
        self.raw = SyncRawApi(self)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Umai-Api-Key": self.api_key,
        }

    def _request_json(self, method: str, path: str, body_factory: BodyFactory) -> JsonBody:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            body = body_factory()
            try:
                with httpx.Client(
                    base_url=self.endpoint,
                    headers=self._headers(),
                    timeout=self.timeout,
                    transport=self.transport,
                ) as http:
                    response = http.request(method, path, json=body if method != "GET" else None)
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                if response.status_code >= 400:
                    raise error_from_response(response)
                parsed = response.json()
                return parsed if isinstance(parsed, dict) else {"data": parsed}
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                raise UmaiUnavailableError(str(exc), retryable=True) from exc
        raise UmaiUnavailableError(str(last_error or "UMAI request failed"), retryable=True)


class AgentMesh:
    def __init__(self, *, client: UmaiClient, agent_id: str, identity_store: IdentityStore) -> None:
        self.client = client
        self.agent_id = agent_id
        self.identity_store = identity_store
        self.identity = identity_store.load(endpoint=client.endpoint, agent_id=agent_id)

    def _identity(self) -> AgentIdentity:
        if self.identity is None:
            self.identity = AgentIdentity.generate(self.agent_id)
        return self.identity

    def _registered_identity(self) -> AgentIdentity:
        identity = self._identity()
        missing = [
            name
            for name in ("agent_did", "public_key_fingerprint", "tenant_id", "environment_id", "project_id")
            if getattr(identity, name) is None
        ]
        if missing:
            raise ValueError(f"Agent identity is not registered; missing {', '.join(missing)}")
        return identity

    async def register(
        self,
        *,
        bootstrap_token: str,
        display_name: str | None = None,
        runtime: str = "generic",
        capabilities: list[str] | None = None,
        metadata: JsonBody | None = None,
    ) -> AgentIdentity:
        identity = self._identity()
        body = {
            "agent_id": identity.agent_id,
            "bootstrap_token": bootstrap_token,
            "public_key_b64": identity.public_key_b64,
            "display_name": display_name,
            "runtime": runtime,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
        }
        data = await self.client._request_json(
            "POST", "/api/v1/agent-identities/register", lambda: body
        )
        identity.agent_did = data["agent_did"]
        identity.public_key_fingerprint = data["public_key_fingerprint"]
        identity.tenant_id = data["tenant_id"]
        identity.environment_id = data["environment_id"]
        identity.project_id = data["project_id"]
        self.identity_store.save(endpoint=self.client.endpoint, identity=identity)
        return identity

    def agent_context(
        self,
        *,
        event: str,
        body_hash: str,
        run_id: str | None = None,
        step_id: str | None = None,
        parent_step_id: str | None = None,
        extra: JsonBody | None = None,
    ) -> AgentContext:
        identity = self._registered_identity()
        signed_at = utcnow_rfc3339()
        nonce = str(uuid.uuid4())
        payload = {
            "event": event,
            "tenant_id": identity.tenant_id,
            "environment_id": identity.environment_id,
            "project_id": identity.project_id,
            "agent_id": identity.agent_id,
            "agent_did": identity.agent_did,
            "run_id": run_id,
            "step_id": step_id,
            "parent_step_id": parent_step_id,
            "nonce": nonce,
            "signed_at": signed_at,
            "body_hash": body_hash,
        }
        if extra:
            payload.update(extra)
        return AgentContext(
            agent_id=identity.agent_id,
            agent_did=identity.agent_did or "",
            run_id=run_id,
            step_id=step_id,
            parent_step_id=parent_step_id,
            nonce=nonce,
            signed_at=signed_at,
            public_key_fingerprint=identity.public_key_fingerprint,
            signature=identity.sign(payload),
        )

    async def start_run(
        self,
        *,
        run_id: str | None = None,
        guardrail_id: str | None = None,
        metadata: JsonBody | None = None,
    ) -> AgentRun:
        resolved_run_id = run_id or str(uuid.uuid4())

        def body() -> JsonBody:
            request = {
                "run_id": resolved_run_id,
                "guardrail_id": guardrail_id,
                "metadata": metadata or {},
            }
            request["agent_context"] = self.agent_context(
                event="agent_run_start",
                body_hash=object_hash(request),
                run_id=resolved_run_id,
            ).model_dump(mode="json")
            return request

        return AgentRun.model_validate(await self.client._request_json("POST", "/api/v1/agent-runs", body))

    async def record_step(
        self,
        *,
        run_id: str,
        event_type: str,
        step_id: str | None = None,
        parent_step_id: str | None = None,
        phase: GuardrailPhase | None = None,
        status: str = "RECORDED",
        action: str | None = None,
        resource_type: str | None = None,
        resource_name: str | None = None,
        payload_summary: str | None = None,
        metadata: JsonBody | None = None,
        input_hash: str | None = None,
        output_hash: str | None = None,
        latency_ms: float | None = None,
        decision_action: str | None = None,
        decision_severity: str | None = None,
        decision_reason: str | None = None,
        policy_id: str | None = None,
        matched_rule_id: str | None = None,
    ) -> AgentStep:
        resolved_step_id = step_id or str(uuid.uuid4())

        def body() -> JsonBody:
            request = {
                "step_id": resolved_step_id,
                "parent_step_id": parent_step_id,
                "event_type": event_type,
                "phase": phase,
                "status": status,
                "action": action,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "payload_summary": payload_summary,
                "metadata": metadata or {},
                "input_hash": input_hash,
                "output_hash": output_hash,
                "latency_ms": latency_ms,
                "decision_action": decision_action,
                "decision_severity": decision_severity,
                "decision_reason": decision_reason,
                "policy_id": policy_id,
                "matched_rule_id": matched_rule_id,
            }
            request["agent_context"] = self.agent_context(
                event="agent_run_step",
                body_hash=object_hash(request),
                run_id=run_id,
                step_id=resolved_step_id,
                parent_step_id=parent_step_id,
            ).model_dump(mode="json")
            return request

        return AgentStep.model_validate(
            await self.client._request_json("POST", f"/api/v1/agent-runs/{run_id}/steps", body)
        )

    def _normalize_input(
        self,
        *,
        messages: list[dict[str, str]],
        phase_focus: Literal["LAST_USER_MESSAGE", "LAST_ASSISTANT_MESSAGE"],
        content_type: Literal["text", "markdown", "json"] = "text",
        artifacts: list[InputArtifact | dict[str, Any]] | None = None,
        language: str | None = None,
    ) -> JsonBody:
        return {
            "messages": messages,
            "phase_focus": phase_focus,
            "content_type": content_type,
            "language": language,
            "artifacts": [
                artifact.model_dump(mode="json") if isinstance(artifact, InputArtifact) else {
                    "artifact_type": artifact.get("artifact_type", "CUSTOM"),
                    "name": artifact.get("name"),
                    "payload_summary": artifact.get("payload_summary"),
                    "content": artifact.get("content"),
                    "content_type": artifact.get("content_type", "text"),
                    "metadata": artifact.get("metadata") or {},
                }
                for artifact in (artifacts or [])
            ],
        }

    async def guard(
        self,
        *,
        guardrail_id: str,
        phase: GuardrailPhase,
        run_id: str | None,
        step_id: str | None,
        messages: list[dict[str, str]],
        phase_focus: Literal["LAST_USER_MESSAGE", "LAST_ASSISTANT_MESSAGE"],
        artifacts: list[InputArtifact | dict[str, Any]] | None = None,
        parent_step_id: str | None = None,
        conversation_id: str | None = None,
        timeout_ms: int = 1500,
        content_type: Literal["text", "markdown", "json"] = "text",
        language: str | None = None,
    ) -> GuardResponse:
        input_payload = self._normalize_input(
            messages=messages,
            phase_focus=phase_focus,
            content_type=content_type,
            artifacts=artifacts,
            language=language,
        )

        def body() -> JsonBody:
            request = {
                "conversation_id": conversation_id,
                "phase": phase,
                "input": input_payload,
                "timeout_ms": timeout_ms,
            }
            request["agent_context"] = self.agent_context(
                event="guard",
                body_hash=object_hash(request),
                run_id=run_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                extra={"guardrail_id": guardrail_id, "phase": phase},
            ).model_dump(mode="json")
            return request

        try:
            response = GuardResponse.model_validate(
                await self.client._request_json("POST", f"/api/v1/guardrails/{guardrail_id}/guard", body)
            )
        except UmaiUnavailableError:
            if self.client.fail_closed:
                raise
            return GuardResponse(
                request_id=str(uuid.uuid4()),
                decision={
                    "action": "ALLOW_WITH_WARNINGS",
                    "allowed": True,
                    "severity": "MEDIUM",
                    "reason": "UMAI guard unavailable; fail-open mode allowed execution",
                },
                latency_ms=0,
                errors=[{"type": "UMAI_UNAVAILABLE_FAIL_OPEN"}],
            )
        if not response.decision.allowed or response.decision.action == "STEP_UP_APPROVAL":
            raise UmaiBlockedError(
                response.decision.reason,
                error_type=response.decision.action,
                retryable=False,
                response_body=response.model_dump(mode="json"),
            )
        return response

    async def guard_tool_input(
        self,
        *,
        guardrail_id: str,
        run_id: str,
        tool_name: str,
        messages: list[dict[str, str]],
        payload_summary: str,
        step_id: str | None = None,
        parent_step_id: str | None = None,
        metadata: JsonBody | None = None,
    ) -> GuardResponse:
        return await self.guard(
            guardrail_id=guardrail_id,
            phase="TOOL_INPUT",
            run_id=run_id,
            step_id=step_id or str(uuid.uuid4()),
            parent_step_id=parent_step_id,
            messages=messages,
            phase_focus="LAST_ASSISTANT_MESSAGE",
            artifacts=[
                {
                    "artifact_type": "TOOL_INPUT",
                    "name": tool_name,
                    "payload_summary": payload_summary,
                    "metadata": {"tool_name": tool_name, **(metadata or {})},
                }
            ],
            conversation_id=run_id,
        )

    async def guard_tool_output(
        self,
        *,
        guardrail_id: str,
        run_id: str,
        tool_name: str,
        output: str,
        step_id: str | None = None,
        parent_step_id: str | None = None,
        metadata: JsonBody | None = None,
    ) -> GuardResponse:
        return await self.guard(
            guardrail_id=guardrail_id,
            phase="TOOL_OUTPUT",
            run_id=run_id,
            step_id=step_id or str(uuid.uuid4()),
            parent_step_id=parent_step_id,
            messages=[{"role": "assistant", "content": output}],
            phase_focus="LAST_ASSISTANT_MESSAGE",
            artifacts=[
                {
                    "artifact_type": "TOOL_OUTPUT",
                    "name": tool_name,
                    "payload_summary": f"{tool_name} returned {len(output)} characters",
                    "metadata": {"tool_name": tool_name, "output_hash": object_hash(output), **(metadata or {})},
                }
            ],
            conversation_id=run_id,
        )

    async def complete_run(
        self,
        run_id: str,
        *,
        status: str = "COMPLETED",
        decision_action: str | None = None,
        decision_severity: str | None = None,
        summary: JsonBody | None = None,
    ) -> AgentRun:
        def body() -> JsonBody:
            request = {
                "status": status,
                "decision_action": decision_action,
                "decision_severity": decision_severity,
                "summary": summary,
            }
            request["agent_context"] = self.agent_context(
                event="agent_run_update",
                body_hash=object_hash(request),
                run_id=run_id,
            ).model_dump(mode="json")
            return request

        return AgentRun.model_validate(
            await self.client._request_json("PATCH", f"/api/v1/agent-runs/{run_id}", body)
        )


# Backwards-compatible names used by the early local SDK.
class UmaiAgentClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        identity: AgentIdentity,
        timeout: float = 10.0,
        fail_closed: bool = True,
    ) -> None:
        self.identity = identity
        self._client = UmaiClient(
            endpoint=base_url,
            api_key=api_key,
            timeout=timeout,
            fail_closed=fail_closed,
        )
        self._agent = self._client.agent(identity.agent_id, identity=identity)

    def agent_context(self, **kwargs: Any) -> JsonBody:
        return self._agent.agent_context(**kwargs).model_dump(mode="json")

    async def register_identity(self, **kwargs: Any) -> JsonBody:
        identity = await self._agent.register(**kwargs)
        return {
            "tenant_id": identity.tenant_id,
            "environment_id": identity.environment_id,
            "project_id": identity.project_id,
            "agent_id": identity.agent_id,
            "agent_did": identity.agent_did,
            "public_key_fingerprint": identity.public_key_fingerprint,
            "trust_score": 0.0,
            "trust_tier": "",
            "identity_status": "ACTIVE",
        }

    async def start_run(self, **kwargs: Any) -> JsonBody:
        return (await self._agent.start_run(**kwargs)).model_dump(mode="json")

    async def record_step(self, **kwargs: Any) -> JsonBody:
        return (await self._agent.record_step(**kwargs)).model_dump(mode="json")

    async def guard(
        self,
        *,
        input_payload: JsonBody,
        phase: GuardrailPhase,
        guardrail_id: str,
        run_id: str | None = None,
        step_id: str | None = None,
        parent_step_id: str | None = None,
        conversation_id: str | None = None,
        timeout_ms: int = 1500,
    ) -> JsonBody:
        return (
            await self._agent.guard(
                guardrail_id=guardrail_id,
                phase=phase,
                run_id=run_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                conversation_id=conversation_id,
                timeout_ms=timeout_ms,
                messages=input_payload["messages"],
                phase_focus=input_payload["phase_focus"],
                content_type=input_payload.get("content_type", "text"),
                language=input_payload.get("language"),
                artifacts=input_payload.get("artifacts", []),
            )
        ).model_dump(mode="json")

    async def complete_run(self, *, run_id: str, **kwargs: Any) -> JsonBody:
        return (await self._agent.complete_run(run_id, **kwargs)).model_dump(mode="json")


AsyncUmaiClient = UmaiClient
