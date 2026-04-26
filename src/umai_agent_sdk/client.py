from __future__ import annotations

import warnings

warnings.warn(
    "`umai_agent_sdk.client` is deprecated; import from `umai` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from umai.client import UmaiAgentClient
from umai.crypto import canonical_json, object_hash
from umai.identity import AgentIdentity as UmaiAgentIdentity

__all__ = ["UmaiAgentClient", "UmaiAgentIdentity", "canonical_json", "object_hash"]

