from dataclasses import dataclass, field


@dataclass
class PrinterSettings:
    com_port: str = ""
    baud_rate: int = 250000
    verify_serial_identity: bool = True
    serial_identity_contains: list[str] = field(
        default_factory=lambda: ["Marlin K_AT", "start"],
    )
    serial_identity_timeout_seconds: float = 3.0
