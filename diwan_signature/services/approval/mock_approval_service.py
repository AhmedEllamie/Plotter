from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from uuid import UUID

from diwan_signature.domain.contracts import ApprovalResponse, ApprovalServiceSettings


class IApprovalService(ABC):
    @abstractmethod
    async def request_approval_async(self, paper_image_bytes: bytes, request_id: UUID) -> ApprovalResponse:
        raise NotImplementedError


class MockApprovalService(IApprovalService):
    def __init__(self, settings: ApprovalServiceSettings):
        self._settings = settings

    async def request_approval_async(self, paper_image_bytes: bytes, request_id: UUID) -> ApprovalResponse:
        await asyncio.sleep(0.5)

        print(f"[MockApprovalService] Processing approval request for RequestId: {request_id}")
        print(f"[MockApprovalService] Image size: {len(paper_image_bytes)} bytes")

        return ApprovalResponse(
            is_approved=True,
            message="Mock approval - Default approved",
            rejection_reason=None,
        )

