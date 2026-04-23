# Software Technical Documentation

## 1) Purpose and Scope

`Software` is a Python port of the Plotter signature printing workflow. It provides:

- A serial printer control layer for pen plotter-style hardware
- SVG-to-G-code conversion
- Approval-orchestrated print workflow
- Two HTTP APIs:
  - FastAPI (`/printer/...`) for service-level endpoints
  - Flask (`/api/...`) for kiosk/web UI and scanner/capture workflows
- A browser frontend and an optional fullscreen Tkinter pen kiosk app
- Ubuntu deployment assets (systemd services + environment templates)

This document describes runtime architecture, module responsibilities, endpoint behavior, configuration sources, deployment patterns, and operational troubleshooting.

---

## 2) High-Level Architecture

Main runtime components:

1. **Entry points**
   - CLI: `Software/main.py`
   - FastAPI app: `Software/api/app.py`
   - Flask app: `Software/flask_app/app.py`

2. **Dependency container**
   - `Software/dependency_injection.py` builds a singleton `ServiceProvider` containing:
     - `PrinterService`
     - `PrintApprovalService`
     - `MockApprovalService`
     - `RequestLogStore`
     - settings objects (`PrinterSettings`, `PrintRetrySettings`, `ApprovalServiceSettings`)

3. **Core domain/services**
   - Printer control and distance tracking: `services/printer/printer_service.py`
   - SVG conversion: `services/printer/svg_converter.py`
   - Approval orchestration: `services/print_approval/print_approval_service.py`
   - Approval provider (mock): `services/approval/mock_approval_service.py`
   - Request logs (in-memory): `stores/request_log_store.py`

4. **Models/contracts**
   - DTOs/enums/settings: `models/contracts.py`, `models/printer_settings.py`

5. **Flask runtime state + response helpers**
   - In-memory uploaded/captured asset state: `flask_app/state.py`
   - Standard API success/error envelope: `flask_app/response.py`
   - Environment loader for capture/scanner integration: `flask_app/config.py`

6. **Frontend and operator surfaces**
   - Browser UI: `flask_app/static/index.html`, `app.js`, `styles.css`
   - Configuration page: `flask_app/static/configuration.html`, `configuration.js`
   - Optional fullscreen pen control app: `flask_app/pen_kiosk_app.py`

---

## 3) Codebase Layout

- `Software/main.py`: CLI + server launch commands
- `Software/dependency_injection.py`: singleton service provider
- `Software/api/`: FastAPI app + printer router
- `Software/flask_app/`: Flask app + frontend + runtime state + config
- `Software/models/`: dataclasses/enums for requests/responses/logs/settings
- `Software/services/printer/`: serial protocol + G-code generation engine
- `Software/services/approval/`: approval service interface + mock implementation
- `Software/services/print_approval/`: print-with-approval orchestration
- `Software/stores/`: request log storage
- `Software/deploy/ubuntu/`: systemd + env templates
- `Software/distance_stats.json`: persisted cumulative distance and pen limit

---

## 4) Runtime Modes

### 4.1 CLI Mode

`python -m Software.main <command>`

Used for:
- manual printer operations (`connect`, `status`, `print`, `bulk-print`)
- G-code generation validation (`generate`)
- maintenance (`distance-stats`, `reset-distance`, `set-pen-max-distance`)
- approval pipeline test flow (`print-with-approval`, `get-request`)
- serving APIs (`serve-api`, `serve-flask`)

### 4.2 FastAPI Mode

`python -m Software.main serve-api --host 0.0.0.0 --port 5000`

- Root app in `api/app.py`
- Routes mounted under `/printer` from `api/printer_controller.py`
- Best suited for API-centric integration and parity with service contracts

### 4.3 Flask Mode

`python -m Software.main serve-flask --host 0.0.0.0 --port 5001`

- Root app in `flask_app/app.py`
- Serves:
  - `/` main web UI
  - `/configuration` config UI
  - `/api/*` rich operational endpoints for print/capture/scanner/status
- Includes extended integration behavior not present in the FastAPI surface

