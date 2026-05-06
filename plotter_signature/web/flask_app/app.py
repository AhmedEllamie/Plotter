from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import queue
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from flask import Flask, Response, g, request, send_file, send_from_directory

from plotter_signature.dependency_injection import ServiceProvider, get_service_provider
from plotter_signature.domain.contracts import PrintRequest, get_paper_size_mm, parse_bool
from plotter_signature.infrastructure.security.api_key_auth import (
    API_KEY_HEADER,
    get_configured_api_key,
    is_api_key_required,
    validate_api_key,
)
from plotter_signature.services.printer.svg_converter import convert_to_gcode
from plotter_signature.web.flask_app.config import ScannerServiceSettings, load_capture_settings, load_scanner_service_settings
from plotter_signature.web.flask_app.response import api_error, api_success
from plotter_signature.web.flask_app.state import RuntimeState
from plotter_signature.web.startup_serial import run_startup_autoconnect


def _run_async(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def _get_json_dict() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    return {}


def _parse_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    return int(str(value))


def _ensure_connected(provider: ServiceProvider) -> None:
    if not provider.printer_service.is_open:
        raise RuntimeError(
            "Printer is not connected. Ensure the server process has opened the serial port "
            "(startup autoconnect / deployment configuration)."
        )


def _ensure_not_busy(provider: ServiceProvider) -> None:
    if provider.printer_service.is_busy:
        raise RuntimeError("Printer is busy.")


def _printer_status_public_dict(provider: ServiceProvider) -> dict[str, Any]:
    payload = asdict(provider.printer_service.get_status())
    payload.pop("port_name", None)
    payload.pop("is_open", None)
    return payload


def _capture_profile_to_scanner_session_payload(capture: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Build scanner session body from a sanitized capture dict. Second value: require quad points list."""
    payload: dict[str, Any] = {
        "autofocus_enabled": bool(capture.get("autofocus_enabled", False)),
        "manual_focus_value": float(capture.get("manual_focus_value", 35)),
    }
    quad_points = capture.get("quad_points")
    if isinstance(quad_points, list) and len(quad_points) == 4:
        payload["quad_points"] = quad_points
        return payload, True
    return payload, False


def _build_print_request(payload: dict[str, Any] | None) -> PrintRequest:
    data = payload or {}
    print_request = PrintRequest.from_dict(data)
    if print_request.scale < 1:
        raise ValueError("Scale must be at least 1.")
    if print_request.rotation < 0 or print_request.rotation > 360:
        raise ValueError("Rotation must be between 0 and 360.")
    if print_request.paper is not None:
        paper_w, paper_h = get_paper_size_mm(print_request.paper)
        print_request.width = f"{paper_w}mm"
        print_request.height = f"{paper_h}mm"
    return print_request


def _extract_print_payload() -> dict[str, Any]:
    json_payload = _get_json_dict()
    if json_payload:
        nested = json_payload.get("printRequest")
        if isinstance(nested, dict):
            return nested
        return json_payload

    raw_json = request.form.get("printRequestJson")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as ex:
            raise ValueError(f"Invalid printRequestJson: {ex}") from ex
        if not isinstance(parsed, dict):
            raise ValueError("printRequestJson must be a JSON object.")
        nested = parsed.get("printRequest")
        if isinstance(nested, dict):
            return nested
        return parsed

    if request.form:
        return request.form.to_dict(flat=True)

    return {}


def _extract_bulk_copies() -> int:
    json_payload = _get_json_dict()
    raw_copies = (
        json_payload.get("copies")
        or request.form.get("copies")
        or request.args.get("copies")
    )
    if raw_copies is None or raw_copies == "":
        raise ValueError("copies is required.")
    try:
        copies = int(str(raw_copies))
    except (TypeError, ValueError) as ex:
        raise ValueError("copies must be an integer.") from ex
    if copies < 1 or copies > 100:
        raise ValueError("copies must be between 1 and 100.")
    return copies


def _convert_svg(svg_payload: bytes, print_request: PrintRequest) -> list[str]:
    if not svg_payload:
        raise ValueError("SVG payload is empty.")
    gcode = convert_to_gcode(io.BytesIO(svg_payload), print_request)
    if not gcode:
        raise ValueError("No drawable paths found. If SVG contains text, convert to paths first.")
    return gcode


def _to_iso8601_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@dataclass
class _QueuedPrintJob:
    job_id: UUID
    kind: str
    svg_payload: bytes
    svg_file_name: str
    print_request_dict: dict[str, Any]
    copies: int


def _extract_capture_image_payload() -> tuple[str, str, bytes]:
    for key in ("photo", "image", "file", "capture"):
        upload = request.files.get(key)
        if upload is None:
            continue
        payload = upload.read()
        if payload:
            return (
                upload.filename or "capture.jpg",
                upload.mimetype or "image/jpeg",
                payload,
            )

    if request.files:
        upload = next(iter(request.files.values()))
        payload = upload.read()
        if payload:
            return (
                upload.filename or "capture.jpg",
                upload.mimetype or "image/jpeg",
                payload,
            )

    json_payload = _get_json_dict()
    image_base64 = json_payload.get("imageBase64") or request.form.get("imageBase64")
    if isinstance(image_base64, str) and image_base64:
        raw_data = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        try:
            payload = base64.b64decode(raw_data)
        except Exception as ex:
            raise ValueError(f"Invalid imageBase64 payload: {ex}") from ex
        if payload:
            return (
                str(json_payload.get("fileName") or request.form.get("fileName") or "capture.jpg"),
                str(json_payload.get("contentType") or request.form.get("contentType") or "image/jpeg"),
                payload,
            )

    raw_binary = request.get_data(cache=False)
    content_type = request.content_type or ""
    if raw_binary and content_type.startswith("image/"):
        return ("capture.jpg", content_type, raw_binary)

    raise ValueError("No capture image payload found.")


def _build_scanner_headers(scanner_settings: ScannerServiceSettings, include_content_type: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    if scanner_settings.token:
        headers["Authorization"] = f"Bearer {scanner_settings.token}"
    return headers


def _scanner_request_json(
    scanner_settings: ScannerServiceSettings,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request_obj = Request(
        url=f"{scanner_settings.base_url}{path}",
        data=data,
        method=method,
        headers=_build_scanner_headers(scanner_settings, include_content_type=body is not None),
    )
    with urlopen(request_obj, timeout=scanner_settings.timeout_seconds) as response:
        status_code = response.getcode()
        raw_body = response.read().decode("utf-8", errors="ignore")
        payload = json.loads(raw_body) if raw_body else {}
        if not isinstance(payload, dict):
            raise ValueError("Scanner response is not a JSON object.")
        return status_code, payload


def _scanner_request_bytes(scanner_settings: ScannerServiceSettings, path: str) -> tuple[int, str, bytes]:
    request_obj = Request(
        url=f"{scanner_settings.base_url}{path}",
        method="GET",
        headers=_build_scanner_headers(scanner_settings),
    )
    with urlopen(request_obj, timeout=scanner_settings.timeout_seconds) as response:
        return (
            response.getcode(),
            response.headers.get_content_type() or "application/octet-stream",
            response.read(),
        )


def _default_ui_profile_path() -> Path:
    override = (os.getenv("PLOTTER_UI_PROFILE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    app_data_dir = (os.getenv("APPDATA") or "").strip()
    if app_data_dir:
        return Path(app_data_dir) / "plotter-signature" / "ui-profile.json"
    return Path.home() / ".plotter-signature" / "ui-profile.json"


def _default_ui_profile_data() -> dict[str, Any]:
    return {
        "print": {
            "width": "210mm",
            "height": "297mm",
            "xPosition": "50mm",
            "yPosition": "50mm",
            "scale": 1,
            "rotation": 0,
            "invertX": False,
            "invertY": True,
        },
        "capture": {
            "autofocus_enabled": False,
            "manual_focus_value": 35,
            "quad_points": [],
        },
        "updatedAt": None,
    }


def _sanitize_ui_profile_data(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = _default_ui_profile_data()
    print_payload = payload.get("print")
    capture_payload = payload.get("capture")
    print_data = dict(defaults["print"])
    capture_data = dict(defaults["capture"])

    if isinstance(print_payload, dict):
        for key in ("width", "height", "xPosition", "yPosition"):
            value = print_payload.get(key)
            if isinstance(value, str) and value.strip():
                print_data[key] = value.strip()
        for key in ("scale", "rotation"):
            raw_value = print_payload.get(key)
            if raw_value is None or raw_value == "":
                continue
            try:
                print_data[key] = float(raw_value)
            except (TypeError, ValueError):
                continue
        for key in ("invertX", "invertY"):
            if key in print_payload:
                print_data[key] = bool(print_payload.get(key))

    if isinstance(capture_payload, dict):
        raw_autofocus = (
            capture_payload.get("autofocus_enabled")
            if "autofocus_enabled" in capture_payload
            else capture_payload.get("autofocusEnabled")
        )
        if raw_autofocus is not None:
            capture_data["autofocus_enabled"] = bool(raw_autofocus)

        raw_focus = (
            capture_payload.get("manual_focus_value")
            if "manual_focus_value" in capture_payload
            else capture_payload.get("manualFocusValue")
        )
        try:
            focus_value = int(float(raw_focus))
            capture_data["manual_focus_value"] = max(0, min(255, focus_value))
        except (TypeError, ValueError):
            pass

        raw_points = (
            capture_payload.get("quad_points")
            if "quad_points" in capture_payload
            else capture_payload.get("quadPoints")
        )
        sanitized_points: list[list[int]] = []
        if isinstance(raw_points, list):
            for point in raw_points:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    continue
                try:
                    x_value = int(round(float(point[0])))
                    y_value = int(round(float(point[1])))
                except (TypeError, ValueError):
                    continue
                sanitized_points.append([x_value, y_value])
        capture_data["quad_points"] = sanitized_points[:4]

    return {
        "print": print_data,
        "capture": capture_data,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _load_ui_profile_data(file_path: Path) -> dict[str, Any]:
    defaults = _default_ui_profile_data()
    if not file_path.exists():
        return defaults
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(payload, dict):
        return defaults
    return _sanitize_ui_profile_data(payload)


def _save_ui_profile_data(file_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_ui_profile_data(payload)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    temp_path.write_text(json.dumps(sanitized, ensure_ascii=True, indent=2), encoding="utf-8")
    temp_path.replace(file_path)
    return sanitized


def create_app(provider: ServiceProvider | None = None) -> Flask:
    provider = provider or get_service_provider()
    capture_settings = load_capture_settings()
    scanner_settings = load_scanner_service_settings()
    runtime_state = RuntimeState()
    last_scanner_manual_config: dict[str, Any] = {}
    capture_jobs_lock = threading.Lock()
    capture_jobs: dict[str, dict[str, Any]] = {}
    ui_profile_lock = threading.Lock()
    ui_profile_path = _default_ui_profile_path()
    ui_profile_exists = ui_profile_path.exists()
    ui_profile_data = _load_ui_profile_data(ui_profile_path)
    api_auth_cookie_name = "plotter_api_auth"

    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # Seed scanner manual config cache from persisted profile so oneshot capture can
    # still run even if startup bootstrap apply was skipped/failed.
    capture_profile = ui_profile_data.get("capture")
    if isinstance(capture_profile, dict):
        seeded_quad_points = capture_profile.get("quad_points")
        if isinstance(seeded_quad_points, list) and len(seeded_quad_points) == 4:
            last_scanner_manual_config["quad_points"] = seeded_quad_points
        if "autofocus_enabled" in capture_profile:
            last_scanner_manual_config["autofocus_enabled"] = bool(capture_profile.get("autofocus_enabled"))
        if "manual_focus_value" in capture_profile:
            try:
                last_scanner_manual_config["manual_focus_value"] = float(capture_profile.get("manual_focus_value"))
            except (TypeError, ValueError):
                pass

    pending_print_queue: queue.Queue[_QueuedPrintJob] = queue.Queue()
    print_execution_lock = threading.Lock()
    active_history_job_holder: dict[str, UUID | None] = {"id": None}

    def _apply_print_stop_side_effects() -> dict[str, Any]:
        jid = active_history_job_holder.get("id")
        if jid:
            st = provider.printer_service.get_status()
            provider.print_history_store.update_completed(
                jid,
                status="stopped",
                copies_printed=int(st.bulk_printed_count or 0),
                error_message="Print stop requested",
                result_json={"printerStatus": asdict(st)},
            )
        runtime_state.clear_uploaded_svg()
        return {"jobStopped": True}

    def _execute_queued_job(job: _QueuedPrintJob) -> dict[str, Any]:
        active_history_job_holder["id"] = job.job_id
        provider.print_history_store.update_started(job.job_id)
        try:
            print_request = _build_print_request(job.print_request_dict)
            gcode = _convert_svg(job.svg_payload, print_request)
            if job.kind == "bulk":
                print_result = _run_async(provider.printer_service.bulk_print(gcode, job.copies))
                copies_printed = int(print_result.copies or 0)
                final_status = "stopped" if copies_printed < job.copies else "completed"
                data = {
                    "svgFileName": job.svg_file_name,
                    "copies": job.copies,
                    "commandCount": len(gcode),
                    "result": asdict(print_result),
                    "bulkProgress": {
                        "requestedTotal": job.copies,
                        "printedCount": copies_printed,
                        "stopRequested": final_status == "stopped",
                    },
                }
            else:
                print_result = _run_async(provider.printer_service.print(gcode))
                final_status = "stopped" if print_result.job_stopped else "completed"
                copies_printed = 0 if print_result.job_stopped else 1
                data = {
                    "svgFileName": job.svg_file_name,
                    "commandCount": len(gcode),
                    "result": asdict(print_result),
                }
            provider.print_history_store.update_completed(
                job.job_id,
                status=final_status,
                copies_printed=copies_printed,
                result_json={"payload": data},
            )
            runtime_state.clear_uploaded_svg()
            return data
        except Exception as ex:
            provider.print_history_store.update_completed(job.job_id, status="failed", error_message=str(ex))
            runtime_state.clear_uploaded_svg()
            raise
        finally:
            active_history_job_holder["id"] = None

    def _drain_pending_print_queue() -> None:
        while True:
            try:
                next_job = pending_print_queue.get_nowait()
            except queue.Empty:
                break
            try:
                _execute_queued_job(next_job)
            except (ValueError, RuntimeError, Exception):
                pass

    def _submit_print_job(
        kind: str,
        svg_payload: bytes,
        svg_file_name: str,
        print_request_dict: dict[str, Any],
        copies: int,
    ) -> tuple[Response, int]:
        svg_name = svg_file_name or "uploaded.svg"
        sha = hashlib.sha256(svg_payload).hexdigest()
        job_uuid = provider.print_history_store.insert_queued(
            job_type=kind,
            signature_file_name=svg_name,
            signature_sha256=sha,
            copies_requested=copies if kind == "bulk" else 1,
        )
        job = _QueuedPrintJob(
            job_id=job_uuid,
            kind=kind,
            svg_payload=svg_payload,
            svg_file_name=svg_name,
            print_request_dict=dict(print_request_dict),
            copies=copies,
        )

        if not print_execution_lock.acquire(blocking=False):
            pending_print_queue.put(job)
            return api_success(
                message="Printer busy; print job queued.",
                data={
                    "queued": True,
                    "jobId": str(job_uuid),
                    "queuePosition": pending_print_queue.qsize(),
                    "jobType": kind,
                    "signatureSha256": sha,
                    "svgFileName": svg_name,
                },
                status_code=202,
            )

        try:
            try:
                out = _execute_queued_job(job)
                _drain_pending_print_queue()
                return api_success(
                    message="Print completed." if kind == "print" else "Bulk print completed.",
                    data={**out, "queued": False, "jobId": str(job_uuid), "jobType": kind},
                )
            except ValueError as ex:
                _drain_pending_print_queue()
                return api_error(str(ex), error_code="PRINT_VALIDATION_ERROR", status_code=400)
            except RuntimeError as ex:
                _drain_pending_print_queue()
                return api_error(str(ex), error_code="PRINT_RUNTIME_ERROR", status_code=400)
            except Exception as ex:
                _drain_pending_print_queue()
                if kind == "bulk":
                    return api_error(f"Bulk print failed: {ex}", error_code="BULK_PRINT_FAILED", status_code=500)
                return api_error(f"Print failed: {ex}", error_code="PRINT_FAILED", status_code=500)
        finally:
            print_execution_lock.release()

    @app.before_request
    def require_api_key_for_api_routes() -> tuple[Response, int] | None:
        if not request.path.startswith("/api/"):
            return None

        header_api_key = (request.headers.get(API_KEY_HEADER) or "").strip()
        cookie_api_key = (request.cookies.get(api_auth_cookie_name) or "").strip()
        provided_api_key = header_api_key or cookie_api_key
        validation = validate_api_key(provided_api_key)
        if validation.is_valid:
            # If a request came with a valid header key, persist auth for browser subresource
            # requests (like <img src="/api/config/scanner/stream.mjpg">) that cannot send
            # custom headers.
            g.issue_api_auth_cookie = bool(header_api_key)
            return None

        return api_error(
            validation.message,
            error_code="UNAUTHORIZED",
            status_code=401,
        )

    @app.after_request
    def issue_api_auth_cookie(response: Response) -> Response:
        if (
            bool(getattr(g, "issue_api_auth_cookie", False))
            and is_api_key_required()
        ):
            configured = get_configured_api_key()
            if configured:
                response.set_cookie(
                    key=api_auth_cookie_name,
                    value=configured,
                    max_age=60 * 60 * 24 * 7,
                    httponly=True,
                    samesite="Lax",
                    secure=False,
                    path="/",
                )
        return response

    def _merge_scanner_manual_config(payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        if "quad_points" not in merged and isinstance(last_scanner_manual_config.get("quad_points"), list):
            merged["quad_points"] = last_scanner_manual_config["quad_points"]
        if "autofocus_enabled" not in merged and "autofocus_enabled" in last_scanner_manual_config:
            merged["autofocus_enabled"] = last_scanner_manual_config.get("autofocus_enabled")
        if "manual_focus_value" not in merged and "manual_focus_value" in last_scanner_manual_config:
            merged["manual_focus_value"] = last_scanner_manual_config.get("manual_focus_value")
        return merged

    def _remember_scanner_manual_config(payload: dict[str, Any], scanner_response: dict[str, Any]) -> None:
        qp_block = scanner_response.get("quad_points")
        if isinstance(qp_block, dict) and isinstance(qp_block.get("manual_config"), dict):
            source = qp_block["manual_config"]
        else:
            source = scanner_response.get("manual_config")
        if not isinstance(source, dict):
            source = payload
        for key in ("autofocus_enabled", "manual_focus_value", "quad_points", "frame_width", "frame_height"):
            if key in source:
                last_scanner_manual_config[key] = source.get(key)

    def _apply_scanner_session_config(
        payload: dict[str, Any],
        *,
        require_quad_points: bool,
    ) -> dict[str, Any]:
        merged_payload = _merge_scanner_manual_config(payload)
        focus_payload = {
            "autofocus_enabled": bool(merged_payload.get("autofocus_enabled", False)),
            "manual_focus_value": float(merged_payload.get("manual_focus_value", 35)),
        }
        quad_points = merged_payload.get("quad_points")
        if require_quad_points and not isinstance(quad_points, list):
            raise RuntimeError("quad_points are required for this operation.")

        try:
            _, focus_mode_response = _scanner_request_json(
                scanner_settings,
                "/session/focus-mode",
                method="POST",
                body=focus_payload,
            )
            if focus_mode_response.get("ok") is False:
                raise RuntimeError(focus_mode_response.get("message") or "Scanner focus mode failed.")

            quad_points_response: dict[str, Any] = {}
            if isinstance(quad_points, list):
                _, quad_points_response = _scanner_request_json(
                    scanner_settings,
                    "/session/quad-points",
                    method="POST",
                    body={"quad_points": quad_points},
                )
                if quad_points_response.get("ok") is False:
                    raise RuntimeError(quad_points_response.get("message") or "Scanner quad points failed.")

            composed_response: dict[str, Any] = {"ok": True}
            composed_response["focus_mode"] = focus_mode_response
            if quad_points_response:
                composed_response["quad_points"] = quad_points_response
            composed_response["manual_config"] = {
                "autofocus_enabled": focus_payload["autofocus_enabled"],
                "manual_focus_value": focus_payload["manual_focus_value"],
                "quad_points": quad_points if isinstance(quad_points, list) else last_scanner_manual_config.get("quad_points"),
                "frame_width": last_scanner_manual_config.get("frame_width"),
                "frame_height": last_scanner_manual_config.get("frame_height"),
            }
            return composed_response
        except HTTPError as ex:
            # New split endpoints may not be available on older scanner services.
            if ex.code not in {404, 405}:
                raise

        _, manual_config_response = _scanner_request_json(
            scanner_settings,
            "/session/manual-config",
            method="POST",
            body=merged_payload,
        )
        if manual_config_response.get("ok") is False:
            raise RuntimeError(manual_config_response.get("message") or "Scanner manual config failed.")
        return manual_config_response

    def _bootstrap_scanner_config_from_profile() -> None:
        if not ui_profile_exists:
            return
        capture_profile = ui_profile_data.get("capture")
        if not isinstance(capture_profile, dict):
            return
        quad_points = capture_profile.get("quad_points")
        if not isinstance(quad_points, list) or len(quad_points) != 4:
            return
        payload = {
            "autofocus_enabled": bool(capture_profile.get("autofocus_enabled", False)),
            "manual_focus_value": float(capture_profile.get("manual_focus_value", 35)),
            "quad_points": quad_points,
        }
        try:
            response = _apply_scanner_session_config(payload, require_quad_points=True)
            _remember_scanner_manual_config(payload, response)
            app.logger.info("Applied scanner focus and quad points from persisted UI profile.")
        except Exception as ex:
            app.logger.warning("Startup scanner config apply skipped: %s", ex)

    _bootstrap_scanner_config_from_profile()

    def _capture_job_snapshot(job_id: str) -> dict[str, Any]:
        with capture_jobs_lock:
            raw = capture_jobs.get(job_id)
            if raw is None:
                raise KeyError(job_id)
            return dict(raw)

    def _capture_job_update(job_id: str, **updates: Any) -> None:
        with capture_jobs_lock:
            job = capture_jobs.get(job_id)
            if job is None:
                return
            job.update(updates)

    def _run_capture_job(job_id: str, readability_required: bool, timeout_seconds: int) -> None:
        _capture_job_update(job_id, state="running", startedAt=datetime.now(timezone.utc).isoformat())
        try:
            _, start_capture_response = _scanner_request_json(
                scanner_settings,
                "/capture/start",
                method="POST",
                body={
                    "readability_required": bool(readability_required),
                    "timeout_seconds": int(timeout_seconds),
                },
            )
            if start_capture_response.get("ok") is False:
                raise RuntimeError(start_capture_response.get("message") or "Scanner capture start failed.")
            capture = start_capture_response.get("capture") or {}
            capture_id = str(capture.get("capture_id") or capture.get("job_id") or "").strip()
            if not capture_id:
                raise RuntimeError("Scanner capture id was not returned.")
            _capture_job_update(job_id, captureId=capture_id, scannerStatus="started")

            max_attempts = max(1, scanner_settings.job_poll_max_attempts)
            interval_seconds = max(0.05, float(scanner_settings.job_poll_interval_seconds))
            latest_capture = capture
            for attempt in range(max_attempts):
                _, capture_status_response = _scanner_request_json(
                    scanner_settings,
                    f"/capture/{capture_id}/status",
                    method="GET",
                )
                latest_capture = capture_status_response.get("capture") or {}
                scanner_status = str(latest_capture.get("status") or "").strip().lower()
                _capture_job_update(
                    job_id,
                    scannerStatus=scanner_status or "unknown",
                    attempts=attempt + 1,
                )
                if scanner_status in {"succeeded", "failed"}:
                    break
                time.sleep(interval_seconds)

            final_status = str(latest_capture.get("status") or "").strip().lower()
            if final_status != "succeeded":
                if final_status not in {"failed"}:
                    _capture_job_update(
                        job_id,
                        state="timeout",
                        completedAt=datetime.now(timezone.utc).isoformat(),
                        error="Capture status polling timed out.",
                    )
                    return
                raise RuntimeError(
                    f"Scanner capture failed: {latest_capture.get('error') or 'unknown_error'} - "
                    f"{latest_capture.get('detail') or 'no detail'}."
                )

            _, content_type, image_payload = _scanner_request_bytes(scanner_settings, f"/capture/{capture_id}/result")
            if not image_payload:
                raise RuntimeError("Scanner returned an empty rectified image.")
            model = runtime_state.set_captured_image(
                file_name=f"rectified-{capture_id}.png",
                content_type=content_type,
                content=image_payload,
            )
            _capture_job_update(
                job_id,
                state="succeeded",
                completedAt=datetime.now(timezone.utc).isoformat(),
                fileName=model.file_name,
                contentType=model.content_type,
                capturedAt=_to_iso8601_utc(model.captured_at),
                imageUrl="/api/config/capture/latest/image",
            )
        except HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            _capture_job_update(
                job_id,
                state="failed",
                completedAt=datetime.now(timezone.utc).isoformat(),
                error=f"Scanner request failed with HTTP {ex.code}.",
                errorCode="SCANNER_HTTP_ERROR",
                details={"statusCode": ex.code, "responseBody": body[:4000]},
            )
        except URLError as ex:
            _capture_job_update(
                job_id,
                state="failed",
                completedAt=datetime.now(timezone.utc).isoformat(),
                error=f"Failed to reach scanner service: {ex}",
                errorCode="SCANNER_UNREACHABLE",
            )
        except Exception as ex:
            _capture_job_update(
                job_id,
                state="failed",
                completedAt=datetime.now(timezone.utc).isoformat(),
                error=str(ex),
                errorCode="SCANNER_CAPTURE_FAILED",
            )

    @app.get("/")
    def home() -> Response:
        if not app.static_folder:
            return api_success(message="Plotter Signature Flask API")[0]
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/configuration")
    def configuration() -> Response:
        if not app.static_folder:
            return api_success(message="Plotter Signature Flask API")[0]
        return send_from_directory(app.static_folder, "configuration.html")

    @app.get("/api/cmd/health")
    def health() -> tuple[Response, int]:
        return api_success(
            message="Service is healthy.",
            data={
                "printerConnected": provider.printer_service.is_open,
                "printerBusy": provider.printer_service.is_busy,
                "captureResetConfigured": capture_settings.is_configured,
            },
        )

    @app.get("/api/config")
    def config() -> tuple[Response, int]:
        return api_success(
            message="Runtime config loaded.",
            data={
                "defaultComPort": provider.printer_service.default_com_port,
                "defaultBaudRate": provider.printer_service.default_baud_rate,
                "captureResetConfigured": capture_settings.is_configured,
                "captureResetMethod": capture_settings.reset_method,
                "scannerServiceConfigured": scanner_settings.is_configured,
                "scannerServiceBaseUrl": scanner_settings.base_url,
            },
        )

    @app.get("/api/config/ui-profile")
    def get_ui_profile() -> tuple[Response, int]:
        with ui_profile_lock:
            return api_success(message="UI profile loaded.", data=dict(ui_profile_data))

    @app.post("/api/config/ui-profile")
    def save_ui_profile() -> tuple[Response, int]:
        payload = _get_json_dict()
        if not payload:
            return api_error("UI profile payload is required.", error_code="UI_PROFILE_REQUIRED", status_code=400)
        try:
            saved_profile = _save_ui_profile_data(ui_profile_path, payload)
        except Exception as ex:
            return api_error(
                f"Failed to save UI profile: {ex}",
                error_code="UI_PROFILE_SAVE_FAILED",
                status_code=500,
            )
        scanner_warning: str | None = None
        with ui_profile_lock:
            ui_profile_data.clear()
            ui_profile_data.update(saved_profile)
            saved_capture = saved_profile.get("capture")
            if isinstance(saved_capture, dict):
                if isinstance(saved_capture.get("quad_points"), list):
                    last_scanner_manual_config["quad_points"] = saved_capture.get("quad_points")
                if "autofocus_enabled" in saved_capture:
                    last_scanner_manual_config["autofocus_enabled"] = bool(saved_capture.get("autofocus_enabled"))
                if "manual_focus_value" in saved_capture:
                    try:
                        last_scanner_manual_config["manual_focus_value"] = float(saved_capture.get("manual_focus_value"))
                    except (TypeError, ValueError):
                        pass

            if scanner_settings.is_configured and isinstance(saved_capture, dict):
                session_payload, require_quad = _capture_profile_to_scanner_session_payload(saved_capture)
                try:
                    scanner_response = _apply_scanner_session_config(session_payload, require_quad_points=require_quad)
                    if scanner_response.get("ok") is False:
                        raise RuntimeError(scanner_response.get("message") or "Scanner session apply failed.")
                    _remember_scanner_manual_config(session_payload, scanner_response)
                except Exception as ex:
                    scanner_warning = str(ex)
                    app.logger.warning("Scanner apply after UI profile save failed: %s", ex)

        data_out = dict(ui_profile_data)
        if scanner_warning:
            data_out["scannerApplyWarning"] = scanner_warning
        message = "UI profile saved."
        if scanner_warning:
            message = f"{message} Scanner apply failed: {scanner_warning}"
        return api_success(message=message, data=data_out)

    @app.get("/api/config/scanner/stream.mjpg")
    def scanner_stream_proxy() -> Response | tuple[Response, int]:
        fps = request.args.get("fps", "10")
        width = request.args.get("width", "0")
        fisheye = request.args.get("fisheye", "1")
        query = urlencode({"fps": fps, "width": width, "fisheye": fisheye})
        path = f"/stream.mjpg?{query}"
        request_obj = Request(
            url=f"{scanner_settings.base_url}{path}",
            method="GET",
            headers=_build_scanner_headers(scanner_settings),
        )
        try:
            upstream = urlopen(request_obj, timeout=scanner_settings.timeout_seconds)
        except HTTPError as ex:
            return api_error(
                f"Scanner stream failed with HTTP {ex.code}.",
                error_code="SCANNER_STREAM_HTTP_ERROR",
                status_code=502,
            )
        except URLError as ex:
            return api_error(
                f"Failed to reach scanner stream: {ex}",
                error_code="SCANNER_STREAM_UNREACHABLE",
                status_code=502,
            )
        except Exception as ex:
            return api_error(f"Scanner stream proxy failed: {ex}", error_code="SCANNER_STREAM_FAILED", status_code=500)

        return Response(
            upstream,
            content_type=upstream.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame"),
            direct_passthrough=True,
        )

    @app.post("/api/config/scanner/capture/start")
    def scanner_capture_start() -> tuple[Response, int]:
        payload = _get_json_dict()
        request_payload = {
            "readability_required": bool(payload.get("readability_required", True)),
            "timeout_seconds": int(payload.get("timeout_seconds", 15)),
        }
        try:
            _, start_capture_response = _scanner_request_json(
                scanner_settings,
                "/capture/start",
                method="POST",
                body=request_payload,
            )
            if start_capture_response.get("ok") is False:
                raise RuntimeError(start_capture_response.get("message") or "Scanner capture start failed.")
            capture = start_capture_response.get("capture") or {}
            capture_id = str(capture.get("capture_id") or capture.get("job_id") or "").strip()
            if not capture_id:
                raise RuntimeError("Scanner capture id was not returned.")
        except HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            return api_error(
                f"Scanner capture start failed with HTTP {ex.code}.",
                error_code="SCANNER_HTTP_ERROR",
                status_code=502,
                details={"statusCode": ex.code, "responseBody": body[:4000]},
            )
        except URLError as ex:
            return api_error(
                f"Failed to reach scanner service: {ex}",
                error_code="SCANNER_UNREACHABLE",
                status_code=502,
            )
        except Exception as ex:
            return api_error(f"Capture start failed: {ex}", error_code="SCANNER_CAPTURE_FAILED", status_code=500)
        return api_success("Scanner capture started.", data={"captureId": capture_id, "capture": capture})

    @app.get("/api/config/scanner/capture/<string:capture_id>/status")
    def scanner_capture_status(capture_id: str) -> tuple[Response, int]:
        capture_id = capture_id.strip()
        if not capture_id:
            return api_error("capture_id is required.", error_code="SCANNER_CONFIG_REQUIRED", status_code=400)
        try:
            _, capture_status_response = _scanner_request_json(
                scanner_settings,
                f"/capture/{capture_id}/status",
                method="GET",
            )
            capture = capture_status_response.get("capture") or {}
        except HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            return api_error(
                f"Scanner capture status failed with HTTP {ex.code}.",
                error_code="SCANNER_HTTP_ERROR",
                status_code=502,
                details={"statusCode": ex.code, "responseBody": body[:4000]},
            )
        except URLError as ex:
            return api_error(
                f"Failed to reach scanner service: {ex}",
                error_code="SCANNER_UNREACHABLE",
                status_code=502,
            )
        except Exception as ex:
            return api_error(f"Capture status failed: {ex}", error_code="SCANNER_CAPTURE_FAILED", status_code=500)
        return api_success("Scanner capture status loaded.", data={"captureId": capture_id, "capture": capture})

    @app.get("/api/config/scanner/capture/<string:capture_id>/result")
    def scanner_capture_result(capture_id: str) -> Response | tuple[Response, int]:
        capture_id = capture_id.strip()
        if not capture_id:
            return api_error("capture_id is required.", error_code="SCANNER_CONFIG_REQUIRED", status_code=400)
        try:
            _, content_type, image_payload = _scanner_request_bytes(scanner_settings, f"/capture/{capture_id}/result")
            if not image_payload:
                raise RuntimeError("Scanner returned an empty rectified image.")
        except HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            return api_error(
                f"Scanner capture result failed with HTTP {ex.code}.",
                error_code="SCANNER_HTTP_ERROR",
                status_code=502,
                details={"statusCode": ex.code, "responseBody": body[:4000]},
            )
        except URLError as ex:
            return api_error(
                f"Failed to reach scanner service: {ex}",
                error_code="SCANNER_UNREACHABLE",
                status_code=502,
            )
        except Exception as ex:
            return api_error(f"Capture result failed: {ex}", error_code="SCANNER_CAPTURE_FAILED", status_code=500)

        runtime_state.set_captured_image(
            file_name=f"rectified-{capture_id}.png",
            content_type=content_type,
            content=image_payload,
        )
        return send_file(
            io.BytesIO(image_payload),
            mimetype=content_type,
            as_attachment=False,
            download_name=f"rectified-{capture_id}.png",
            max_age=0,
        )

    @app.post("/api/config/scanner/capture/run")
    def scanner_capture_run() -> tuple[Response, int]:
        payload = _get_json_dict()
        readability_required = bool(payload.get("readability_required", True))
        timeout_seconds = int(payload.get("timeout_seconds", 15))
        job_id = str(uuid4())
        with capture_jobs_lock:
            capture_jobs[job_id] = {
                "jobId": job_id,
                "state": "pending",
                "readabilityRequired": readability_required,
                "timeoutSeconds": timeout_seconds,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "startedAt": None,
                "completedAt": None,
                "captureId": None,
                "scannerStatus": None,
                "attempts": 0,
                "error": None,
                "errorCode": None,
                "details": None,
                "fileName": None,
                "contentType": None,
                "capturedAt": None,
                "imageUrl": None,
            }

        worker = threading.Thread(
            target=_run_capture_job,
            args=(job_id, readability_required, timeout_seconds),
            daemon=True,
        )
        worker.start()
        return api_success(
            "Scanner capture orchestration started.",
            data={"jobId": job_id, "state": "pending"},
            status_code=202,
        )

    @app.get("/api/config/scanner/capture/run/<string:job_id>")
    def scanner_capture_run_status(job_id: str) -> tuple[Response, int]:
        job_id = job_id.strip()
        if not job_id:
            return api_error("job_id is required.", error_code="SCANNER_CONFIG_REQUIRED", status_code=400)
        try:
            snapshot = _capture_job_snapshot(job_id)
        except KeyError:
            return api_error("Capture job not found.", error_code="CAPTURE_JOB_NOT_FOUND", status_code=404)
        return api_success("Capture orchestration status loaded.", data=snapshot)

    @app.get("/api/cmd/status")
    def status() -> tuple[Response, int]:
        return api_success(message="Printer status loaded.", data=_printer_status_public_dict(provider))

    @app.post("/api/cmd/print")
    def print_svg() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
        except RuntimeError as ex:
            return api_error(str(ex), error_code="PRINTER_STATE_ERROR", status_code=409)

        upload = request.files.get("svg") or request.files.get("file")
        if upload is None:
            return api_error(
                "SVG file is required on each print (multipart field 'svg' or 'file').",
                error_code="SVG_REQUIRED",
                status_code=400,
            )
        svg_payload = upload.read()
        svg_file_name = upload.filename or "uploaded.svg"
        if not svg_payload:
            return api_error("Uploaded SVG is empty.", error_code="EMPTY_SVG", status_code=400)

        print_request_dict = _extract_print_payload()
        return _submit_print_job("print", svg_payload, svg_file_name, print_request_dict, copies=1)

    @app.post("/api/cmd/print/bulk")
    def bulk_print_svg() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
        except RuntimeError as ex:
            return api_error(str(ex), error_code="PRINTER_STATE_ERROR", status_code=409)

        upload = request.files.get("svg") or request.files.get("file")
        if upload is None:
            return api_error(
                "SVG file is required on each bulk print (multipart field 'svg' or 'file').",
                error_code="SVG_REQUIRED",
                status_code=400,
            )
        svg_payload = upload.read()
        svg_file_name = upload.filename or "uploaded.svg"
        if not svg_payload:
            return api_error("Uploaded SVG is empty.", error_code="EMPTY_SVG", status_code=400)

        try:
            copies = _extract_bulk_copies()
        except ValueError as ex:
            return api_error(str(ex), error_code="PRINT_VALIDATION_ERROR", status_code=400)

        print_request_dict = _extract_print_payload()
        return _submit_print_job("bulk", svg_payload, svg_file_name, print_request_dict, copies=copies)

    @app.post("/api/cmd/bulk/stop")
    def stop_bulk_print() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
            stop_requested = provider.printer_service.stop_bulk_print()
        except RuntimeError as ex:
            return api_error(str(ex), error_code="PRINTER_STATE_ERROR", status_code=409)
        except Exception as ex:
            return api_error(f"Failed to stop bulk print: {ex}", error_code="BULK_STOP_FAILED", status_code=500)

        if not stop_requested:
            return api_error("No active print job to stop.", error_code="PRINTER_NOT_BUSY", status_code=409)

        data = _apply_print_stop_side_effects()

        return api_success(
            message="Bulk stop requested.",
            data=data,
        )

    @app.post("/api/cmd/void")
    def void_print() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
            if provider.printer_service.is_voiding:
                return api_error(
                    "Void operation already running.",
                    error_code="VOID_BUSY",
                    status_code=409,
                )
            if provider.printer_service.is_printing:
                stop_requested = provider.printer_service.request_print_cancel()
                if not stop_requested:
                    return api_error("No active print job to stop.", error_code="PRINTER_NOT_BUSY", status_code=409)
                data = _apply_print_stop_side_effects()
                return api_success(
                    message="Current print job stop requested. The printer will eject and return to idle.",
                    data=data,
                )
            result = _run_async(provider.printer_service.void_print())
        except RuntimeError as ex:
            return api_error(str(ex), error_code="VOID_RUNTIME_ERROR", status_code=409)
        except Exception as ex:
            return api_error(f"Void print failed: {ex}", error_code="VOID_FAILED", status_code=500)

        return api_success("Void print completed.", data=asdict(result))

    @app.post("/api/config/change-pen/start")
    def change_pen_start() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
            _ensure_not_busy(provider)
            result = _run_async(provider.printer_service.pen_change_start())
        except RuntimeError as ex:
            return api_error(str(ex), error_code="PEN_CHANGE_STATE_ERROR", status_code=409)
        except Exception as ex:
            return api_error(f"Pen change start failed: {ex}", error_code="PEN_CHANGE_START_FAILED", status_code=500)

        return api_success("Pen change start completed.", data=asdict(result))

    @app.post("/api/config/change-pen/finish")
    def change_pen_finish() -> tuple[Response, int]:
        try:
            _ensure_connected(provider)
            _ensure_not_busy(provider)
            result = _run_async(provider.printer_service.pen_change_finish())
        except RuntimeError as ex:
            return api_error(str(ex), error_code="PEN_CHANGE_STATE_ERROR", status_code=409)
        except Exception as ex:
            return api_error(
                f"Pen change finish failed: {ex}",
                error_code="PEN_CHANGE_FINISH_FAILED",
                status_code=500,
            )

        return api_success("Pen change finish completed.", data=asdict(result))

    @app.post("/api/config/change-pen")
    def change_pen() -> tuple[Response, int]:
        payload = _get_json_dict() or request.form.to_dict(flat=True)
        mode = str(payload.get("mode", "start")).strip().lower()
        if mode not in {"start", "finish"}:
            return api_error(
                "Change pen mode must be 'start' or 'finish'.",
                error_code="INVALID_PEN_MODE",
                status_code=400,
            )
        if mode == "start":
            return change_pen_start()
        return change_pen_finish()

    @app.post("/api/config/reset")
    def reset() -> tuple[Response, int]:
        if provider.printer_service.is_busy:
            return api_error(
                "Cannot reset while printer is busy.",
                error_code="PRINTER_BUSY",
                status_code=409,
            )

        payload = _get_json_dict()
        try:
            stats = provider.printer_service.reset_cumulative_distance()
            max_pen_distance = payload.get("maxPenDistanceM")
            if max_pen_distance is not None:
                stats = provider.printer_service.set_max_pen_distance_m(float(max_pen_distance))
        except ValueError as ex:
            return api_error(str(ex), error_code="RESET_VALIDATION_ERROR", status_code=400)
        except Exception as ex:
            return api_error(f"Reset failed: {ex}", error_code="RESET_FAILED", status_code=500)

        return api_success(
            message="Printer distance stats reset.",
            data={"stats": stats},
        )

    @app.post("/api/config/pen-max-distance")
    def set_pen_max_distance() -> tuple[Response, int]:
        payload = _get_json_dict() or request.form.to_dict(flat=True)
        raw_meters = payload.get("meters") or payload.get("maxPenDistanceM")
        if raw_meters is None:
            return api_error(
                "meters is required.",
                error_code="PEN_MAX_DISTANCE_REQUIRED",
                status_code=400,
            )
        try:
            stats = provider.printer_service.set_max_pen_distance_m(float(raw_meters))
        except ValueError as ex:
            return api_error(str(ex), error_code="PEN_MAX_DISTANCE_INVALID", status_code=400)
        except Exception as ex:
            return api_error(
                f"Failed to set max pen distance: {ex}",
                error_code="PEN_MAX_DISTANCE_FAILED",
                status_code=500,
            )

        return api_success(
            message="Max pen distance updated.",
            data={"stats": stats},
        )

    def _scanner_manual_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Strip API-only keys so they are never sent to the scanner session endpoints."""
        work = dict(payload)
        work.pop("includeDataUri", None)
        return work

    def _scanner_capture_manual_impl(*, include_data_uri_default: bool) -> tuple[Response, int]:
        payload = _get_json_dict()
        if not payload:
            return api_error("Capture config payload is required.", error_code="SCANNER_CONFIG_REQUIRED", status_code=400)

        session_payload = _scanner_manual_session_payload(payload)
        include_data_uri = parse_bool(payload.get("includeDataUri"), default=include_data_uri_default)

        try:
            manual_config_response = _apply_scanner_session_config(session_payload, require_quad_points=True)
            if manual_config_response.get("ok") is False:
                raise RuntimeError(manual_config_response.get("message") or "Scanner manual config failed.")
            _remember_scanner_manual_config(session_payload, manual_config_response)

            _, start_capture_response = _scanner_request_json(
                scanner_settings,
                "/capture/start",
                method="POST",
                body={"readability_required": True, "timeout_seconds": 15},
            )
            capture = start_capture_response.get("capture") or {}
            capture_id = str(capture.get("capture_id") or capture.get("job_id") or "").strip()
            if not capture_id:
                raise RuntimeError("Scanner capture id was not returned.")

            latest_capture = capture
            for _ in range(scanner_settings.job_poll_max_attempts):
                _, capture_status_response = _scanner_request_json(
                    scanner_settings,
                    f"/capture/{capture_id}/status",
                    method="GET",
                )
                latest_capture = capture_status_response.get("capture") or {}
                status = str(latest_capture.get("status") or "").strip().lower()
                if status in {"succeeded", "failed"}:
                    break
                time.sleep(scanner_settings.job_poll_interval_seconds)

            final_status = str(latest_capture.get("status") or "").strip().lower()
            if final_status != "succeeded":
                raise RuntimeError(
                    f"Scanner capture failed: {latest_capture.get('error') or 'unknown_error'} - "
                    f"{latest_capture.get('detail') or 'no detail'}."
                )

            _, content_type, image_payload = _scanner_request_bytes(scanner_settings, f"/capture/{capture_id}/result")
            if not image_payload:
                raise RuntimeError("Scanner returned an empty rectified image.")

        except HTTPError as ex:
            body = ex.read().decode("utf-8", errors="ignore")
            return api_error(
                f"Scanner request failed with HTTP {ex.code}.",
                error_code="SCANNER_HTTP_ERROR",
                status_code=502,
                details={"statusCode": ex.code, "responseBody": body[:4000]},
            )
        except URLError as ex:
            return api_error(
                f"Failed to reach scanner service: {ex}",
                error_code="SCANNER_UNREACHABLE",
                status_code=502,
            )
        except Exception as ex:
            return api_error(f"Manual scanner capture failed: {ex}", error_code="SCANNER_CAPTURE_FAILED", status_code=500)

        model = runtime_state.set_captured_image(
            file_name=f"rectified-{capture_id}.png",
            content_type=content_type,
            content=image_payload,
        )
        data: dict[str, Any] = {
            "captureId": capture_id,
            "fileName": model.file_name,
            "contentType": model.content_type,
            "sizeBytes": len(model.content),
            "capturedAt": _to_iso8601_utc(model.captured_at),
            "imageUrl": "/api/config/capture/latest/image",
        }
        if include_data_uri:
            encoded = base64.b64encode(model.content).decode("ascii")
            data["dataUri"] = f"data:{model.content_type};base64,{encoded}"

        return api_success(
            message="Manual scanner capture completed.",
            data=data,
        )

    @app.post("/api/config/scanner/capture-manual")
    def scanner_capture_manual() -> tuple[Response, int]:
        return _scanner_capture_manual_impl(include_data_uri_default=False)

    @app.post("/api/config/scanner/capture/oneshot")
    def scanner_capture_oneshot() -> tuple[Response, int]:
        return _scanner_capture_manual_impl(include_data_uri_default=True)

    @app.post("/api/config/capture")
    def capture_upload() -> tuple[Response, int]:
        try:
            file_name, content_type, payload = _extract_capture_image_payload()
        except ValueError as ex:
            return api_error(str(ex), error_code="CAPTURE_PAYLOAD_INVALID", status_code=400)
        except Exception as ex:
            return api_error(f"Capture upload failed: {ex}", error_code="CAPTURE_UPLOAD_FAILED", status_code=500)

        model = runtime_state.set_captured_image(file_name, content_type, payload)
        return api_success(
            message="Captured image stored.",
            data={
                "fileName": model.file_name,
                "contentType": model.content_type,
                "sizeBytes": len(model.content),
                "capturedAt": _to_iso8601_utc(model.captured_at),
                "imageUrl": "/api/config/capture/latest/image",
            },
            status_code=201,
        )

    @app.get("/api/config/capture/latest")
    def capture_latest() -> tuple[Response, int]:
        model = runtime_state.get_captured_image()
        if model is None:
            return api_error("No captured image available.", error_code="CAPTURE_NOT_FOUND", status_code=404)

        include_data_uri = parse_bool(request.args.get("includeDataUri"), default=False)
        data: dict[str, Any] = {
            "fileName": model.file_name,
            "contentType": model.content_type,
            "sizeBytes": len(model.content),
            "capturedAt": _to_iso8601_utc(model.captured_at),
            "imageUrl": "/api/config/capture/latest/image",
        }
        if include_data_uri:
            encoded = base64.b64encode(model.content).decode("ascii")
            data["dataUri"] = f"data:{model.content_type};base64,{encoded}"

        return api_success(message="Latest captured image loaded.", data=data)

    @app.get("/api/config/capture/latest/image")
    def capture_latest_image() -> Response | tuple[Response, int]:
        model = runtime_state.get_captured_image()
        if model is None:
            return api_error("No captured image available.", error_code="CAPTURE_NOT_FOUND", status_code=404)

        return send_file(
            io.BytesIO(model.content),
            mimetype=model.content_type,
            as_attachment=False,
            download_name=model.file_name,
            max_age=0,
        )

    @app.get("/api/config/print-history")
    def print_history() -> tuple[Response, int]:
        try:
            days = int(request.args.get("days", "30"))
            limit = int(request.args.get("limit", "500"))
        except ValueError:
            return api_error("days and limit must be integers.", error_code="INVALID_QUERY", status_code=400)
        items = provider.print_history_store.list_since(days=days, limit=limit)
        return api_success(
            message="Print history loaded.",
            data={"items": items, "days": days, "limit": limit},
        )

    run_startup_autoconnect(provider.printer_service)

    return app


app = create_app()
