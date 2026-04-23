from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from plotter_signature.domain.contracts import (
    ApprovalServiceSettings,
    PrintRetrySettings,
    parse_bool,
)
from plotter_signature.domain.printer_settings import PrinterSettings
from plotter_signature.infrastructure.stores.request_log_store import RequestLogStore
from plotter_signature.services.approval.mock_approval_service import MockApprovalService
from plotter_signature.services.print_approval.print_approval_service import PrintApprovalService
from plotter_signature.services.printer.printer_service import PrinterService


@dataclass
class ServiceProvider:
    printer_settings: PrinterSettings
    print_retry_settings: PrintRetrySettings
    approval_service_settings: ApprovalServiceSettings
    printer_service: PrinterService
    request_log_store: RequestLogStore
    approval_service: MockApprovalService
    print_approval_service: PrintApprovalService


def _load_default_config() -> dict[str, Any]:
    # Repo root is the parent of the `plotter_signature` package folder.
    repo_root = Path(__file__).resolve().parent.parent
    default_config_path = repo_root / "appsettings.json"
    if not default_config_path.exists():
        return {}
    with default_config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_service_provider(config: dict[str, Any] | None = None) -> ServiceProvider:
    config = config or _load_default_config()

    printer_cfg = config.get("Printer", {})
    retry_cfg = config.get("PrintRetry", {})
    approval_cfg = config.get("ApprovalService", {})

    printer_settings = PrinterSettings(
        com_port=str(printer_cfg.get("ComPort", "COM5")),
        baud_rate=int(printer_cfg.get("BaudRate", 250000)),
    )
    print_retry_settings = PrintRetrySettings(
        max_retries=int(retry_cfg.get("MaxRetries", 3)),
        retry_delay_ms=int(retry_cfg.get("RetryDelayMs", 1000)),
    )
    approval_service_settings = ApprovalServiceSettings(
        endpoint=str(approval_cfg.get("Endpoint", "")),
        api_key=str(approval_cfg.get("ApiKey", "")),
        timeout_seconds=int(approval_cfg.get("TimeoutSeconds", 30)),
        use_mock_service=parse_bool(approval_cfg.get("UseMockService"), default=True),
    )

    request_log_store = RequestLogStore()
    printer_service = PrinterService(printer_settings)

    # Current Python port intentionally keeps mock approval only (per requested scope).
    approval_service = MockApprovalService(approval_service_settings)
    print_approval_service = PrintApprovalService(
        request_log_store=request_log_store,
        printer_service=printer_service,
        approval_service=approval_service,
        print_retry_settings=print_retry_settings,
    )

    return ServiceProvider(
        printer_settings=printer_settings,
        print_retry_settings=print_retry_settings,
        approval_service_settings=approval_service_settings,
        printer_service=printer_service,
        request_log_store=request_log_store,
        approval_service=approval_service,
        print_approval_service=print_approval_service,
    )


_provider_lock = Lock()
_global_provider: ServiceProvider | None = None


def get_service_provider() -> ServiceProvider:
    global _global_provider
    with _provider_lock:
        if _global_provider is None:
            _global_provider = build_service_provider()
        return _global_provider


def reset_service_provider() -> None:
    global _global_provider
    with _provider_lock:
        _global_provider = None
