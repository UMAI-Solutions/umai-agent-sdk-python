from __future__ import annotations

from umai import UmaiClient


umai = UmaiClient(
    endpoint="http://localhost:8080",
    api_key="demo-key",
    fail_closed=False,
)

print("Fail-open is for demos only. Production agents should use fail_closed=True.")

