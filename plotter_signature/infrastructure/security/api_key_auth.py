from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

API_KEY_ENV_VAR = "PLOTTER_API_KEY"
API_KEY_HEADER = "X-API-Key"
DEFAULT_API_KEY = "QSCWDVEFBRGN"


@dataclass(frozen=True)
class ApiKeyValidationResult:
    is_valid: bool
    is_server_configured: bool
    message: str


def get_configured_api_key() -> str:
    configured = os.getenv(API_KEY_ENV_VAR, "").strip()
    if configured:
        return configured
    return DEFAULT_API_KEY


def validate_api_key(provided_api_key: str | None) -> ApiKeyValidationResult:
    configured_api_key = get_configured_api_key()

    normalized_provided = (provided_api_key or "").strip()
    if not normalized_provided:
        return ApiKeyValidationResult(
            is_valid=False,
            is_server_configured=True,
            message=f"Missing {API_KEY_HEADER} header.",
        )

    if not hmac.compare_digest(normalized_provided, configured_api_key):
        return ApiKeyValidationResult(
            is_valid=False,
            is_server_configured=True,
            message=f"Invalid {API_KEY_HEADER} header.",
        )

    return ApiKeyValidationResult(
        is_valid=True,
        is_server_configured=True,
        message="Authorized.",
    )
