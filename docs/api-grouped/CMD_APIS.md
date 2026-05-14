# CMD APIs (`/api/cmd/*`)

The `cmd` group contains execution/action endpoints only.

Common success envelope:
- `success: true`
- `message: string`
- `data: object`
- `errorCode: null`

Common error envelope:
- `success: false`
- `message: string`
- `data: null`
- `errorCode: string`
- `details: object` (optional)

## `GET /api/cmd/health`

### Description
Returns a quick service health snapshot.

### How to use
Call when you need liveness/readiness information for UI boot or monitoring.

### What it takes
- No body.
- Requires header: `X-API-Key`.

### Response
- `printerConnected`
- `printerBusy`
- `captureResetConfigured`

### Error codes
- No endpoint-specific runtime error code (auth middleware errors still apply).

## `GET /api/cmd/status`

### Description
Returns current printer runtime status.

### How to use
Poll from UI/kiosk to render connection, busy state, distance, and bulk state.

### What it takes
- No body.
- Requires header: `X-API-Key`.

### Response
- Printer runtime status (same fields as internal `PrinterStatus` **except** serial port name is not exposed), plus **`printer_connected`** (`boolean`): `true` when the **server** process has the plotter serial port open.

### Error codes
- No endpoint-specific runtime error code (auth middleware errors still apply).

## `POST /api/cmd/print`

### Description
Prints one job. Requires a fresh multipart SVG on every request; the server clears stored SVG after each job. If the printer is already printing (or other jobs are waiting), the job is accepted into an in-memory FIFO queue.

### How to use
1. Send multipart form with `svg` (file) and `printRequestJson` (stringified JSON with optional nested `printRequest`).
2. `POST /api/config/upload` remains optional (e.g. for preview); print does **not** use previously uploaded SVG alone.

### What it takes
- Multipart: **`svg`** file part (required).
- Multipart or JSON: print settings via `printRequestJson` or JSON body with `printRequest`.
- Requires header: `X-API-Key`.

### Response
- **200**: job ran immediately — `queued: false`, `jobId`, `svgFileName`, `commandCount`, slim **`result`** (`commands_sent`, `cumulative_distance_mm`, `executed_distance_mm`, `execution_percent`, `job_stopped`).
- **202**: printer busy — `queued: true`, `jobId`, `queuePosition`, `jobType`, `signatureSha256`, `svgFileName`.

### Error codes
- `PRINTER_STATE_ERROR` (409) — not connected
- `SVG_REQUIRED` (400) — missing `svg` file part
- `EMPTY_SVG` (400)
- `PRINT_VALIDATION_ERROR` (400)
- `PRINT_RUNTIME_ERROR` (400)
- `PRINT_FAILED` (500)

## `POST /api/cmd/print/bulk`

### Description
Runs multi-copy printing in **one** server job using one SVG file. Same queue rules as single print: multipart `svg` is required; **202** if printer is busy. After completion or stop, stored SVG is cleared.

### How to use
Send multipart form: `svg`, `copies` (1–100), and `printRequestJson` (optional nested `printRequest`).

### What it takes
- Multipart **`svg`** (required), `copies`, print settings.
- Requires header: `X-API-Key`.

### Response
- **200** or **202** (same queue shape as single print). On **200**, bulk adds **`bulkProgress`**; **`result`** is slim (`cumulative_distance_mm`, `execution_percent`, `total_commands_sent`). No top-level **`copies`** on 200 (see `bulkProgress.requestedTotal`).

### Error codes
- `PRINTER_STATE_ERROR` (409)
- `SVG_REQUIRED` (400)
- `EMPTY_SVG` (400)
- `PRINT_VALIDATION_ERROR` (400)
- `PRINT_RUNTIME_ERROR` (400)
- `BULK_PRINT_FAILED` (500)

## `POST /api/cmd/bulk/stop`

### Description
Requests **graceful** stop for an active **bulk** print: the **current copy** finishes (full eject), then no further copies are started. Clears any stored uploaded SVG on the server so the next job must upload again. **`POST /api/cmd/void` while printing does not cancel mid-copy**; it queues a void after the job completes.

### How to use
Call from UI stop button while bulk operation is running.

### What it takes
- No body required.
- Requires header: `X-API-Key`.

### Response
- `status` (updated printer status)

### Error codes
- `PRINTER_STATE_ERROR` (409)
- `PRINTER_NOT_BUSY` (409)
- `BULK_STOP_FAILED` (500)

## `POST /api/cmd/void`

### Description
When the printer is **idle**, runs the void/eject-safe printer sequence without drawing. When a **print or bulk job** is active (`is_printing`), **queues** a single void: the current job runs to completion (including its normal eject), then the server runs **`void_print()`** once. Poll `GET /api/cmd/status` for `void_after_print_pending`. This avoids aborting during “paper ready” / before init (bad eject geometry). **`POST /api/cmd/bulk/stop`** remains the way to stop a bulk run gracefully between copies.

**Note:** Pen-change operations mark the printer busy but are not `is_printing`; void while pen-change still uses the idle void path or may conflict — prefer finishing pen change first.

### How to use
Use after rejection or maintenance when idle. While printing, void schedules an extra void cycle **after** the job instead of an immediate cancel.

### What it takes
- No body required.
- Requires header: `X-API-Key`.

### Response
- Idle: **`data`** is `{}` — use **`message`** for the outcome text; use `GET /api/cmd/status` for state.
- While printing: **`data`** is `{ "voidQueued": true, "voidAfterPrintPending": true }` — void runs automatically when the job ends.

### Error codes
- `VOID_BUSY` (409) — void already running
- `VOID_RUNTIME_ERROR` (409)
- `VOID_FAILED` (500)
