from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def object_hash(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def encode_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_b64(value: str) -> bytes:
    padding = "=" * (-len(value.strip()) % 4)
    return base64.urlsafe_b64decode((value.strip() + padding).encode("ascii"))


def utcnow_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def public_key_fingerprint(public_key_b64: str) -> str:
    return "sha256:" + encode_b64(hashlib.sha256(decode_b64(public_key_b64)).digest())


def endpoint_hash(endpoint: str) -> str:
    normalized = endpoint.rstrip("/").lower()
    return encode_b64(hashlib.sha256(normalized.encode("utf-8")).digest())[:16]

