from dataclasses import dataclass


@dataclass
class PrinterSettings:
    com_port: str = "COM5"
    baud_rate: int = 250000

