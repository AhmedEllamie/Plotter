from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask


def register_cmd_routes(app: Flask, handlers: dict[str, Callable[..., Any]]) -> None:
    app.add_url_rule("/api/cmd/health", endpoint="cmd_health", view_func=handlers["health"], methods=["GET"])
    app.add_url_rule("/api/cmd/status", endpoint="cmd_status", view_func=handlers["status"], methods=["GET"])
    app.add_url_rule("/api/cmd/print", endpoint="cmd_print", view_func=handlers["print_svg"], methods=["POST"])
    app.add_url_rule(
        "/api/cmd/print/bulk",
        endpoint="cmd_print_bulk",
        view_func=handlers["bulk_print_svg"],
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/cmd/bulk/stop",
        endpoint="cmd_bulk_stop",
        view_func=handlers["stop_bulk_print"],
        methods=["POST"],
    )
    app.add_url_rule("/api/cmd/void", endpoint="cmd_void", view_func=handlers["void_print"], methods=["POST"])
