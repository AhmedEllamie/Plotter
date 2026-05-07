# Config APIs (`/api/config/*`)

The `config` group contains setup, scanner, capture, and operational configuration endpoints.

Common success envelope:
- `success: true`
- `message: string`
- `data: object|array`
- `errorCode: null`

Common error envelope:
- `success: false`
- `message: string`
- `data: null`
- `errorCode: string`
- `details: object` (optional)

## `GET /api/config`
### Description
Returns runtime config and integration flags.
### How to use
Load defaults/UI config at startup.
### What it takes
- No body, requires `X-API-Key`.
### Response
- Scanner/capture config flags.
### Error codes
- No endpoint-specific runtime error code.

## Serial (HTTP + Desktop / CLI)
### Description
Use **`GET /api/config/serial-ports`**, **`GET /api/config/serial-port-check`**, **`POST /api/config/auto-connect`**, and **`POST /api/config/disconnect`** from the config UI or automation, or use the Desktop App / CLI on the same machine:

```bash
python -m plotter_signature.cli scan-serial --device-match "CH340"
python -m plotter_signature.cli connect --device-match "CH340"
python -m plotter_signature.cli disconnect
```

`--device-match` is matched against `device`, `name`, `description`, `manufacturer`, and `hwid`.

## `POST /api/config/auto-connect`
### Description
Opens printer serial connection using **AutoConnect** (optional explicit `comPort`, else default + enumerated ports). Flask and FastAPI also run **the same resolver once at process startup** by default (**`AUTO_CONNECT_ON_STARTUP`** can be `0` / `false` / `no` / `off` to disable).
### How to use
Send optional `comPort` / `baudRate`, or `{}` for discovery.
### What it takes
- JSON body optional.
- Requires `X-API-Key` when `PLOTTER_API_KEY` is set on the server.
### Response
- Printer status model after connect.
### Error codes
- `ALREADY_CONNECTED` (409)
- `INVALID_BAUD_RATE` (400)
- `AUTO_CONNECT_FAILED` (400)
- `CONNECT_FAILED` (400)

## `POST /api/config/disconnect`
### Description
Closes printer connection if safe.
### How to use
Call from config UI disconnect action.
### What it takes
- No body, requires `X-API-Key`.
### Response
- Printer status model after disconnect.
### Error codes
- `NOT_CONNECTED` (409)
- `PRINTER_BUSY` (409)

## `POST /api/config/change-pen/start`
## `POST /api/config/change-pen/finish`
## `POST /api/config/change-pen`
### Description
Pen change control endpoints (`start`, `finish`, or mode-based dispatcher).
### How to use
- Use `/start` and `/finish` directly, or `/change-pen` with `mode`.
### What it takes
- `/change-pen` accepts body/form `mode=start|finish`.
- Requires `X-API-Key`.
### Response
- **`data`** is an empty object `{}` on success for `start` and `finish` — use **`message`** for the outcome; use `GET /api/cmd/status` for printer state.
### Error codes
- `PEN_CHANGE_STATE_ERROR` (409) (`start`/`finish`)
- `PEN_CHANGE_START_FAILED` (500)
- `PEN_CHANGE_FINISH_FAILED` (500)
- `INVALID_PEN_MODE` (400) (`/change-pen`)

## `POST /api/config/reset`
### Description
Resets distance stats and optional max pen distance update.
### How to use
Send optional `maxPenDistanceM`.
### What it takes
- JSON body optional.
- Requires `X-API-Key` when server auth is enabled.
### Response
- **`data`** with **`maxPenDistanceM`**; full distance fields: `GET /api/cmd/status`.
### Error codes
- `PRINTER_BUSY` (409)
- `RESET_VALIDATION_ERROR` (400)
- `RESET_FAILED` (500)

