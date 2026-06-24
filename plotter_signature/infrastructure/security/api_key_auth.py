from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

API_KEY_ENV_VAR = "PLOTTER_API_KEY"
API_KEY_HEADER = "X-API-Key"

API_KEY_REQUIRED_MESSAGE = (
    f"{API_KEY_ENV_VAR} must be configured on the server. "
    "Set it in /etc/plotter-signature/plotter-signature.env (Ubuntu) or your environment."
)


@dataclass(frozen=True)
class ApiKeyValidationResult:
    is_valid: bool
    is_server_configured: bool
    message: str


def is_api_key_required() -> bool:
    """API key auth is mandatory for HTTP. Always True."""
    return True


def get_configured_api_key() -> str:
    """Returns the server key. Empty string only if not yet configured (handled at startup)."""
    return os.getenv(API_KEY_ENV_VAR, "").strip()


def validate_api_key(provided_api_key: str | None) -> ApiKeyValidationResult:
    configured_api_key = get_configured_api_key()
    if not configured_api_key:
        return ApiKeyValidationResult(
            is_valid=False,
            is_server_configured=False,
            message=API_KEY_REQUIRED_MESSAGE,
        )

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
