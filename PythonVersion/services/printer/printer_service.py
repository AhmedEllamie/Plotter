from __future__ import annotations

import asyncio
import json
import math
import re
import threading
import time
from pathlib import Path
from typing import Any

from PythonVersion.models.contracts import PrintResponse, PrinterStatus
from PythonVersion.models.printer_settings import PrinterSettings
from PythonVersion.services.printer.i_printer_service import IPrinterService

try:
    import serial
except ImportError:  # pragma: no cover - depends on environment
    serial = None


class PrinterService(IPrinterService):
    def __init__(self, settings: PrinterSettings):
        self._settings = settings
        self._port: Any | None = None
        self._is_printing = False
        self._print_lock = threading.Lock()
        self._distance_lock = threading.Lock()
        self._stats_file = Path(__file__).resolve().parents[2] / "distance_stats.json"
        self._cumulative_distance_mm, self._max_pen_distance_m = self._load_distance_settings()
        self._current_svg_total_distance_mm = 0.0
        self._current_executed_distance_mm = 0.0
        self._stop_requested = threading.Event()
        self._bulk_requested_total = 0
        self._bulk_printed_count = 0

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
        return self._is_printing

    @property
    def default_com_port(self) -> str:
        return self._settings.com_port

    @property
    def default_baud_rate(self) -> int:
        return self._settings.baud_rate

    def open_port(self, com_port: str | None = None, baud_rate: int | None = None) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed. Install requirements first.")

        port_name = com_port or self._settings.com_port
        baud = baud_rate or self._settings.baud_rate

        if self._port and self._port.is_open:
            self._port.close()

        self._port = serial.Serial(
            port=port_name,
            baudrate=baud,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,
            write_timeout=2.0,
        )

        # Match the C# serial settings and startup delay.
        self._port.dtr = True
        self._port.rts = True
        time.sleep(1.5)
        self._port.reset_input_buffer()
        self._port.reset_output_buffer()

    def close_port(self) -> None:
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None

    def get_status(self) -> PrinterStatus:
        current_percent = self._calculate_execution_percent(
            self._current_executed_distance_mm,
            self._current_svg_total_distance_mm,
        )
        used_pen_distance_m = self._cumulative_distance_mm / 1000.0
        return PrinterStatus(
            is_open=self.is_open,
            port_name=self.port_name,
            is_printing=self.is_printing,
            bulk_requested_total=self._bulk_requested_total,
            bulk_printed_count=self._bulk_printed_count,
            bulk_stop_requested=self._stop_requested.is_set(),
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
            result = await asyncio.to_thread(self._execute_print_cycle, gcode)
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
                    if self._stop_requested.is_set():
                        break
                    result = self._execute_print_cycle(gcode)
                    total_commands += result["commands_sent"]
                    total_executed_distance += result["executed_distance_mm"]
                    self._bulk_printed_count += 1

            await asyncio.to_thread(run)
            self._add_to_cumulative_distance(total_executed_distance)
            printed_copies = self._bulk_printed_count
            total_svg_distance = svg_total_distance * printed_copies
            stopped = self._stop_requested.is_set() and printed_copies < copies
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
        self._begin_print_job()
        try:
            await asyncio.to_thread(self._execute_void_cycle)
            return PrintResponse(
                message="Void print complete - paper ejected without printing.",
                commands_sent=0,
            )
        finally:
            self._end_print_job()

    def stop_bulk_print(self) -> bool:
        with self._print_lock:
            if not self._is_printing:
                return False
            self._stop_requested.set()
            return True

    async def pen_change_start(self) -> PrintResponse:
        self._begin_print_job()
        try:
            await asyncio.to_thread(self._execute_pen_change_start)
            return PrintResponse(
                message="Pen change start complete. Replace pen, then run pen-change-finish.",
                commands_sent=2,
            )
        finally:
            self._end_print_job()

    async def pen_change_finish(self) -> PrintResponse:
        self._begin_print_job()
        try:
            await asyncio.to_thread(self._execute_pen_change_finish)
            return PrintResponse(
                message="Pen change finish complete. Printer is ready to continue.",
                commands_sent=2,
            )
        finally:
            self._end_print_job()

    def _end_print_job(self) -> None:
        with self._print_lock:
            self._is_printing = False

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
        self._send_safe("G1 E0.0 F4000")

        print("  Ejecting: Move X to 215...")
        self._send_safe("G0 X215.0 F6000.0")

        print("  Ejecting: Start motor (M106)...")
        self._send_safe("M106")

        print("  Ejecting: Push paper Y500...")
        self._send_safe("G0 Y500.0 F6000.0")

        print("  Ejecting: Wait (M400)...")
        self._send_safe("M400")

        print("  Ejecting: Stop motor (M107)...")
        self._send_safe("M107")

        print("Eject complete")

    def _send(self, gcode: str) -> None:
        self._ensure_port_open()
        payload = (gcode + "\n").encode("ascii", errors="ignore")
        self._port.write(payload)
        self._wait_for_ok()

    def _send_safe(self, gcode: str) -> None:
        try:
            self._send(gcode)
        except Exception:
            # Keep eject cycle resilient even if one command fails.
            pass

    def _wait_for_ok(self, timeout_seconds: int = 10) -> None:
        start = time.time()
        buffer = ""

        while True:
            self._throw_if_stop_requested()
            if time.time() - start > timeout_seconds:
                # Keep parity with C# behavior: timeout does not fail the job.
                return

            try:
                data = self._read_existing()
                if data:
                    buffer += data
                    if "ok" in buffer.lower():
                        return
            except Exception:
                pass

            time.sleep(0.005)

    def _wait_for(self, expected: str, timeout_seconds: int) -> None:
        start = time.time()
        buffer = ""
        expected_lower = expected.lower()

        while True:
            self._throw_if_stop_requested()
            if time.time() - start > timeout_seconds:
                raise TimeoutError(f"Timeout waiting for '{expected}'.")

            try:
                data = self._read_existing()
                if data:
                    buffer += data
                    if expected_lower in buffer.lower():
                        return
            except Exception:
                pass

            time.sleep(0.01)

    def _read_existing(self) -> str:
        self._ensure_port_open()
        waiting = getattr(self._port, "in_waiting", 0)
        if waiting <= 0:
            return ""
        raw = self._port.read(waiting)
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

    def _begin_print_job(self) -> None:
        with self._print_lock:
            if self._is_printing:
                raise RuntimeError("Printer is busy.")
            self._is_printing = True
            self._stop_requested.clear()
            self._bulk_requested_total = 0
            self._bulk_printed_count = 0
            self._current_svg_total_distance_mm = 0.0
            self._current_executed_distance_mm = 0.0

    def _throw_if_stop_requested(self) -> None:
        if self._stop_requested.is_set():
            raise RuntimeError("Bulk print stop requested by user.")

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

