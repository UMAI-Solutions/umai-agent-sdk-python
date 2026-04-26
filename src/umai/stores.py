from __future__ import annotations

import json
import os
import stat
import base64
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .crypto import decode_b64, encode_b64, endpoint_hash
from .identity import AgentIdentity


class IdentityStore(Protocol):
    def load(self, *, endpoint: str, agent_id: str) -> AgentIdentity | None: ...

    def save(self, *, endpoint: str, identity: AgentIdentity) -> None: ...


def _fernet_for_passphrase(passphrase: str, salt_b64: str) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=decode_b64(salt_b64),
        iterations=390000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8"))))


class FileIdentityStore:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        allow_plaintext_private_key: bool = False,
        passphrase: str | None = None,
    ) -> None:
        self.root = Path(root or Path.home() / ".umai" / "agents")
        self.allow_plaintext_private_key = allow_plaintext_private_key
        self.passphrase = passphrase

    def _path(self, endpoint: str, agent_id: str) -> Path:
        return self.root / endpoint_hash(endpoint) / f"{agent_id}.json"

    def load(self, *, endpoint: str, agent_id: str) -> AgentIdentity | None:
        path = self._path(endpoint, agent_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if "encrypted_private_key" in data:
            passphrase = self.passphrase or os.getenv("UMAI_IDENTITY_PASSPHRASE")
            if not passphrase:
                raise ValueError("UMAI_IDENTITY_PASSPHRASE is required to load encrypted UMAI identity")
            try:
                private_key_b64 = _fernet_for_passphrase(passphrase, data["salt"]).decrypt(
                    data["encrypted_private_key"].encode("ascii")
                )
            except InvalidToken as exc:
                raise ValueError("Invalid UMAI identity passphrase") from exc
            data["private_key_b64"] = private_key_b64.decode("utf-8")
        elif not self.allow_plaintext_private_key:
            raise ValueError(
                "Plaintext UMAI identity file refused; pass allow_plaintext_private_key=True "
                "for local demos or set UMAI_IDENTITY_PASSPHRASE for encrypted storage."
            )
        return AgentIdentity.from_dict(data)

    def save(self, *, endpoint: str, identity: AgentIdentity) -> None:
        path = self._path(endpoint, identity.agent_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = identity.to_dict()
        passphrase = self.passphrase or os.getenv("UMAI_IDENTITY_PASSPHRASE")
        if passphrase:
            salt = encode_b64(os.urandom(16))
            encrypted = _fernet_for_passphrase(passphrase, salt).encrypt(
                identity.private_key_b64.encode("utf-8")
            )
            data.pop("private_key_b64", None)
            data["encrypted_private_key"] = encrypted.decode("ascii")
            data["salt"] = salt
            data["encryption"] = "fernet-pbkdf2-sha256"
        elif not self.allow_plaintext_private_key:
            raise ValueError(
                "Refusing to persist plaintext UMAI private key. Set UMAI_IDENTITY_PASSPHRASE "
                "or pass allow_plaintext_private_key=True for local demos."
            )
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


class EnvIdentityStore:
    def __init__(self, prefix: str = "UMAI_AGENT") -> None:
        self.prefix = prefix

    def _get(self, name: str) -> str | None:
        return os.getenv(f"{self.prefix}_{name}")

    def load(self, *, endpoint: str, agent_id: str) -> AgentIdentity | None:
        del endpoint
        private_key = self._get("PRIVATE_KEY_B64")
        if not private_key:
            return None
        identity = AgentIdentity.from_private_key(agent_id, private_key)
        identity.agent_did = self._get("DID")
        identity.public_key_fingerprint = self._get("PUBLIC_KEY_FINGERPRINT")
        identity.tenant_id = os.getenv("UMAI_TENANT_ID") or self._get("TENANT_ID")
        identity.environment_id = os.getenv("UMAI_ENVIRONMENT_ID") or self._get("ENVIRONMENT_ID")
        identity.project_id = os.getenv("UMAI_PROJECT_ID") or self._get("PROJECT_ID")
        return identity

    def save(self, *, endpoint: str, identity: AgentIdentity) -> None:
        del endpoint, identity
        raise ValueError("EnvIdentityStore is read-only")


class MemoryIdentityStore:
    def __init__(self, identity: AgentIdentity | None = None) -> None:
        self.identity = identity

    def load(self, *, endpoint: str, agent_id: str) -> AgentIdentity | None:
        del endpoint
        if self.identity and self.identity.agent_id == agent_id:
            return self.identity
        return None

    def save(self, *, endpoint: str, identity: AgentIdentity) -> None:
        del endpoint
        self.identity = identity
