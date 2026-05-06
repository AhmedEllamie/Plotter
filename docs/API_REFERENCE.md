# Plotter Signature — Flask API reference (detailed)

Full HTTP reference for `[plotter_signature/web/flask_app/app.py](../plotter-signature/plotter_signature/web/flask_app/app.py)`. Grouping matches `[plotter-signature/docs/api-grouped/](../plotter-signature/docs/api-grouped/README.md)`: **Command** (`/api/cmd/`*) and **Config** (`/api/config/`*). Each operation lists **parameters with data types**, `**data` shapes**, and **concrete request/response examples**.

---

## Example convention

Examples use:


| Placeholder | Value                                                             |
| ----------- | ----------------------------------------------------------------- |
| Base URL    | `http://127.0.0.1:5000`                                           |
| API key for examples | Configure the same key in browser **Configuration → API Key** only when `PLOTTER_API_KEY` is set on the server. |


All JSON success bodies wrap payloads in the [standard envelope](#global-envelope-auth-http-status) (`success`, `message`, `data`, `errorCode`, `details`). Field order in JSON may vary.

---

## Table of contents

- [Global: envelope, auth, HTTP status](#global-envelope-auth-http-status)
- [Static HTML](#static-html)
- [Group: Command APIs](#group-command-apis-apicmd)
- [Group: Config APIs](#group-config-apis-apiconfig)
  - [Config — Capture](#config--capture)
- [Shared schemas](#shared-schemas)
- [API index (endpoints in this document)](#api-index-endpoints-in-this-document)

---

## Global: envelope, auth, HTTP status

### Response envelope (all `/api/`* JSON responses)


| Field       | Type                    | Description                                               |
| ----------- | ----------------------- | --------------------------------------------------------- |
| `success`   | `boolean`               | `true` if the call succeeded.                             |
| `message`   | `string`                | Human-readable summary.                                   |
| `data`      | `object | array | null` | Payload; `null` on many errors.                           |
| `errorCode` | `string | null`         | Machine code on failure; `null` on success.               |
| `details`   | `object | null`         | Optional extra context (e.g. upstream HTTP body snippet). |


Source: `[response.py](../plotter-signature/plotter_signature/web/flask_app/response.py)`.

**Example error (auth failure):**

```http
GET /api/cmd/status HTTP/1.1
Host: 127.0.0.1:5000
```

```json
{
  "success": false,
  "message": "Invalid X-API-Key header.",
  "data": null,
  "errorCode": "UNAUTHORIZED",
  "details": null
}
```

HTTP status: `401`.

### Authentication (all `/api/*` routes)


| Location    | Name               | Type     | Required    | Description                                                                                                                                       |
| ----------- | ------------------ | -------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| HTTP header | `X-API-Key`        | `string` | When `PLOTTER_API_KEY` is set | Must match server key or request returns **401**. |
| Cookie      | `plotter_api_auth` | `string` | Alternative                     | Set after a successful request that sent `X-API-Key`; used for `<img>` / stream URLs that cannot send headers. |


When **`PLOTTER_API_KEY` is unset or empty** on the server, API key authentication is **disabled** and requests **do not** need `X-API-Key`.

When **`PLOTTER_API_KEY` is set**, **all** `/api/*` routes require a matching `X-API-Key` (missing or invalid → **401**).


If the cookie is already valid, the header may be omitted (**only when** server auth is enabled).


| `errorCode`           | HTTP | Meaning               |
| --------------------- | ---- | --------------------- |
| `UNAUTHORIZED`        | 401  | Missing or wrong key. |


### Changing the server API key

1. On the plotter host, set or update **`PLOTTER_API_KEY`** in the environment (or in the systemd override / `.env` file used at service start).
2. **Restart** the Flask (or FastAPI) process so the new value loads.
3. Update every client (**Configuration page saved API Key**, kiosk env / key file if used, integrations) so they send the same value in **`X-API-Key`**.
4. Omit `PLOTTER_API_KEY` entirely on the server if you want authentication **disabled** (open LAN installs only).


### Static HTML (no API key)


| Method | Path             | Response type                                    |
| ------ | ---------------- | ------------------------------------------------ |
| `GET`  | `/`              | `text/html` or JSON fallback if no static folder |
| `GET`  | `/configuration` | `text/html` or JSON fallback                     |


**Example — dashboard (no key):**

```bash
curl -sS "http://127.0.0.1:5000/"
```

Response: HTML document (or minimal JSON if static folder missing).

---

## Group: Command APIs (`/api/cmd/*`)

Common header: `**X-API-Key**`: `string`.

---

### `GET /api/cmd/health`


| Location | Name | Type | Required | Default | Description    |
| -------- | ---- | ---- | -------- | ------- | -------------- |
| —        | —    | —    | —        | —       | No parameters. |


**Success `data` object**


| Field                    | Type      | Description                                           |
| ------------------------ | --------- | ----------------------------------------------------- |
| `printerConnected`       | `boolean` | Serial port open.                                     |
| `printerBusy`            | `boolean` | `true` when the printer is busy (print, bulk, void, or pen change). |
| `captureResetConfigured` | `boolean` | `CAPTURE_RESET_URL` set (see `FlaskCaptureSettings`). |


**HTTP:** `200`

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" "http://127.0.0.1:5000/api/cmd/health"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Service is healthy.",
  "data": {
    "printerConnected": true,
    "printerBusy": false,
    "captureResetConfigured": true
  },
  "errorCode": null,
  "details": null
}
```

---

### `GET /api/cmd/status`


| Location | Name | Type | Required | Description    |
| -------- | ---- | ---- | -------- | -------------- |
| —        | —    | —    | —        | No parameters. |


**Success `data` object — public `PrinterStatus` (serial port name is not exposed on this route)**


| Field                           | Type      | Description                                               |
| ------------------------------- | --------- | --------------------------------------------------------- |
| `is_open`                       | `boolean` | `true` if serial port is open.                            |
| `is_busy`                       | `boolean` | `true` during print, bulk, void, or pen change.         |
| `is_printing`                   | `boolean` | `true` only during **print** or **bulk** jobs.          |
| `bulk_requested_total`          | `integer` | Bulk job: total copies requested (last bulk job context). |
| `bulk_printed_count`            | `integer` | Bulk job: copies completed.                               |
| `bulk_stop_requested`           | `boolean` | Cooperative cancel flag set.                              |
| `current_svg_total_distance_mm` | `number`  | Total path length (mm) for current SVG context.           |
| `current_executed_distance_mm`  | `number`  | Pen-down distance executed (mm) for current job.          |
| `current_execution_percent`     | `number`  | 0–100 progress for current execution.                     |
| `cumulative_distance_mm`        | `number`  | Lifetime pen distance (mm) persisted on disk.             |
| `max_pen_distance_m`            | `number`  | Configured max pen travel (meters).                       |
| `used_pen_distance_m`           | `number`  | `cumulative_distance_mm / 1000`.                          |
| `remaining_pen_percent`         | `number`  | Estimated remaining pen life (percent).                   |


**HTTP:** `200`

**Example request**

```bash
curl -sS -H "X-API-Key: YOUR_KEY" "http://127.0.0.1:5000/api/cmd/status"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Printer status loaded.",
  "data": {
    "is_open": true,
    "is_busy": false,
    "is_printing": false,
    "bulk_requested_total": 0,
    "bulk_printed_count": 0,
    "bulk_stop_requested": false,
    "current_svg_total_distance_mm": 0.0,
    "current_executed_distance_mm": 0.0,
    "current_execution_percent": 0.0,
    "cumulative_distance_mm": 12450.25,
    "max_pen_distance_m": 2.5,
    "used_pen_distance_m": 12.450,
    "remaining_pen_percent": 90.12
  },
  "errorCode": null,
  "details": null
}
```

---

### `POST /api/cmd/print`


| Location    | Name               | Type                             | Required | Default | Description                                                                                             |
| ----------- | ------------------ | -------------------------------- | -------- | ------- | ------------------------------------------------------------------------------------------------------- |
| Header      | `Content-Type`     | `string`                         | Yes      | —       | Must be `multipart/form-data`.                                                                          |
| Multipart   | `svg` or `file`    | `file` (bytes)                   | **Yes** one of | —       | SVG file for this request only. |
| Multipart   | `printRequestJson` | `string`                         | No       | —       | Stringified JSON; may contain nested `printRequest` with `[PrintRequest](#printrequest-fields)` fields. |
| Multipart   | (flat keys)        | `string` / `integer` / `boolean` | No       | —       | Any `[PrintRequest](#printrequest-fields)` keys as form fields (e.g. `scale`, `xPosition`).             |
| Body (JSON) | (entire body)      | `object`                         | No       | —       | Used only if JSON present: top-level keys or nested `printRequest` (see `_extract_print_payload`).      |


**Preconditions:** Printer connected; otherwise `409` `PRINTER_STATE_ERROR`.

**Success `data` (immediate completion, HTTP `200`)**


| Field          | Type      | Description                                                      |
| -------------- | --------- | ---------------------------------------------------------------- |
| `queued`       | `boolean` | `false`.                                                         |
| `jobId`        | `string`  | UUID string, print history row id.                               |
| `jobType`      | `string`  | `"print"`.                                                       |
| `svgFileName`  | `string`  | Original upload name.                                            |
| `commandCount` | `integer` | G-code line count.                                               |
| `result`       | `object`  | `[PrintResponse](#printresponse-as-json)`.                       |
| `status`       | `object`  | Same shape as `[GET /api/cmd/status](#get-apicmdstatus)` `data`. |


**Queued `data` (HTTP `202`)**


| Field             | Type      | Description                                        |
| ----------------- | --------- | -------------------------------------------------- |
| `queued`          | `boolean` | `true`.                                            |
| `jobId`           | `string`  | UUID string.                                       |
| `queuePosition`   | `integer` | Queue depth after enqueue (`queue.Queue.qsize()`). |
| `jobType`         | `string`  | `"print"`.                                         |
| `signatureSha256` | `string`  | Hex SHA-256 of SVG bytes.                          |
| `svgFileName`     | `string`  | Filename.                                          |


**Error `errorCode`**


| Code                     | HTTP | Description                                  |
| ------------------------ | ---- | -------------------------------------------- |
| `PRINTER_STATE_ERROR`    | 409  | Not connected.                               |
| `SVG_REQUIRED`           | 400  | Missing `svg` part.                          |
| `EMPTY_SVG`              | 400  | Zero-length file.                            |
| `PRINT_VALIDATION_ERROR` | 400  | Bad scale/rotation/copies or SVG conversion. |
| `PRINT_RUNTIME_ERROR`    | 400  | Runtime error in job.                        |
| `PRINT_FAILED`           | 500  | Unexpected failure.                          |


**Example request** (multipart + `printRequestJson`)

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/cmd/print" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -F "svg=@./signature.svg;type=image/svg+xml" \
  -F 'printRequestJson={"printRequest":{"paper":"A4","scale":1,"rotation":0,"invertY":true}}'
```

**Example response** `200` (job ran immediately)

```json
{
  "success": true,
  "message": "Print completed.",
  "data": {
    "svgFileName": "signature.svg",
    "commandCount": 842,
    "result": {
      "message": "Print complete.",
      "commands_sent": 840,
      "copies": 0,
      "total_commands_sent": 0,
      "svg_total_distance_mm": 156.32,
      "executed_distance_mm": 156.32,
      "execution_percent": 100.0,
      "cumulative_distance_mm": 12606.57,
      "job_stopped": false
    },
    "status": {
      "is_open": true,
      "port_name": "COM3",
      "is_printing": false,
      "bulk_requested_total": 0,
      "bulk_printed_count": 0,
      "bulk_stop_requested": false,
      "current_svg_total_distance_mm": 156.32,
      "current_executed_distance_mm": 156.32,
      "current_execution_percent": 100.0,
      "cumulative_distance_mm": 12606.57,
      "max_pen_distance_m": 2.5,
      "used_pen_distance_m": 12.607,
      "remaining_pen_percent": 89.85
    },
    "queued": false,
    "jobId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "jobType": "print"
  },
  "errorCode": null,
  "details": null
}
```

**Example response** `202` (printer busy, queued)

```json
{
  "success": true,
  "message": "Printer busy; print job queued.",
  "data": {
    "queued": true,
    "jobId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "queuePosition": 1,
    "jobType": "print",
    "signatureSha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "svgFileName": "signature.svg"
  },
  "errorCode": null,
  "details": null
}
```

**Example error** `409`

```json
{
  "success": false,
  "message": "Printer is not connected. Call POST /api/config/auto-connect first.",
  "data": null,
  "errorCode": "PRINTER_STATE_ERROR",
  "details": null
}
```

---

### `POST /api/cmd/print/bulk`

Same `**multipart/form-data**` and print parameters as single print, plus:


| Location         | Name     | Type      | Required | Constraints | Description              |
| ---------------- | -------- | --------- | -------- | ----------- | ------------------------ |
| Multipart / JSON | `copies` | `integer` | **Yes**  | `1`–`100`   | Number of sheets/copies. |


`copies` sources (first hit wins in code): JSON body `copies`, form `copies`, query `copies`.

**Success `data` (HTTP `200`, not queued):** Same pattern as single print, plus:


| Field          | Type      | Description                                            |
| -------------- | --------- | ------------------------------------------------------ |
| `copies`       | `integer` | Requested total copies (bulk).                         |
| `bulkProgress` | `object`  | `requestedTotal`, `printedCount`, `stopRequested`.     |
| `result`       | `object`  | `[PrintResponse](#printresponse-as-json)`.             |
| `status`       | `object`  | Full `PrinterStatus` (same fields as status endpoint). |


**Queued `data` (HTTP `202`):** Same shape as print queue response; `jobType` is `"bulk"`.

**Extra `errorCode`:** `BULK_PRINT_FAILED` (`500`).

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/cmd/print/bulk" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -F "svg=@./signature.svg;type=image/svg+xml" \
  -F "copies=5" \
  -F 'printRequestJson={"paper":"A4","scale":1}'
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Bulk print completed.",
  "data": {
    "svgFileName": "signature.svg",
    "copies": 5,
    "commandCount": 842,
    "result": {
      "message": "Bulk print complete.",
      "commands_sent": 4200,
      "copies": 5,
      "total_commands_sent": 4200,
      "svg_total_distance_mm": 781.6,
      "executed_distance_mm": 781.6,
      "execution_percent": 100.0,
      "cumulative_distance_mm": 13388.17,
      "job_stopped": false
    },
    "bulkProgress": {
      "requestedTotal": 5,
      "printedCount": 5,
      "stopRequested": false
    },
    "status": {
      "is_open": true,
      "port_name": "COM3",
      "is_printing": false,
      "bulk_requested_total": 5,
      "bulk_printed_count": 5,
      "bulk_stop_requested": false,
      "current_svg_total_distance_mm": 156.32,
      "current_executed_distance_mm": 156.32,
      "current_execution_percent": 100.0,
      "cumulative_distance_mm": 13388.17,
      "max_pen_distance_m": 2.5,
      "used_pen_distance_m": 13.388,
      "remaining_pen_percent": 89.22
    },
    "queued": false,
    "jobId": "550e8400-e29b-41d4-a716-446655440000",
    "jobType": "bulk"
  },
  "errorCode": null,
  "details": null
}
```

---

### `POST /api/cmd/bulk/stop`


| Location | Name | Type | Required | Description |
| -------- | ---- | ---- | -------- | ----------- |
| —        | —    | —    | —        | No body.    |


**Success `data`**


| Field    | Type     | Description                                                                       |
| -------- | -------- | --------------------------------------------------------------------------------- |
| `status` | `object` | Full `PrinterStatus` (same fields as `[GET /api/cmd/status](#get-apicmdstatus)`). |


Side effects: sets cooperative cancel, marks active history job `stopped`, clears uploaded SVG.

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/cmd/bulk/stop" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Bulk stop requested.",
  "data": {
    "status": {
      "is_open": true,
      "port_name": "COM3",
      "is_printing": true,
      "bulk_requested_total": 10,
      "bulk_printed_count": 3,
      "bulk_stop_requested": true,
      "current_svg_total_distance_mm": 156.32,
      "current_executed_distance_mm": 98.4,
      "current_execution_percent": 62.95,
      "cumulative_distance_mm": 13100.5,
      "max_pen_distance_m": 2.5,
      "used_pen_distance_m": 13.1,
      "remaining_pen_percent": 89.45
    }
  },
  "errorCode": null,
  "details": null
}
```

---

### `POST /api/cmd/void`


| Location | Name | Type | Required | Description |
| -------- | ---- | ---- | -------- | ----------- |
| —        | —    | —    | —        | No body.    |


**Idle printer — success `data`:** `[PrintResponse](#printresponse-as-json)` object.

**Busy printer — success `data`:** `{ "status": <PrinterStatus> }` (same as bulk stop).

**Example request (idle)**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/cmd/void" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Example response** `200` (idle — void cycle completed)

```json
{
  "success": true,
  "message": "Void print completed.",
  "data": {
    "message": "Void print complete - paper ejected without printing.",
    "commands_sent": 0,
    "copies": 0,
    "total_commands_sent": 0,
    "svg_total_distance_mm": 0.0,
    "executed_distance_mm": 0.0,
    "execution_percent": 0.0,
    "cumulative_distance_mm": 13100.5,
    "job_stopped": false
  },
  "errorCode": null,
  "details": null
}
```

**Example response** `200` (busy — cancel requested)

```json
{
  "success": true,
  "message": "Current print job stop requested. The printer will eject and return to idle.",
  "data": {
    "status": {
      "is_open": true,
      "port_name": "COM3",
      "is_printing": true,
      "bulk_requested_total": 0,
      "bulk_printed_count": 0,
      "bulk_stop_requested": true,
      "current_svg_total_distance_mm": 156.32,
      "current_executed_distance_mm": 45.2,
      "current_execution_percent": 28.9,
      "cumulative_distance_mm": 13100.5,
      "max_pen_distance_m": 2.5,
      "used_pen_distance_m": 13.1,
      "remaining_pen_percent": 89.45
    }
  },
  "errorCode": null,
  "details": null
}
```

---

## Group: Config APIs (`/api/config/*`)

Header: `**X-API-Key**`: `string` (unless cookie session valid).

---

### Config — Runtime config

#### `GET /api/config`

No parameters.

**Success `data`**


| Field                      | Type      | Description                           |
| -------------------------- | --------- | ------------------------------------- |
| `defaultComPort`           | `string`  | Default serial device name.           |
| `defaultBaudRate`          | `integer` | Default baud.                         |
| `captureResetConfigured`   | `boolean` | Reset URL configured.                 |
| `captureResetMethod`       | `string`  | e.g. `POST`, `GET` from env.          |
| `scannerServiceConfigured` | `boolean` | `SCANNER_SERVICE_BASE_URL` non-empty. |
| `scannerServiceBaseUrl`    | `string`  | Scanner base URL.                     |


**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" "http://127.0.0.1:5000/api/config"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Runtime config loaded.",
  "data": {
    "defaultComPort": "COM3",
    "defaultBaudRate": 115200,
    "captureResetConfigured": true,
    "captureResetMethod": "POST",
    "scannerServiceConfigured": true,
    "scannerServiceBaseUrl": "http://127.0.0.1:8008"
  },
  "errorCode": null,
  "details": null
}
```

---

### Config — Serial & connection

#### `GET /api/config/serial-ports`

**Example response** `200`

```json
{
  "success": true,
  "message": "Serial ports listed.",
  "data": {
    "ports": [
      {
        "device": "COM3",
        "description": "USB-SERIAL CH340",
        "manufacturer": "wch.cn"
      },
      {
        "device": "COM5",
        "description": "Silicon Labs CP210x",
        "manufacturer": "Silicon Laboratories"
      }
    ]
  },
  "errorCode": null,
  "details": null
}
```

---

#### `GET /api/config/serial-port-check`


| Location | Name     | Type     | Required | Description                    |
| -------- | -------- | -------- | -------- | ------------------------------ |
| Query    | `device` | `string` | **Yes**  | e.g. `COM3` or `/dev/ttyUSB0`. |


**Example request**

```bash
curl -sS -G -H "X-API-Key: QSCWDVEFBRGN" \
  --data-urlencode "device=COM3" \
  "http://127.0.0.1:5000/api/config/serial-port-check"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Serial device check complete.",
  "data": {
    "device": "COM3",
    "exists": true,
    "readable": true,
    "writable": true,
    "resolvedTarget": "\\\\.\\COM3"
  },
  "errorCode": null,
  "details": null
}
```

---

#### `POST /api/config/auto-connect`

Opens the printer serial link. **`comPort` / `com_port`** selects one device; **`{}`** runs **AutoConnect**: default COM from server settings, then filtered serial candidates.

**Errors:** `400` `AUTO_CONNECT_FAILED` (`details.attemptedPorts`), `409` `ALREADY_CONNECTED`.

**Startup:** Flask and FastAPI also run this resolver once when the process starts (**enabled by default**) unless **`AUTO_CONNECT_ON_STARTUP`** is `0`, `false`, `no`, or `off`; failures are logged and the server still listens.

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/auto-connect" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"comPort\":\"COM3\",\"baudRate\":115200}"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Connected to COM3.",
  "data": {
    "is_open": true,
    "port_name": "COM3",
    "is_busy": false,
    "is_printing": false,
    "bulk_requested_total": 0,
    "bulk_printed_count": 0,
    "bulk_stop_requested": false,
    "current_svg_total_distance_mm": 0.0,
    "current_executed_distance_mm": 0.0,
    "current_execution_percent": 0.0,
    "cumulative_distance_mm": 13100.5,
    "max_pen_distance_m": 2.5,
    "used_pen_distance_m": 13.1,
    "remaining_pen_percent": 89.45
  },
  "errorCode": null,
  "details": null
}
```

---

#### `POST /api/config/disconnect`

**Example response** `200`

```json
{
  "success": true,
  "message": "Disconnected from printer.",
  "data": {
    "is_open": false,
    "port_name": "N/A",
    "is_busy": false,
    "is_printing": false,
    "bulk_requested_total": 0,
    "bulk_printed_count": 0,
    "bulk_stop_requested": false,
    "current_svg_total_distance_mm": 0.0,
    "current_executed_distance_mm": 0.0,
    "current_execution_percent": 0.0,
    "cumulative_distance_mm": 13100.5,
    "max_pen_distance_m": 2.5,
    "used_pen_distance_m": 13.1,
    "remaining_pen_percent": 89.45
  },
  "errorCode": null,
  "details": null
}
```

---

### Config — Pen maintenance

#### `POST /api/config/change-pen/start`

**Example response** `200`

```json
{
  "success": true,
  "message": "Pen change start completed.",
  "data": {
    "message": "Pen change start complete. Replace pen, then run pen-change-finish.",
    "commands_sent": 2,
    "copies": 0,
    "total_commands_sent": 0,
    "svg_total_distance_mm": 0.0,
    "executed_distance_mm": 0.0,
    "execution_percent": 0.0,
    "cumulative_distance_mm": 13100.5,
    "job_stopped": false
  },
  "errorCode": null,
  "details": null
}
```

---

#### `POST /api/config/change-pen/finish`

No body. Same preconditions as **start** (printer connected, not busy).

**Success `data`:** `[PrintResponse](#printresponse-as-json)`.

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/change-pen/finish" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Pen change finish completed.",
  "data": {
    "message": "Pen change finish complete. Printer is ready to continue.",
    "commands_sent": 2,
    "copies": 0,
    "total_commands_sent": 0,
    "svg_total_distance_mm": 0.0,
    "executed_distance_mm": 0.0,
    "execution_percent": 0.0,
    "cumulative_distance_mm": 13100.5,
    "job_stopped": false
  },
  "errorCode": null,
  "details": null
}
```

---

#### `POST /api/config/change-pen`

**Example request** (`finish`)

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/change-pen" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"finish\"}"
```

---

#### `POST /api/config/reset`

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/reset" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"maxPenDistanceM\":3.0}"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Printer distance stats reset.",
  "data": {
    "stats": {
      "currentSvgTotalDistanceMm": 0.0,
      "currentExecutedDistanceMm": 0.0,
      "currentExecutionPercent": 0.0,
      "cumulativeDistanceMm": 0.0,
      "maxPenDistanceM": 3.0,
      "usedPenDistanceM": 0.0,
      "remainingPenPercent": 100.0
    }
  },
  "errorCode": null,
  "details": null
}
```

`stats` matches `PrinterService.get_distance_stats()` (camelCase keys, numeric values).

---

#### `POST /api/config/pen-max-distance`

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/pen-max-distance" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"meters\":2.75}"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Max pen distance updated.",
  "data": {
    "stats": {
      "currentSvgTotalDistanceMm": 0.0,
      "currentExecutedDistanceMm": 0.0,
      "currentExecutionPercent": 0.0,
      "cumulativeDistanceMm": 0.0,
      "maxPenDistanceM": 2.75,
      "usedPenDistanceM": 0.0,
      "remainingPenPercent": 100.0
    }
  },
  "errorCode": null,
  "details": null
}
```

---

### Config — Scanner proxy

#### `GET /api/config/scanner/stream.mjpg`

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/scanner/stream.mjpg?fps=10&width=640&fisheye=1" \
  --output stream.bin
```

**Example response** `200`  
Body: `multipart/x-mixed-replace` MJPEG stream (binary, not JSON).  
Errors return JSON envelope with `SCANNER_STREAM_`*.

---

#### `POST /api/config/scanner/manual-config`

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/scanner/manual-config" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"autofocus_enabled\":false,\"manual_focus_value\":35,\"quad_points\":[[100,90],[600,90],[600,400],[100,400]]}"
```

**Example response** `200` (shape depends on upstream; illustrative)

```json
{
  "success": true,
  "message": "Scanner manual config applied.",
  "data": {
    "ok": true,
    "manual_config": {
      "autofocus_enabled": false,
      "manual_focus_value": 35,
      "quad_points": [[100, 90], [600, 90], [600, 400], [100, 400]],
      "frame_width": 1280,
      "frame_height": 720,
      "valid": true,
      "validation_message": "ok",
      "updated_at": "2026-04-28T14:35:00+00:00"
    }
  },
  "errorCode": null,
  "details": null
}
```

---

### Config — Capture

Single-step scanner rectification; applies manual session settings, runs the scanner capture pipeline server-side, and stores the rectified PNG as the latest dashboard image. The server may still expose other capture-related URLs for the built-in web UI; this section documents only the oneshot call.

#### `POST /api/config/scanner/capture/oneshot`

Non-empty JSON body. Scanner-session keys match `[POST /api/config/scanner/manual-config](#post-apiconfigscannermanual-config)`; `includeDataUri` is API-only and is stripped before the payload is forwarded to the scanner.


| Location | Name                 | Type                                | Required | Default | Description                                                        |
| -------- | -------------------- | ----------------------------------- | -------- | ------- | ------------------------------------------------------------------ |
| Body     | `quad_points`        | `[[number,number],...]` (4 corners) | **Yes**  | —       | Perspective quad in frame pixel coordinates.                       |
| Body     | `autofocus_enabled`  | `boolean`                           | No       | `false` | When true, scanner runs autofocus before capture.                  |
| Body     | `manual_focus_value` | `number`                            | No       | `35`    | Manual focus index when autofocus is off.                          |
| Body     | `includeDataUri`     | `boolean`                           | No       | `true`  | When true, response includes a `data:image/png;base64,...` string. |


**Success `data`**


| Field         | Type      | Description                                                                                                                            |
| ------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `captureId`   | `string`  | Scanner job / capture id.                                                                                                              |
| `fileName`    | `string`  | Stored file name (e.g. `rectified-{id}.png`).                                                                                          |
| `contentType` | `string`  | MIME type of the stored image.                                                                                                         |
| `sizeBytes`   | `integer` | Decoded image size.                                                                                                                    |
| `capturedAt`  | `string`  | ISO-8601 timestamp (UTC).                                                                                                              |
| `imageUrl`    | `string`  | Path for the same stored bytes returned when `includeDataUri` is true (suitable for `<img src="…">` when the cookie session is valid). |
| `dataUri`     | `string`  | Present only when `includeDataUri` is true.                                                                                            |


Common scanner failures use `SCANNER_CAPTURE_FAILED`, `SCANNER_HTTP_ERROR`, `SCANNER_UNREACHABLE`, or `SCANNER_CONFIG_REQUIRED` (`400` when the body is missing or not a JSON object).

**Example request**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/scanner/capture/oneshot" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"autofocus_enabled\":false,\"manual_focus_value\":35,\"quad_points\":[[100,90],[600,90],[600,400],[100,400]],\"includeDataUri\":true}"
```

**Example response** `200` (`dataUri` truncated)

```json
{
  "success": true,
  "message": "Manual scanner capture completed.",
  "data": {
    "captureId": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "fileName": "rectified-c3d4e5f6-a7b8-9012-cdef-123456789012.png",
    "contentType": "image/png",
    "sizeBytes": 582934,
    "capturedAt": "2026-04-28T14:42:00.000000+00:00",
    "imageUrl": "/api/config/capture/latest/image",
    "dataUri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...(truncated)"
  },
  "errorCode": null,
  "details": null
}
```

---

### Config — Print history & approval logs

#### `GET /api/config/print-history`

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/print-history?days=7&limit=50"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Print history loaded.",
  "data": {
    "items": [
      {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "job_type": "print",
        "status": "completed",
        "signature_file_name": "signature.svg",
        "signature_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "copies_requested": 1,
        "copies_printed": 1,
        "queued_at": "2026-04-28T13:00:00+00:00",
        "started_at": "2026-04-28T13:00:01+00:00",
        "completed_at": "2026-04-28T13:02:30+00:00",
        "error_message": null,
        "result": {
          "payload": {
            "svgFileName": "signature.svg",
            "commandCount": 842,
            "result": {
              "message": "Print complete.",
              "commands_sent": 840,
              "copies": 0,
              "total_commands_sent": 0,
              "svg_total_distance_mm": 156.32,
              "executed_distance_mm": 156.32,
              "execution_percent": 100.0,
              "cumulative_distance_mm": 12606.57,
              "job_stopped": false
            },
            "status": {
              "is_open": true,
              "port_name": "COM3"
            }
          }
        }
      }
    ],
    "days": 7,
    "limit": 50
  },
  "errorCode": null,
  "details": null
}
```

---

#### `GET /api/config/requests/{request_id}`

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/requests/6ba7b810-9dad-11d1-80b4-00c04fd430c8"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Request log loaded.",
  "data": {
    "id": "11111111-2222-3333-4444-555555555555",
    "requestId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "status": "APPROVED",
    "statusValue": 2,
    "approvalResponse": "{\"approved\":true}",
    "errorMessage": null,
    "createdAt": "2026-04-28T12:00:00+00:00",
    "updatedAt": "2026-04-28T12:00:05+00:00",
    "completedAt": "2026-04-28T12:01:00+00:00"
  },
  "errorCode": null,
  "details": null
}
```

---

#### `GET /api/config/requests`

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/requests?count=5"
```

**Example response** `200`

```json
{
  "success": true,
  "message": "Recent request logs loaded.",
  "data": [
    {
      "id": "11111111-2222-3333-4444-555555555555",
      "requestId": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "status": "PRINTED",
      "statusValue": 5,
      "approvalResponse": null,
      "errorMessage": null,
      "createdAt": "2026-04-28T12:00:00+00:00",
      "updatedAt": "2026-04-28T12:05:00+00:00",
      "completedAt": "2026-04-28T12:05:00+00:00"
    }
  ],
  "errorCode": null,
  "details": null
}
```

---

## Shared schemas

### PrintRequest fields

Used inside multipart `printRequestJson`, nested JSON `printRequest`, or as flat form keys.


| Field        | JSON keys                | Type            | Default   | Validation                                                                      |
| ------------ | ------------------------ | --------------- | --------- | ------------------------------------------------------------------------------- |
| Paper preset | `paper`, `Paper`         | `string | null` | `null`    | Must match a [Paper enum](#paper-enum-values) name or value (case-insensitive). |
| Width        | `width`, `Width`         | `string`        | `"210mm"` | Replaced when `paper` is set from preset.                                       |
| Height       | `height`, `Height`       | `string`        | `"297mm"` | Replaced when `paper` is set.                                                   |
| X position   | `xPosition`, `XPosition` | `string`        | `"50mm"`  |                                                                                 |
| Y position   | `yPosition`, `YPosition` | `string`        | `"50mm"`  |                                                                                 |
| Scale        | `scale`, `Scale`         | `integer`       | `1`       | Must be ≥ `1`.                                                                  |
| Rotation     | `rotation`, `Rotation`   | `integer`       | `0`       | `0`–`360`.                                                                      |
| Invert X     | `invertX`, `InvertX`     | `boolean`       | `false`   | Parsed via `parse_bool` (accepts `1`/`true`/`yes` in strings).                  |
| Invert Y     | `invertY`, `InvertY`     | `boolean`       | `true`    | Same parsing.                                                                   |


### PrintResponse (as JSON)


| Field                    | Type      |
| ------------------------ | --------- |
| `message`                | `string`  |
| `commands_sent`          | `integer` |
| `copies`                 | `integer` |
| `total_commands_sent`    | `integer` |
| `svg_total_distance_mm`  | `number`  |
| `executed_distance_mm`   | `number`  |
| `execution_percent`      | `number`  |
| `cumulative_distance_mm` | `number`  |
| `job_stopped`            | `boolean` |


### PrinterStatus (as JSON)

Same 13 fields as in `[GET /api/cmd/status](#get-apicmdstatus)`; keys are **snake_case** as returned by `dataclasses.asdict` (`port_name`, `is_open`, …).

### RequestLog (as JSON)


| Field              | Type            |
| ------------------ | --------------- |
| `id`               | `string`        |
| `requestId`        | `string`        |
| `status`           | `string`        |
| `statusValue`      | `integer`       |
| `approvalResponse` | `string | null` |
| `errorMessage`     | `string | null` |
| `createdAt`        | `string`        |
| `updatedAt`        | `string`        |
| `completedAt`      | `string | null` |


---

## API index (endpoints in this document)

Quick checklist of every HTTP surface **documented above** (method + path). All `/api/`* routes expect `[X-API-Key` authentication](#authentication-all-api-routes) unless a valid `plotter_api_auth` cookie is already set.

### Static pages (no API key)


| Method | Path             |
| ------ | ---------------- |
| `GET`  | `/`              |
| `GET`  | `/configuration` |


### Command group — `/api/cmd/*`


| Method | Path                  |
| ------ | --------------------- |
| `GET`  | `/api/cmd/health`     |
| `GET`  | `/api/cmd/status`     |
| `POST` | `/api/cmd/print`      |
| `POST` | `/api/cmd/print/bulk` |
| `POST` | `/api/cmd/bulk/stop`  |
| `POST` | `/api/cmd/void`       |


### Configuration group — `/api/config/*`

**Runtime config**


| Method | Path          |
| ------ | ------------- |
| `GET`  | `/api/config` |


**Serial & connection**


| Method | Path                            |
| ------ | ------------------------------- |
| `GET`  | `/api/config/serial-ports`      |
| `GET`  | `/api/config/serial-port-check` |
| `POST` | `/api/config/auto-connect`     |
| `POST` | `/api/config/disconnect`        |


**Pen maintenance**


| Method | Path                            |
| ------ | ------------------------------- |
| `POST` | `/api/config/change-pen/start`  |
| `POST` | `/api/config/change-pen/finish` |
| `POST` | `/api/config/change-pen`        |
| `POST` | `/api/config/reset`             |
| `POST` | `/api/config/pen-max-distance`  |


**Scanner proxy** (forwards to upstream scanner HTTP service)


| Method | Path                                |
| ------ | ----------------------------------- |
| `GET`  | `/api/config/scanner/stream.mjpg`   |
| `POST` | `/api/config/scanner/manual-config` |


**Capture** (single-shot scanner storage)


| Method | Path                                  |
| ------ | ------------------------------------- |
| `POST` | `/api/config/scanner/capture/oneshot` |


**Print history**


| Method | Path                                |
| ------ | ----------------------------------- |
| `GET`  | `/api/config/print-history`         |


**Total:** 2 static routes + Flask JSON/binary API routes under `/api/*` (see tables above).

---

## Source

Implemented in `[app.py](../plotter-signature/plotter_signature/web/flask_app/app.py)`; domain types in `[contracts.py](../plotter-signature/plotter_signature/domain/contracts.py)`; config in `[config.py](../plotter-signature/plotter_signature/web/flask_app/config.py)`.