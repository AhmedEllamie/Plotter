from __future__ import annotations

import asyncio
import base64
import io
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile

from plotter_signature.dependency_injection import ServiceProvider, get_service_provider
from plotter_signature.domain.contracts import (
    PrintApprovalRequest,
    PrintRequest,
    PrintWithApprovalRequest,
    get_paper_size_mm,
    parse_paper,
)
from plotter_signature.infrastructure.security.api_key_auth import is_api_key_required, validate_api_key
from plotter_signature.services.printer.printer_service import AutoConnectFailedError
from plotter_signature.services.printer.svg_converter import convert_to_gcode


def _printer_status_public_dict(provider: ServiceProvider) -> dict[str, Any]:
    payload = asdict(provider.printer_service.get_status())
    payload.pop("port_name", None)
    return payload


def _print_request_form(
    paper: str | None = Form(default=None),
    width: str = Form(default="210mm"),
    height: str = Form(default="297mm"),
    x_position: str = Form(default="50mm", alias="xPosition"),
    y_position: str = Form(default="50mm", alias="yPosition"),
    scale: int = Form(default=1),
    rotation: int = Form(default=0),
    invert_x: bool = Form(default=False, alias="invertX"),
    invert_y: bool = Form(default=True, alias="invertY"),
) -> PrintRequest:
    return PrintRequest(
        paper=parse_paper(paper),
        width=width,
        height=height,
        x_position=x_position,
        y_position=y_position,
        scale=scale,
        rotation=rotation,
        invert_x=invert_x,
        invert_y=invert_y,
    )


def _ensure_connected(provider: ServiceProvider) -> None:
    if not provider.printer_service.is_open:
        raise HTTPException(
            status_code=400,
            detail="Printer is not connected. Call POST /printer/auto-connect first.",
        )


def _ensure_not_busy(provider: ServiceProvider) -> None:
    if provider.printer_service.is_busy:
        raise HTTPException(status_code=409, detail="Printer is busy.")


def _read_upload_to_stream(upload: UploadFile) -> io.BytesIO:
    payload = upload.file.read()
    return io.BytesIO(payload)


def _convert_svg(svg_stream: io.BytesIO, req: PrintRequest) -> list[str]:
    if req.scale < 1:
        raise HTTPException(status_code=400, detail="Scale must be at least 1.")

    if req.rotation < 0 or req.rotation > 360:
        raise HTTPException(status_code=400, detail="Rotation must be between 0 and 360.")

    if req.paper is not None:
        paper_w, paper_h = get_paper_size_mm(req.paper)
        req.width = f"{paper_w}mm"
        req.height = f"{paper_h}mm"

    gcode = convert_to_gcode(svg_stream, req)
    if len(gcode) == 0:
        raise HTTPException(
            status_code=400,
            detail="No drawable paths found. If SVG contains text, convert to path first.",
        )
    return gcode


def _parse_print_with_approval_request(raw_json: str) -> PrintWithApprovalRequest:
    try:
        payload: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as ex:
        raise HTTPException(status_code=400, detail=f"Invalid printRequest JSON: {ex}") from ex

    try:
        return PrintWithApprovalRequest.from_dict(payload)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Invalid print request payload: {ex}") from ex


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not is_api_key_required():
        return
    validation = validate_api_key(x_api_key)
    if validation.is_valid:
        return
    raise HTTPException(status_code=401, detail=validation.message)


