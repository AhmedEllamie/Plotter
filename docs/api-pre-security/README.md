# Flask API Docs (Pre-Security)

These files describe historical **short** paths (e.g. `/api/health`). The live Flask app groups them as **`/api/cmd/*`** (commands) and **`/api/config/*`** (configuration, scanner, capture). See `API_REFERENCE.md` for full paths and **optional** `PLOTTER_API_KEY` behavior.

## Endpoints
- [GET /api/health](GET_api_health.md) → `GET /api/cmd/health`
- [GET /api/config](GET_api_config.md) → `GET /api/config`
- [GET /api/scanner/stream.mjpg](GET_api_scanner_stream_mjpg.md) → `GET /api/config/scanner/stream.mjpg`
- [POST /api/scanner/manual-config](POST_api_scanner_manual_config.md) → `POST /api/config/scanner/manual-config`
- [POST /api/scanner/capture/start](POST_api_scanner_capture_start.md) → `POST /api/config/scanner/capture/start`
- [POST /api/scanner/capture/run](POST_api_scanner_capture_run.md) → `POST /api/config/scanner/capture/run`
- [GET /api/scanner/capture/&lt;capture_id&gt;/status](GET_api_scanner_capture_status.md) → `GET /api/config/scanner/capture/{capture_id}/status`
- [GET /api/scanner/capture/&lt;capture_id&gt;/result](GET_api_scanner_capture_result.md) → `GET /api/config/scanner/capture/{capture_id}/result`
- [GET /api/scanner/capture/run/&lt;job_id&gt;](GET_api_scanner_capture_run_job_id.md) → `GET /api/config/scanner/capture/run/{job_id}`
- [GET /api/serial-ports](GET_api_serial_ports.md) → `GET /api/config/serial-ports`
- [GET /api/serial-port-check](GET_api_serial_port_check.md) → `GET /api/config/serial-port-check`
- [POST /api/config/auto-connect](POST_api_auto_connect.md)
- [POST /api/disconnect](POST_api_disconnect.md) → `POST /api/config/disconnect`
- [GET /api/status](GET_api_status.md) → `GET /api/cmd/status`
- [POST /api/print](POST_api_print.md) → `POST /api/cmd/print`
- [POST /api/print/bulk](POST_api_print_bulk.md) → `POST /api/cmd/print/bulk`
- [POST /api/print/bulk/stop](POST_api_print_bulk_stop.md) → `POST /api/cmd/bulk/stop`
- [POST /api/void](POST_api_void.md) → `POST /api/cmd/void`
- [POST /api/change-pen/start](POST_api_change_pen_start.md) → `POST /api/config/change-pen/start`
- [POST /api/change-pen/finish](POST_api_change_pen_finish.md) → `POST /api/config/change-pen/finish`
- [POST /api/change-pen](POST_api_change_pen.md) → `POST /api/config/change-pen`
- [POST /api/reset](POST_api_reset.md) → **removed**; use `POST /api/config/pen-distance` with `resetCumulative`
- [POST /api/pen-max-distance](POST_api_pen_max_distance.md) → **removed**; use `POST /api/config/pen-distance` with `meters`
- **Pen distance:** live app **`POST /api/config/pen-distance`** (see `API_REFERENCE.md`)
- [POST /api/scanner/capture-manual](POST_api_scanner_capture_manual.md) → `POST /api/config/scanner/capture-manual`
- ~~[POST /api/capture](POST_api_capture.md)~~ → **`POST /api/config/capture` removed** — use scanner oneshot; see `POST_api_capture.md` stub.
- [GET /api/capture/latest](GET_api_capture_latest.md) → `GET /api/config/capture/latest`
- [GET /api/capture/latest/image](GET_api_capture_latest_image.md) → `GET /api/config/capture/latest/image`

**Removed routes** (call scanner or automation directly instead where applicable):

- ~~`POST /api/config/upload`~~ — print jobs send SVG via multipart only.
- ~~`POST /api/config/scanner/focus-adjust`~~ — use scanner service `POST /session/focus-adjust` (see `FLASK_SCANNER_HTTP_INTEGRATION.md`).
- ~~`POST /api/config/capture/request`~~ — call `CAPTURE_RESET_URL` from deployment automation.
- ~~`GET /api/config/requests`~~ / ~~`GET /api/config/requests/{id}`~~ — removed.