### 4.4 Tkinter Pen Kiosk Mode

`python -m Software.flask_app.pen_kiosk_app`

- Fullscreen desktop operator UI
- Uses Flask backend endpoints over HTTP (`/api/status`, `/api/change-pen/*`, `/api/reset`, `/api/pen-max-distance`)

---

## 5) Dependency Injection and Configuration Source

`build_service_provider()` in `dependency_injection.py`:

1. Attempts to load defaults from `appsettings.json` at the repo root (if present)
2. Builds settings:
   - `PrinterSettings(com_port, baud_rate)`
   - `PrintRetrySettings(max_retries, retry_delay_ms)`
   - `ApprovalServiceSettings(endpoint, api_key, timeout_seconds, use_mock_service)`
3. Constructs service graph:
   - `RequestLogStore`
   - `PrinterService`
   - `MockApprovalService` (currently fixed to mock scope)
   - `PrintApprovalService`
4. Exposes a process-wide singleton via `get_service_provider()`

Implication:
- CLI, FastAPI, and Flask all share the same in-process provider instance (per process).

---

## 6) Data Contracts and Domain Types

Defined in `models/contracts.py`.

### 6.1 Print and Paper

- `Paper` enum supports A/B/Letter/Legal/Tabloid/envelopes/cards/custom
- `get_paper_size_mm()` maps standard paper to width/height
- `PrintRequest`:
  - `paper`, `width`, `height`
  - `x_position`, `y_position`
  - `scale`, `rotation`
  - `invert_x`, `invert_y`

Behavior:
- If `paper` is specified, width/height are overwritten from known paper dimensions.
- Validation rules across the app:
  - `scale >= 1`
  - `0 <= rotation <= 360`

### 6.2 Printer Responses/Status

- `PrintResponse`: message, commands/copies totals, distance telemetry
- `PrinterStatus`:
  - connection + busy flags
  - bulk progress
  - current and cumulative distance
  - pen lifecycle metrics:
    - `max_pen_distance_m`
    - `used_pen_distance_m`
    - `remaining_pen_percent`

### 6.3 Approval and Logging

- `PrintApprovalRequest`: paper image + signature SVG + print settings + approval flag
- `PrintWithApprovalRequest`: print settings + shouldApprove
- `PrintWithApprovalResponse`: request_id, approved/printed flags, message, commands_sent
- `RequestStatus` lifecycle enum:
  - NEW, WAITING_FOR_APPROVAL, APPROVED, REJECTED, PRINTING, PRINTED, VOIDED, COMPLETED, FAILED
- `RequestLog`: event-style state entries with timestamps

---

## 7) Printer Service Internals

Implemented in `services/printer/printer_service.py`.

### 7.1 Serial Connection Behavior

- Uses `pyserial` if installed
- Open parameters:
  - parity none, 8-bit, 1 stop bit
  - timeout `0`, write timeout `2.0`
  - DTR/RTS enabled
  - startup wait `1.5s` before buffer reset

### 7.2 Print Lifecycle

For each print cycle:

1. Handshake command `M998R`
2. Wait until serial stream contains `"paper ready"` (60s timeout)
3. Init commands:
   - `G92 X9.0 Y-56.0 Z0`
   - `G21`
   - `G90`
   - `G1 E0.0 F4000`
4. Send generated G-code lines
5. Always run eject sequence in `finally` block:
   - `G1 E0.0 F4000`
   - `G0 X215.0 F6000.0`
   - `M106`
   - `G0 Y500.0 F6000.0`
   - `M400`
   - `M107`

### 7.3 Bulk Print

- `bulk_print(gcode, copies)` loops print cycles
- `copies` constrained to 1..100 in API/CLI layer
- stop request via `stop_bulk_print()` sets an event checked during execution
- returns partial completion if stopped

### 7.4 Void Print

- Same handshake/init/eject pattern
- No drawing commands executed
- Used when approval rejects a request

### 7.5 Pen Change Commands

- Start: `G90`, `G1 E7.5 F5000` (pen change position)
- Finish: `G90`, `G1 E0.0 F5000` (ready/up position)

