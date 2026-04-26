from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from .crypto import canonical_json, decode_b64, encode_b64


@dataclass
class AgentIdentity:
    agent_id: str
    private_key_b64: str
    public_key_b64: str
    agent_did: str | None = None
    public_key_fingerprint: str | None = None
    tenant_id: str | None = None
    environment_id: str | None = None
    project_id: str | None = None

    @classmethod
    def generate(cls, agent_id: str) -> "AgentIdentity":
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        return cls(
            agent_id=agent_id,
            private_key_b64=encode_b64(private_bytes),
            public_key_b64=encode_b64(public_bytes),
        )

    @classmethod
    def from_private_key(cls, agent_id: str, private_key_b64: str) -> "AgentIdentity":
        private_key = Ed25519PrivateKey.from_private_bytes(decode_b64(private_key_b64))
        public_bytes = private_key.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        return cls(
            agent_id=agent_id,
            private_key_b64=private_key_b64,
            public_key_b64=encode_b64(public_bytes),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        return cls(
            agent_id=data["agent_id"],
            private_key_b64=data["private_key_b64"],
            public_key_b64=data["public_key_b64"],
            agent_did=data.get("agent_did"),
            public_key_fingerprint=data.get("public_key_fingerprint"),
            tenant_id=data.get("tenant_id"),
            environment_id=data.get("environment_id"),
            project_id=data.get("project_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_registered(self) -> bool:
        return all([self.agent_did, self.public_key_fingerprint, self.tenant_id, self.environment_id, self.project_id])

    def sign(self, payload: dict[str, Any]) -> str:
        private_key = Ed25519PrivateKey.from_private_bytes(decode_b64(self.private_key_b64))
        return encode_b64(private_key.sign(canonical_json(payload).encode("utf-8")))


UmaiAgentIdentity = AgentIdentity

