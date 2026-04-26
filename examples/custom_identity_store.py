from __future__ import annotations

from umai import AgentIdentity
from umai.stores import IdentityStore


class VaultIdentityStore:
    """Example shape for a customer-managed Vault/KMS identity store."""

    def load(self, *, endpoint: str, agent_id: str) -> AgentIdentity | None:
        del endpoint, agent_id
        # Fetch and decrypt the agent private key from Vault/KMS here.
        return None

    def save(self, *, endpoint: str, identity: AgentIdentity) -> None:
        del endpoint, identity
        # Encrypt and persist identity material in Vault/KMS here.
        raise NotImplementedError


def build_store() -> IdentityStore:
    return VaultIdentityStore()

