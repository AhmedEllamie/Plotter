from __future__ import annotations

from typing import Any

from flask import Response, jsonify


def api_success(message: str, data: Any = None, status_code: int = 200) -> tuple[Response, int]:
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
    error_code: str,
    status_code: int = 400,
    details: Any = None,
) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "success": False,
                "message": message,
                "data": None,
                "errorCode": error_code,
                "details": details,
            }
        ),
        status_code,
    )
