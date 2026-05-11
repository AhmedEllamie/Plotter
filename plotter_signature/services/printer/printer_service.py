from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from plotter_signature.domain.contracts import PrintResponse, PrinterStatus
from plotter_signature.domain.printer_settings import PrinterSettings
from plotter_signature.services.printer.i_printer_service import IPrinterService

try:
    import serial
except ImportError:  # pragma: no cover - depends on environment
    serial = None


AUTCONNECT_PROBE_CAP = 32

logger = logging.getLogger(__name__)

_SERIAL_IO_ERROR_TYPES: tuple[type[BaseException], ...] = (OSError,)
if serial is not None:
    _SERIAL_IO_ERROR_TYPES = (OSError, serial.SerialException)


class AutoConnectFailedError(RuntimeError):
    def __init__(self, message: str, *, attempted_ports: list[str]) -> None:
        super().__init__(message)
        self.attempted_ports = attempted_ports


class SerialIdentityError(RuntimeError):
    """Unprompted serial banner did not contain required firmware markers."""


class PrinterService(IPrinterService):
    def __init__(self, settings: PrinterSettings):
        self._settings = settings
        self._port: Any | None = None
        self._busy_kind: str = "idle"
        self._print_lock = threading.Lock()
        self._distance_lock = threading.Lock()
        self._stats_file = Path(__file__).resolve().parents[2] / "distance_stats.json"
        self._cumulative_distance_mm, self._max_pen_distance_m = self._load_distance_settings()
        self._current_svg_total_distance_mm = 0.0
        self._current_executed_distance_mm = 0.0
        self._stop_requested = threading.Event()
        self._bulk_graceful_stop_requested = threading.Event()
        self._bulk_requested_total = 0
        self._bulk_printed_count = 0
        self._serial_lock = threading.RLock()

    _COMMAND_VALUE_PATTERN = re.compile(r"([A-Za-z])\s*(-?\d+(?:\.\d+)?)")

    @property
    def is_open(self) -> bool:
        return bool(self._port and self._port.is_open)

    @property
    def port_name(self) -> str:
        if self._port and self._port.is_open:
            return str(self._port.port)
        return "N/A"

    @property
    def is_printing(self) -> bool:
        return self._busy_kind == "print"

    @property
    def is_busy(self) -> bool:
        return self._busy_kind != "idle"

    @property
    def is_voiding(self) -> bool:
        return self._busy_kind == "void"

    @property
    def default_com_port(self) -> str:
        return self._settings.com_port

    @property
    def default_baud_rate(self) -> int:
        return self._settings.baud_rate

    def open_port(self, com_port: str | None = None, baud_rate: int | None = None) -> None:
        with self._serial_lock:
            self._open_port_core(com_port, baud_rate)

    def _open_port_core(self, com_port: str | None = None, baud_rate: int | None = None) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed. Install requirements first.")

        port_name = com_port or self._settings.com_port
        baud = baud_rate or self._settings.baud_rate

        if self._port and self._port.is_open:
            self._port.close()

        try:
            self._port = serial.Serial(
                port=port_name,
                baudrate=baud,
                parity=serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,
                write_timeout=2.0,
            )
        except PermissionError as ex:
            raise PermissionError(
                f"{ex!s} On Linux, add the service user to the 'dialout' group "
                "(e.g. sudo usermod -aG dialout <user>), use SupplementaryGroups=dialout in the "
                "bundled systemd unit when non-root, and see docs/UBUNTU_RELEASE_GUIDE.md."
            ) from ex

        self._port.dtr = True
        self._port.rts = True
        time.sleep(1.5)

        markers = [m for m in self._settings.serial_identity_contains if m]
        if self._settings.verify_serial_identity and markers:
            banner = self._read_serial_identity_banner(self._settings.serial_identity_timeout_seconds)
            if not self._serial_identity_satisfied(banner, markers):
                logger.warning(
                    "Serial identity mismatch on %s (banner length=%s).",
                    port_name,
                    len(banner),
                )
                self._close_port_unlocked()
                raise SerialIdentityError(
                    f"Serial identity check failed on {port_name}: "
                    f"expected substrings {markers!r} in boot banner.",
                )
        elif self._settings.verify_serial_identity and not markers:
            logger.warning("VerifySerialIdentity is true but SerialIdentityContains is empty; skipping banner check.")

        self._port.reset_input_buffer()
        self._port.reset_output_buffer()

    def _serial_identity_satisfied(self, banner: str, markers: list[str]) -> bool:
        blob = banner.lower()
        return all(m.lower() in blob for m in markers)

    def _read_serial_identity_banner(self, timeout_seconds: float) -> str:
        if not self._port or not self._port.is_open:
            return ""
        deadline = time.monotonic() + max(0.05, timeout_seconds)
        parts: list[str] = []
        while time.monotonic() < deadline:
            waiting = getattr(self._port, "in_waiting", 0)
            if waiting > 0:
                raw = self._port.read(waiting)
                if raw:
                    parts.append(raw.decode("ascii", errors="ignore"))
            blob = "".join(parts)
            markers = [m for m in self._settings.serial_identity_contains if m]
            if markers and self._serial_identity_satisfied(blob, markers):
                return blob
            time.sleep(0.01)
        return "".join(parts)

    def _close_port_unlocked(self) -> None:
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None

    def _invalidate_serial_after_io_error(self, exc: BaseException) -> None:
        if not isinstance(exc, _SERIAL_IO_ERROR_TYPES):
            return
        logger.warning("Serial I/O error; closing port: %s", exc)
        with self._serial_lock:
            self._close_port_unlocked()

    @staticmethod
    def list_filtered_serial_device_names() -> list[str]:
        try:
            from serial.tools import list_ports
        except ImportError:
            return []

        names: list[str] = []
        is_windows = sys.platform.startswith("win")
        is_linux = sys.platform.startswith("linux")
        try:
            for p in list_ports.comports():
                device = (p.device or "").strip()
                if not device:
                    continue
                if is_windows and not re.fullmatch(r"COM\d+", device, flags=re.IGNORECASE):
                    continue
                if is_linux:
                    if not re.fullmatch(r"(?:/dev/)?tty(?:USB|ACM)\d+", device, flags=re.IGNORECASE):
                        continue
                    if not device.startswith("/dev/"):
                        device = f"/dev/{device}"
                if is_windows:
                    device = device.upper()
                names.append(device)
        except Exception:
            return []
        names = list(dict.fromkeys(names))
        names.sort()
        return names

    def autoconnect(self, explicit_com_port: str | None = None, baud_rate: int | None = None) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed. Install requirements first.")
        baud = baud_rate or self._settings.baud_rate
        attempted: list[str] = []
        explicit = (explicit_com_port or "").strip()
        if explicit:
            targets = [explicit]
        else:
            targets = []
            default = (self._settings.com_port or "").strip()
            if default:
                targets.append(default)
            for name in self.list_filtered_serial_device_names():
                if name not in targets:
                    targets.append(name)
            targets = targets[:AUTCONNECT_PROBE_CAP]
        if not targets:
            raise AutoConnectFailedError("No serial ports to try.", attempted_ports=[])
        last_err = ""
        with self._serial_lock:
            for port in targets:
                attempted.append(port)
                try:
                    self._open_port_core(port, baud)
                    return
                except Exception as ex:
                    last_err = str(ex)
                    self._close_port_unlocked()
        raise AutoConnectFailedError(
            f"Could not open any serial port. Last error: {last_err}",
            attempted_ports=attempted,
        )

    def ensure_serial_ready(self, max_attempts: int = 3, delay_seconds: float = 0.3) -> None:
        if self.is_open:
            return
        last_err: BaseException | None = None
        for attempt in range(max_attempts):
            logger.info("ensure_serial_ready: reconnect attempt %s/%s", attempt + 1, max_attempts)
            try:
                self.autoconnect()
                if self.is_open:
                    logger.info("ensure_serial_ready: connected on %s", self.port_name)
                    return
            except AutoConnectFailedError as ex:
                last_err = ex
                logger.warning("ensure_serial_ready: autoconnect failed: %s", ex)
            except Exception as ex:
                last_err = ex
                logger.warning("ensure_serial_ready: unexpected error: %s", ex)
            if attempt < max_attempts - 1:
                time.sleep(delay_seconds)
        raise RuntimeError(
            "Printer serial port is not available after reconnect attempts.",
        ) from last_err

    def close_port(self) -> None:
        with self._serial_lock:
            self._close_port_unlocked()

    def get_status(self) -> PrinterStatus:
        current_percent = self._calculate_execution_percent(
            self._current_executed_distance_mm,
            self._current_svg_total_distance_mm,
        )
        used_pen_distance_m = self._cumulative_distance_mm / 1000.0
        return PrinterStatus(
            is_open=self.is_open,
            port_name=self.port_name,
            is_busy=self.is_busy,
            is_printing=self.is_printing,
            bulk_requested_total=self._bulk_requested_total,
            bulk_printed_count=self._bulk_printed_count,
            bulk_stop_requested=self._bulk_graceful_stop_requested.is_set()
            or (self._bulk_requested_total > 0 and self._stop_requested.is_set()),
            current_svg_total_distance_mm=round(self._current_svg_total_distance_mm, 3),
            current_executed_distance_mm=round(self._current_executed_distance_mm, 3),
            current_execution_percent=current_percent,
            cumulative_distance_mm=round(self._cumulative_distance_mm, 3),
            max_pen_distance_m=round(self._max_pen_distance_m, 6),
            used_pen_distance_m=round(used_pen_distance_m, 6),
            remaining_pen_percent=self._calculate_remaining_pen_percent(),
        )

    async def print(self, gcode: list[str]) -> PrintResponse:
        self._begin_print_job()
        try:
            try:
                result = await asyncio.to_thread(self._execute_print_cycle, gcode)
            except RuntimeError:
                if not self._stop_requested.is_set():
                    raise
                self._add_to_cumulative_distance(self._current_executed_distance_mm)
                execution_percent = self._calculate_execution_percent(
                    self._current_executed_distance_mm,
                    self._current_svg_total_distance_mm,
                )
                self._stop_requested.clear()
                return PrintResponse(
                    message="Print stopped by user.",
                    commands_sent=0,
                    svg_total_distance_mm=round(self._current_svg_total_distance_mm, 3),
                    executed_distance_mm=round(self._current_executed_distance_mm, 3),
                    execution_percent=execution_percent,
                    cumulative_distance_mm=round(self._cumulative_distance_mm, 3),
                    job_stopped=True,
                )
            self._add_to_cumulative_distance(result["executed_distance_mm"])
            execution_percent = self._calculate_execution_percent(
                result["executed_distance_mm"], result["svg_total_distance_mm"]
            )
            return PrintResponse(
                message="Print complete.",
                commands_sent=result["commands_sent"],
                svg_total_distance_mm=round(result["svg_total_distance_mm"], 3),
                executed_distance_mm=round(result["executed_distance_mm"], 3),
                execution_percent=execution_percent,
                cumulative_distance_mm=round(self._cumulative_distance_mm, 3),
                job_stopped=False,
            )
        finally:
            self._end_print_job()

    async def bulk_print(self, gcode: list[str], copies: int) -> PrintResponse:
        self._begin_print_job()
        total_commands = 0
        total_executed_distance = 0.0
        svg_total_distance = self.calculate_svg_distance_mm(gcode)
        self._bulk_requested_total = copies
        self._bulk_printed_count = 0
        try:
            def run() -> None:
                nonlocal total_commands, total_executed_distance
                for _ in range(copies):
                    if self._bulk_graceful_stop_requested.is_set():
                        break
                    if self._stop_requested.is_set():
                        break
                    try:
                        result = self._execute_print_cycle(gcode)
                    except RuntimeError:
                        if not self._stop_requested.is_set():
                            raise
                        total_executed_distance += self._current_executed_distance_mm
                        break
                    total_commands += result["commands_sent"]
                    total_executed_distance += result["executed_distance_mm"]
                    self._bulk_printed_count += 1

            await asyncio.to_thread(run)
            self._add_to_cumulative_distance(total_executed_distance)
            printed_copies = self._bulk_printed_count
            graceful_pending = self._bulk_graceful_stop_requested.is_set()
            immediate_pending = self._stop_requested.is_set()
            stopped = printed_copies < copies and (graceful_pending or immediate_pending)
            if stopped:
                total_svg_distance = svg_total_distance * copies
            else:
                total_svg_distance = svg_total_distance * printed_copies
            if self._stop_requested.is_set():
                self._stop_requested.clear()
            if self._bulk_graceful_stop_requested.is_set():
                self._bulk_graceful_stop_requested.clear()
            return PrintResponse(
                message="Bulk print stopped by user." if stopped else "Bulk print complete.",
                copies=printed_copies,
                total_commands_sent=total_commands,
                svg_total_distance_mm=round(total_svg_distance, 3),
                executed_distance_mm=round(total_executed_distance, 3),
                execution_percent=self._calculate_execution_percent(total_executed_distance, total_svg_distance),
                cumulative_distance_mm=round(self._cumulative_distance_mm, 3),
            )
        finally:
            self._end_print_job()

    async def void_print(self) -> PrintResponse:
        self._begin_busy("void")
        try:
            await asyncio.to_thread(self._execute_void_cycle)
            return PrintResponse(
                message="Void print complete - paper ejected without printing.",
                commands_sent=0,
            )
        finally:
            self._end_busy()

    def request_print_cancel(self) -> bool:
        with self._print_lock:
            if self._busy_kind != "print":
                return False
            self._stop_requested.set()
            return True

    def stop_bulk_print(self) -> bool:
        with self._print_lock:
            if self._busy_kind != "print":
                return False
            if self._bulk_requested_total <= 0:
                return False
            self._bulk_graceful_stop_requested.set()
            return True

    async def pen_change_start(self) -> PrintResponse:
        self._begin_busy("pen_change")
        try:
            await asyncio.to_thread(self._execute_pen_change_start)
            return PrintResponse(
                message="Pen change start complete. Replace pen, then run pen-change-finish.",
                commands_sent=2,
            )
        finally:
            self._end_busy()

    async def pen_change_finish(self) -> PrintResponse:
        self._begin_busy("pen_change")
        try:
            await asyncio.to_thread(self._execute_pen_change_finish)
            return PrintResponse(
                message="Pen change finish complete. Printer is ready to continue.",
                commands_sent=2,
            )
        finally:
            self._end_busy()

    def _end_busy(self) -> None:
        with self._print_lock:
            self._busy_kind = "idle"

    def _begin_busy(self, kind: str) -> None:
        with self._print_lock:
            if self._busy_kind != "idle":
                raise RuntimeError("Printer is busy.")
            self._busy_kind = kind
            if kind == "print":
                self._stop_requested.clear()
                self._bulk_graceful_stop_requested.clear()
                self._bulk_requested_total = 0
                self._bulk_printed_count = 0
                self._current_svg_total_distance_mm = 0.0
                self._current_executed_distance_mm = 0.0

    def _begin_print_job(self) -> None:
        self._begin_busy("print")

    def _end_print_job(self) -> None:
        self._end_busy()

    def _execute_print_cycle(self, gcode: list[str]) -> dict[str, float | int]:
        state = {"x": 0.0, "y": 0.0, "pen_down": False}
        total_distance = self.calculate_svg_distance_mm(gcode)
        self._current_svg_total_distance_mm = total_distance
        executed_distance = 0.0
        try:
            print("=== Starting print cycle ===")
            print("Sending M998R handshake...")
            self._send("M998R")

            print("Waiting for 'paper ready'...")
            self._wait_for("paper ready", timeout_seconds=60)
            print("Paper ready!")

            print("Sending init commands...")
            self._send("G92 X9.0 Y-56.0 Z0")
            self._send("G21")
            self._send("G90")
            self._send("G1 E0.0 F4000")
            print("Init complete")

            print(f"Sending {len(gcode)} G-code commands...")
            sent_count = 0
            for line in gcode:
                self._throw_if_stop_requested()
                cmd = line.strip()
                if not cmd or cmd.startswith(";"):
                    continue
                executed_distance += self._distance_delta_for_command(cmd, state)
                self._current_executed_distance_mm = executed_distance
                self._send(cmd)
                sent_count += 1
                if sent_count % 50 == 0:
                    print(f"  Sent {sent_count} commands...")
            print(f"Sent all {sent_count} commands")
            return {
                "commands_sent": sent_count,
                "svg_total_distance_mm": total_distance,
                "executed_distance_mm": executed_distance,
            }
        except Exception as ex:
            print(f"!!! ERROR during print: {ex}")
            raise
        finally:
            print("=== Starting eject sequence ===")
            self._eject_paper()
            print("=== Print cycle complete ===")

    def _execute_void_cycle(self) -> None:
        try:
            print("=== Starting VOID cycle (no printing) ===")
            print("Sending M998R handshake...")
            self._send("M998R")

            print("Waiting for 'paper ready'...")
            self._wait_for("paper ready", timeout_seconds=60)
            print("Paper ready!")

            print("Sending init commands (pen stays UP)...")
            self._send("G92 X9.0 Y-56.0 Z0")
            self._send("G21")
            self._send("G90")
            self._send("G1 E0.0 F4000")
            print("Init complete - no printing, pen remains up")
        except Exception as ex:
            print(f"!!! ERROR during void cycle: {ex}")
            raise
        finally:
            print("=== Starting eject sequence ===")
            self._eject_paper()
            print("=== Void cycle complete ===")

    def _execute_pen_change_start(self) -> None:
        print("=== Starting pen-change-start ===")
        self._send("G90")
        self._send("G1 E7.5 F5000")
        print("Pen moved to change position (E7.5)")
        print("=== Pen-change-start complete ===")

    def _execute_pen_change_finish(self) -> None:
        print("=== Starting pen-change-finish ===")
        self._send("G90")
        self._send("G1 E0.0 F5000")
        print("Pen moved to ready/up position (E0.0)")
        print("=== Pen-change-finish complete ===")

    def _eject_paper(self) -> None:
        print("  Ejecting: Pen up...")
        self._send_safe("G1 E0.0 F4000", respect_stop=False)

        print("  Ejecting: Move X to 215...")
        self._send_safe("G0 X215.0 F6000.0", respect_stop=False)

        print("  Ejecting: Start motor (M106)...")
        self._send_safe("M106", respect_stop=False)

        print("  Ejecting: Push paper Y500...")
        self._send_safe("G0 Y500.0 F6000.0", respect_stop=False)

        print("  Ejecting: Wait (M400)...")
        self._send_safe("M400", respect_stop=False)

        print("  Ejecting: Stop motor (M107)...")
        self._send_safe("M107", respect_stop=False)

        print("Eject complete")

    def _send(self, gcode: str, *, respect_stop: bool = True) -> None:
        self._ensure_port_open()
        payload = (gcode + "\n").encode("ascii", errors="ignore")
        try:
            self._port.write(payload)
        except BaseException as ex:
            self._invalidate_serial_after_io_error(ex)
            raise
        self._wait_for_ok(respect_stop=respect_stop)

    def _send_safe(self, gcode: str, *, respect_stop: bool = True) -> None:
        try:
            self._send(gcode, respect_stop=respect_stop)
        except Exception:
            # Keep eject cycle resilient even if one command fails.
            pass

    def _wait_for_ok(self, timeout_seconds: int = 10, *, respect_stop: bool = True) -> None:
        start = time.time()
        buffer = ""

        while True:
            if respect_stop:
                self._throw_if_stop_requested()
            if time.time() - start > timeout_seconds:
                # Keep parity with C# behavior: timeout does not fail the job.
                return

            data = self._read_existing()
            if data:
                buffer += data
                if "ok" in buffer.lower():
                    return

            time.sleep(0.005)

    def _wait_for(self, expected: str, timeout_seconds: int) -> None:
        start = time.time()
        buffer = ""
        expected_lower = expected.lower()

        while True:
            self._throw_if_stop_requested()
            if time.time() - start > timeout_seconds:
                raise TimeoutError(f"Timeout waiting for '{expected}'.")

            data = self._read_existing()
            if data:
                buffer += data
                if expected_lower in buffer.lower():
                    return

            time.sleep(0.01)

    def _read_existing(self) -> str:
        self._ensure_port_open()
        waiting = getattr(self._port, "in_waiting", 0)
        if waiting <= 0:
            return ""
        try:
            raw = self._port.read(waiting)
        except BaseException as ex:
            self._invalidate_serial_after_io_error(ex)
            raise
        if not raw:
            return ""
        return raw.decode("ascii", errors="ignore")

    def _ensure_port_open(self) -> None:
        if not self._port or not self._port.is_open:
            raise RuntimeError("Printer port is not open.")

    def calculate_svg_distance_mm(self, gcode: list[str]) -> float:
        total = 0.0
        state = {"x": 0.0, "y": 0.0, "pen_down": False}
        for line in gcode:
            cmd = line.strip()
            if not cmd or cmd.startswith(";"):
                continue
            total += self._distance_delta_for_command(cmd, state)
        return total

    def get_distance_stats(self) -> dict[str, float]:
        return {
            "currentSvgTotalDistanceMm": round(self._current_svg_total_distance_mm, 3),
            "currentExecutedDistanceMm": round(self._current_executed_distance_mm, 3),
            "currentExecutionPercent": self._calculate_execution_percent(
                self._current_executed_distance_mm,
                self._current_svg_total_distance_mm,
            ),
            "cumulativeDistanceMm": round(self._cumulative_distance_mm, 3),
            "maxPenDistanceM": round(self._max_pen_distance_m, 6),
            "usedPenDistanceM": round(self._cumulative_distance_mm / 1000.0, 6),
            "remainingPenPercent": self._calculate_remaining_pen_percent(),
        }

    def reset_cumulative_distance(self) -> dict[str, float]:
        with self._distance_lock:
            self._cumulative_distance_mm = 0.0
            self._save_cumulative_distance()
        return self.get_distance_stats()

    def set_max_pen_distance_m(self, meters: float) -> dict[str, float]:
        if meters <= 0:
            raise ValueError("Max pen distance must be greater than 0 meters.")
        with self._distance_lock:
            self._max_pen_distance_m = meters
            self._save_cumulative_distance()
        return self.get_distance_stats()

    def _throw_if_stop_requested(self) -> None:
        if self._stop_requested.is_set():
            raise RuntimeError("Print job stop requested by user.")

    def _distance_delta_for_command(self, command: str, state: dict[str, float | bool]) -> float:
        parsed = self._parse_command_values(command)
        g_value = parsed.get("G")
        e_value = parsed.get("E")
        if e_value is not None:
            state["pen_down"] = e_value > 0.0

        if g_value is None or int(round(g_value)) not in {0, 1}:
            return 0.0

        has_x = "X" in parsed
        has_y = "Y" in parsed
        if not has_x and not has_y:
            return 0.0

        current_x = float(state["x"])
        current_y = float(state["y"])
        next_x = parsed.get("X", current_x)
        next_y = parsed.get("Y", current_y)
        dx = next_x - current_x
        dy = next_y - current_y
        distance = math.hypot(dx, dy)
        state["x"] = next_x
        state["y"] = next_y
        return distance if bool(state["pen_down"]) else 0.0

    def _parse_command_values(self, command: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for match in self._COMMAND_VALUE_PATTERN.finditer(command):
            try:
                values[match.group(1).upper()] = float(match.group(2))
            except ValueError:
                continue
        return values

    def _calculate_execution_percent(self, executed_mm: float, total_mm: float) -> float:
        if total_mm <= 0:
            return 0.0
        return round(min(100.0, (executed_mm / total_mm) * 100.0), 2)

    def _load_distance_settings(self) -> tuple[float, float]:
        if not self._stats_file.exists():
            return 0.0, 0.0
        try:
            data = json.loads(self._stats_file.read_text(encoding="utf-8"))
            cumulative_distance = float(data.get("cumulativeDistanceMm", 0.0))
            max_pen_distance = float(data.get("maxPenDistanceM", 0.0))
            return cumulative_distance, max_pen_distance
        except Exception:
            return 0.0, 0.0

    def _save_cumulative_distance(self) -> None:
        payload = {
            "cumulativeDistanceMm": round(self._cumulative_distance_mm, 6),
            "maxPenDistanceM": round(self._max_pen_distance_m, 6),
        }
        self._stats_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _add_to_cumulative_distance(self, distance_mm: float) -> None:
        if distance_mm <= 0:
            return
        with self._distance_lock:
            self._cumulative_distance_mm += distance_mm
            self._save_cumulative_distance()

    def _calculate_remaining_pen_percent(self) -> float:
        if self._max_pen_distance_m <= 0:
            return 0.0
        used_pen_distance_m = self._cumulative_distance_mm / 1000.0
        remaining_percent = ((self._max_pen_distance_m - used_pen_distance_m) / self._max_pen_distance_m) * 100.0
        return round(max(0.0, min(100.0, remaining_percent)), 2)