### 7.6 Distance Tracking

The service calculates pen-down drawing distance by parsing G-code motion:
- Only `G0`/`G1` with X/Y deltas contribute
- Distance counted only when pen is down (`E > 0`)

Tracked metrics:
- current SVG distance
- current executed distance
- execution percent (`executed / planned`)
- cumulative distance (persisted)
- remaining pen percent based on configurable max pen distance

Persistence file:
- `Software/distance_stats.json`
  - `cumulativeDistanceMm`
  - `maxPenDistanceM`

---

## 8) SVG to G-code Conversion Engine

Implemented in `services/printer/svg_converter.py`.

### 8.1 Supported SVG Geometry

- `<path>` (with command parser)
- `<line>`, `<rect>`, `<circle>`, `<ellipse>`, `<polyline>`, `<polygon>`
- recursively traverses child nodes
- ignores content in `<defs>`

### 8.2 Path Command Coverage

Parses and flattens:
- Move/line: `M, L, H, V, Z`
- Cubic curves: `C, S`
- Quadratic curves: `Q, T`
- Arcs: `A`
- Relative and absolute forms supported

Bezier and arc flattening are approximated into polylines.

### 8.3 Coordinate Transform Pipeline

For each point:
1. Normalize by viewBox min offsets
2. Convert SVG units to mm scale factor
3. Apply `scale`
4. Apply `invert_x`/`invert_y`
5. Rotate around center by `rotation`
6. Apply `x_position`/`y_position` offsets

### 8.4 G-code Emission Pattern

Per polyline:
- move to first point with pen up (`G0`)
- pen down (`G1 E8.0 F4000`)
- draw remaining points (`G1 X.. Y.. F5000.0`)
- at path transitions, pen lifted as needed
- final pen up command appended

---

## 9) Approval Workflow

Orchestrated by `services/print_approval/print_approval_service.py`.

Flow:

1. Create request ID and NEW log
2. Read paper image bytes (if provided)
3. Log WAITING_FOR_APPROVAL
4. Call approval service (`request_approval_async`)
5. Resolve approval result:
   - reject path -> VOIDED -> execute `void_print()` -> COMPLETED
   - approve path -> convert SVG -> PRINTING -> retry print loop -> PRINTED -> COMPLETED
6. On any exception -> FAILED log and rethrow

Retry behavior:
- controlled by `PrintRetrySettings(max_retries, retry_delay_ms)`

Current implementation detail:
- approval provider is `MockApprovalService` and always approves after a simulated delay.
- `should_approve` input can still force rejection flow when set false.

---

## 10) Storage and State Model

### 10.1 RequestLogStore

`stores/request_log_store.py` is in-memory and thread-safe:
- grouped by `request_id`
- indexed by log `id`
- supports latest-by-request, full history, recent list

Not durable across process restart.

### 10.2 Flask RuntimeState

`flask_app/state.py` stores in-memory:
- latest uploaded SVG
- latest captured image

Used by Flask endpoints to allow multi-step workflow (`upload` then `print`, capture retrieval endpoints, etc.).

Not durable across process restart.

---

## 11) API Surfaces

## 11.1 FastAPI (`/printer`)

From `api/printer_controller.py`:

- `POST /printer/connect`
- `POST /printer/disconnect`
- `GET /printer/status`
- `POST /printer/generate`
- `POST /printer/print`
- `POST /printer/print/bulk`
- `POST /printer/print-with-approval`
- `GET /printer/requests/{request_id}`

FastAPI validation style:
- Raises HTTP 400/409/404 via `HTTPException`.

## 11.2 Flask (`/api`)

From `flask_app/app.py`:

Core printer:
- `POST /api/connect`
- `POST /api/disconnect`
- `GET /api/status`
- `POST /api/upload`
- `POST /api/print`
- `POST /api/print/bulk`
- `POST /api/print/bulk/stop`
- `POST /api/void`
- `POST /api/change-pen/start`
- `POST /api/change-pen/finish`
- `POST /api/change-pen` (mode = start|finish)
- `POST /api/reset`
- `POST /api/pen-max-distance`

