from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path
from tkinter import BOTH, LEFT, RIGHT, X, Button, Canvas, Entry, Frame, Label, StringVar, Tk, messagebox

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from plotter_signature.cli import CliSerialConnectError, connect_printer_serial, scan_serial_devices
from plotter_signature.dependency_injection import get_service_provider

_DEFAULT_PLOTTER_ENV_FILE = "/etc/plotter-signature/plotter-signature.env"

_KIOSK_SERIAL_BAUD = 250000


def _kiosk_settings_path() -> Path:
    local = os.getenv("LOCALAPPDATA") or os.getenv("XDG_CONFIG_HOME") or ""
    if local:
        return Path(local) / "PlotterPenKiosk" / "settings.json"
    return Path.home() / ".config" / "plotter_pen_kiosk" / "settings.json"


def _load_kiosk_settings() -> dict[str, str]:
    path = _kiosk_settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("api_base_url", "com_port_override", "device_match"):
        val = data.get(key)
        if isinstance(val, str):
            out[key] = val.strip()
    return out


def _save_kiosk_settings(api_base_url: str, com_port_override: str, device_match: str = "") -> None:
    path = _kiosk_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_base_url": api_base_url.strip().rstrip("/"),
        "com_port_override": com_port_override.strip(),
        "device_match": device_match.strip(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_plotter_api_key_from_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("PLOTTER_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return value
    except OSError:
        pass
    return ""


class PenKioskApp:
    def __init__(self, api_base_url: str | None = None) -> None:
        saved = _load_kiosk_settings()
        default_base = (os.getenv("PLOTTER_KIOSK_API_BASE") or "http://127.0.0.1:5001").strip()
        resolved_base = (api_base_url or saved.get("api_base_url") or default_base).strip()
        self._api_base_url = resolved_base.rstrip("/")
        self._root = Tk()
        self._root.title("Plotter Pen Config Kiosk")
        self._root.configure(bg="#0f172a")
        self._root.attributes("-fullscreen", True)
        self._root.bind("<F11>", self._toggle_fullscreen)
        self._provider = get_service_provider()

        self._status_poll_ms = 3000
        self._api_busy = False
        self._http_ok = False

        self._server_url_var = StringVar(value=self._api_base_url)
        self._com_port_var = StringVar(value=saved.get("com_port_override", ""))
        self._device_match_var = StringVar(
            value=saved.get("device_match", os.getenv("PLOTTER_SERIAL_DEVICE_MATCH", ""))
        )

        self._connection_badge = StringVar(value="USB: Disconnected")
        self._busy_badge = StringVar(value="Idle")
        self._local_usb_status_var = StringVar(value="Local USB: not connected")
        self._cumulative_distance_value = StringVar(value="0.000 m")
        self._executed_distance_value = StringVar(value="0.000 m")
        self._execution_percent_value = StringVar(value="0.00%")
        self._pen_remaining_value = StringVar(value="N/A")
        self._bulk_progress_value = StringVar(value="0 / 0")
        self._bulk_stop_value = StringVar(value="No")
        self._max_pen_distance_var = StringVar(value="")
        self._inline_error_var = StringVar(value="")

        self._link_detail_var = StringVar(value="Checking…")

        self._connection_badge_label: Label | None = None
        self._busy_badge_label: Label | None = None
        self._feedback_box = None
        self._status_card: Frame | None = None
        self._connection_card: Frame | None = None
        self._change_pen_card: Frame | None = None
        self._active_card_idx = 0  # 0=Status, 1=Port/Connect, 2=Change Pen
        self._mode_label_var = StringVar(value="Status")
        self._switch_canvas: Canvas | None = None
        self._switch_knob: int | None = None
        self._connection_lamp_canvas: Canvas | None = None
        self._connection_lamp_oval: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root_frame = Frame(self._root, bg="#0f172a", padx=24, pady=20)
        root_frame.pack(fill=BOTH, expand=True)

        switch_row = Frame(root_frame, bg="#0f172a")
        switch_row.pack(fill=X, pady=(0, 14))
        Label(
            switch_row,
            textvariable=self._mode_label_var,
            bg="#0f172a",
            fg="#cbd5e1",
            font=("Segoe UI", 14, "bold"),
        ).pack(side=RIGHT)
        self._switch_canvas = Canvas(
            switch_row,
            width=204,
            height=44,
            bg="#0f172a",
            highlightthickness=0,
            bd=0,
        )
        self._switch_canvas.pack(side=RIGHT, padx=(0, 10))
        self._switch_canvas.create_rectangle(4, 10, 200, 34, outline="#64748b", fill="#1e293b", width=2)
        self._switch_canvas.create_text(36, 22, text="S", fill="#cbd5e1", font=("Segoe UI", 11, "bold"))
        self._switch_canvas.create_text(102, 22, text="C", fill="#cbd5e1", font=("Segoe UI", 11, "bold"))
        self._switch_canvas.create_text(168, 22, text="P", fill="#cbd5e1", font=("Segoe UI", 11, "bold"))
        self._switch_knob = self._switch_canvas.create_oval(8, 12, 56, 32, fill="#e2e8f0", outline="#cbd5e1")
        self._switch_canvas.bind("<Button-1>", self._toggle_cards_event)

        cards_container = Frame(root_frame, bg="#0f172a")
        cards_container.pack(fill=BOTH, expand=True)

        self._status_card = Frame(
            cards_container,
            bg="#111827",
            padx=20,
            pady=20,
            highlightbackground="#334155",
            highlightthickness=1,
        )
        self._build_status_card(self._status_card)

        self._connection_card = Frame(
            cards_container,
            bg="#111827",
            padx=20,
            pady=20,
            highlightbackground="#334155",
            highlightthickness=1,
        )
        self._build_connection_card(self._connection_card)

        self._change_pen_card = Frame(
            cards_container,
            bg="#111827",
            padx=20,
            pady=20,
            highlightbackground="#334155",
            highlightthickness=1,
        )
        self._build_change_pen_card(self._change_pen_card)

        self._apply_active_card()

    def _build_connection_card(self, parent: Frame) -> None:
        Label(
            parent,
            text="Port / Connect",
            bg="#111827",
            fg="#f8fafc",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        conn_box = Frame(parent, bg="#111827")
        conn_box.pack(fill=BOTH, expand=True)
        Label(conn_box, text="Printer IP / server URL", bg="#111827", fg="#94a3b8", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        Entry(
            conn_box,
            textvariable=self._server_url_var,
            font=("Segoe UI", 13),
            bg="#0b1220",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
        ).pack(fill=X, ipady=6, pady=(2, 6))
        apply_row = Frame(conn_box, bg="#111827")
        apply_row.pack(fill=X, pady=(0, 10))
        Button(
            apply_row,
            text="Apply server",
            command=self._apply_server_url,
            bg="#334155",
            fg="#ffffff",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=10,
            font=("Segoe UI", 12, "bold"),
            cursor="hand2",
        ).pack(side=LEFT)
        Label(conn_box, text="Local USB serial (this PC)", bg="#111827", fg="#94a3b8", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        Entry(
            conn_box,
            textvariable=self._com_port_var,
            font=("Segoe UI", 13),
            bg="#0b1220",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
        ).pack(fill=X, ipady=6, pady=(2, 8))
        Label(
            conn_box,
            text="Plotter USB info match (optional: CH340, CP210x, VID:PID=xxxx:yyyy)",
            bg="#111827",
            fg="#94a3b8",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        Entry(
            conn_box,
            textvariable=self._device_match_var,
            font=("Segoe UI", 13),
            bg="#0b1220",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
        ).pack(fill=X, ipady=6, pady=(2, 8))
        btn_row = Frame(conn_box, bg="#111827")
        btn_row.pack(fill=X)
        for text, cmd, bgc in (
            ("Scan ports", self._scan_local_ports, "#334155"),
            ("Connect", self._connect_local_serial, "#0ea5e9"),
            ("Disconnect USB", self._disconnect_local_serial, "#64748b"),
        ):
            Button(
                btn_row,
                text=text,
                command=cmd,
                bg=bgc,
                fg="#ffffff",
                activeforeground="#ffffff",
                relief="flat",
                padx=16,
                pady=10,
                font=("Segoe UI", 12, "bold"),
                cursor="hand2",
            ).pack(side=LEFT, padx=(0, 8))
        Label(
            conn_box,
            textvariable=self._local_usb_status_var,
            bg="#111827",
            fg="#cbd5e1",
            font=("Segoe UI", 12),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _build_status_card(self, parent: Frame) -> None:
        Label(
            parent,
            text="Status",
            bg="#111827",
            fg="#f8fafc",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        link_row = Frame(parent, bg="#111827")
        link_row.pack(fill=X, pady=(0, 12))
        self._connection_lamp_canvas = Canvas(
            link_row, width=48, height=44, bg="#111827", highlightthickness=0, bd=0
        )
        self._connection_lamp_canvas.pack(side=LEFT)
        self._connection_lamp_oval = self._connection_lamp_canvas.create_oval(
            10, 6, 38, 34, fill="#64748b", outline="#475569", width=2
        )
        lbl_col = Frame(link_row, bg="#111827")
        lbl_col.pack(side=LEFT, padx=(10, 0))
        Label(
            lbl_col,
            textvariable=self._link_detail_var,
            bg="#111827",
            fg="#e2e8f0",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")

        badges_row = Frame(parent, bg="#111827")
        badges_row.pack(fill=X, pady=(0, 10))
        self._connection_badge_label = self._badge(badges_row, self._connection_badge, ok=False)
        self._connection_badge_label.pack(side=LEFT, padx=(0, 8))
        self._busy_badge_label = self._badge(badges_row, self._busy_badge, ok=True)
        self._busy_badge_label.pack(side=LEFT)

        self._metric_row(parent, "Cumulative distance", self._cumulative_distance_value)
        self._metric_row(parent, "Executed distance", self._executed_distance_value)
        self._metric_row(parent, "Execution progress", self._execution_percent_value)
        self._metric_row(parent, "Pen remaining", self._pen_remaining_value)
        self._metric_row(parent, "Bulk progress", self._bulk_progress_value)
        self._metric_row(parent, "Bulk stop requested", self._bulk_stop_value)

    def _build_change_pen_card(self, parent: Frame) -> None:
        Label(
            parent,
            text="Change Pen",
            bg="#111827",
            fg="#f8fafc",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        actions_row = Frame(parent, bg="#111827")
        actions_row.pack(fill=X, pady=(0, 14))
        Button(
            actions_row,
            text="PenDown",
            command=lambda: self._run_action("PenDown command sent.", "/api/config/change-pen/start"),
            bg="#0ea5e9",
            fg="#ffffff",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            relief="flat",
            padx=30,
            pady=14,
            font=("Segoe UI", 15, "bold"),
            cursor="hand2",
        ).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        Button(
            actions_row,
            text="PenUp",
            command=lambda: self._run_action("PenUp command sent.", "/api/config/change-pen/finish"),
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            activeforeground="#ffffff",
            relief="flat",
            padx=30,
            pady=14,
            font=("Segoe UI", 15, "bold"),
            cursor="hand2",
        ).pack(side=LEFT, fill=X, expand=True, padx=(8, 0))

        Label(
            parent,
            text="Max Pen Distance (meters)",
            bg="#111827",
            fg="#cbd5e1",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(10, 4))

        input_row = Frame(parent, bg="#111827")
        input_row.pack(fill=X, pady=(0, 4))
        Entry(
            input_row,
            textvariable=self._max_pen_distance_var,
            font=("Segoe UI", 14),
            bg="#0b1220",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            width=20,
        ).pack(side=LEFT, fill=X, expand=True, ipady=8, padx=(0, 10))
        Button(
            input_row,
            text="Save",
            command=self._set_max_pen_distance,
            bg="#7c3aed",
            fg="#ffffff",
            activebackground="#6d28d9",
            activeforeground="#ffffff",
            relief="flat",
            padx=24,
            pady=10,
            font=("Segoe UI", 13, "bold"),
            cursor="hand2",
        ).pack(side=LEFT)

        Label(
            parent,
            textvariable=self._inline_error_var,
            bg="#111827",
            fg="#fca5a5",
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(2, 10))

        Button(
            parent,
            text="Reset Distance",
            command=self._confirm_reset_distance,
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            relief="flat",
            padx=24,
            pady=16,
            font=("Segoe UI", 14, "bold"),
            cursor="hand2",
        ).pack(fill=X, pady=(2, 0))

    def _badge(self, parent: Frame, text_variable: StringVar, ok: bool) -> Label:
        return Label(
            parent,
            textvariable=text_variable,
            bg="#14532d" if ok else "#7f1d1d",
            fg="#dcfce7" if ok else "#fee2e2",
            font=("Segoe UI", 11, "bold"),
            padx=12,
            pady=4,
        )

    def _metric_row(self, parent: Frame, key: str, value: StringVar) -> None:
        row = Frame(parent, bg="#111827")
        row.pack(fill=X, pady=3)
        Label(
            row,
            text=key,
            bg="#111827",
            fg="#94a3b8",
            font=("Segoe UI", 12, "bold"),
        ).pack(side=LEFT)
        Label(
            row,
            textvariable=value,
            bg="#111827",
            fg="#f8fafc",
            font=("Segoe UI", 12, "bold"),
        ).pack(side=RIGHT)

    _SWITCH_KNOB_POS = (
        (8, 12, 56, 32),
        (74, 12, 122, 32),
        (140, 12, 188, 32),
    )

    def _move_switch_knob(self, idx: int) -> None:
        if self._switch_canvas is None or self._switch_knob is None:
            return
        i = max(0, min(2, idx))
        x1, y1, x2, y2 = self._SWITCH_KNOB_POS[i]
        self._switch_canvas.coords(self._switch_knob, x1, y1, x2, y2)

    def _apply_active_card(self) -> None:
        for card in (self._status_card, self._connection_card, self._change_pen_card):
            if card is not None:
                card.pack_forget()
        idx = max(0, min(2, self._active_card_idx))
        self._active_card_idx = idx
        if idx == 1 and self._connection_card is not None:
            self._connection_card.pack(fill=BOTH, expand=True)
            self._mode_label_var.set("Port / Connect")
        elif idx == 2 and self._change_pen_card is not None:
            self._change_pen_card.pack(fill=BOTH, expand=True)
            self._mode_label_var.set("Change Pen")
        elif self._status_card is not None:
            self._status_card.pack(fill=BOTH, expand=True)
            self._mode_label_var.set("Status")
        self._move_switch_knob(self._active_card_idx)

    def _toggle_cards_event(self, event: object) -> None:
        mx = getattr(event, "x", None)
        if mx is None or self._switch_canvas is None:
            self._active_card_idx = (self._active_card_idx + 1) % 3
            self._apply_active_card()
            return
        if mx < 68:
            self._active_card_idx = 0
        elif mx < 136:
            self._active_card_idx = 1
        else:
            self._active_card_idx = 2
        self._apply_active_card()

    def _toggle_fullscreen(self, _event: object) -> None:
        current = bool(self._root.attributes("-fullscreen"))
        self._root.attributes("-fullscreen", not current)

    def _is_local_serial_open(self) -> bool:
        return self._provider.printer_service.is_open

    def _set_usb_lamp(self, connected: bool) -> None:
        if self._connection_lamp_canvas is None or self._connection_lamp_oval is None:
            return
        if connected:
            fill, outline = "#22c55e", "#15803d"
        else:
            fill, outline = "#ef4444", "#b91c1c"
        self._connection_lamp_canvas.itemconfig(self._connection_lamp_oval, fill=fill, outline=outline)

    def _update_link_detail_line(self) -> None:
        http = "OK" if self._http_ok else "unreachable"
        usb = "open" if self._is_local_serial_open() else "closed"
        self._link_detail_var.set(f"Server: {http} | Local USB: {usb}")

    def _after_local_serial_changed(self) -> None:
        o = self._is_local_serial_open()
        self._set_usb_lamp(o)
        self._set_badge_color(self._connection_badge_label, "USB: Connected" if o else "USB: Disconnected", o)
        port = self._com_port_var.get().strip() or "—"
        self._local_usb_status_var.set(f"Local USB: {port} — {'open' if o else 'closed'}")
        self._update_link_detail_line()

    def _scan_local_ports(self) -> None:
        if self._api_busy:
            return

        def worker() -> None:
            self._api_busy = True
            try:
                devices = scan_serial_devices()
                self._root.after(0, lambda: self._present_scan_results(devices))
            except Exception as ex:
                self._root.after(0, lambda err=ex: messagebox.showerror("Scan ports", str(err)))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _present_scan_results(self, devices: list[dict[str, str]]) -> None:
        if not devices:
            self._local_usb_status_var.set("Local USB: no serial ports found.")
            messagebox.showinfo("Serial ports", "No serial ports found.")
            return
        if not self._com_port_var.get().strip():
            self._com_port_var.set(devices[0]["device"])
        rows = []
        for item in devices[:50]:
            meta = " | ".join(
                part
                for part in (
                    item.get("device", ""),
                    item.get("description", ""),
                    item.get("manufacturer", ""),
                    item.get("hwid", ""),
                )
                if part
            )
            rows.append(meta)
        head = "\n".join(rows)
        tail = f"\n… {len(devices)} total" if len(devices) > 50 else ""
        self._local_usb_status_var.set(f"Local USB: listed {len(devices)} port(s). First: {devices[0]['device']}")
        messagebox.showinfo("Serial ports", head + tail)

    def _connect_local_serial(self) -> None:
        if self._api_busy:
            return
        device_or_match = self._com_port_var.get().strip()
        explicit_device = device_or_match
        device_match = self._device_match_var.get().strip()
        if device_or_match and not (
            device_or_match.startswith("/dev/") or re.fullmatch(r"(?i)com\d+", device_or_match)
        ):
            explicit_device = ""
            device_match = device_match or device_or_match
        if not explicit_device and not device_match:
            messagebox.showwarning("USB connect", "Enter a device path or USB info match first.")
            return
        if sys.platform.startswith("win") and re.fullmatch(r"(?i)com\d+", explicit_device):
            explicit_device = explicit_device.upper()

        def worker() -> None:
            self._api_busy = True
            try:
                result = connect_printer_serial(
                    self._provider,
                    com_port=explicit_device or None,
                    baud_rate=_KIOSK_SERIAL_BAUD,
                    device_match=device_match or None,
                )
                connected_port = str(result.get("connectedPort") or "")
                if connected_port:
                    self._root.after(0, lambda p=connected_port: self._com_port_var.set(p))
                self._root.after(
                    0,
                    lambda: _save_kiosk_settings(
                        self._api_base_url,
                        self._com_port_var.get(),
                        self._device_match_var.get(),
                    ),
                )
                self._root.after(0, self._after_local_serial_changed)
            except CliSerialConnectError as ex:
                self._root.after(0, lambda err=ex: messagebox.showerror("USB connect", json.dumps(err.payload, indent=2)))
                self._root.after(0, self._after_local_serial_changed)
            except Exception as ex:
                self._root.after(0, lambda err=ex: messagebox.showerror("USB connect", str(err)))
                self._root.after(0, self._after_local_serial_changed)
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _disconnect_local_serial(self) -> None:
        def worker() -> None:
            self._provider.printer_service.close_port()
            self._root.after(0, self._after_local_serial_changed)

        threading.Thread(target=worker, daemon=True).start()

    def _append_feedback(self, message: str, is_error: bool = False) -> None:
        _ = message
        _ = is_error

    def _resolve_api_key(self) -> str:
        """Match Flask auth: prefer live env file (so key rotation applies without kiosk restart)."""
        explicit = os.getenv("PLOTTER_API_KEY_FILE")
        if explicit is not None:
            path = explicit.strip()
            if path:
                key = _read_plotter_api_key_from_file(path)
                if key:
                    return key
        else:
            key = _read_plotter_api_key_from_file(_DEFAULT_PLOTTER_ENV_FILE)
            if key:
                return key
        return (os.getenv("PLOTTER_API_KEY") or "").strip()

    def _apply_server_url(self) -> None:
        raw = self._server_url_var.get().strip()
        if not raw:
            self._append_feedback("Enter a plotter server URL (e.g. http://192.168.1.5:5001).", is_error=True)
            return
        if not raw.lower().startswith(("http://", "https://")):
            raw = f"http://{raw}"
        self._api_base_url = raw.rstrip("/")
        self._server_url_var.set(self._api_base_url)
        _save_kiosk_settings(self._api_base_url, self._com_port_var.get(), self._device_match_var.get())
        self._append_feedback("Server URL applied.")
        self._refresh_status_now()

    def _refresh_status_now(self) -> None:
        try:
            status = self._api_get("/api/cmd/status")
            self._http_ok = True
            is_busy = bool(status.get("is_busy") or status.get("is_printing"))

            self._set_badge_color(self._busy_badge_label, "Busy" if is_busy else "Idle", not is_busy)

            self._cumulative_distance_value.set(self._format_meters_from_mm(status.get("cumulative_distance_mm")))
            self._executed_distance_value.set(self._format_meters_from_mm(status.get("current_executed_distance_mm")))
            self._execution_percent_value.set(self._format_percent(status.get("current_execution_percent")))

            max_pen_distance = float(status.get("max_pen_distance_m") or 0.0)
            self._pen_remaining_value.set(
                self._format_percent(status.get("remaining_pen_percent")) if max_pen_distance > 0 else "N/A"
            )
            self._bulk_progress_value.set(
                f"{int(status.get('bulk_printed_count') or 0)} / {int(status.get('bulk_requested_total') or 0)}"
            )
            self._bulk_stop_value.set("Yes" if bool(status.get("bulk_stop_requested")) else "No")

            if max_pen_distance > 0 and not self._max_pen_distance_var.get().strip():
                self._max_pen_distance_var.set(str(max_pen_distance))
        except HTTPError as ex:
            self._http_ok = False
            self._append_feedback(f"Status HTTP error: {ex.code}", is_error=True)
        except URLError as ex:
            self._http_ok = False
            self._append_feedback(f"Status network error: {ex.reason}", is_error=True)
        except Exception as ex:
            self._http_ok = False
            self._append_feedback(f"Status error: {ex}", is_error=True)

        self._after_local_serial_changed()

    def _request_headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if json_body:
            headers["Content-Type"] = "application/json"
        key = self._resolve_api_key()
        if key:
            headers["X-API-Key"] = key
        return headers

    @staticmethod
    def _format_meters_from_mm(value: object) -> str:
        try:
            mm = float(value or 0.0)
        except (TypeError, ValueError):
            return "0.000 m"
        return f"{(mm / 1000.0):.3f} m"

    @staticmethod
    def _format_percent(value: object) -> str:
        try:
            percent = float(value or 0.0)
        except (TypeError, ValueError):
            return "0.00%"
        return f"{max(0.0, min(100.0, percent)):.2f}%"

    def _api_post(self, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        request = Request(
            url=f"{self._api_base_url}{path}",
            data=json.dumps(payload or {}).encode("utf-8"),
            headers=self._request_headers(json_body=True),
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict) or parsed.get("success") is False:
                raise RuntimeError(str(parsed.get("message") or f"Request failed ({response.status})"))
            data = parsed.get("data")
            return data if isinstance(data, dict) else {}

    def _api_get(self, path: str) -> dict[str, object]:
        request = Request(
            url=f"{self._api_base_url}{path}",
            headers=self._request_headers(json_body=False),
            method="GET",
        )
        with urlopen(request, timeout=12) as response:
            body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict) or parsed.get("success") is False:
                raise RuntimeError(str(parsed.get("message") or f"Request failed ({response.status})"))
            data = parsed.get("data")
            return data if isinstance(data, dict) else {}

    def _run_action(self, success_message: str, endpoint: str) -> None:
        if self._api_busy:
            self._append_feedback("Another action is running. Please wait.", is_error=True)
            return

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post(endpoint, {})
                self._root.after(0, lambda m=success_message: self._append_feedback(m))
                self._root.after(0, self._refresh_status_now)
            except Exception as ex:
                self._root.after(0, lambda err=ex: self._append_feedback(str(err), is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _set_max_pen_distance(self) -> None:
        raw_value = self._max_pen_distance_var.get().strip()
        try:
            meters = float(raw_value)
            if meters <= 0:
                raise ValueError
        except ValueError:
            self._inline_error_var.set("Please enter a valid value greater than 0.")
            self._append_feedback("Invalid max distance input.", is_error=True)
            return

        self._inline_error_var.set("")

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post("/api/config/pen-max-distance", {"meters": meters})
                self._root.after(0, lambda: self._append_feedback("Max pen distance updated."))
                self._root.after(0, self._refresh_status_now)
            except Exception as ex:
                self._root.after(0, lambda err=ex: self._append_feedback(str(err), is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_reset_distance(self) -> None:
        if not messagebox.askyesno("Reset Distance", "Reset cumulative distance now?"):
            return

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post("/api/config/reset", {})
                self._root.after(0, lambda: self._append_feedback("Distance reset completed."))
                self._root.after(0, self._refresh_status_now)
            except Exception as ex:
                self._root.after(0, lambda err=ex: self._append_feedback(str(err), is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _set_badge_color(self, label: Label | None, text: str, ok_color: bool) -> None:
        if label is None:
            return
        label.configure(
            text=text,
            bg="#14532d" if ok_color else "#7f1d1d",
            fg="#dcfce7" if ok_color else "#fee2e2",
        )

    def _refresh_status(self) -> None:
        try:
            self._refresh_status_now()
        finally:
            self._root.after(self._status_poll_ms, self._refresh_status)

    def run(self) -> None:
        self._append_feedback("Pen kiosk started.")
        self._refresh_status()
        self._root.mainloop()


def main() -> None:
    app = PenKioskApp()
    app.run()


if __name__ == "__main__":
    main()
