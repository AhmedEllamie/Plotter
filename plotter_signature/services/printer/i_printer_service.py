from __future__ import annotations

from abc import ABC, abstractmethod

from plotter_signature.domain.contracts import PrintResponse, PrinterStatus


class IPrinterService(ABC):
    @property
    @abstractmethod
    def is_open(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def port_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_printing(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def default_com_port(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def default_baud_rate(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def open_port(self, com_port: str | None = None, baud_rate: int | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def close_port(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> PrinterStatus:
        raise NotImplementedError

    @abstractmethod
    async def print(self, gcode: list[str]) -> PrintResponse:
        raise NotImplementedError

    @abstractmethod
    async def bulk_print(self, gcode: list[str], copies: int) -> PrintResponse:
        raise NotImplementedError

    @abstractmethod
    def stop_bulk_print(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def void_print(self) -> PrintResponse:
        raise NotImplementedError

    @abstractmethod
    async def pen_change_start(self) -> PrintResponse:
        raise NotImplementedError

    @abstractmethod
    async def pen_change_finish(self) -> PrintResponse:
        raise NotImplementedError

    @abstractmethod
    def get_distance_stats(self) -> dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def reset_cumulative_distance(self) -> dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def set_max_pen_distance_m(self, meters: float) -> dict[str, float]:
        raise NotImplementedError

