from __future__ import annotations

import asyncio
import os
import uuid

from umai import UmaiClient
from umai.stores import FileIdentityStore


async def main() -> None:
    umai = UmaiClient(endpoint=os.environ["UMAI_ENDPOINT"], api_key=os.environ["UMAI_API_KEY"])
    agent = umai.agent(
        os.getenv("UMAI_AGENT_ID", "raw-equivalent-agent"),
        identity_store=FileIdentityStore(allow_plaintext_private_key=True),
    )
    if not agent.identity or not agent.identity.is_registered:
        await agent.register(bootstrap_token=os.environ["UMAI_AGENT_BOOTSTRAP_TOKEN"])

    run_id = f"raw-equivalent-{uuid.uuid4()}"
    await agent.start_run(run_id=run_id, guardrail_id=os.environ["UMAI_GUARDRAIL_ID"])
    await agent.guard(
        guardrail_id=os.environ["UMAI_GUARDRAIL_ID"],
        phase="PRE_LLM",
        run_id=run_id,
        step_id="pre-llm",
        messages=[{"role": "user", "content": "hello"}],
        phase_focus="LAST_USER_MESSAGE",
        conversation_id=run_id,
    )
    await agent.record_step(
        run_id=run_id,
        step_id="agent-end",
        event_type="agent_end",
        status="COMPLETED",
        payload_summary="Raw equivalent run completed",
    )
    await agent.complete_run(run_id, status="COMPLETED")
    print(run_id)


if __name__ == "__main__":
    asyncio.run(main())

