"""Optional serial AutoConnect on HTTP server process startup."""

from __future__ import annotations

import logging
import os

from plotter_signature.services.printer.i_printer_service import IPrinterService
from plotter_signature.services.printer.printer_service import AutoConnectFailedError


def startup_autoconnect_enabled() -> bool:
    raw = (os.getenv("AUTO_CONNECT_ON_STARTUP") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def run_startup_autoconnect(printer_service: IPrinterService, *, log: logging.Logger | None = None) -> None:
    """Best-effort: open plotter serial using existing AutoConnect resolver. Never raises."""
    logger = log or logging.getLogger(__name__)
    if not startup_autoconnect_enabled():
        logger.info("Startup AutoConnect skipped (AUTO_CONNECT_ON_STARTUP disabled).")
        return
    if printer_service.is_open:
        logger.info("Startup AutoConnect skipped (serial port already open).")
        return
    try:
        printer_service.autoconnect()
        logger.info("Startup AutoConnect succeeded.")
    except AutoConnectFailedError as ex:
        logger.warning(
            "Startup AutoConnect failed: %s attempted_ports=%s",
            ex,
            getattr(ex, "attempted_ports", []),
        )
    except Exception:
        logger.exception("Startup AutoConnect failed with unexpected error")
