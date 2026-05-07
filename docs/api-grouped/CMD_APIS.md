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
- Full printer status model (connection flags, distance metrics, bulk fields, pen fields).

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
- **200**: job ran immediately — `queued: false`, `jobId`, `svgFileName`, `commandCount`, `result`, `status`.
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
- **200** or **202** (same shape as single print); bulk payload includes `copies`, `bulkProgress`, `result` with `copies` / `total_commands_sent`.

### Error codes
- `PRINTER_STATE_ERROR` (409)
- `SVG_REQUIRED` (400)
- `EMPTY_SVG` (400)
- `PRINT_VALIDATION_ERROR` (400)
- `PRINT_RUNTIME_ERROR` (400)
- `BULK_PRINT_FAILED` (500)

## `POST /api/cmd/bulk/stop`

### Description
Requests cooperative stop for an active bulk print. Clears any stored uploaded SVG on the server so the next job must upload again.

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
When the printer is **idle**, runs the void/eject-safe printer sequence without drawing. When the printer is **busy** (active print or bulk job), requests the same in-job **cancel** as `POST /api/cmd/bulk/stop`: the firmware path stops between G-code lines, runs the normal eject in the print cycle `finally`, and the next job can start. Does **not** start a second serial “void” cycle on top of an in-flight job.

**Note:** Pen-change operations also mark the printer busy; cancel is requested but those command paths may not honor the stop flag until supported.

### How to use
Use after rejection or maintenance when idle; use as an emergency **stop** while printing (terminator) without losing the ability to print again.

### What it takes
- No body required.
- Requires header: `X-API-Key`.

### Response
- Idle: **`data`** is an empty object `{}` — use **`message`** for the outcome text; use `GET /api/cmd/status` for state.
- Busy: same shape as bulk stop — `data.status` with updated `PrinterStatus` (cancel requested; job finishes asynchronously on the worker).

### Error codes
- `VOID_RUNTIME_ERROR` (409)
- `PRINTER_NOT_BUSY` (409) — if busy flag was inconsistent (rare race).
- `VOID_FAILED` (500)
