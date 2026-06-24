from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID

from plotter_signature.dependency_injection import get_service_provider
from plotter_signature.dependency_injection import ServiceProvider
from plotter_signature.domain.contracts import (
    PrintApprovalRequest,
    PrintRequest,
    PrintWithApprovalRequest,
    get_paper_size_mm,
)
from plotter_signature.services.printer.printer_service import AutoConnectFailedError
from plotter_signature.services.printer.svg_converter import convert_to_gcode

_SERIAL_MATCH_ENV_KEYS = ("PLOTTER_SERIAL_DEVICE_MATCH", "PLOTTER_DEVICE_MATCH")


def _json_arg_to_dict(value: str) -> dict[str, Any]:
    candidate = Path(value)
    if candidate.exists() and candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _build_print_request(raw_json: str) -> PrintRequest:
    return PrintRequest.from_dict(_json_arg_to_dict(raw_json))


def _convert_svg_for_cli(svg_path: str, request: PrintRequest) -> list[str]:
    if request.scale <= 0:
        raise ValueError("Scale must be greater than 0.")
    if request.rotation < 0 or request.rotation > 360:
        raise ValueError("Rotation must be between 0 and 360.")
    if request.paper is not None:
        paper_w, paper_h = get_paper_size_mm(request.paper)
        request.width = f"{paper_w}mm"
        request.height = f"{paper_h}mm"

    with Path(svg_path).open("rb") as f:
        svg_stream = io.BytesIO(f.read())
    gcode = convert_to_gcode(svg_stream, request)
    if not gcode:
        raise ValueError("No drawable paths found.")
    return gcode


