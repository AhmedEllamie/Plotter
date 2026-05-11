from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_lock = Lock()
_last: dict[str, Any] | None = None


@dataclass(frozen=True)
class LastApiErrorSnapshot:
    error_code: int
    message: str
    at: str
    http_status: int | None
    path: str | None

    def as_status_fields(self) -> dict[str, Any]:
        return {
            "lastApiErrorCode": self.error_code,
            "lastApiErrorMessage": self.message,
            "lastApiErrorAt": self.at,
        }


def record_api_error(
    *,
    error_code: int,
    message: str,
    status_code: int | None = None,
    path: str | None = None,
) -> None:
    global _last
    snap = {
        "errorCode": error_code,
        "message": message,
        "httpStatus": status_code,
        "path": path,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _last = snap


def clear_last_api_error() -> None:
    global _last
    with _lock:
        _last = None


def get_last_api_error() -> LastApiErrorSnapshot | None:
    with _lock:
        if _last is None:
            return None
        raw = _last
    hs = raw.get("httpStatus")
    p = raw.get("path")
    return LastApiErrorSnapshot(
        error_code=int(raw["errorCode"]),
        message=str(raw["message"]),
        at=str(raw["at"]),
        http_status=None if hs is None else int(hs),
        path=None if p is None else str(p),
    )
