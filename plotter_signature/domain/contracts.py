from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, BinaryIO
from uuid import UUID, uuid4


class Paper(str, Enum):
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    B4 = "B4"
    B5 = "B5"
    LETTER = "Letter"
    LEGAL = "Legal"
    TABLOID = "Tabloid"
    ENVELOPE_10 = "Envelope_10"
    ENVELOPE_9 = "Envelope_9"
    ENVELOPE_C5 = "Envelope_C5"
    ENVELOPE_C6 = "Envelope_C6"
    ENVELOPE_DL = "Envelope_DL"
    CARD_4X6 = "Card_4x6"
    CARD_5X7 = "Card_5x7"
    CUSTOM = "Custom"


def get_paper_size_mm(paper: Paper) -> tuple[float, float]:
    paper_sizes: dict[Paper, tuple[float, float]] = {
        Paper.A3: (297, 420),
        Paper.A4: (210, 297),
        Paper.A5: (148, 210),
        Paper.A6: (105, 148),
        Paper.B4: (250, 353),
        Paper.B5: (176, 250),
        Paper.LETTER: (216, 279),
        Paper.LEGAL: (216, 356),
        Paper.TABLOID: (279, 432),
        Paper.ENVELOPE_10: (105, 241),
        Paper.ENVELOPE_9: (98, 225),
        Paper.ENVELOPE_C5: (162, 229),
        Paper.ENVELOPE_C6: (114, 162),
        Paper.ENVELOPE_DL: (110, 220),
        Paper.CARD_4X6: (102, 152),
        Paper.CARD_5X7: (127, 178),
    }
    return paper_sizes.get(paper, (210, 297))


def parse_paper(value: str | None) -> Paper | None:
    if not value:
        return None

    normalized = value.strip()
    for member in Paper:
        if normalized.lower() == member.value.lower():
            return member
        if normalized.lower() == member.name.lower():
            return member
    return None


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


class RequestStatus(IntEnum):
    NEW = 0
    WAITING_FOR_APPROVAL = 1
    APPROVED = 2
    REJECTED = 3
    PRINTING = 4
    PRINTED = 5
    VOIDED = 6
    COMPLETED = 7
    FAILED = 8


@dataclass
class PrintRequest:
    paper: Paper | None = None
    width: str = "210mm"
    height: str = "297mm"
    x_position: str = "50mm"
    y_position: str = "50mm"
    scale: int = 1
    rotation: int = 0
    invert_x: bool = False
    invert_y: bool = True

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PrintRequest":
        paper_value = data.get("paper") or data.get("Paper")
        return PrintRequest(
            paper=parse_paper(paper_value),
            width=str(data.get("width", data.get("Width", "210mm"))),
            height=str(data.get("height", data.get("Height", "297mm"))),
            x_position=str(data.get("xPosition", data.get("XPosition", "50mm"))),
            y_position=str(data.get("yPosition", data.get("YPosition", "50mm"))),
            scale=int(data.get("scale", data.get("Scale", 1))),
            rotation=int(data.get("rotation", data.get("Rotation", 0))),
            invert_x=parse_bool(data.get("invertX", data.get("InvertX")), default=False),
            invert_y=parse_bool(data.get("invertY", data.get("InvertY")), default=True),
        )


@dataclass
class PrintResponse:
    message: str = ""
    commands_sent: int = 0
    copies: int = 0
    total_commands_sent: int = 0
    svg_total_distance_mm: float = 0.0
    executed_distance_mm: float = 0.0
    execution_percent: float = 0.0
    cumulative_distance_mm: float = 0.0


@dataclass
class PrinterStatus:
    is_open: bool = False
    port_name: str = "N/A"
    is_printing: bool = False
    bulk_requested_total: int = 0
    bulk_printed_count: int = 0
    bulk_stop_requested: bool = False
    current_svg_total_distance_mm: float = 0.0
    current_executed_distance_mm: float = 0.0
    current_execution_percent: float = 0.0
    cumulative_distance_mm: float = 0.0
    max_pen_distance_m: float = 0.0
    used_pen_distance_m: float = 0.0
    remaining_pen_percent: float = 0.0


@dataclass
class PrintRetrySettings:
    max_retries: int = 3
    retry_delay_ms: int = 1000


@dataclass
class PrintApprovalRequest:
    paper_image_stream: BinaryIO | None
    paper_image_file_name: str | None
    signature_svg_stream: BinaryIO
    signature_svg_file_name: str
    print_settings: PrintRequest = field(default_factory=PrintRequest)
    should_approve: bool = True


@dataclass
class PrintWithApprovalRequest:
    print_settings: PrintRequest = field(default_factory=PrintRequest)
    should_approve: bool = True

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PrintWithApprovalRequest":
        print_settings_data = data.get("printSettings", data.get("PrintSettings", {}))
        return PrintWithApprovalRequest(
            print_settings=PrintRequest.from_dict(print_settings_data),
            should_approve=parse_bool(data.get("shouldApprove", data.get("ShouldApprove")), default=True),
        )


@dataclass
class PrintWithApprovalResponse:
    request_id: UUID
    status: str
    was_approved: bool
    was_printed: bool
    message: str
    commands_sent: int


@dataclass
class ApprovalResponse:
    is_approved: bool
    message: str
    rejection_reason: str | None = None


@dataclass
class ApprovalServiceSettings:
    endpoint: str = ""
    api_key: str = ""
    timeout_seconds: int = 30
    use_mock_service: bool = True


@dataclass
class RequestLog:
    id: UUID = field(default_factory=uuid4)
    request_id: UUID = field(default_factory=uuid4)
    status: RequestStatus = RequestStatus.NEW
    approval_response: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "requestId": str(self.request_id),
            "status": self.status.name,
            "statusValue": int(self.status),
            "approvalResponse": self.approval_response,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }

