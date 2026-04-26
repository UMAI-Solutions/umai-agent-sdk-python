from __future__ import annotations

import time
import uuid
from typing import Any

from umai import AgentMesh, UmaiError, object_hash

try:
    from agents import Agent, Runner
    from agents.lifecycle import RunHooksBase
    from agents.run_context import RunContextWrapper
    from agents.tool import Tool
except Exception:  # pragma: no cover - optional dependency
    Agent = Any  # type: ignore
    Runner = Any  # type: ignore
    RunHooksBase = object  # type: ignore
    RunContextWrapper = Any  # type: ignore
    Tool = Any  # type: ignore


class UmaiOpenAIGovernanceHooks(RunHooksBase):
    """OpenAI Agents SDK hooks that stream lifecycle events into UMAI."""

    def __init__(
        self,
        agent: AgentMesh,
        *,
        run_id: str | None = None,
        strict_observability: bool = False,
    ) -> None:
        self.agent = agent
        self.run_id = run_id or str(uuid.uuid4())
        self.strict_observability = strict_observability
        self._started_at: dict[str, float] = {}
        self._agent_steps: dict[str, str] = {}

    async def start(self, *, guardrail_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        await self.agent.start_run(
            run_id=self.run_id,
            guardrail_id=guardrail_id,
            metadata=metadata or {"adapter": "openai-agents"},
        )

    async def finish(self, *, status: str = "COMPLETED", summary: dict[str, Any] | None = None) -> None:
        await self.agent.complete_run(self.run_id, status=status, summary=summary or {})

    async def _observe(self, coro) -> None:
        try:
            await coro
        except UmaiError:
            if self.strict_observability:
                raise

    async def on_agent_start(self, context: RunContextWrapper[Any], agent: Agent[Any]) -> None:
        del context
        self._started_at[agent.name] = time.perf_counter()
        step_id = str(uuid.uuid4())
        self._agent_steps[agent.name] = step_id
        await self._observe(
            self.agent.record_step(
                run_id=self.run_id,
                step_id=step_id,
                event_type="agent_start",
                status="RUNNING",
                resource_type="agent",
                resource_name=agent.name,
                payload_summary=f"Agent {agent.name} started",
                metadata={"agent_name": agent.name},
            )
        )

    async def on_agent_end(self, context: RunContextWrapper[Any], agent: Agent[Any], output: Any) -> None:
        del context
        parent_step_id = self._agent_steps.get(agent.name)
        latency_ms = (time.perf_counter() - self._started_at.get(agent.name, time.perf_counter())) * 1000
        await self._observe(
            self.agent.record_step(
                run_id=self.run_id,
                event_type="agent_end",
                parent_step_id=parent_step_id,
                status="COMPLETED",
                resource_type="agent",
                resource_name=agent.name,
                payload_summary=f"Agent {agent.name} completed",
                output_hash=object_hash(str(output)),
                latency_ms=latency_ms,
                metadata={"agent_name": agent.name},
            )
        )

    async def on_tool_start(self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool) -> None:
        del context
        await self._observe(
            self.agent.record_step(
                run_id=self.run_id,
                parent_step_id=self._agent_steps.get(agent.name),
                event_type="tool_start",
                phase="TOOL_INPUT",
                status="RUNNING",
                action="call",
                resource_type="tool",
                resource_name=tool.name,
                payload_summary=f"{agent.name} called {tool.name}",
                metadata={"agent_name": agent.name, "tool_name": tool.name},
            )
        )

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Tool,
        result: str,
    ) -> None:
        del context
        await self._observe(
            self.agent.record_step(
                run_id=self.run_id,
                parent_step_id=self._agent_steps.get(agent.name),
                event_type="tool_end",
                phase="TOOL_OUTPUT",
                status="COMPLETED",
                resource_type="tool",
                resource_name=tool.name,
                payload_summary=f"{tool.name} returned {len(str(result))} characters",
                output_hash=object_hash(str(result)),
                metadata={"agent_name": agent.name, "tool_name": tool.name},
            )
        )

    async def on_handoff(
        self,
        context: RunContextWrapper[Any],
        from_agent: Agent[Any],
        to_agent: Agent[Any],
    ) -> None:
        del context
        await self._observe(
            self.agent.record_step(
                run_id=self.run_id,
                parent_step_id=self._agent_steps.get(from_agent.name),
                event_type="handoff",
                status="RECORDED",
                action="handoff",
                resource_type="agent",
                resource_name=to_agent.name,
                payload_summary=f"{from_agent.name} handed off to {to_agent.name}",
                metadata={"from_agent": from_agent.name, "to_agent": to_agent.name},
            )
        )


class UmaiOpenAIGuardian:
    """High-level OpenAI Agents SDK runner protected by UMAI guardrails."""

    def __init__(
        self,
        *,
        agent: AgentMesh,
        guardrail_id: str,
        strict_observability: bool = False,
    ) -> None:
        self.agent = agent
        self.guardrail_id = guardrail_id
        self.strict_observability = strict_observability

    async def run(
        self,
        openai_agent: Agent[Any],
        prompt: str,
        *,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        max_turns: int = 10,
    ) -> Any:
        resolved_run_id = run_id or f"openai-agents-{uuid.uuid4()}"
        root_step_id = f"pre-llm-{uuid.uuid4()}"
        hooks = UmaiOpenAIGovernanceHooks(
            self.agent,
            run_id=resolved_run_id,
            strict_observability=self.strict_observability,
        )
        await hooks.start(
            guardrail_id=self.guardrail_id,
            metadata={"framework": "openai-agents", **(metadata or {})},
        )
        try:
            await self.agent.guard(
                guardrail_id=self.guardrail_id,
                phase="PRE_LLM",
                run_id=resolved_run_id,
                step_id=root_step_id,
                messages=[{"role": "user", "content": prompt}],
                phase_focus="LAST_USER_MESSAGE",
                conversation_id=resolved_run_id,
                artifacts=[
                    {
                        "artifact_type": "CUSTOM",
                        "name": "user_prompt",
                        "payload_summary": "Initial user request",
                        "metadata": {"framework": "openai-agents"},
                    }
                ],
            )
            result = await Runner.run(openai_agent, prompt, hooks=hooks, max_turns=max_turns)
            final_output = str(result.final_output)
            await self.agent.guard(
                guardrail_id=self.guardrail_id,
                phase="POST_LLM",
                run_id=resolved_run_id,
                step_id=f"post-llm-{uuid.uuid4()}",
                parent_step_id=root_step_id,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_output},
                ],
                phase_focus="LAST_ASSISTANT_MESSAGE",
                conversation_id=resolved_run_id,
                artifacts=[
                    {
                        "artifact_type": "CUSTOM",
                        "name": "final_answer",
                        "payload_summary": "Final assistant response",
                        "metadata": {"output_hash": object_hash(final_output)},
                    }
                ],
            )
            await hooks.finish(status="COMPLETED", summary={"final_output_hash": object_hash(final_output)})
            return result
        except Exception:
            await hooks.finish(status="FAILED", summary={"error": "OpenAI Agents run failed"})
            raise


__all__ = ["UmaiOpenAIGovernanceHooks", "UmaiOpenAIGuardian"]

