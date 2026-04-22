from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class UploadedSvg:
    file_name: str
    content: bytes
    uploaded_at: datetime


@dataclass(frozen=True)
class CapturedImage:
    file_name: str
    content_type: str
    content: bytes
    captured_at: datetime


class RuntimeState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._uploaded_svg: UploadedSvg | None = None
        self._captured_image: CapturedImage | None = None

    def set_uploaded_svg(self, file_name: str, content: bytes) -> UploadedSvg:
        file_name = file_name or "uploaded.svg"
        model = UploadedSvg(
            file_name=file_name,
            content=content,
            uploaded_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._uploaded_svg = model
        return model

    def get_uploaded_svg(self) -> UploadedSvg | None:
        with self._lock:
            return self._uploaded_svg

    def clear_uploaded_svg(self) -> None:
        with self._lock:
            self._uploaded_svg = None

    def set_captured_image(self, file_name: str, content_type: str, content: bytes) -> CapturedImage:
        file_name = file_name or "capture.jpg"
        content_type = content_type or "image/jpeg"
        model = CapturedImage(
            file_name=file_name,
            content_type=content_type,
            content=content,
            captured_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._captured_image = model
        return model

    def get_captured_image(self) -> CapturedImage | None:
        with self._lock:
            return self._captured_image
