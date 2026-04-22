from __future__ import annotations

import json
import threading
from tkinter import BOTH, LEFT, RIGHT, X, Button, Canvas, Entry, Frame, Label, StringVar, Tk, messagebox
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PenKioskApp:
    def __init__(self, api_base_url: str = "http://127.0.0.1:5001") -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._root = Tk()
        self._root.title("Diwan Pen Config Kiosk")
        self._root.configure(bg="#0f172a")
        self._root.attributes("-fullscreen", True)
        self._root.bind("<F11>", self._toggle_fullscreen)

        self._status_poll_ms = 3000
        self._api_busy = False

        self._connection_badge = StringVar(value="Disconnected")
        self._busy_badge = StringVar(value="Idle")
        self._port_value = StringVar(value="N/A")
        self._cumulative_distance_value = StringVar(value="0.000 m")
        self._executed_distance_value = StringVar(value="0.000 m")
        self._execution_percent_value = StringVar(value="0.00%")
        self._pen_remaining_value = StringVar(value="N/A")
        self._bulk_progress_value = StringVar(value="0 / 0")
        self._bulk_stop_value = StringVar(value="No")
        self._max_pen_distance_var = StringVar(value="")
        self._inline_error_var = StringVar(value="")
        self._showing_status_card = True

        self._connection_badge_label: Label | None = None
        self._busy_badge_label: Label | None = None
        self._feedback_box = None
        self._status_card: Frame | None = None
        self._change_pen_card: Frame | None = None
        self._mode_label_var = StringVar(value="Status")
        self._switch_canvas: Canvas | None = None
        self._switch_knob: int | None = None
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
            width=140,
            height=44,
            bg="#0f172a",
            highlightthickness=0,
            bd=0,
        )
        self._switch_canvas.pack(side=RIGHT, padx=(0, 10))
        self._switch_canvas.create_rectangle(4, 10, 136, 34, outline="#64748b", fill="#1e293b", width=2)
        self._switch_knob = self._switch_canvas.create_oval(8, 12, 56, 32, fill="#e2e8f0", outline="#cbd5e1")
        self._switch_canvas.create_text(30, 22, text="S", fill="#0f172a", font=("Segoe UI", 12, "bold"))
        self._switch_canvas.create_text(110, 22, text="P", fill="#cbd5e1", font=("Segoe UI", 12, "bold"))
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

        self._show_status_card()

    def _build_status_card(self, parent: Frame) -> None:
        Label(
            parent,
            text="Status",
            bg="#111827",
            fg="#f8fafc",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        badges_row = Frame(parent, bg="#111827")
        badges_row.pack(fill=X, pady=(0, 10))
        self._connection_badge_label = self._badge(badges_row, self._connection_badge, ok=True)
        self._connection_badge_label.pack(side=LEFT, padx=(0, 8))
        self._busy_badge_label = self._badge(badges_row, self._busy_badge, ok=True)
        self._busy_badge_label.pack(side=LEFT)

        self._metric_row(parent, "Port", self._port_value)
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
            command=lambda: self._run_action("PenDown command sent.", "/api/change-pen/start"),
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
            command=lambda: self._run_action("PenUp command sent.", "/api/change-pen/finish"),
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

    def _toggle_fullscreen(self, _event: object) -> None:
        current = bool(self._root.attributes("-fullscreen"))
        self._root.attributes("-fullscreen", not current)

    def _show_status_card(self) -> None:
        if self._change_pen_card is not None:
            self._change_pen_card.pack_forget()
        if self._status_card is not None:
            self._status_card.pack(fill=BOTH, expand=True)
        self._showing_status_card = True
        self._mode_label_var.set("Status")
        if self._switch_canvas is not None and self._switch_knob is not None:
            self._switch_canvas.coords(self._switch_knob, 8, 12, 56, 32)

    def _show_change_pen_card(self) -> None:
        if self._status_card is not None:
            self._status_card.pack_forget()
        if self._change_pen_card is not None:
            self._change_pen_card.pack(fill=BOTH, expand=True)
        self._showing_status_card = False
        self._mode_label_var.set("Change Pen")
        if self._switch_canvas is not None and self._switch_knob is not None:
            self._switch_canvas.coords(self._switch_knob, 84, 12, 132, 32)

    def _toggle_cards(self) -> None:
        if self._showing_status_card:
            self._show_change_pen_card()
            return
        self._show_status_card()

    def _toggle_cards_event(self, _event: object) -> None:
        self._toggle_cards()

    def _append_feedback(self, message: str, is_error: bool = False) -> None:
        _ = message
        _ = is_error

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
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=12) as response:
            body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body) if body else {}
            if not isinstance(parsed, dict) or parsed.get("success") is False:
                raise RuntimeError(str(parsed.get("message") or f"Request failed ({response.status})"))
            data = parsed.get("data")
            return data if isinstance(data, dict) else {}

    def _api_get(self, path: str) -> dict[str, object]:
        request = Request(url=f"{self._api_base_url}{path}", method="GET")
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
                self._root.after(0, lambda: self._append_feedback(success_message))
                self._root.after(0, self._refresh_status)
            except Exception as ex:
                self._root.after(0, lambda: self._append_feedback(str(ex), is_error=True))
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
                self._api_post("/api/pen-max-distance", {"meters": meters})
                self._root.after(0, lambda: self._append_feedback("Max pen distance updated."))
                self._root.after(0, self._refresh_status)
            except Exception as ex:
                self._root.after(0, lambda: self._append_feedback(str(ex), is_error=True))
            finally:
                self._api_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_reset_distance(self) -> None:
        if not messagebox.askyesno("Reset Distance", "Reset cumulative distance now?"):
            return

        def worker() -> None:
            self._api_busy = True
            try:
                self._api_post("/api/reset", {"clearUploadedSvg": False})
                self._root.after(0, lambda: self._append_feedback("Distance reset completed."))
                self._root.after(0, self._refresh_status)
            except Exception as ex:
                self._root.after(0, lambda: self._append_feedback(str(ex), is_error=True))
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
            status = self._api_get("/api/status")
            is_open = bool(status.get("is_open"))
            is_busy = bool(status.get("is_printing"))

            self._set_badge_color(self._connection_badge_label, "Connected" if is_open else "Disconnected", is_open)
            self._set_badge_color(self._busy_badge_label, "Busy" if is_busy else "Idle", not is_busy)
            self._port_value.set(str(status.get("port_name") or "N/A"))
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
            self._append_feedback(f"Status HTTP error: {ex.code}", is_error=True)
        except URLError as ex:
            self._append_feedback(f"Status network error: {ex.reason}", is_error=True)
        except Exception as ex:
            self._append_feedback(f"Status error: {ex}", is_error=True)
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
