from __future__ import annotations

import warnings

warnings.warn(
    "`umai_agent_sdk.openai_agents` is deprecated; import from "
    "`umai.integrations.openai_agents` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from umai.integrations.openai_agents import UmaiOpenAIGovernanceHooks, UmaiOpenAIGuardian

__all__ = ["UmaiOpenAIGovernanceHooks", "UmaiOpenAIGuardian"]