def create_printer_router(provider: ServiceProvider | None = None) -> APIRouter:
    provider = provider or get_service_provider()
    router = APIRouter(prefix="/printer", tags=["printer"], dependencies=[Depends(_require_api_key)])

    @router.post("/auto-connect")
    async def auto_connect(com_port: str | None = None, baud_rate: int | None = None):
        if provider.printer_service.is_open:
            raise HTTPException(
                status_code=409,
                detail=f"Already connected to {provider.printer_service.port_name}. Disconnect first.",
            )
        try:
            await asyncio.to_thread(
                provider.printer_service.autoconnect,
                com_port,
                baud_rate,
            )
        except AutoConnectFailedError as ex:
            raise HTTPException(
                status_code=400,
                detail=str(ex),
            ) from ex
        except Exception as ex:
            raise HTTPException(status_code=400, detail=f"Failed to auto-connect: {ex}") from ex

        return {"message": f"Connected to {provider.printer_service.port_name}."}

    @router.post("/disconnect")
    async def disconnect():
        if not provider.printer_service.is_open:
            raise HTTPException(status_code=409, detail="Not connected.")
        if provider.printer_service.is_busy:
            raise HTTPException(status_code=409, detail="Cannot disconnect while printer is busy.")

        provider.printer_service.close_port()
        return {"message": "Disconnected."}

    @router.get("/status")
    async def get_status():
        return _printer_status_public_dict(provider)

    @router.post("/generate")
    async def generate(svg: UploadFile = File(...), req: PrintRequest = Depends(_print_request_form)):
        if not svg.filename:
            raise HTTPException(status_code=400, detail="No SVG file provided.")

        svg_stream = _read_upload_to_stream(svg)
        gcode = _convert_svg(svg_stream, req)
        svg_distance = provider.printer_service.calculate_svg_distance_mm(gcode)
        return {
            "message": f"Generated {len(gcode)} G-code commands.",
            "commandCount": len(gcode),
            "svgTotalDistanceMm": round(svg_distance, 3),
            "gcode": gcode,
        }

    @router.post("/print")
    async def print_signature(svg: UploadFile = File(...), req: PrintRequest = Depends(_print_request_form)):
        _ensure_connected(provider)
        _ensure_not_busy(provider)

        svg_stream = _read_upload_to_stream(svg)
        gcode = _convert_svg(svg_stream, req)
        result = await provider.printer_service.print(gcode)
        return asdict(result)

    @router.post("/print/bulk")
    async def bulk_print(
        svg: UploadFile = File(...),
        copies: int = Form(...),
        req: PrintRequest = Depends(_print_request_form),
    ):
        _ensure_connected(provider)
        _ensure_not_busy(provider)

        if copies < 1 or copies > 100:
            raise HTTPException(status_code=400, detail="Copies must be between 1 and 100.")

        svg_stream = _read_upload_to_stream(svg)
        gcode = _convert_svg(svg_stream, req)
        result = await provider.printer_service.bulk_print(gcode, copies)
        return asdict(result)

    @router.post("/print-with-approval")
    async def print_with_approval(
        paper_image: UploadFile | None = File(default=None, alias="paperImage"),
        paper_image_base64: str | None = Form(default=None, alias="paperImageBase64"),
        signature_svg: UploadFile = File(..., alias="signatureSvg"),
        print_request_json: str = Form(..., alias="printRequestJson"),
    ):
        _ensure_connected(provider)
        _ensure_not_busy(provider)

        if not signature_svg.filename:
            raise HTTPException(status_code=400, detail="No signature SVG file provided.")

        print_with_approval_req = _parse_print_with_approval_request(print_request_json)

        paper_stream: io.BytesIO | None = None
        paper_filename: str | None = None
        if paper_image is not None:
            paper_stream = _read_upload_to_stream(paper_image)
            paper_filename = paper_image.filename
        elif paper_image_base64:
            try:
                base64_data = paper_image_base64.split(",", 1)[1] if "," in paper_image_base64 else paper_image_base64
                paper_stream = io.BytesIO(base64.b64decode(base64_data))
            except Exception as ex:
                raise HTTPException(status_code=400, detail=f"Invalid paperImageBase64: {ex}") from ex

        signature_stream = _read_upload_to_stream(signature_svg)
        request = PrintApprovalRequest(
            paper_image_stream=paper_stream,
            paper_image_file_name=paper_filename,
            signature_svg_stream=signature_stream,
            signature_svg_file_name=signature_svg.filename or "signature.svg",
            print_settings=print_with_approval_req.print_settings,
            should_approve=print_with_approval_req.should_approve,
        )

        try:
            response = await provider.print_approval_service.print_with_approval_async(request)
            return asdict(response)
        except ValueError as ex:
            raise HTTPException(status_code=400, detail=str(ex)) from ex
        except RuntimeError as ex:
            raise HTTPException(status_code=400, detail=str(ex)) from ex
        except HTTPException:
            raise
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Error: {ex}") from ex

    return router