class CliSerialConnectError(RuntimeError):
    def __init__(self, message: str, *, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = payload


def _normalize_serial_device(device: str) -> str:
    candidate = device.strip()
    if sys.platform.startswith("win") and re.fullmatch(r"COM\d+", candidate, flags=re.IGNORECASE):
        return candidate.upper()
    if sys.platform.startswith("linux") and re.fullmatch(r"tty(?:USB|ACM)\d+", candidate, flags=re.IGNORECASE):
        return f"/dev/{candidate}"
    return candidate


def _candidate_match_text(candidate: dict[str, str]) -> str:
    return " ".join(
        value
        for key in ("device", "name", "description", "manufacturer", "hwid")
        if (value := candidate.get(key, "").strip())
    ).lower()


def scan_serial_devices() -> list[dict[str, str]]:
    try:
        from serial.tools import list_ports
    except ImportError as ex:
        raise RuntimeError("pyserial is required to scan serial ports.") from ex

    devices: list[dict[str, str]] = []
    is_windows = sys.platform.startswith("win")
    is_linux = sys.platform.startswith("linux")
    for port in list_ports.comports():
        device = _normalize_serial_device(str(port.device or ""))
        if not device:
            continue
        if is_windows and not re.fullmatch(r"COM\d+", device, flags=re.IGNORECASE):
            continue
        if is_linux and not re.fullmatch(r"/dev/tty(?:USB|ACM)\d+", device, flags=re.IGNORECASE):
            continue
        devices.append(
            {
                "device": device,
                "name": str(getattr(port, "name", "") or "").strip(),
                "description": str(getattr(port, "description", "") or "").strip(),
                "manufacturer": str(getattr(port, "manufacturer", "") or "").strip(),
                "hwid": str(getattr(port, "hwid", "") or "").strip(),
            }
        )
    devices.sort(key=lambda item: item["device"])
    return devices


def _resolve_device_match(explicit_match: str | None) -> str:
    if explicit_match and explicit_match.strip():
        return explicit_match.strip()
    for env_key in _SERIAL_MATCH_ENV_KEYS:
        value = (os.getenv(env_key) or "").strip()
        if value:
            return value
    return ""


def _select_serial_device(device_match: str, candidates: list[dict[str, str]]) -> dict[str, str] | None:
    needle = device_match.strip().lower()
    if not needle:
        return None
    for candidate in candidates:
        if needle in _candidate_match_text(candidate):
            return candidate
    return None


def connect_printer_serial(
    provider: ServiceProvider,
    *,
    com_port: str | None = None,
    baud_rate: int | None = None,
    device_match: str | None = None,
) -> dict[str, Any]:
    explicit_port = _normalize_serial_device(com_port or "") if com_port else ""
    match = _resolve_device_match(device_match)
    candidates = scan_serial_devices()
    selected = _select_serial_device(match, candidates)

    if match and selected is None and not explicit_port:
        raise CliSerialConnectError(
            f"No serial port matched device info '{match}'.",
            payload={
                "error": f"No serial port matched device info '{match}'.",
                "deviceMatch": match,
                "attemptedPorts": [candidate["device"] for candidate in candidates],
                "serialDevices": candidates,
            },
        )

    if explicit_port or selected is not None:
        target = explicit_port or selected["device"]
        try:
            provider.printer_service.open_port(com_port=target, baud_rate=baud_rate)
        except Exception as ex:
            raise CliSerialConnectError(
                f"Failed to open serial port {target}: {ex}",
                payload={
                    "error": f"Failed to open serial port {target}: {ex}",
                    "attemptedPorts": [target],
                    "deviceMatch": match or None,
                    "matchedDevice": selected,
                    "serialDevices": candidates,
                },
            ) from ex
        return {
            "connectedPort": provider.printer_service.port_name,
            "attemptedPorts": [target],
            "deviceMatch": match or None,
            "matchedDevice": selected,
            "serialDevices": candidates,
        }

    try:
        provider.printer_service.autoconnect(explicit_com_port=None, baud_rate=baud_rate)
    except AutoConnectFailedError as ex:
        raise CliSerialConnectError(
            str(ex),
            payload={
                "error": str(ex),
                "attemptedPorts": ex.attempted_ports,
                "deviceMatch": None,
                "matchedDevice": None,
                "serialDevices": candidates,
            },
        ) from ex
    return {
        "connectedPort": provider.printer_service.port_name,
        "attemptedPorts": [],
        "deviceMatch": None,
        "matchedDevice": None,
        "serialDevices": candidates,
    }


def _ensure_connected(
    com_port: str | None,
    baud_rate: int | None,
    auto_connect: bool,
    device_match: str | None = None,
) -> bool:
    provider = get_service_provider()
    if provider.printer_service.is_open:
        return False
    if not auto_connect:
        raise RuntimeError("Printer is not connected. Use connect command or enable --auto-connect.")

    connect_printer_serial(provider, com_port=com_port, baud_rate=baud_rate, device_match=device_match)
    return True


def cmd_connect(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    if provider.printer_service.is_open:
        _print_json({"message": f"Already connected to {provider.printer_service.port_name}."})
        return 0

    connect_result = connect_printer_serial(
        provider,
        com_port=args.com_port,
        baud_rate=args.baud_rate,
        device_match=args.device_match,
    )
    _print_json(
        {
            "message": f"Connected to {provider.printer_service.port_name}.",
            "status": asdict(provider.printer_service.get_status()),
            "serial": connect_result,
        }
    )
    return 0


def cmd_disconnect(_: argparse.Namespace) -> int:
    provider = get_service_provider()
    if not provider.printer_service.is_open:
        _print_json({"message": "Not connected."})
        return 0
    provider.printer_service.close_port()
    _print_json({"message": "Disconnected."})
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    provider = get_service_provider()
    _print_json(asdict(provider.printer_service.get_status()))
    return 0


def cmd_scan_serial(args: argparse.Namespace) -> int:
    candidates = scan_serial_devices()
    match = _resolve_device_match(args.device_match)
    selected = _select_serial_device(match, candidates)
    _print_json(
        {
            "deviceMatch": match or None,
            "selected": selected,
            "serialDevices": candidates,
        }
    )
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    request = _build_print_request(args.print_request_json)
    gcode = _convert_svg_for_cli(args.svg, request)
    svg_distance = provider.printer_service.calculate_svg_distance_mm(gcode)
    _print_json(
        {
            "message": f"Generated {len(gcode)} G-code commands.",
            "commandCount": len(gcode),
            "svgTotalDistanceMm": round(svg_distance, 3),
            "gcode": gcode,
        }
    )
    return 0


async def _cmd_print_async(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    auto_opened = _ensure_connected(args.com_port, args.baud_rate, args.auto_connect, args.device_match)
    try:
        request = _build_print_request(args.print_request_json)
        gcode = _convert_svg_for_cli(args.svg, request)
        result = await provider.printer_service.print(gcode)
        _print_json(asdict(result))
        return 0
    finally:
        if auto_opened:
            provider.printer_service.close_port()


def cmd_print(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_print_async(args))


async def _cmd_bulk_print_async(args: argparse.Namespace) -> int:
    if args.copies < 1 or args.copies > 100:
        raise ValueError("Copies must be between 1 and 100.")

    provider = get_service_provider()
    auto_opened = _ensure_connected(args.com_port, args.baud_rate, args.auto_connect, args.device_match)
    try:
        request = _build_print_request(args.print_request_json)
        gcode = _convert_svg_for_cli(args.svg, request)
        result = await provider.printer_service.bulk_print(gcode, args.copies)
        _print_json(asdict(result))
        return 0
    finally:
        if auto_opened:
            provider.printer_service.close_port()


def cmd_bulk_print(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_bulk_print_async(args))


async def _cmd_pen_change_start_async(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    auto_opened = _ensure_connected(args.com_port, args.baud_rate, args.auto_connect, args.device_match)
    try:
        result = await provider.printer_service.pen_change_start()
        _print_json(asdict(result))
        return 0
    finally:
        if auto_opened:
            provider.printer_service.close_port()


def cmd_pen_change_start(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_pen_change_start_async(args))


async def _cmd_pen_change_finish_async(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    auto_opened = _ensure_connected(args.com_port, args.baud_rate, args.auto_connect, args.device_match)
    try:
        result = await provider.printer_service.pen_change_finish()
        _print_json(asdict(result))
        return 0
    finally:
        if auto_opened:
            provider.printer_service.close_port()


def cmd_pen_change_finish(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_pen_change_finish_async(args))


async def _cmd_print_with_approval_async(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    auto_opened = _ensure_connected(args.com_port, args.baud_rate, args.auto_connect, args.device_match)
    try:
        request_payload = _json_arg_to_dict(args.request_json)
        request_model = PrintWithApprovalRequest.from_dict(request_payload)

        paper_stream: io.BytesIO | None = None
        paper_filename: str | None = None
        if args.paper_image:
            paper_path = Path(args.paper_image)
            paper_stream = io.BytesIO(paper_path.read_bytes())
            paper_filename = paper_path.name
        elif args.paper_image_base64:
            raw = args.paper_image_base64
            data = raw.split(",", 1)[1] if "," in raw else raw
            paper_stream = io.BytesIO(base64.b64decode(data))

        signature_path = Path(args.signature_svg)
        signature_stream = io.BytesIO(signature_path.read_bytes())

        approval_request = PrintApprovalRequest(
            paper_image_stream=paper_stream,
            paper_image_file_name=paper_filename,
            signature_svg_stream=signature_stream,
            signature_svg_file_name=signature_path.name,
            print_settings=request_model.print_settings,
            should_approve=request_model.should_approve,
        )

        response = await provider.print_approval_service.print_with_approval_async(approval_request)
        _print_json(asdict(response))
        return 0
    finally:
        if auto_opened:
            provider.printer_service.close_port()


def cmd_print_with_approval(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_print_with_approval_async(args))


def cmd_get_request(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    request_id = UUID(args.request_id)
    log = asyncio.run(provider.print_approval_service.get_request_log_async(request_id))
    if log is None:
        _print_json({"message": f"Request log with ID {request_id} not found."})
        return 1

    _print_json(log.to_dict())
    return 0


def cmd_distance_stats(_: argparse.Namespace) -> int:
    provider = get_service_provider()
    _print_json(provider.printer_service.get_distance_stats())
    return 0


def cmd_reset_distance(_: argparse.Namespace) -> int:
    provider = get_service_provider()
    _print_json(
        {
            "message": "Cumulative distance reset to 0 mm.",
            "stats": provider.printer_service.reset_cumulative_distance(),
        }
    )
    return 0


def cmd_set_pen_max_distance(args: argparse.Namespace) -> int:
    provider = get_service_provider()
    stats = provider.printer_service.set_max_pen_distance_m(args.meters)
    _print_json(
        {
            "message": f"Max pen distance set to {args.meters} meters.",
            "stats": stats,
        }
    )
    return 0


def cmd_serve_api(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError as ex:
        raise RuntimeError("uvicorn is not installed. Install project requirements first.") from ex

    from plotter_signature.web.fastapi_app.app import create_app

    app = create_app(get_service_provider())
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_serve_flask(args: argparse.Namespace) -> int:
    try:
        from plotter_signature.web.flask_app.app import create_app
    except ImportError as ex:
        raise RuntimeError("Flask app is unavailable. Install project requirements first.") from ex

    app = create_app(get_service_provider())
    app.run(host=args.host, port=args.port, debug=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plotter Signature CLI for printer automation.")
    sub = parser.add_subparsers(dest="command", required=True)

    connect = sub.add_parser("connect", help="Open printer serial connection.")
    connect.add_argument("--com-port", dest="com_port", default=None)
    connect.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    connect.add_argument(
        "--device-match",
        dest="device_match",
        default=None,
        help="Match serial device metadata (description/manufacturer/hwid), e.g. CH340 or VID:PID=1A86:7523.",
    )
    connect.set_defaults(func=cmd_connect)

    disconnect = sub.add_parser("disconnect", help="Close printer serial connection.")
    disconnect.set_defaults(func=cmd_disconnect)

    status = sub.add_parser("status", help="Show printer status.")
    status.set_defaults(func=cmd_status)

    scan_serial = sub.add_parser("scan-serial", help="List USB serial devices and selected metadata match.")
    scan_serial.add_argument(
        "--device-match",
        dest="device_match",
        default=None,
        help="Optional metadata text to match against description/manufacturer/hwid.",
    )
    scan_serial.set_defaults(func=cmd_scan_serial)

    generate = sub.add_parser("generate", help="Convert SVG to G-code.")
    generate.add_argument("--svg", required=True, help="Path to SVG file.")
    generate.add_argument(
        "--print-request-json",
        required=True,
        help="JSON string or path containing PrintRequest fields.",
    )
    generate.set_defaults(func=cmd_generate)

    print_cmd = sub.add_parser("print", help="Generate + print one signature.")
    print_cmd.add_argument("--svg", required=True)
    print_cmd.add_argument("--print-request-json", required=True)
    print_cmd.add_argument("--com-port", dest="com_port", default=None)
    print_cmd.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    print_cmd.add_argument("--device-match", dest="device_match", default=None)
    print_cmd.add_argument("--auto-connect", action=argparse.BooleanOptionalAction, default=True)
    print_cmd.set_defaults(func=cmd_print)

    bulk = sub.add_parser("bulk-print", help="Generate + print multiple copies.")
    bulk.add_argument("--svg", required=True)
    bulk.add_argument("--print-request-json", required=True)
    bulk.add_argument("--copies", required=True, type=int)
    bulk.add_argument("--com-port", dest="com_port", default=None)
    bulk.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    bulk.add_argument("--device-match", dest="device_match", default=None)
    bulk.add_argument("--auto-connect", action=argparse.BooleanOptionalAction, default=True)
    bulk.set_defaults(func=cmd_bulk_print)

    pen_change_start = sub.add_parser("pen-change-start", help="Move pen to change position.")
    pen_change_start.add_argument("--com-port", dest="com_port", default=None)
    pen_change_start.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    pen_change_start.add_argument("--device-match", dest="device_match", default=None)
    pen_change_start.add_argument("--auto-connect", action=argparse.BooleanOptionalAction, default=True)
    pen_change_start.set_defaults(func=cmd_pen_change_start)

    pen_change_finish = sub.add_parser("pen-change-finish", help="Move pen back to ready/up position.")
    pen_change_finish.add_argument("--com-port", dest="com_port", default=None)
    pen_change_finish.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    pen_change_finish.add_argument("--device-match", dest="device_match", default=None)
    pen_change_finish.add_argument("--auto-connect", action=argparse.BooleanOptionalAction, default=True)
    pen_change_finish.set_defaults(func=cmd_pen_change_finish)

    approval = sub.add_parser("print-with-approval", help="Run approval workflow and print/void.")
    approval.add_argument("--signature-svg", required=True)
    approval.add_argument("--request-json", required=True, help="JSON string or path to request payload.")
    approval.add_argument("--paper-image", default=None)
    approval.add_argument("--paper-image-base64", default=None)
    approval.add_argument("--com-port", dest="com_port", default=None)
    approval.add_argument("--baud-rate", dest="baud_rate", type=int, default=None)
    approval.add_argument("--device-match", dest="device_match", default=None)
    approval.add_argument("--auto-connect", action=argparse.BooleanOptionalAction, default=True)
    approval.set_defaults(func=cmd_print_with_approval)

    request = sub.add_parser("get-request", help="Get latest in-memory request log by request ID.")
    request.add_argument("--request-id", required=True)
    request.set_defaults(func=cmd_get_request)

    distance_stats = sub.add_parser("distance-stats", help="Show pen movement distance statistics.")
    distance_stats.set_defaults(func=cmd_distance_stats)

    reset_distance = sub.add_parser("reset-distance", help="Reset cumulative pen movement distance.")
    reset_distance.set_defaults(func=cmd_reset_distance)

    set_pen_max = sub.add_parser("set-pen-max-distance", help="Set max supported pen distance in meters.")
    set_pen_max.add_argument("--meters", required=True, type=float)
    set_pen_max.set_defaults(func=cmd_set_pen_max_distance)

    api = sub.add_parser("serve-api", help="Run FastAPI server.")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=5000)
    api.add_argument("--reload", action="store_true")
    api.set_defaults(func=cmd_serve_api)

    flask_api = sub.add_parser("serve-flask", help="Run Flask server with frontend UI.")
    flask_api.add_argument("--host", default="0.0.0.0")
    flask_api.add_argument("--port", type=int, default=5001)
    flask_api.add_argument("--reload", action="store_true")
    flask_api.set_defaults(func=cmd_serve_flask)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except CliSerialConnectError as ex:
        _print_json(ex.payload)
        return 1
    except Exception as ex:
        _print_json({"error": str(ex)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

