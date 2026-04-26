# Agent Identity

UMAI Agent Mesh uses Ed25519 identities. The SDK can generate and store identity
material locally, from environment variables, in memory for tests, or through a
custom customer-managed store.

Production deployments should set `UMAI_IDENTITY_PASSPHRASE` or provide a
Vault/KMS-backed `IdentityStore`.

