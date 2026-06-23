from __future__ import annotations

from typing import Any

from flask import Response, has_request_context, jsonify, request

from plotter_signature.infrastructure.errors.api_error_codes import normalize_api_error_parts
from plotter_signature.web.last_api_error import clear_last_api_error, record_api_error


def api_success(message: str, data: Any = None, status_code: int = 200) -> tuple[Response, int]:
    if has_request_context() and request.method not in ("GET", "HEAD"):
        clear_last_api_error()
    return (
        jsonify(
            {
                "success": True,
                "message": message,
                "data": data,
                "errorCode": None,
            }
        ),
        status_code,
    )


def api_error(
    message: str,
    error_code: str | int,
    status_code: int = 400,
    details: Any = None,
    data: Any = None,
) -> tuple[Response, int]:
    numeric, final_message = normalize_api_error_parts(message, error_code)
    path = str(request.path) if has_request_context() else None
    record_api_error(error_code=numeric, message=final_message, status_code=status_code, path=path)
    return (
        jsonify(
            {
                "success": False,
                "message": final_message,
                "data": data,
                "errorCode": numeric,
                "details": details,
            }
        ),
        status_code,
    )


def api_job_status(
    data: dict[str, Any],
    *,
    status: str,
    error_message: str | None = None,
    error_code: str | int | None = None,
) -> tuple[Response, int]:
    if status == "failed":
        raw_code = error_code if error_code is not None else "PRINT_RUNTIME_ERROR"
        raw_msg = (error_message or "").strip() or "Command job failed."
        return api_error(raw_msg, raw_code, status_code=200, data=data)

    status_messages = {
        "pending": "Command job is pending.",
        "running": "Command job is running.",
        "completed": "Command job completed.",
        "stopped": "Command job stopped.",
    }
    return api_success(message=status_messages.get(status, "Command job status loaded."), data=data)
