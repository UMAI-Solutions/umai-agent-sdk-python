# API Reference

Primary imports:

```python
from umai import UmaiClient, AgentIdentity
from umai.stores import FileIdentityStore, EnvIdentityStore, MemoryIdentityStore
from umai.integrations.openai_agents import UmaiOpenAIGuardian
```

Core classes:

- `UmaiClient`: async HTTP client and SDK entrypoint.
- `AgentMesh`: high-level helper for one registered agent identity.
- `AgentIdentity`: Ed25519 identity material and signing helper.
- `FileIdentityStore`: local encrypted or explicit-plaintext identity storage.
- `UmaiOpenAIGuardian`: OpenAI Agents SDK runner with UMAI guardrails and work-tree observability.

Compatibility imports:

```python
from umai_agent_sdk import UmaiAgentClient, UmaiAgentIdentity
```

The compatibility namespace is deprecated and will be removed after the SDK API reaches 1.0.

