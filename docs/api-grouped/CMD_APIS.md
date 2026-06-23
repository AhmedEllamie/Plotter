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
- `data: object | null` (failed job polls may include slim job in `data`)
- `errorCode: integer`
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

## `GET /api/cmd/jobs/queue`

### Description
Returns the server-wide FIFO command queue snapshot.

### Response
- `active`: running job or `null`
- `pending`: array of pending jobs in order
- Each job: `jobId`, `jobType`, `status` (`pending` | `running`), `queuePosition` when pending, `svgFileName`

## `GET /api/cmd/jobs/{job_id}`

### Description
Poll async command job status (print, bulk, void, bulk_stop).

### Response
- `jobId`, `jobType`, `status` (`pending` | `running` | `completed` | `failed` | `stopped`)
- `queuePosition` when pending
- `svgFileName` when applicable
- `result` when `status` is `completed` or `stopped`
- On `status: failed`: HTTP `200`, `success: false`, errors in top-level `message` / `errorCode` (not in `data`)

### Error codes
- `CMD_JOB_NOT_FOUND` (404)

## `POST /api/cmd/print`

### Description
Accepts a print job into the unified async command queue. Does **not** block until G-code completes.

### How to use
1. Ensure system profile has `initialized: true` (Send scanner config on `/configuration`).
2. Send multipart form with **`svg`** file only. Print settings are read from `ui-profile.json`.
3. Poll `GET /api/cmd/jobs/{jobId}` until `status` is `completed`, `failed`, or `stopped`.

### What it takes
- Multipart: **`svg`** file part (required).
- Print settings: server profile only — do **not** send `printRequestJson` or print form fields.
- Requires header: `X-API-Key`.

### Response
- **200**: `jobId`, `jobType`, `status` (`pending`), `queuePosition`

### Error codes
- `CONFIG_NOT_INITIALIZED` (409) — profile not initialized
- `PRINT_SETTINGS_NOT_ALLOWED` (400) — print fields in request
- `PRINTER_STATE_ERROR` (409) — not connected
- `SVG_REQUIRED` (400) — missing `svg` file part
- `EMPTY_SVG` (400)
- `PRINT_VALIDATION_ERROR` (400)

## `POST /api/cmd/print/bulk`

### Description
Accepts a multi-copy bulk job into the async queue. Same accept contract as single print.

### How to use
Send multipart form: `svg`, `copies` (1–100). Poll job status until terminal (`completed`, `failed`, or `stopped`). Use `GET /api/cmd/status` for live bulk counts while running.

### What it takes
- Multipart **`svg`** (required), `copies`.
- Requires header: `X-API-Key`.

### Response
- **200**: `jobId`, `jobType` (`bulk`), `status`, `queuePosition`

### Error codes
- Same validation/connection errors as single print

## `POST /api/cmd/bulk/stop`

### Description
Requests graceful bulk stop. Effect is applied **immediately at accept** (not when the bulk_stop job reaches the front of the FIFO queue).

### How to use
Call while bulk is running or when a bulk job is pending. Poll the bulk print `jobId` for G-code completion; poll the bulk_stop `jobId` for acceptance record.

### What it takes
- Optional JSON body: `{ "targetJobId": "<bulk-job-uuid>" }`.
- Omit `targetJobId` → stop first bulk (running bulk first, else first pending bulk).
- Requires header: `X-API-Key`.

### Behavior
- **Running bulk:** graceful stop after current copy (e.g. 5/10 → finish copy 5, skip 6–10).
- **Pending bulk:** cancelled immediately, removed from pending queue.
- **Single print running:** unaffected.
- **No bulk target:** HTTP 409 + `PRINTER_NOT_BUSY`.

### Response
- **200**: `jobId`, `jobType` (`bulk_stop`), `status`, `queuePosition`

### Error codes
- `PRINTER_STATE_ERROR` (409) — not connected
- `PRINTER_NOT_BUSY` (409) — no matching bulk at accept
- `PRINT_VALIDATION_ERROR` (400) — invalid `targetJobId`

## `POST /api/cmd/void`

### Description
Enqueues a void command in the same FIFO queue as print/bulk/stop. Does not block until void G-code completes.

### How to use
Submit void; poll `GET /api/cmd/jobs/{jobId}` or `GET /api/cmd/jobs/queue`.

### What it takes
- No body required.
- Requires header: `X-API-Key`.

### Response
- **200**: `jobId`, `jobType` (`void`), `status`, `queuePosition`

### Error codes
- `VOID_RUNTIME_ERROR` (409) — not connected
