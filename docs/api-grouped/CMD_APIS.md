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
Prints one job using uploaded SVG or the last stored SVG.

### How to use
1. Optionally upload SVG first via `/api/config/upload`.
2. Send print request settings.

### What it takes
- JSON or form payload; supports nested `printRequest`.
- Optional multipart SVG file (`svg`) to print directly.
- Requires header: `X-API-Key`.

### Response
- `svgFileName`
- `commandCount`
- `result`
- `status`

### Error codes
- `PRINTER_STATE_ERROR` (409)
- `EMPTY_SVG` (400)
- `SVG_NOT_UPLOADED` (400)
- `PRINT_VALIDATION_ERROR` (400)
- `PRINT_RUNTIME_ERROR` (400)
- `PRINT_FAILED` (500)

## `POST /api/cmd/print/bulk`

### Description
Runs multi-copy printing.

### How to use
Send standard print request plus `copies` (1..100).

### What it takes
- Same print payload types as single print.
- `copies` required (JSON, form, or query).
- Requires header: `X-API-Key`.

### Response
- `svgFileName`
- `copies`
- `commandCount`
- `result`
- `bulkProgress` (`requestedTotal`, `printedCount`, `stopRequested`)
- `status`

### Error codes
- `PRINTER_STATE_ERROR` (409)
- `EMPTY_SVG` (400)
- `SVG_NOT_UPLOADED` (400)
- `PRINT_VALIDATION_ERROR` (400)
- `PRINT_RUNTIME_ERROR` (400)
- `BULK_PRINT_FAILED` (500)

## `POST /api/cmd/bulk/stop`

### Description
Requests cooperative stop for an active bulk print.

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
Runs void/eject-safe printer sequence without drawing.

### How to use
Use after rejection or maintenance operations.

### What it takes
- No body required.
- Requires header: `X-API-Key`.

### Response
- Void operation result object.

### Error codes
- `VOID_RUNTIME_ERROR` (409)
- `VOID_FAILED` (500)
