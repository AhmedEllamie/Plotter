from __future__ import annotations

from threading import Lock
from typing import Dict, List
from uuid import UUID

from plotter_signature.domain.contracts import RequestLog


class RequestLogStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._logs_by_request: Dict[UUID, List[RequestLog]] = {}
        self._logs_by_id: Dict[UUID, RequestLog] = {}

    def add(self, log: RequestLog) -> None:
        with self._lock:
            self._logs_by_request.setdefault(log.request_id, []).append(log)
            self._logs_by_id[log.id] = log

    def get_by_id(self, log_id: UUID) -> RequestLog | None:
        with self._lock:
            return self._logs_by_id.get(log_id)

    def get_by_request_id(self, request_id: UUID) -> RequestLog | None:
        with self._lock:
            logs = self._logs_by_request.get(request_id, [])
            if not logs:
                return None
            return sorted(logs, key=lambda x: x.created_at, reverse=True)[0]

    def get_all_by_request_id(self, request_id: UUID) -> list[RequestLog]:
        with self._lock:
            logs = self._logs_by_request.get(request_id, [])
            return list(sorted(logs, key=lambda x: x.created_at))

    def update(self, log: RequestLog) -> None:
        with self._lock:
            if log.id in self._logs_by_id:
                self._logs_by_id[log.id] = log

            request_logs = self._logs_by_request.get(log.request_id)
            if not request_logs:
                self._logs_by_request[log.request_id] = [log]
                return

            for idx, existing in enumerate(request_logs):
                if existing.id == log.id:
                    request_logs[idx] = log
                    return
            request_logs.append(log)

    def get_recent(self, count: int = 50) -> list[RequestLog]:
        with self._lock:
            all_logs = list(self._logs_by_id.values())
            return list(sorted(all_logs, key=lambda x: x.created_at, reverse=True)[:count])

