from __future__ import annotations

from typing import Any

# Unknown / unregistered legacy string keys resolve to this numeric code.
UNKNOWN_LEGACY_CODE = 0

# Stable mapping: legacy string token → integer (documented in API_REFERENCE.md).
LEGACY_API_ERROR_CODES: dict[str, int] = {
    "BULK_PRINT_FAILED": 1001,
    "BULK_STOP_FAILED": 1002,
    "CAPTURE_JOB_NOT_FOUND": 1003,
    "CMD_JOB_NOT_FOUND": 1043,
    "CAPTURE_JOB_TIMEOUT": 1004,
    "CAPTURE_NOT_FOUND": 1005,
    "CAPTURE_PAYLOAD_INVALID": 1006,
    "CAPTURE_SETTINGS_NOT_ALLOWED": 1040,
    "CAPTURE_UPLOAD_FAILED": 1007,
    "CONFIG_NOT_INITIALIZED": 1041,
    "EMPTY_SVG": 1008,
    "INVALID_PEN_MODE": 1009,
    "INVALID_QUERY": 1010,
    "PEN_CHANGE_FINISH_FAILED": 1011,
    "PEN_CHANGE_START_FAILED": 1012,
    "PEN_CHANGE_STATE_ERROR": 1013,
    "PEN_MAX_DISTANCE_FAILED": 1014,
    "PEN_MAX_DISTANCE_INVALID": 1015,
    "PEN_MAX_DISTANCE_REQUIRED": 1016,
    "PRINT_FAILED": 1017,
    "PRINT_RUNTIME_ERROR": 1018,
    "PRINT_SETTINGS_NOT_ALLOWED": 1042,
    "PRINT_VALIDATION_ERROR": 1019,
    "PRINTER_BUSY": 1020,
    "PRINTER_NOT_BUSY": 1021,
    "PRINTER_STATE_ERROR": 1022,
    "RESET_FAILED": 1023,
    "RESET_VALIDATION_ERROR": 1024,
    "SCANNER_CAPTURE_FAILED": 1025,
    "SCANNER_CONFIG_REQUIRED": 1026,
    "SCANNER_HTTP_ERROR": 1027,
    "SCANNER_STREAM_FAILED": 1028,
    "SCANNER_STREAM_HTTP_ERROR": 1029,
    "SCANNER_STREAM_UNREACHABLE": 1030,
    "SCANNER_UNREACHABLE": 1031,
    "SVG_REQUIRED": 1032,
    "UI_PROFILE_REQUIRED": 1033,
    "UI_PROFILE_SAVE_FAILED": 1034,
    "UNAUTHORIZED": 1035,
    "VOID_BUSY": 1036,
    "VOID_FAILED": 1037,
    "VOID_RUNTIME_ERROR": 1038,
    "PEN_DISTANCE_NO_ACTION": 1039,
}


def numeric_code_for_legacy(legacy: str) -> int:
    return LEGACY_API_ERROR_CODES.get(legacy, UNKNOWN_LEGACY_CODE)


def normalize_api_error_parts(message: str, error_code: str | int) -> tuple[int, str]:
    """Return (numeric_code, final_message). Legacy strings get a [TOKEN] prefix when missing."""
    if isinstance(error_code, int):
        return error_code, message
    legacy = error_code
    numeric = numeric_code_for_legacy(legacy)
    bracket = f"[{legacy}]"
    if message.startswith(bracket) or message.startswith(f"{bracket} "):
        return numeric, message
    return numeric, f"{bracket} {message}"


def fastapi_http_exception_legacy_token(status_code: int, detail: Any) -> str:
    """Map HTTP status + detail text to a registry key for consistent numeric codes."""
    text = detail if isinstance(detail, str) else str(detail)
    lower = text.lower()

    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 500:
        return "PRINT_RUNTIME_ERROR"
    if status_code == 409 and "busy" in lower:
        return "PRINTER_BUSY"
    if "not connected" in lower:
        return "PRINT_RUNTIME_ERROR"
    if "no svg file provided" in lower or "no signature svg" in lower:
        return "SVG_REQUIRED"
    if status_code == 400:
        return "PRINT_VALIDATION_ERROR"
    return "PRINT_VALIDATION_ERROR"


def fastapi_validation_error_legacy_token() -> str:
    return "PRINT_VALIDATION_ERROR"


def format_fastapi_message(legacy_token: str, detail: Any) -> str:
    text = detail if isinstance(detail, str) else str(detail)
    _numeric, msg = normalize_api_error_parts(text, legacy_token)
    return msg
