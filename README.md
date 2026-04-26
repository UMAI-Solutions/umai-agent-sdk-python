# UMAI Agent SDK for Python

Production Python SDK for UMAI Agent Mesh Governance, guardrails, signed agent
identity, and agent work-tree observability.

```bash
pip install umai-agent-sdk
pip install umai-agent-sdk[openai]
```

```python
from umai import UmaiClient
from umai.stores import FileIdentityStore

umai = UmaiClient(endpoint="https://api.umai.ai", api_key="...")
agent = umai.agent(
    "support-agent",
    identity_store=FileIdentityStore(allow_plaintext_private_key=True),
)

await agent.register(bootstrap_token="...")
run = await agent.start_run(guardrail_id="gr-prod")
decision = await agent.guard_tool_input(
    guardrail_id="gr-prod",
    run_id=run.run_id,
    tool_name="crm.lookup",
    payload_summary="Lookup customer profile",
    messages=[{"role": "assistant", "content": "Call crm.lookup"}],
)
await agent.complete_run(run.run_id)
```

The SDK is a convenience layer over UMAI HTTP APIs. Every SDK feature maps to
public UMAI endpoints and can be implemented without the SDK.

