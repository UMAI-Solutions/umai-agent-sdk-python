# Production Checklist

- Use `fail_closed=True`.
- Store private keys in encrypted local storage or a Vault/KMS-backed store.
- Register every agent with explicit capabilities.
- Guard every protected tool, MCP, memory, and model phase.
- Monitor Control Center Agents > Runs for blocked decisions and trust changes.
- Rotate agent credentials when hosts or secrets change.

