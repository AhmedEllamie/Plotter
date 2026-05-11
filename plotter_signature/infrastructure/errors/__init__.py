"""Shared API error code registry (Flask + FastAPI)."""

from plotter_signature.infrastructure.errors.api_error_codes import (
    LEGACY_API_ERROR_CODES,
    UNKNOWN_LEGACY_CODE,
    fastapi_http_exception_legacy_token,
    normalize_api_error_parts,
    numeric_code_for_legacy,
)

__all__ = [
    "LEGACY_API_ERROR_CODES",
    "UNKNOWN_LEGACY_CODE",
    "fastapi_http_exception_legacy_token",
    "normalize_api_error_parts",
    "numeric_code_for_legacy",
]
