from __future__ import annotations

import warnings

warnings.warn(
    "`umai_agent_sdk` is deprecated; import from `umai` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from umai import *  # noqa: F403
from umai import AgentIdentity as UmaiAgentIdentity
from umai.client import UmaiAgentClient
from umai.integrations.openai_agents import UmaiOpenAIGovernanceHooks

__all__ = [
    "UmaiAgentClient",
    "UmaiAgentIdentity",
    "UmaiOpenAIGovernanceHooks",
    "canonical_json",
    "object_hash",
]