Capture and scanner:
- `POST /api/capture/request` (trigger external capture reset URL)
- `POST /api/capture`
- `GET /api/capture/latest`
- `GET /api/capture/latest/image`
- `GET /api/scanner/stream.mjpg` (proxy stream)
- `POST /api/scanner/manual-config`
- `POST /api/scanner/focus-adjust`
- `POST /api/scanner/capture/start`
- `GET /api/scanner/capture/{capture_id}/status`
- `GET /api/scanner/capture/{capture_id}/result`
- `POST /api/scanner/capture-manual`

System/config:
- `GET /api/health`
- `GET /api/config`
- `GET /api/serial-ports`
- `GET /api/serial-port-check`
- `GET /api/requests/{request_id}`
- `GET /api/requests?count=10`

Flask response envelope:
- success: `{ success: true, message, data, errorCode: null }`
- error: `{ success: false, message, data: null, errorCode, details? }`

---

## 12) Scanner and Capture Integration

Configured in `flask_app/config.py` and consumed in `flask_app/app.py`.

### 12.1 Capture Reset Trigger

`POST /api/capture/request` sends HTTP request to external reset endpoint using:
- `CAPTURE_RESET_URL` (required for this feature)
- `CAPTURE_RESET_TOKEN` (optional bearer token)
- `CAPTURE_RESET_TIMEOUT_SECONDS`
- `CAPTURE_RESET_METHOD` (GET/POST/etc)

### 12.2 Scanner Service HTTP Calls

Flask app can proxy/control an external scanner service:
- base URL and auth token from env
- focus mode + quad points config
- manual capture polling loop with timeout attempts
- result retrieval and local runtime storage

Note:
- The code currently reads scanner token from `SCANNER_SERVICE_TOKEN`.
- The sample env template uses `SCANNER_SERVICE_BEARER_TOKEN`.
- Align these names in deployment to avoid silent auth misconfiguration.

---

## 13) Frontend and Operator UX

### 13.1 Browser UI

Served by Flask static files:
- Main dashboard (`/`)
- Configuration page (`/configuration`)

Capabilities include:
- printer connect/disconnect/status
- SVG upload + print
- bulk print and stop
- void print
- pen change commands
- serial port scan/check
- capture/scanner workflow actions

### 13.2 Pen Kiosk Desktop App

`flask_app/pen_kiosk_app.py`:
- fullscreen Tkinter app
- polls `/api/status` every 3s
- actions:
  - PenDown / PenUp
  - set max pen distance
  - reset cumulative distance
- intended for kiosk sessions and operator-only maintenance station

---

## 14) CLI Reference

Primary commands in `main.py`:

- `connect`, `disconnect`, `status`
- `generate --svg --print-request-json`
- `print --svg --print-request-json [--auto-connect]`
- `bulk-print --svg --print-request-json --copies [--auto-connect]`
- `void` is API-only (no direct CLI command currently)
- `pen-change-start`, `pen-change-finish`
- `print-with-approval --signature-svg --request-json [paper image input]`
- `get-request --request-id`
- `distance-stats`, `reset-distance`, `set-pen-max-distance --meters`
- `serve-api`, `serve-flask`

`--print-request-json` accepts either:
- inline JSON string
- path to a JSON file

---

## 15) Deployment (Ubuntu / systemd)

Assets:

- `deploy/ubuntu/plotter-signature-flask.service`
- `deploy/ubuntu/plotter-signature.env.example`
- `deploy/ubuntu/plotter-pen-kiosk.service`
- `deploy/ubuntu/plotter-pen-kiosk.desktop`
- `UBUNTU_RELEASE_GUIDE.md` for release process

### 15.1 Flask Service

Runs:
- `/opt/plotter-signature/.venv/bin/python -m Software.main serve-flask --host 0.0.0.0 --port 5001`

Uses env file:
- `/etc/plotter-signature/plotter-signature.env`

### 15.2 Kiosk Service

