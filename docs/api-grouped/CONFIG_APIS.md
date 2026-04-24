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
- `defaultComPort`, `defaultBaudRate`, scanner/capture config flags.
### Error codes
- No endpoint-specific runtime error code.

## `GET /api/config/serial-ports`
### Description
Lists valid serial ports for current OS.
### How to use
Populate connection dropdown.
### What it takes
- No body, requires `X-API-Key`.
### Response
- `ports[]` with `device`, `description`, `manufacturer`.
### Error codes
- `SERIAL_LIST_UNAVAILABLE` (503)
- `SERIAL_LIST_FAILED` (500)

## `GET /api/config/serial-port-check`
### Description
Validates one serial port path/device.
### How to use
Check selected port before connect.
### What it takes
- Query param `device`.
- Requires `X-API-Key`.
### Response
- `device`, `exists`, `readable`, `writable`, `resolvedTarget`.
### Error codes
- `SERIAL_DEVICE_REQUIRED` (400)
- `SERIAL_DEVICE_INVALID` (400)

## `POST /api/config/connect`
### Description
Opens printer serial connection.
### How to use
Send optional `comPort` and `baudRate` then connect.
### What it takes
- JSON body optional.
- Requires `X-API-Key`.
### Response
- Printer status model after connect.
### Error codes
- `ALREADY_CONNECTED` (409)
- `INVALID_BAUD_RATE` (400)
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

## `POST /api/config/upload`
### Description
Uploads/stores SVG for later print commands.
### How to use
Multipart upload with key `svg` (or `file`).
### What it takes
- Multipart file payload.
- Requires `X-API-Key`.
### Response
- `fileName`, `sizeBytes`, `uploadedAt`.
### Error codes
- `SVG_REQUIRED` (400)
- `EMPTY_SVG` (400)

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
- Pen action result object.
### Error codes
- `PEN_CHANGE_STATE_ERROR` (409) (`start`/`finish`)
- `PEN_CHANGE_START_FAILED` (500)
- `PEN_CHANGE_FINISH_FAILED` (500)
- `INVALID_PEN_MODE` (400) (`/change-pen`)

## `POST /api/config/reset`
### Description
Resets distance stats and optional max pen distance update.
### How to use
Send optional `maxPenDistanceM`, `clearUploadedSvg`.
### What it takes
- JSON body optional.
- Requires `X-API-Key`.
### Response
- `stats`, `clearedUploadedSvg`.
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

## `POST /api/config/scanner/manual-config`
### Description
Applies scanner session config (focus mode + optional quad points).
### How to use
Send autofocus/manual focus (and optional quad points).
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

## `POST /api/config/scanner/focus-adjust`
### Description
Sends incremental focus adjustment.
### How to use
Send direction/step payload.
### What it takes
- JSON payload required.
- Requires `X-API-Key`.
### Response
- Scanner focus adjust result.
### Error codes
- `SCANNER_CONFIG_REQUIRED` (400)
- `SCANNER_HTTP_ERROR` (502)
- `SCANNER_UNREACHABLE` (502)
- `SCANNER_CONFIG_FAILED` (500)

## `POST /api/config/scanner/capture/oneshot`
### Description
Primary one-call capture API used by the Capture button.
### How to use
Send one request to perform full scanner capture sequence and get final result metadata.
### What it takes
- JSON payload required by manual capture flow (quad points/config payload).
- Requires `X-API-Key`.
### Response
- Final capture payload including:
  - `captureId`
  - `fileName`
  - `contentType`
  - `capturedAt`
  - `imageUrl`
### Error codes
- `SCANNER_CONFIG_REQUIRED` (400)
- `SCANNER_HTTP_ERROR` (502)
- `SCANNER_UNREACHABLE` (502)
- `SCANNER_CAPTURE_FAILED` (500)

