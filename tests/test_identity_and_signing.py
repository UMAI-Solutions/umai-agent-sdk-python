from __future__ import annotations

import json
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from umai import AgentIdentity, UmaiClient, canonical_json, object_hash, public_key_fingerprint
from umai.crypto import decode_b64
from umai.stores import FileIdentityStore, MemoryIdentityStore


def test_canonical_json_and_object_hash_are_stable() -> None:
    left = {"b": 2, "a": {"z": 1}}
    right = {"a": {"z": 1}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert object_hash(left) == object_hash(right)


def test_agent_context_signature_verifies() -> None:
    tenant_id = str(uuid.uuid4())
    identity = AgentIdentity.generate("agent-1")
    identity.tenant_id = tenant_id
    identity.environment_id = "dev"
    identity.project_id = "project"
    identity.agent_did = "did:umai:test:agent-1"
    identity.public_key_fingerprint = public_key_fingerprint(identity.public_key_b64)
    agent = UmaiClient(endpoint="https://umai.example", api_key="uk_test").agent(
        "agent-1",
        identity_store=MemoryIdentityStore(identity),
    )
    body_hash = object_hash({"hello": "world"})
    context = agent.agent_context(
        event="guard",
        body_hash=body_hash,
        run_id="run-1",
        step_id="step-1",
        extra={"guardrail_id": "gr-1", "phase": "TOOL_INPUT"},
    )
    signed_payload = {
        "event": "guard",
        "tenant_id": tenant_id,
        "environment_id": "dev",
        "project_id": "project",
        "agent_id": "agent-1",
        "agent_did": "did:umai:test:agent-1",
        "run_id": "run-1",
        "step_id": "step-1",
        "parent_step_id": None,
        "nonce": context.nonce,
        "signed_at": context.signed_at,
        "body_hash": body_hash,
        "guardrail_id": "gr-1",
        "phase": "TOOL_INPUT",
    }
    Ed25519PublicKey.from_public_bytes(decode_b64(identity.public_key_b64)).verify(
        decode_b64(context.signature),
        canonical_json(signed_payload).encode("utf-8"),
    )


def test_file_identity_store_refuses_plaintext_by_default(tmp_path) -> None:
    store = FileIdentityStore(tmp_path)
    with pytest.raises(ValueError, match="Refusing to persist plaintext"):
        store.save(endpoint="https://umai.example", identity=AgentIdentity.generate("agent-1"))


def test_file_identity_store_plaintext_demo_roundtrip(tmp_path) -> None:
    store = FileIdentityStore(tmp_path, allow_plaintext_private_key=True)
    identity = AgentIdentity.generate("agent-1")
    store.save(endpoint="https://umai.example", identity=identity)
    loaded = store.load(endpoint="https://umai.example", agent_id="agent-1")
    assert loaded is not None
    assert loaded.private_key_b64 == identity.private_key_b64


def test_file_identity_store_encrypted_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UMAI_IDENTITY_PASSPHRASE", "test-passphrase")
    store = FileIdentityStore(tmp_path)
    identity = AgentIdentity.generate("agent-1")
    store.save(endpoint="https://umai.example", identity=identity)
    stored = next(tmp_path.rglob("agent-1.json"))
    assert "encrypted_private_key" in json.loads(stored.read_text())
    loaded = store.load(endpoint="https://umai.example", agent_id="agent-1")
    assert loaded is not None
    assert loaded.private_key_b64 == identity.private_key_b64