Runs:
- `/opt/plotter-signature/.venv/bin/python -m Software.flask_app.pen_kiosk_app`

Intended for graphical user session; separate from Flask backend service.

---

## 16) Environment Variables

### 16.1 Capture

- `PLOTTER_API_KEY` (required shared inbound auth secret)
- `CAPTURE_RESET_URL`
- `CAPTURE_RESET_TOKEN`
- `CAPTURE_RESET_TIMEOUT_SECONDS` (float)
- `CAPTURE_RESET_METHOD`

### 16.2 Scanner

- `SCANNER_SERVICE_BASE_URL` (default `http://127.0.0.1:8008`)
- `SCANNER_SERVICE_TOKEN` (used by runtime code)
- `SCANNER_SERVICE_TIMEOUT_SECONDS`
- `SCANNER_JOB_POLL_INTERVAL_SECONDS`
- `SCANNER_JOB_POLL_MAX_ATTEMPTS`

### 16.3 Service-level default settings from appsettings.json (optional)

When `appsettings.json` exists at the repo root, these sections are read:
- `Printer` (`ComPort`, `BaudRate`)
- `PrintRetry` (`MaxRetries`, `RetryDelayMs`)
- `ApprovalService` (`Endpoint`, `ApiKey`, `TimeoutSeconds`, `UseMockService`)

---

## 17) Error Handling and Reliability

Design characteristics:

- Print cycles use `finally` to execute paper ejection
- Bulk stop is cooperative using a stop event
- Request logs capture lifecycle states and failures
- API layers normalize errors into readable responses
- `wait_for_ok` timeout does not hard-fail by design (C# parity behavior)

Operational implications:

- A command ACK timeout may still allow workflow continuation
- In-memory state (request logs, uploaded SVG, captured image) is lost on restart
- Printer disconnection during active print raises runtime exceptions

---

## 18) Security and Operational Notes

- Inbound API key authentication is required for:
  - Flask: all `/api/*` endpoints
  - FastAPI: all `/printer/*` endpoints
- Clients must send header `X-API-Key` with the same secret configured in `PLOTTER_API_KEY`.
- Scanner and capture integrations continue to support outbound bearer tokens.
- Production deployment should be protected at network/proxy layer.
- Services may run as root in provided templates; prefer least-privilege user where possible.
- On Linux, serial access generally requires membership in `dialout`.

---

## 19) Known Gaps and Current Port Scope

Current intentional scope:

- Approval service is mock-backed
- Request log persistence is in-memory only (no database)
- No formal test suite is currently included in this module

Integration caveat:

- Env key mismatch exists between code (`SCANNER_SERVICE_TOKEN`) and sample env (`SCANNER_SERVICE_BEARER_TOKEN`).

---

## 20) Troubleshooting Guide

### Printer will not connect

- Verify serial device exists:
  - Windows: `COMx`
  - Linux: `/dev/ttyUSB*` or `/dev/ttyACM*`
- Confirm process has serial permissions
- Confirm port is not locked by another process
- Check `pyserial` installed in active venv

### Print fails with “No drawable paths found”

- SVG may contain text objects not converted to paths
- Re-export SVG with outlines/paths
- Validate SVG content is non-empty

### Bulk print stops unexpectedly

- Check if `/api/print/bulk/stop` was triggered
- Inspect service logs for runtime exceptions mid-cycle

### Capture/scanner endpoints fail

- Verify scanner service URL/token env values
- Confirm scanner service endpoints exist and version matches expected routes
- Validate timeout values are sufficient for environment

### Pen remaining percent always 0

- Set max pen distance with:
  - API: `POST /api/pen-max-distance`
  - CLI: `set-pen-max-distance --meters <value>`

---

## 21) Recommended Next Documentation Actions

To keep this file aligned with code changes:

1. Add this file to release checklist updates
2. Add endpoint contract examples (request/response payload samples)
3. Add sequence diagrams for:
   - print cycle
   - approval workflow
   - scanner manual capture workflow
4. Add a dedicated “production hardening” section if deployed outside trusted LAN

