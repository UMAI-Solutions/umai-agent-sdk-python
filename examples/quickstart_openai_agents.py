from __future__ import annotations

import asyncio
import os

from agents import Agent, function_tool

from umai import UmaiClient
from umai.integrations.openai_agents import UmaiOpenAIGuardian
from umai.stores import FileIdentityStore


@function_tool
async def lookup_demo_order(account_id: str) -> str:
    """Look up a synthetic demo account order."""
    return f"Demo account {account_id} has sample order order_123 for a SIM test fixture."


async def main() -> None:
    umai = UmaiClient(
        endpoint=os.environ["UMAI_ENDPOINT"],
        api_key=os.environ["UMAI_API_KEY"],
        fail_closed=True,
        timeout=30,
    )
    agent_mesh = umai.agent(
        os.getenv("UMAI_AGENT_ID", "openai-agents-quickstart"),
        identity_store=FileIdentityStore(allow_plaintext_private_key=True),
    )
    if not agent_mesh.identity or not agent_mesh.identity.is_registered:
        await agent_mesh.register(
            bootstrap_token=os.environ["UMAI_AGENT_BOOTSTRAP_TOKEN"],
            display_name="OpenAI Agents Quickstart",
            runtime="openai-agents",
            capabilities=["demo:read"],
        )

    openai_agent = Agent(
        name="Customer Support Agent",
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        instructions="Use tools when needed and keep answers concise.",
        tools=[lookup_demo_order],
    )
    guardian = UmaiOpenAIGuardian(
        agent=agent_mesh,
        guardrail_id=os.environ["UMAI_GUARDRAIL_ID"],
    )
    result = await guardian.run(
        openai_agent,
        "Use the demo order lookup tool for anonymized demo account demo_42.",
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())

