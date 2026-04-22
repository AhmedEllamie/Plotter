from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class FlaskCaptureSettings:
    reset_url: str
    reset_token: str
    reset_timeout_seconds: float
    reset_method: str

    @property
    def is_configured(self) -> bool:
        return bool(self.reset_url)


@dataclass(frozen=True)
class ScannerServiceSettings:
    base_url: str
    token: str
    timeout_seconds: float
    job_poll_interval_seconds: float
    job_poll_max_attempts: int

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)


def load_capture_settings() -> FlaskCaptureSettings:
    return FlaskCaptureSettings(
        reset_url=os.getenv("CAPTURE_RESET_URL", "").strip(),
        reset_token=os.getenv("CAPTURE_RESET_TOKEN", "").strip(),
        reset_timeout_seconds=_parse_float(os.getenv("CAPTURE_RESET_TIMEOUT_SECONDS"), default=8.0),
        reset_method=os.getenv("CAPTURE_RESET_METHOD", "POST").strip().upper() or "POST",
    )


def load_scanner_service_settings() -> ScannerServiceSettings:
    base_url = os.getenv("SCANNER_SERVICE_BASE_URL", "http://127.0.0.1:8008").strip().rstrip("/")
    max_attempts = int(os.getenv("SCANNER_JOB_POLL_MAX_ATTEMPTS", "40").strip() or "40")
    if max_attempts < 1:
        max_attempts = 1

    return ScannerServiceSettings(
        base_url=base_url,
        token=os.getenv("SCANNER_SERVICE_TOKEN", "").strip(),
        timeout_seconds=_parse_float(os.getenv("SCANNER_SERVICE_TIMEOUT_SECONDS"), default=15.0),
        job_poll_interval_seconds=_parse_float(os.getenv("SCANNER_JOB_POLL_INTERVAL_SECONDS"), default=0.4),
        job_poll_max_attempts=max_attempts,
    )
