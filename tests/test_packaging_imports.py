from __future__ import annotations


def test_new_import_namespace() -> None:
    from umai import UmaiClient

    assert UmaiClient.__name__ == "UmaiClient"


def test_legacy_import_namespace() -> None:
    from umai_agent_sdk import UmaiAgentClient, UmaiAgentIdentity

    assert UmaiAgentClient.__name__ == "UmaiAgentClient"
    assert UmaiAgentIdentity.__name__ == "AgentIdentity"

