from __future__ import annotations

import json
import os
import socket
import sys
import threading
from pathlib import Path
from tkinter import BOTH, E, LEFT, RIGHT, W, X, Button, Canvas, Entry, Frame, Label, StringVar, Tk, messagebox

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DEFAULT_PLOTTER_ENV_FILE = "/etc/plotter-signature/plotter-signature.env"


def _strict_kiosk_enabled() -> bool:
    """Linux touch kiosks: lock fullscreen unless PLOTTER_KIOSK_RELAXED is set."""
    relaxed = os.getenv("PLOTTER_KIOSK_RELAXED", "").strip().lower()
    if relaxed in ("1", "true", "yes", "on"):
        return False
    return sys.platform.startswith("linux")


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
    val = data.get("api_base_url")
    return {"api_base_url": val.strip()} if isinstance(val, str) else {}


def _local_ipv4s_for_display() -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            ip = probe.getsockname()[0]
            if ip and ip not in seen:
                seen.add(ip)
                ordered.append(ip)
        except OSError:
            pass
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET, type=socket.SOCK_DGRAM):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in seen:
                seen.add(ip)
                ordered.append(ip)
    except OSError:
        pass
    if not ordered:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and ip != "127.0.0.1" and ip not in seen:
                ordered.append(ip)
        except OSError:
            pass
    if not ordered:
        return "Unavailable"
    return ", ".join(ordered)


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
    _INFO_FG_OK = "#a7f3d0"
    _INFO_FG_BAD = "#fecaca"
    _INFO_FG_WARN = "#fde68a"
    _INFO_FG_MUTED = "#94a3b8"
    _SWITCH_KNOB_POS = (
        (8, 12, 56, 32),
        (80, 12, 128, 32),
    )

    def __init__(self, api_base_url: str | None = None) -> None:
        saved = _load_kiosk_settings()
        default_base = (os.getenv("PLOTTER_KIOSK_API_BASE") or "http://127.0.0.1:5001").strip()
        resolved_base = (api_base_url or saved.get("api_base_url") or default_base).strip()
        self._api_base_url = resolved_base.rstrip("/")
        self._root = Tk()
        self._root.title("Plotter Pen Config Kiosk")
        self._root.configure(bg="#0f172a")
        self._strict_kiosk = _strict_kiosk_enabled()
        self._kiosk_guard_ms = 800
        self._kiosk_guard_running = False

        self._root.protocol("WM_DELETE_WINDOW", lambda: None)
        self._setup_kiosk_window()

        self._status_poll_ms = 3000
        self._api_busy = False
        self._http_ok = False
        self._plotter_connected = False

        self._current_ip_var = StringVar(value="Resolving…")
        self._cumulative_distance_value = StringVar(value="0.000 m")
        self._executed_distance_value = StringVar(value="0.000 m")
        self._execution_percent_value = StringVar(value="0.00%")
        self._pen_remaining_value = StringVar(value="N/A")
        self._bulk_progress_value = StringVar(value="0 / 0")
        self._bulk_stop_value = StringVar(value="No")
        self._max_pen_distance_var = StringVar(value="")
        self._inline_error_var = StringVar(value="")
        self._api_feedback_code_var = StringVar(value="")
        self._api_feedback_message_var = StringVar(value="")
        self._error_code_label: Label | None = None
        self._api_feedback_message_label: Label | None = None
        self._info_server_label: Label | None = None
        self._info_plotter_label: Label | None = None
        self._info_state_label: Label | None = None

        self._mode_label_var = StringVar(value="Status")
        self._status_card: Frame | None = None
        self._change_pen_card: Frame | None = None
        self._active_card_idx = 0
        self._switch_canvas: Canvas | None = None
        self._switch_knob: int | None = None

        self._build_ui()
        self._root.after(0, self._apply_kiosk_window_mode)
        self._root.after(250, self._apply_kiosk_window_mode)
        self._root.after(1000, self._apply_kiosk_window_mode)

    def _setup_kiosk_window(self) -> None:
        self._apply_kiosk_window_mode()
        if not self._strict_kiosk:
            return
        root = self._root
        root.bind("<FocusOut>", self._on_kiosk_focus_out, add="+")
        root.bind("<Unmap>", self._on_kiosk_unmap, add="+")
        for seq in (
            "<Escape>",
            "<F11>",
            "<Alt-F4>",
            "<Control-q>",
            "<Control-Q>",
            "<Super_L>",
            "<Super_R>",
            "<Button-4>",
            "<Button-5>",
        ):
            root.bind_all(seq, self._block_kiosk_exit, add="+")

    def _screen_size(self) -> tuple[int, int]:
        self._root.update_idletasks()
        width = int(self._root.winfo_screenwidth() or 0)
        height = int(self._root.winfo_screenheight() or 0)
        if width < 320 or height < 240:
            return 1920, 1080
        return width, height

    def _apply_kiosk_window_mode(self) -> None:
        root = self._root
        width, height = self._screen_size()
        try:
            if root.state() == "iconic":
                root.deiconify()
        except Exception:
            pass
        try:
            root.attributes("-fullscreen", True)
        except Exception:
            pass
        try:
            root.geometry(f"{width}x{height}+0+0")
        except Exception:
            pass
        if self._strict_kiosk:
            try:
                root.overrideredirect(True)
            except Exception:
                pass
            try:
                root.attributes("-type", "splash")
            except Exception:
                pass
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            root.lift()
            root.focus_force()
        except Exception:
            pass

    def _on_kiosk_focus_out(self, _event: object) -> None:
        if self._strict_kiosk:
            self._root.after(50, self._apply_kiosk_window_mode)

    def _on_kiosk_unmap(self, _event: object) -> None:
        if self._strict_kiosk:
            self._root.after(10, self._apply_kiosk_window_mode)

    @staticmethod
    def _block_kiosk_exit(_event: object) -> str:
        return "break"

    def _start_kiosk_guard(self) -> None:
        if self._kiosk_guard_running:
            return
        self._kiosk_guard_running = True
        self._kiosk_guard_tick()

    def _kiosk_guard_tick(self) -> None:
        try:
            if self._strict_kiosk:
                self._apply_kiosk_window_mode()
        finally:
            self._root.after(self._kiosk_guard_ms, self._kiosk_guard_tick)

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
            width=140,
            height=44,
            bg="#0f172a",
            highlightthickness=0,
            bd=0,
        )
        self._switch_canvas.pack(side=RIGHT, padx=(0, 10))
        self._switch_canvas.create_rectangle(4, 10, 136, 34, outline="#64748b", fill="#1e293b", width=2)
        self._switch_canvas.create_text(36, 22, text="S", fill="#cbd5e1", font=("Segoe UI", 11, "bold"))
        self._switch_canvas.create_text(104, 22, text="P", fill="#cbd5e1", font=("Segoe UI", 11, "bold"))
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

    def _build_status_card(self, parent: Frame) -> None:
        bg = "#1e293b"
        # Outer section titles (Info / Meters / Errors) omitted for small HDMI; row labels kept.
        info_panel = self._status_section(parent, "")
        self._prepare_status_grid(info_panel)
        r = 0
        self._grid_cell_key(info_panel, bg, r, 0, "Printer IP")
        self._grid_cell_value_var(info_panel, bg, r, 1, self._current_ip_var, wraplength=340)
        self._grid_cell_key(info_panel, bg, r, 2, "Server")
        self._info_server_label = self._grid_cell_value_plain(info_panel, bg, r, 3)
        r += 1
        self._grid_cell_key(info_panel, bg, r, 0, "Plotter")
        self._info_plotter_label = self._grid_cell_value_plain(info_panel, bg, r, 1)
        self._grid_cell_key(info_panel, bg, r, 2, "State")
        self._info_state_label = self._grid_cell_value_plain(info_panel, bg, r, 3)

        meters_panel = self._status_section(parent, "")
        self._prepare_status_grid(meters_panel)
        r = 0
        self._grid_cell_key(meters_panel, bg, r, 0, "Cumulative distance (m)")
        self._grid_cell_value_var(meters_panel, bg, r, 1, self._cumulative_distance_value)
        self._grid_cell_key(meters_panel, bg, r, 2, "Executed distance (m)")
        self._grid_cell_value_var(meters_panel, bg, r, 3, self._executed_distance_value)
        r += 1
        self._grid_cell_key(meters_panel, bg, r, 0, "Execution progress")
        self._grid_cell_value_var(meters_panel, bg, r, 1, self._execution_percent_value)
        self._grid_cell_key(meters_panel, bg, r, 2, "Pen remaining")
        self._grid_cell_value_var(meters_panel, bg, r, 3, self._pen_remaining_value)
        r += 1
        self._grid_cell_key(meters_panel, bg, r, 0, "Bulk progress")
        self._grid_cell_value_var(meters_panel, bg, r, 1, self._bulk_progress_value)
        self._grid_cell_key(meters_panel, bg, r, 2, "Bulk stop requested")
        self._grid_cell_value_var(meters_panel, bg, r, 3, self._bulk_stop_value)

        errors_panel = self._status_section(parent, "")
        errors_panel.grid_columnconfigure(0, weight=0)
        errors_panel.grid_columnconfigure(1, weight=1)
        self._grid_cell_key(errors_panel, bg, 0, 0, "Error code")
        self._error_code_label = self._grid_cell_value_plain(errors_panel, bg, 0, 1, columnspan=3)
        self._grid_cell_key(errors_panel, bg, 1, 0, "Error message")
        self._api_feedback_message_label = self._grid_cell_value_plain(
            errors_panel,
            bg,
            1,
            1,
            font=("Segoe UI", 12),
            initial_fg="#64748b",
            wraplength=900,
            columnspan=3,
        )

    def _status_section(self, parent: Frame, title: str) -> Frame:
        block = Frame(parent, bg="#111827")
        block.pack(fill=X, pady=(0, 10))
        if title.strip():
            Label(
                block,
                text=title,
                bg="#111827",
                fg="#94a3b8",
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w", pady=(0, 8))
        inner = Frame(block, bg="#1e293b", padx=18, pady=14)
        inner.pack(fill=BOTH, expand=True)
        return inner

    def _prepare_status_grid(self, inner: Frame) -> None:
        inner.grid_columnconfigure(0, weight=0)
        inner.grid_columnconfigure(1, weight=1)
        inner.grid_columnconfigure(2, weight=0)
        inner.grid_columnconfigure(3, weight=1)

    def _grid_cell_key(self, inner: Frame, bg: str, row: int, col: int, text: str) -> None:
        Label(
            inner,
            text=text,
            bg=bg,
            fg="#94a3b8",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).grid(row=row, column=col, sticky=W, padx=(0, 8), pady=3)

    def _grid_cell_value_var(
        self,
        inner: Frame,
        bg: str,
        row: int,
        col: int,
        var: StringVar,
        *,
        wraplength: int = 0,
    ) -> Label:
        kw: dict = {
            "textvariable": var,
            "bg": bg,
            "fg": "#f8fafc",
            "font": ("Segoe UI", 12, "bold"),
            "anchor": "w",
        }
        if wraplength > 0:
            kw["wraplength"] = wraplength
            kw["justify"] = "left"
        label = Label(inner, **kw)
        label.grid(row=row, column=col, sticky=W + E, padx=(0, 16), pady=3)
        return label

    def _grid_cell_value_plain(
        self,
        inner: Frame,
        bg: str,
        row: int,
        col: int,
        *,
        font: object = ("Segoe UI", 12, "bold"),
        initial_fg: str = "#f8fafc",
        wraplength: int = 0,
        columnspan: int = 1,
    ) -> Label:
        kw: dict = {"text": "—", "bg": bg, "fg": initial_fg, "font": font, "anchor": "w"}
        if wraplength > 0:
            kw["wraplength"] = wraplength
            kw["justify"] = "left"
        label = Label(inner, **kw)
        label.grid(row=row, column=col, columnspan=columnspan, sticky=W + E, padx=(0, 8), pady=3)
        return label

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

    def _move_switch_knob(self, idx: int) -> None:
        if self._switch_canvas is None or self._switch_knob is None:
            return
        i = max(0, min(1, idx))
        x1, y1, x2, y2 = self._SWITCH_KNOB_POS[i]
        self._switch_canvas.coords(self._switch_knob, x1, y1, x2, y2)

    def _apply_active_card(self) -> None:
        for card in (self._status_card, self._change_pen_card):
            if card is not None:
                card.pack_forget()
        idx = max(0, min(1, self._active_card_idx))
        self._active_card_idx = idx
        if idx == 1 and self._change_pen_card is not None:
            self._change_pen_card.pack(fill=BOTH, expand=True)
            self._mode_label_var.set("Change Pen")
        elif self._status_card is not None:
            self._status_card.pack(fill=BOTH, expand=True)
            self._mode_label_var.set("Status")
        self._move_switch_knob(self._active_card_idx)

    def _toggle_cards_event(self, event: object) -> None:
        mx = getattr(event, "x", None)
        if mx is None or self._switch_canvas is None:
            self._active_card_idx = (self._active_card_idx + 1) % 2
            self._apply_active_card()
            return
        if mx < 70:
            self._active_card_idx = 0
        else:
            self._active_card_idx = 1
        self._apply_active_card()

    def _set_key_value_cell(self, label: Label | None, text: str, fg: str) -> None:
        if label is None:
            return
        label.configure(text=text, fg=fg)

    def _clear_error_panel(self) -> None:
        self._api_feedback_code_var.set("")
        self._api_feedback_message_var.set("")
        if self._error_code_label is not None:
            self._error_code_label.configure(text="—", fg="#64748b")
        if self._api_feedback_message_label is not None:
            self._api_feedback_message_label.configure(text="—", fg="#64748b")

    def _refresh_status_now(self) -> None:
        try:
            status = self._api_get("/api/cmd/status")
            self._http_ok = True
            self._plotter_connected = bool(status.get("printer_connected"))
            is_busy = bool(status.get("is_busy") or status.get("is_printing"))

            ok_fg, bad_fg, warn_fg = self._INFO_FG_OK, self._INFO_FG_BAD, self._INFO_FG_WARN
            self._set_key_value_cell(self._info_server_label, "OK", ok_fg)
            self._set_key_value_cell(
                self._info_plotter_label,
                "Connected" if self._plotter_connected else "Disconnected",
                ok_fg if self._plotter_connected else bad_fg,
            )
            self._set_key_value_cell(
                self._info_state_label,
                "Busy" if is_busy else "Idle",
                warn_fg if is_busy else ok_fg,
            )

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

            lc = status.get("lastApiErrorCode")
            lm = status.get("lastApiErrorMessage")
            if lc is not None and lm not in (None, ""):
                try:
                    code_str = str(int(lc))
                except (TypeError, ValueError):
                    code_str = str(lc)
                self._append_feedback(str(lm), is_error=True, error_code=code_str)
            else:
                self._clear_error_panel()
        except HTTPError as ex:
            self._http_ok = False
            self._plotter_connected = False
            bad_fg, muted_fg = self._INFO_FG_BAD, self._INFO_FG_MUTED
            self._set_key_value_cell(self._info_server_label, f"HTTP {ex.code}", bad_fg)
            self._set_key_value_cell(self._info_plotter_label, "—", muted_fg)
            self._set_key_value_cell(self._info_state_label, "—", muted_fg)
            code, msg = self._decode_http_error(ex)
            self._append_feedback(msg or f"Status HTTP error: {ex.code}", is_error=True, error_code=code)
        except URLError as ex:
            self._http_ok = False
            self._plotter_connected = False
            bad_fg, muted_fg = self._INFO_FG_BAD, self._INFO_FG_MUTED
            self._set_key_value_cell(self._info_server_label, "unreachable", bad_fg)
            self._set_key_value_cell(self._info_plotter_label, "—", muted_fg)
            self._set_key_value_cell(self._info_state_label, "—", muted_fg)
            self._append_feedback(f"Status network error: {ex.reason}", is_error=True)
        except Exception as ex:
            self._http_ok = False
            self._plotter_connected = False
            bad_fg, muted_fg = self._INFO_FG_BAD, self._INFO_FG_MUTED
            self._set_key_value_cell(self._info_server_label, "error", bad_fg)
            self._set_key_value_cell(self._info_plotter_label, "—", muted_fg)
            self._set_key_value_cell(self._info_state_label, "—", muted_fg)
            self._append_feedback(f"Status error: {ex}", is_error=True)

        self._current_ip_var.set(_local_ipv4s_for_display())

    @staticmethod
    def _decode_http_error(ex: HTTPError) -> tuple[str | None, str]:
        try:
            body = ex.read().decode("utf-8", errors="ignore")
            data = json.loads(body) if body.strip() else {}
            if isinstance(data, dict):
                raw_code = data.get("errorCode")
                msg = data.get("message")
                if isinstance(msg, str):
                    if isinstance(raw_code, int):
                        return str(raw_code), msg
                    if isinstance(raw_code, str) and raw_code.isdigit():
                        return raw_code, msg
                    return None, msg
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return None, f"HTTP {ex.code} {ex.reason}"

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

    def _resolve_api_key(self) -> str:
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

    def _run_action(self, success_message: str, endpoint: str) -> None:
        if self._api_busy:
            self._append_feedback("Another action is running. Please wait.", is_error=True)
            return

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post(endpoint, {})
                self._root.after(0, lambda m=success_message: self._append_feedback(m, is_error=False))
                self._root.after(0, self._refresh_status_now)
            except HTTPError as ex:
                code, msg = self._decode_http_error(ex)
                self._root.after(
                    0,
                    lambda c=code, m=msg, sc=ex.code: self._append_feedback(
                        m or f"HTTP {sc}", is_error=True, error_code=c
                    ),
                )
            except Exception as ex:
                self._root.after(0, lambda err=str(ex): self._append_feedback(err, is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _append_feedback(self, message: str, is_error: bool = False, error_code: str | None = None) -> None:
        trimmed = (message or "").strip()[:800]
        code_plain = (error_code or "").strip() if is_error else ""
        self._api_feedback_code_var.set(code_plain)
        self._api_feedback_message_var.set(trimmed)

        if self._error_code_label is not None:
            code_display = code_plain if code_plain else "—"
            self._error_code_label.configure(
                text=code_display,
                fg="#fecaca" if is_error and code_plain else "#64748b",
            )

        if self._api_feedback_message_label is not None:
            msg_display = trimmed if trimmed else "—"
            if is_error:
                self._api_feedback_message_label.configure(text=msg_display, fg="#fecaca")
            else:
                self._api_feedback_message_label.configure(
                    text=msg_display,
                    fg="#86efac" if trimmed else "#64748b",
                )

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
                self._api_post("/api/config/pen-distance", {"meters": meters})
                self._root.after(0, lambda: self._append_feedback("Max pen distance updated.", is_error=False))
                self._root.after(0, self._refresh_status_now)
            except HTTPError as ex:
                code, msg = self._decode_http_error(ex)
                self._root.after(
                    0,
                    lambda c=code, m=msg, sc=ex.code: self._append_feedback(
                        m or f"HTTP {sc}", is_error=True, error_code=c
                    ),
                )
            except Exception as ex:
                self._root.after(0, lambda err=str(ex): self._append_feedback(err, is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_reset_distance(self) -> None:
        if not messagebox.askyesno("Reset Distance", "Reset cumulative distance now?"):
            return

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post("/api/config/pen-distance", {"resetCumulative": True})
                self._root.after(0, lambda: self._append_feedback("Distance reset completed.", is_error=False))
                self._root.after(0, self._refresh_status_now)
            except HTTPError as ex:
                code, msg = self._decode_http_error(ex)
                self._root.after(
                    0,
                    lambda c=code, m=msg, sc=ex.code: self._append_feedback(
                        m or f"HTTP {sc}", is_error=True, error_code=c
                    ),
                )
            except Exception as ex:
                self._root.after(0, lambda err=str(ex): self._append_feedback(err, is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_status(self) -> None:
        try:
            self._refresh_status_now()
        finally:
            self._root.after(self._status_poll_ms, self._refresh_status)

    def run(self) -> None:
        self._append_feedback("Pen kiosk started.")
        self._start_kiosk_guard()
        self._refresh_status()
        self._root.mainloop()


def main() -> None:
    app = PenKioskApp()
    app.run()


if __name__ == "__main__":
    main()
