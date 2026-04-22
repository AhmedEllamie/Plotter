from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from diwan_signature.domain.contracts import (
    PrintApprovalRequest,
    PrintResponse,
    PrintRetrySettings,
    PrintWithApprovalResponse,
    RequestLog,
    RequestStatus,
    get_paper_size_mm,
)
from diwan_signature.infrastructure.stores.request_log_store import RequestLogStore
from diwan_signature.services.approval.mock_approval_service import IApprovalService
from diwan_signature.services.printer.i_printer_service import IPrinterService
from diwan_signature.services.printer.svg_converter import convert_to_gcode


class PrintApprovalService:
    def __init__(
        self,
        request_log_store: RequestLogStore,
        printer_service: IPrinterService,
        approval_service: IApprovalService,
        print_retry_settings: PrintRetrySettings,
    ) -> None:
        self._request_log_store = request_log_store
        self._printer_service = printer_service
        self._approval_service = approval_service
        self._print_retry_settings = print_retry_settings
        self._logger = logging.getLogger(self.__class__.__name__)

    async def print_with_approval_async(self, request: PrintApprovalRequest) -> PrintWithApprovalResponse:
        request_id = uuid4()

        try:
            self._logger.info("Starting print with approval workflow. RequestId: %s", request_id)
            await self._create_log_entry_async(request_id, RequestStatus.NEW)

            paper_image_bytes = await self._read_stream_to_byte_array_async(request.paper_image_stream)
            self._logger.info(
                "Paper image read: %d bytes. RequestId: %s",
                len(paper_image_bytes),
                request_id,
            )

            await self._create_log_entry_async(request_id, RequestStatus.WAITING_FOR_APPROVAL)

            approval_response = await self._approval_service.request_approval_async(paper_image_bytes, request_id)
            should_approve = request.should_approve and approval_response.is_approved

            await self._create_log_entry_async(
                request_id,
                RequestStatus.APPROVED if should_approve else RequestStatus.REJECTED,
                approval_response=approval_response.message,
            )

            if not should_approve:
                return await self._execute_rejected_print_async(request_id)

            return await self._execute_approved_print_async(request, request_id)
        except Exception as ex:
            self._logger.exception("Error in print with approval workflow. RequestId: %s", request_id)
            await self._create_log_entry_async(request_id, RequestStatus.FAILED, error_message=str(ex))
            raise

    async def get_request_log_async(self, request_id: UUID) -> RequestLog | None:
        return self._request_log_store.get_by_request_id(request_id)

    async def get_all_logs_by_request_id_async(self, request_id: UUID) -> list[RequestLog]:
        return self._request_log_store.get_all_by_request_id(request_id)

    async def get_recent_requests_async(self, count: int = 10) -> list[RequestLog]:
        return self._request_log_store.get_recent(count)

    async def _create_log_entry_async(
        self,
        request_id: UUID,
        status: RequestStatus,
        approval_response: str | None = None,
        error_message: str | None = None,
    ) -> RequestLog:
        now = datetime.now(timezone.utc)
        log = RequestLog(
            id=uuid4(),
            request_id=request_id,
            status=status,
            approval_response=approval_response,
            error_message=error_message,
            created_at=now,
            updated_at=now,
            completed_at=now if status in (RequestStatus.COMPLETED, RequestStatus.FAILED) else None,
        )
        self._request_log_store.add(log)
        return log

    async def _execute_rejected_print_async(self, request_id: UUID) -> PrintWithApprovalResponse:
        self._logger.info("Executing void print (rejected). RequestId: %s", request_id)
        await self._create_log_entry_async(request_id, RequestStatus.VOIDED)
        await self._printer_service.void_print()
        await self._create_log_entry_async(request_id, RequestStatus.COMPLETED)

        return PrintWithApprovalResponse(
            request_id=request_id,
            status="Completed",
            was_approved=False,
            was_printed=False,
            message="Request rejected - void print executed (paper ejected without printing).",
            commands_sent=0,
        )

    async def _execute_approved_print_async(
        self,
        request: PrintApprovalRequest,
        request_id: UUID,
    ) -> PrintWithApprovalResponse:
        self._logger.info("Executing approved print. RequestId: %s", request_id)

        gcode = self._convert_svg_to_gcode(request.signature_svg_stream, request.print_settings)
        if not gcode:
            error_message = "Failed to convert SVG to G-code. No drawable paths found."
            await self._create_log_entry_async(request_id, RequestStatus.FAILED, error_message=error_message)
            raise RuntimeError(error_message)

        await self._create_log_entry_async(request_id, RequestStatus.PRINTING)

        print_result: PrintResponse | None = None
        attempt = 0
        last_exception: Exception | None = None

        while attempt < self._print_retry_settings.max_retries:
            attempt += 1
            try:
                print_result = await self._printer_service.print(gcode)
                self._logger.info("Print successful on attempt %d. RequestId: %s", attempt, request_id)
                break
            except Exception as ex:
                last_exception = ex
                self._logger.warning(
                    "Print attempt %d failed. RequestId: %s. Error: %s",
                    attempt,
                    request_id,
                    ex,
                )
                if attempt < self._print_retry_settings.max_retries:
                    await asyncio.sleep(self._print_retry_settings.retry_delay_ms / 1000.0)

        if print_result is None:
            error_message = f"Print failed after {attempt} attempts: {last_exception}"
            await self._create_log_entry_async(request_id, RequestStatus.FAILED, error_message=error_message)
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(error_message)

        await self._create_log_entry_async(request_id, RequestStatus.PRINTED)
        await self._create_log_entry_async(request_id, RequestStatus.COMPLETED)

        return PrintWithApprovalResponse(
            request_id=request_id,
            status="Completed",
            was_approved=True,
            was_printed=True,
            message="Print completed successfully.",
            commands_sent=print_result.commands_sent,
        )

    async def _read_stream_to_byte_array_async(self, stream: BinaryIO | None) -> bytes:
        if stream is None:
            return b""
        if hasattr(stream, "seek"):
            stream.seek(0)
        payload = stream.read()
        if isinstance(payload, str):
            return payload.encode("utf-8")
        return payload

    def _convert_svg_to_gcode(self, svg_stream: BinaryIO, print_settings) -> list[str] | None:
        if print_settings.scale < 1:
            raise ValueError("Scale must be at least 1.")
        if print_settings.rotation < 0 or print_settings.rotation > 360:
            raise ValueError("Rotation must be between 0 and 360.")

        if print_settings.paper is not None:
            paper_w, paper_h = get_paper_size_mm(print_settings.paper)
            print_settings.width = f"{paper_w}mm"
            print_settings.height = f"{paper_h}mm"

        if hasattr(svg_stream, "seek"):
            svg_stream.seek(0)
        gcode = convert_to_gcode(svg_stream, print_settings)
        return gcode if gcode else None