## `POST /api/config/pen-max-distance`
### Description
Sets max pen distance threshold in meters.
### How to use
Send `meters` (or `maxPenDistanceM`).
### What it takes
- JSON/form payload.
- Requires `X-API-Key`.
### Response
- `stats`.
### Error codes
- `PEN_MAX_DISTANCE_REQUIRED` (400)
- `PEN_MAX_DISTANCE_INVALID` (400)
- `PEN_MAX_DISTANCE_FAILED` (500)

## `GET /api/config/scanner/stream.mjpg`
### Description
Proxies scanner MJPEG stream.
### How to use
Set optional query (`fps`, `width`, `fisheye`) and bind image source.
### What it takes
- Query optional.
- Requires `X-API-Key`.
### Response
- Stream response (`multipart/x-mixed-replace`).
### Error codes
- `SCANNER_STREAM_HTTP_ERROR` (502)
- `SCANNER_STREAM_UNREACHABLE` (502)
- `SCANNER_STREAM_FAILED` (500)

## Scanner manual config
### Description
`POST /api/config/scanner/manual-config` applies scanner session config (focus mode + optional quad points). The same capture fields can be saved via `POST /api/config/ui-profile` under the `capture` section (`autofocus_enabled`, `manual_focus_value`, `quad_points`).
### How to use
Send autofocus/manual focus (and optional quad points) to **`POST /api/config/scanner/manual-config`**, or persist them in the UI profile.
### What it takes
- JSON payload required.
- Requires `X-API-Key`.
### Response
- Scanner config apply result.
### Error codes
- `SCANNER_CONFIG_REQUIRED` (400)
- `SCANNER_HTTP_ERROR` (502)
- `SCANNER_UNREACHABLE` (502)
- `SCANNER_CONFIG_FAILED` (500)

## `POST /api/config/scanner/capture/oneshot`
### Description
Primary one-call capture API used by the Capture button.
### How to use
Send one request to perform full scanner capture sequence and get final result metadata (same fields as `GET /api/config/capture/latest`, including optional inline image).
### What it takes
- JSON payload required by manual capture flow (quad points/config payload).
- Optional `includeDataUri` (boolean, default **true** for this route): when true, response includes `dataUri` (`data:{contentType};base64,...`) so clients can show the image without a follow-up `GET` to `.../capture/latest/image`.
- Requires `X-API-Key`.
### Response
- Final capture payload including:
  - `captureId`
  - `fileName`
  - `contentType`
  - `sizeBytes`
  - `capturedAt`
  - `imageUrl`
  - `includeDataUri` true: `dataUri` for direct use as an `<img src>`.
### Error codes
- `SCANNER_CONFIG_REQUIRED` (400)
- `SCANNER_HTTP_ERROR` (502)
- `SCANNER_UNREACHABLE` (502)
- `SCANNER_CAPTURE_FAILED` (500)

## `POST /api/config/scanner/capture-manual`
### Description
Same capture pipeline as oneshot; defaults `includeDataUri` to **false** unless the client sets `includeDataUri: true`. The key `includeDataUri` is never forwarded to the scanner service (API-only).
### How to use
Advanced clients that want metadata only (no base64 image) omit `includeDataUri` or set it to false.
### What it takes
- Same JSON body as oneshot (`quad_points`, focus fields, optional `includeDataUri`).
- Requires `X-API-Key`.
### Response
- Same shape as oneshot (`captureId`, `fileName`, `contentType`, `sizeBytes`, `capturedAt`, `imageUrl`, optional `dataUri`).
### Error codes
- Same as oneshot.

## `GET /api/config/print-history`

### Description
Lists persisted print/bulk job history from SQLite (default **last 30 days**). Each row includes timestamps, `job_type` (`print` / `bulk`), status, signature file name, SHA-256, copies requested/printed, and optional `result` snapshot.

### How to use
Dashboard or auditing; query `days` (default 30) and `limit` (default 500, max 2000).

### What it takes
- Query: `days`, `limit` (optional).
- Requires `X-API-Key`.

### Response
- `items[]`, `days`, `limit`

### Error codes
- `INVALID_QUERY` (400)
