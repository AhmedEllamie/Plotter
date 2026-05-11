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
) -> tuple[Response, int]:
    numeric, final_message = normalize_api_error_parts(message, error_code)
    path = str(request.path) if has_request_context() else None
    record_api_error(error_code=numeric, message=final_message, status_code=status_code, path=path)
    return (
        jsonify(
            {
                "success": False,
                "message": final_message,
                "data": None,
                "errorCode": numeric,
                "details": details,
            }
        ),
        status_code,
    )
