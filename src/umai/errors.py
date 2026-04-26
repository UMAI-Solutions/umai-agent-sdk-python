from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class UmaiError(Exception):
    message: str
    status_code: int | None = None
    error_type: str | None = None
    retryable: bool = False
    response_body: dict[str, Any] | None = None

    def __str__(self) -> str:
        if self.error_type:
            return f"{self.error_type}: {self.message}"
        return self.message


class UmaiBlockedError(UmaiError):
    pass


class UmaiUnavailableError(UmaiError):
    pass


class UmaiSignatureError(UmaiError):
    pass


class UmaiAuthenticationError(UmaiError):
    pass


class UmaiForbiddenError(UmaiError):
    pass


def error_from_response(response: httpx.Response) -> UmaiError:
    error_type = None
    message = response.text
    retryable = response.status_code >= 500
    body: dict[str, Any] | None = None
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
            error = parsed.get("error")
            if isinstance(error, dict):
                error_type = str(error.get("type") or "")
                message = str(error.get("message") or message)
                retryable = bool(error.get("retryable", retryable))
    except ValueError:
        pass

    kwargs = {
        "message": message,
        "status_code": response.status_code,
        "error_type": error_type,
        "retryable": retryable,
        "response_body": body,
    }
    if response.status_code == 401:
        if error_type and "SIGNATURE" in error_type:
            return UmaiSignatureError(**kwargs)
        return UmaiAuthenticationError(**kwargs)
    if response.status_code == 403:
        return UmaiForbiddenError(**kwargs)
    if response.status_code >= 500:
        return UmaiUnavailableError(**kwargs)
    return UmaiError(**kwargs)

