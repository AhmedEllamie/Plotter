# Plotter Signature — Flask API reference (detailed)

Full HTTP reference for `[plotter_signature/web/flask_app/app.py](../plotter-signature/plotter_signature/web/flask_app/app.py)`. Grouping matches `[plotter-signature/docs/api-grouped/](../plotter-signature/docs/api-grouped/README.md)`: **Command** (`/api/cmd/`*) and **Config** (`/api/config/`*). Each operation lists **parameters with data types**, `**data` shapes**, and **concrete request/response examples**.

---

## Example convention

Examples use:


| Placeholder          | Value                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------ |
| Base URL             | `http://127.0.0.1:5000`                                                                                      |
| API key for examples | Configure the same key in browser **Configuration → API Key**; `PLOTTER_API_KEY` is mandatory on the server. |


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


| Field       | Type      | Description                                                                                                                                               |
| ----------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `success`   | `boolean` | `true` if the call succeeded.                                                                                                                             |
| `message`   | `string`  | Human-readable summary. On errors, legacy machine tokens (e.g. `UNAUTHORIZED`) are folded into this field as `**[TOKEN] ...`** after the opening bracket. |
| `data`      | `object   | array                                                                                                                                                     |
| `errorCode` | `integer  | null`                                                                                                                                                     |
| `details`   | `object   | null`                                                                                                                                                     |


Source: `[response.py](../plotter-signature/plotter_signature/web/flask_app/response.py)`.

**Example error (auth failure):**

```http
GET /api/cmd/status HTTP/1.1
Host: 127.0.0.1:5000
```

```json
{
  "success": false,
  "message": "[UNAUTHORIZED] Invalid X-API-Key header.",
  "data": null,
  "errorCode": 1035,
  "details": null
}
```

HTTP status: `401`.

### API error code registry

All failing JSON responses that use the standard envelope expose a numeric top-level `**errorCode**`. The same integer is assigned per legacy string key (for documentation and logs). Unknown legacy keys at the server resolve to `**0**`; the raw token still appears inside `**message**` when applicable.


| `errorCode` | Legacy token                          |
| ----------- | ------------------------------------- |
| 1001        | `BULK_PRINT_FAILED`                   |
| 1002        | `BULK_STOP_FAILED`                    |
| 1003        | `CAPTURE_JOB_NOT_FOUND`               |
| 1004        | `CAPTURE_JOB_TIMEOUT`                 |
| 1005        | `CAPTURE_NOT_FOUND`                   |
| 1006        | `CAPTURE_PAYLOAD_INVALID` — reserved; formerly upload validation (`POST /api/config/capture` removed). |
| 1007        | `CAPTURE_UPLOAD_FAILED`               |
| 1008        | `EMPTY_SVG`                           |
| 1009        | `INVALID_PEN_MODE`                    |
| 1010        | `INVALID_QUERY`                       |
| 1011        | `PEN_CHANGE_FINISH_FAILED`            |
| 1012        | `PEN_CHANGE_START_FAILED`             |
| 1013        | `PEN_CHANGE_STATE_ERROR`              |
| 1014        | `PEN_MAX_DISTANCE_FAILED`             |
| 1015        | `PEN_MAX_DISTANCE_INVALID`            |
| 1016        | `PEN_MAX_DISTANCE_REQUIRED`           |
| 1017        | `PRINT_FAILED`                        |
| 1018        | `PRINT_RUNTIME_ERROR`                 |
| 1019        | `PRINT_VALIDATION_ERROR`              |
| 1020        | `PRINTER_BUSY`                        |
| 1021        | `PRINTER_NOT_BUSY`                    |
| 1022        | `PRINTER_STATE_ERROR`                 |
| 1023        | `RESET_FAILED`                        |
| 1024        | `RESET_VALIDATION_ERROR`              |
| 1025        | `SCANNER_CAPTURE_FAILED`              |
| 1026        | `SCANNER_CONFIG_REQUIRED`             |
| 1027        | `SCANNER_HTTP_ERROR`                  |
| 1028        | `SCANNER_STREAM_FAILED`               |
| 1029        | `SCANNER_STREAM_HTTP_ERROR`           |
| 1030        | `SCANNER_STREAM_UNREACHABLE`          |
| 1031        | `SCANNER_UNREACHABLE`                 |
| 1032        | `SVG_REQUIRED`                        |
| 1033        | `UI_PROFILE_REQUIRED`                 |
| 1034        | `UI_PROFILE_SAVE_FAILED`              |
| 1035        | `UNAUTHORIZED`                        |
| 1036        | `VOID_BUSY`                           |
| 1037        | `VOID_FAILED`                         |
| 1038        | `VOID_RUNTIME_ERROR`                  |
| 1039        | `PEN_DISTANCE_NO_ACTION`              |
| 0           | *(unregistered / unknown legacy key)* |


Implementation: `[api_error_codes.py](../plotter-signature/plotter_signature/infrastructure/errors/api_error_codes.py)`.

### Last API error snapshot (`GET /api/cmd/status`)

The server keeps a thread-safe **last API error** record (updated whenever any route returns an error through the shared `api_error` helper). Successful **mutating** responses (`POST`, `PUT`, `PATCH`, `DELETE`) clear this snapshot; `**GET`** and `**HEAD`** success responses do **not** clear it, so operators can still see recent failures while polling status.

The current snapshot is merged into `**GET /api/cmd/status`** success payload as:


| Field                 | Type     | Description |
| --------------------- | -------- | ----------- |
| `lastApiErrorCode`    | `integer | null`       |
| `lastApiErrorMessage` | `string  | null`       |
| `lastApiErrorAt`      | `string  | null`       |


These fields describe the **last recorded failure**, not an error in the status response itself (which remains `200` / `success: true` when the status call succeeds).

### Authentication (all `/api/`* routes)


| Location    | Name        | Type     | Required                                                     | Description                                                                                                                                                                                                      |
| ----------- | ----------- | -------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HTTP header | `X-API-Key` | `string` | **Yes** for every `/api/`* route                             | Must match server `PLOTTER_API_KEY` or request returns **401**.                                                                                                                                                  |
| Query       | `token`     | `string` | Alternative (**only** `GET /api/config/scanner/stream.mjpg`) | Must equal `**PLOTTER_STREAM_TOKEN`** if that env is non-empty, otherwise `**PLOTTER_API_KEY`**. Lets the configuration page use `<img src="...">`, which cannot send headers. **May appear in logs/referrers.** |


`**PLOTTER_API_KEY` is mandatory.** Flask `create_app` raises `RuntimeError` and refuses to start if the variable is missing or blank. There is no anonymous / development bypass.

All `/api/`* routes require a matching `**X-API-Key`** header, **except** the scanner stream which may also use the `**token`** query parameter as described above (missing or invalid → **401**).


| `errorCode` (numeric) | Legacy token   | HTTP | Meaning               |
| --------------------- | -------------- | ---- | --------------------- |
| 1035                  | `UNAUTHORIZED` | 401  | Missing or wrong key. |


### Changing the server API key (Flask on Ubuntu)

Bundled production units load `**EnvironmentFile=/etc/plotter-signature/plotter-signature.env`** for `**plotter-signature-flask.service`** (see `[deploy/ubuntu/plotter-signature-flask.service](../deploy/ubuntu/plotter-signature-flask.service)`). Adjust paths if your install differs.

1. **Edit the env file** and set a new long random secret for `**PLOTTER_API_KEY`** (the service refuses to start if this line is missing, blank, or commented out):

```bash
sudo nano /etc/plotter-signature/plotter-signature.env
```

Example line (replace the value only):

```bash
PLOTTER_API_KEY=your-new-long-random-secret
```

You can copy the template from `[plotter-signature.env.example](../deploy/ubuntu/plotter-signature.env.example)` if the file does not exist yet (`sudo mkdir -p /etc/plotter-signature` first).

1. **Restart Flask** so the process reloads the environment:

```bash
sudo systemctl restart plotter-signature-flask
```

If you edited a systemd **drop-in** or unit file, run `**sudo systemctl daemon-reload`** before restarting.

1. **Quick check** (default bundled unit listens on `**5001`**; change host/port if your `serve-flask` args differ):

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: your-new-long-random-secret" \
  "http://127.0.0.1:5001/api/cmd/health"
```

Expect `**200**`. A wrong or missing key returns `**401**`.

1. **Update every client** — **Configuration → API Key**, kiosk env / `/etc/plotter-signature/plotter-signature.env` (or `PLOTTER_API_KEY_FILE`), and any integrations — so `**X-API-Key`** matches the server. For `**GET /api/config/scanner/stream.mjpg`**, use query `**token`** as documented, or set a separate `**PLOTTER_STREAM_TOKEN**` for the URL while keeping `**PLOTTER_API_KEY**` on normal `**fetch**` calls.

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


| Field                    | Type      | Description                                                         |
| ------------------------ | --------- | ------------------------------------------------------------------- |
| `printerConnected`       | `boolean` | Serial port open.                                                   |
| `printerBusy`            | `boolean` | `true` when the printer is busy (print, bulk, void, or pen change). |
| `captureResetConfigured` | `boolean` | `CAPTURE_RESET_URL` set (see `FlaskCaptureSettings`).               |


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
  "errorCode": null
}
```

---

### `GET /api/cmd/status`


| Location | Name | Type | Required | Description    |
| -------- | ---- | ---- | -------- | -------------- |
| —        | —    | —    | —        | No parameters. |


**Success `data` object — public status (serial port name is not exposed; use `printer_connected` for link state)**


| Field                           | Type      | Description                                                                                                                                                                                                                                   |
| ------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `printer_connected`             | `boolean` | `true` if the **HTTP server** has the serial port open.                                                                                                                                                                                       |
| `is_busy`                       | `boolean` | `true` during print, bulk, void, or pen change.                                                                                                                                                                                               |
| `is_printing`                   | `boolean` | `true` only during **print** or **bulk** jobs.                                                                                                                                                                                                |
| `bulk_requested_total`          | `integer` | Bulk job: total copies requested (last bulk job context).                                                                                                                                                                                     |
| `bulk_printed_count`            | `integer` | Bulk job: fully completed copies plus **one** while a bulk copy is actively running (capped at `bulk_requested_total`). Single print / idle: use `0`.                                                                                         |
| `bulk_stop_requested`           | `boolean` | Bulk graceful stop requested, or (while a bulk job is active) immediate cancel when the internal stop flag is set. May also reflect a recent `POST /api/cmd/bulk/stop` accepted by this process (use **one API worker** per machine so status matches stop). |
| `void_after_print_pending`      | `boolean` | `true` after `POST /api/cmd/void` was accepted **while** a print or bulk job was running; the void cycle will run automatically when that job finishes. Coalesced to one pending void. |
| `current_svg_total_distance_mm` | `number`  | Total path length (mm) for current SVG context.                                                                                                                                                                                               |
| `current_executed_distance_mm`  | `number`  | Pen-down distance executed (mm) for current job.                                                                                                                                                                                              |
| `current_execution_percent`     | `number`  | 0–100 progress for current execution.                                                                                                                                                                                                         |
| `cumulative_distance_mm`        | `number`  | Lifetime pen distance (mm) persisted on disk.                                                                                                                                                                                                 |
| `max_pen_distance_m`            | `number`  | Configured max pen travel (meters).                                                                                                                                                                                                           |
| `used_pen_distance_m`           | `number`  | `cumulative_distance_mm / 1000`.                                                                                                                                                                                                              |
| `remaining_pen_percent`         | `number`  | Estimated remaining pen life (percent).                                                                                                                                                                                                       |
| `lastApiErrorCode`              | `integer  | null`                                                                                                                                                                                                                                         |
| `lastApiErrorMessage`           | `string   | null`                                                                                                                                                                                                                                         |
| `lastApiErrorAt`                | `string   | null`                                                                                                                                                                                                                                         |


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
    "printer_connected": true,
    "is_busy": false,
    "is_printing": false,
    "bulk_requested_total": 0,
    "bulk_printed_count": 0,
    "bulk_stop_requested": false,
    "void_after_print_pending": false,
    "current_svg_total_distance_mm": 0.0,
    "current_executed_distance_mm": 0.0,
    "current_execution_percent": 0.0,
    "cumulative_distance_mm": 12450.25,
    "max_pen_distance_m": 2.5,
    "used_pen_distance_m": 12.450,
    "remaining_pen_percent": 90.12,
    "lastApiErrorCode": null,
    "lastApiErrorMessage": null,
    "lastApiErrorAt": null
  },
  "errorCode": null,
}
```

---

### `POST /api/cmd/print`


| Location    | Name               | Type                             | Required       | Default | Description                                                                                             |
| ----------- | ------------------ | -------------------------------- | -------------- | ------- | ------------------------------------------------------------------------------------------------------- |
| Header      | `Content-Type`     | `string`                         | Yes            | —       | Must be `multipart/form-data`.                                                                          |
| Multipart   | `svg` or `file`    | `file` (bytes)                   | **Yes** one of | —       | SVG file for this request only.                                                                         |
| Multipart   | `printRequestJson` | `string`                         | No             | —       | Stringified JSON; may contain nested `printRequest` with `[PrintRequest](#printrequest-fields)` fields. |
| Multipart   | (flat keys)        | `string` / `integer` / `boolean` | No             | —       | Any `[PrintRequest](#printrequest-fields)` keys as form fields (e.g. `scale`, `xPosition`).             |
| Body (JSON) | (entire body)      | `object`                         | No             | —       | Used only if JSON present: top-level keys or nested `printRequest` (see `_extract_print_payload`).      |


**Print settings fallback:** Any omitted `[PrintRequest](#printrequest-fields)` values are taken from the persisted server ui-profile (`GET /api/config/ui-profile` → `print` object). Fields sent in the request override the profile.

**Preconditions:** Printer connected; otherwise `409` `PRINTER_STATE_ERROR`.

**Success `data` (immediate completion, HTTP `200`)**


| Field          | Type      | Description                                                                                                                |
| -------------- | --------- | -------------------------------------------------------------------------------------------------------------------------- |
| `queued`       | `boolean` | `false`.                                                                                                                   |
| `jobId`        | `string`  | UUID string, print history row id.                                                                                         |
| `jobType`      | `string`  | `"print"`.                                                                                                                 |
| `svgFileName`  | `string`  | Original upload name.                                                                                                      |
| `commandCount` | `integer` | G-code line count.                                                                                                         |
| `result`       | `object`  | Slim print summary: `commands_sent`, `cumulative_distance_mm`, `executed_distance_mm`, `execution_percent`, `job_stopped`. |


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


| Code | Legacy token             | HTTP | Description                                  |
| ---- | ------------------------ | ---- | -------------------------------------------- |
| 1022 | `PRINTER_STATE_ERROR`    | 409  | Not connected.                               |
| 1032 | `SVG_REQUIRED`           | 400  | Missing `svg` part.                          |
| 1008 | `EMPTY_SVG`              | 400  | Zero-length file.                            |
| 1019 | `PRINT_VALIDATION_ERROR` | 400  | Bad scale/rotation/copies or SVG conversion. |
| 1018 | `PRINT_RUNTIME_ERROR`    | 400  | Runtime error in job.                        |
| 1017 | `PRINT_FAILED`           | 500  | Unexpected failure.                          |


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
      "commands_sent": 840,
      "cumulative_distance_mm": 12606.57,
      "executed_distance_mm": 156.32,
      "execution_percent": 100.0,
      "job_stopped": false
    },
    "queued": false,
    "jobId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "jobType": "print"
  },
  "errorCode": null
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
  "errorCode": null
}
```

**Example error** `409`

```json
{
  "success": false,
  "message": "[PRINTER_STATE_ERROR] Printer is not connected. Open the plotter from the Desktop App or CLI first.",
  "data": null,
  "errorCode": 1022,
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


| Field          | Type     | Description                                                                              |
| -------------- | -------- | ---------------------------------------------------------------------------------------- |
| `bulkProgress` | `object` | `requestedTotal`, `printedCount`, `stopRequested`.                                       |
| `result`       | `object` | Slim bulk summary: `cumulative_distance_mm`, `execution_percent`, `total_commands_sent`. |


**Queued `data` (HTTP `202`):** Same shape as print queue response; `jobType` is `"bulk"`.

**Extra `errorCode`:** `1017` (`PRINT_FAILED`) on HTTP `500`.

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
    "commandCount": 842,
    "result": {
      "cumulative_distance_mm": 13388.17,
      "execution_percent": 100.0,
      "total_commands_sent": 4200
    },
    "bulkProgress": {
      "requestedTotal": 5,
      "printedCount": 5,
      "stopRequested": false
    },
    "queued": false,
    "jobId": "550e8400-e29b-41d4-a716-446655440000",
    "jobType": "bulk"
  },
  "errorCode": null
}
```

---

### `POST /api/cmd/bulk/stop`


| Location | Name | Type | Required | Description |
| -------- | ---- | ---- | -------- | ----------- |
| —        | —    | —    | —        | No body.    |


**Success `data`**


| Field        | Type      | Description                                                                                                                                                                                                                               |
| ------------ | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `jobStopped` | `boolean` | Always `true` when stop was accepted (history side effect).                                                                                                                                                                               |
| `status`     | `object`  | Slim snapshot (not full `GET /api/cmd/status`): `bulk_printed_count`, `bulk_requested_total`, `cumulative_distance_mm`, `current_svg_total_distance_mm`, `remaining_pen_percent`, `used_pen_distance_m` — same count semantics as status. |


Side effects: requests **graceful** bulk stop (current copy runs to completion and ejects; further copies are not started). **`POST /api/cmd/void` no longer cancels an active print**; it queues a void for after the job (see [void](#post-apicmdvoid)). Marks active history job `stopped`, clears uploaded SVG. Use **one HTTP worker process** per deployment if you rely on `GET /api/cmd/status` staying in sync with bulk stop across requests.

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
  "message": "Bulk stop requested. The current copy will finish; remaining copies will not start.",
  "data": {
    "jobStopped": true,
    "status": {
      "bulk_printed_count": 3,
      "bulk_requested_total": 10,
      "cumulative_distance_mm": 13100.5,
      "current_svg_total_distance_mm": 156.32,
      "remaining_pen_percent": 89.45,
      "used_pen_distance_m": 13.1
    }
  },
  "errorCode": null
}
```

---

### `POST /api/cmd/void`


| Location | Name | Type | Required | Description |
| -------- | ---- | ---- | -------- | ----------- |
| —        | —    | —    | —        | No body.    |


**Idle printer (not printing):** runs the full void/eject-safe sequence (handshake, paper ready, init, eject). Success **`data`:** `{}`. Use **`message`** for the outcome text. While this void is running, **`POST /api/cmd/print`** / **bulk** use the same submission lock as print jobs: expect **202** with `queued: true` if another client submits a print during void; the queue is drained when void finishes.

**While a print or bulk job is active (`is_printing`):** does **not** cancel mid-job. Sets a **coalesced** pending void; success **`data`:** `{ "voidQueued": true, "voidAfterPrintPending": true }`. After the job completes (including its normal `finally` eject), the server runs **`void_print()`** once automatically. Poll `[GET /api/cmd/status](#get-apicmdstatus)` for `void_after_print_pending`.

If a queued void fails internally, the error is logged; the print job outcome is unchanged. Call `POST /api/cmd/void` again when idle if you still need a void cycle.

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
  "data": {},
  "errorCode": null,
  "details": null
}
```

**Example response** `200` (void accepted while printing — queued)

```json
{
  "success": true,
  "message": "Void queued; it will run automatically after the current print or bulk job completes.",
  "data": {
    "voidQueued": true,
    "voidAfterPrintPending": true
  },
  "errorCode": null,
  "details": null
}
```

---

## Group: Config APIs (`/api/config/*`)

Header: `**X-API-Key`**: `string` (required on every route, except the scanner stream may use query `token` as documented).

---

### Config — Runtime config

#### `GET /api/config`

No parameters.

**Success `data`**


| Field                      | Type      | Description                           |
| -------------------------- | --------- | ------------------------------------- |
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

Serial scan/check/connect/disconnect config APIs were removed. Use the Desktop App local USB panel or CLI direct serial commands instead:

```bash
python -m plotter_signature.cli scan-serial --device-match "CH340"
python -m plotter_signature.cli connect --device-match "CH340"
python -m plotter_signature.cli disconnect
```

`--device-match` is checked against USB serial metadata (`device`, `name`, `description`, `manufacturer`, `hwid`) so Ubuntu can move the plotter between `/dev/ttyUSB*` paths without changing the API surface.

---

### Config — Pen maintenance

#### `POST /api/config/change-pen/start`

No body. Printer must be connected and not busy.

**Success `data`:** empty object `{}`. Use `**message`** for the outcome text; use `[GET /api/cmd/status](#get-apicmdstatus)` for live printer state.

**Example response** `200`

```json
{
  "success": true,
  "message": "Pen change start completed.",
  "data": {},
  "errorCode": null,
  "details": null
}
```

---

#### `POST /api/config/change-pen/finish`

No body. Same preconditions as **start** (printer connected, not busy).

**Success `data`:** empty object `{}`. Use `**message`** for the outcome text; use `[GET /api/cmd/status](#get-apicmdstatus)` for live printer state.

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
  "data": {},
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

#### `POST /api/config/pen-distance`

**Only** endpoint for cumulative distance reset and/or max pen distance in this API version. (`POST /api/config/reset` and `POST /api/config/pen-max-distance` were removed; use this route instead.)

**Request body** (JSON, or form fields with the same keys)


| Field             | Type      | Required | Description                                                                                             |
| ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `resetCumulative` | `boolean` | No       | Default `false`. If `true`, zeros cumulative distance. `**409` `PRINTER_BUSY`** if the printer is busy. |
| `meters`          | `number`  | No*      | Sets max pen distance in meters (**must be > 0** if provided).                                          |


 At least one of `**resetCumulative: true`** or **`meters`** must be present; otherwise `**400`** `PEN_DISTANCE_NO_ACTION` (`1039`).

**Processing order:** When both apply, cumulative reset runs **first**, then max distance.

**Combined example** (reset then set max in one call):

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/pen-distance" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"resetCumulative\":true,\"meters\":3.0}"
```

**Success `data`**


| Field                  | Type     | Description                                                                            |
| ---------------------- | -------- | -------------------------------------------------------------------------------------- |
| `maxPenDistanceM`      | `number` | Configured max (meters).                                                               |
| `remainingPenPercent`  | `number` | Remaining pen life estimate (percent).                                                 |
| `cumulativeDistanceMm` | `number` | Present **only when** `resetCumulative` was `true`; value after reset (typically `0`). |


**Example — reset only**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/pen-distance" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"resetCumulative\":true}"
```

**Example — set max only**

```bash
curl -sS -X POST "http://127.0.0.1:5000/api/config/pen-distance" \
  -H "X-API-Key: QSCWDVEFBRGN" \
  -H "Content-Type: application/json" \
  -d "{\"meters\":2.75}"
```

**Example response** `200` (combined)

```json
{
  "success": true,
  "message": "Cumulative distance reset and max pen distance updated.",
  "data": {
    "maxPenDistanceM": 3.0,
    "remainingPenPercent": 100.0,
    "cumulativeDistanceMm": 0.0
  },
  "errorCode": null,
  "details": null
}
```

**Error `errorCode` (numeric)**


| Code | Legacy                     | HTTP | Description                                     |
| ---- | -------------------------- | ---- | ----------------------------------------------- |
| 1039 | `PEN_DISTANCE_NO_ACTION`   | 400  | Neither reset nor max distance supplied.        |
| 1020 | `PRINTER_BUSY`             | 409  | Reset requested while printer is busy.          |
| 1015 | `PEN_MAX_DISTANCE_INVALID` | 400  | Invalid max distance (e.g. ≤ 0 or bad number).  |
| 1023 | `RESET_FAILED`             | 500  | Unexpected failure (combined or reset portion). |
| 1014 | `PEN_MAX_DISTANCE_FAILED`  | 500  | Unexpected failure on max-distance path alone.  |


---

### Config — UI profile

#### `GET /api/config/ui-profile`

Returns the saved UI profile: `**print`** (paper, position, scale, rotation, invert flags), `**capture`** (scanner/camera corner quad and focus settings), and `**updatedAt`**.

**Example response** `200` uses the usual envelope; `**data`** is the profile object (not wrapped again).

---

#### `POST /api/config/ui-profile`

**Request body is the profile object itself** — a JSON object with top-level `**capture`** and `**print`** keys (same logical shape as `**data`** from `GET /api/config/ui-profile`).

**Do not** send the full API response envelope from `GET` (for example, do **not** nest everything under a top-level `**data`** property). The server only reads `**capture`** and `**print`** from the **root** of the JSON body. If you post `{ "data": { "capture": { ... } } }`, `**capture` and `print` are ignored**, the server falls back to defaults (`capture.quad_points` becomes `[]`, `manual_focus_value` to `35`, default `print` settings), and `**success`** can still be `**true`**. You may also see `**scannerApplyWarning`** if scanner session apply fails afterward.

Optional: on success, `**data**` may include `**scannerApplyWarning**` (string) when the profile file saved but pushing capture settings to the scanner service failed (for example upstream **HTTP 400**).

`**updatedAt`** is written by the server on save; clients may omit it in the request.

**Example request body** (root-level `capture` / `print` only)

```json
{
  "capture": {
    "autofocus_enabled": false,
    "manual_focus_value": 25,
    "quad_points": [[1727, 45], [1712, 1074], [282, 1057], [287, 50]]
  },
  "print": {
    "width": "210mm",
    "height": "297mm",
    "xPosition": "0",
    "yPosition": "0",
    "scale": 1,
    "rotation": 0,
    "invertX": true,
    "invertY": true
  }
}
```

**Error codes:** `UI_PROFILE_REQUIRED` (400), `UI_PROFILE_SAVE_FAILED` (500).

---

### Config — Scanner proxy

#### `GET /api/config/scanner/stream.mjpg`

Send `**X-API-Key`** **or** set query `**token`** to `**PLOTTER_API_KEY`** (or to `**PLOTTER_STREAM_TOKEN`** when that env is set). The configuration page adds `**token**` from the saved API key for `<img>` previews. Anonymous viewers are rejected with **401**.

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/scanner/stream.mjpg?fps=10&width=640&fisheye=1" \
  --output stream.bin
```

**Example (stream `token` instead of header)**

```bash
curl -sS \
  "http://127.0.0.1:5000/api/config/scanner/stream.mjpg?fisheye=1&token=QSCWDVEFBRGN" \
  --output stream.bin
```

**Example response** `200`  
Body: `multipart/x-mixed-replace` MJPEG stream (binary, not JSON).  
Errors return JSON envelope with `SCANNER_STREAM_`*.

Scanner manual config is embedded in `POST /api/config/ui-profile` under the `capture` section (`autofocus_enabled`, `manual_focus_value`, `quad_points`). Saving the UI profile applies those settings to the scanner session when scanner integration is configured.

---

### Config — Capture

Scanner rectification stores the latest dashboard image server-side. Use **`POST /api/config/scanner/capture/oneshot`** (below) or scanner orchestration routes. **`POST /api/config/capture` (multipart / base64 upload) was removed** — use the scanner pipeline or another integration that calls `set_captured_image` internally.

#### `GET /api/config/capture/latest`

Optional query: `includeDataUri` (`boolean`). Returns metadata for the in-memory latest capture (same shape as oneshot success `data` without requiring `captureId`).

#### `GET /api/config/capture/latest/image`

Returns the raw image bytes (`Content-Type` from stored capture). Requires `X-API-Key` like other `/api/*` routes.

#### `POST /api/config/scanner/capture/oneshot`

Non-empty JSON body. Scanner-session keys match the `capture` section of `POST /api/config/ui-profile`; `includeDataUri` is API-only and is stripped before the payload is forwarded to the scanner.


| Location | Name                 | Type                                | Required | Default | Description                                                        |
| -------- | -------------------- | ----------------------------------- | -------- | ------- | ------------------------------------------------------------------ |
| Body     | `quad_points`        | `[[number,number],...]` (4 corners) | **Yes**  | —       | Perspective quad in frame pixel coordinates.                       |
| Body     | `autofocus_enabled`  | `boolean`                           | No       | `false` | When true, scanner runs autofocus before capture.                  |
| Body     | `manual_focus_value` | `number`                            | No       | `35`    | Manual focus index when autofocus is off.                          |
| Body     | `includeDataUri`     | `boolean`                           | No       | `true`  | When true, response includes a `data:image/png;base64,...` string. |


**Success `data`**


| Field         | Type      | Description                                                                                                                                 |
| ------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `captureId`   | `string`  | Scanner job / capture id.                                                                                                                   |
| `fileName`    | `string`  | Stored file name (e.g. `rectified-{id}.png`).                                                                                               |
| `contentType` | `string`  | MIME type of the stored image.                                                                                                              |
| `sizeBytes`   | `integer` | Decoded image size.                                                                                                                         |
| `capturedAt`  | `string`  | ISO-8601 timestamp (UTC).                                                                                                                   |
| `imageUrl`    | `string`  | Path for the same stored bytes returned when `includeDataUri` is true (same `**X-API-Key**` rules as other `/api/*` URLs if under `/api/`). |
| `dataUri`     | `string`  | Present only when `includeDataUri` is true.                                                                                                 |


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

Query parameters:


| Name      | Type      | Default | Description                                                                                                                                                                                           |
| --------- | --------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `days`    | `integer` | `30`    | Only jobs with `queued_at` within this many days (min `1`).                                                                                                                                           |
| `limit`   | `integer` | `500`   | Max rows (clamped `1`–`2000`).                                                                                                                                                                        |
| `compact` | `boolean` | `false` | If `true` / `1` / `yes`, each `items[]` entry is trimmed: omits `started_at`, omits `error_message` when null, unwraps stored `result.payload` into a slim `result` (+ `bulkProgress` for bulk jobs). |


**Default (`compact` off):** Each item includes all SQLite columns (`started_at`, `error_message`, etc.) and `**result`** as stored (for new jobs, `result.payload` holds the same slim print/bulk shapes as `POST /api/cmd/print` responses).

**Example request**

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/print-history?days=7&limit=50"
```

**Example response** `200` with `compact=true`

```bash
curl -sS -H "X-API-Key: QSCWDVEFBRGN" \
  "http://127.0.0.1:5000/api/config/print-history?days=7&limit=50&compact=1"
```

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
        "completed_at": "2026-04-28T13:02:30+00:00",
        "result": {
          "commands_sent": 840,
          "cumulative_distance_mm": 12606.57,
          "executed_distance_mm": 156.32,
          "execution_percent": 100.0,
          "job_stopped": false
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

Older rows may still use a nested `result.payload` shape when `compact` is off. Failed jobs include `error_message` when set.

Request log listing/detail config APIs were removed. Use `GET /api/config/print-history` for persisted print/bulk job history.

---

## Shared schemas

### PrintRequest fields

Used inside multipart `printRequestJson`, nested JSON `printRequest`, or as flat form keys. Omitted keys fall back to ui-profile `print` (see `POST /api/cmd/print`).


| Field        | JSON keys                | Type      | Default   | Validation                                                     |
| ------------ | ------------------------ | --------- | --------- | -------------------------------------------------------------- |
| Paper preset | `paper`, `Paper`         | `string   | null`     | `null`                                                         |
| Width        | `width`, `Width`         | `string`  | `"210mm"` | Replaced when `paper` is set from preset.                      |
| Height       | `height`, `Height`       | `string`  | `"297mm"` | Replaced when `paper` is set.                                  |
| X position   | `xPosition`, `XPosition` | `string`  | `"50mm"`  |                                                                |
| Y position   | `yPosition`, `YPosition` | `string`  | `"50mm"`  |                                                                |
| Scale        | `scale`, `Scale`         | `integer` | `1`       | Must be ≥ `1`.                                                 |
| Rotation     | `rotation`, `Rotation`   | `integer` | `0`       | `0`–`360`.                                                     |
| Invert X     | `invertX`, `InvertX`     | `boolean` | `false`   | Parsed via `parse_bool` (accepts `1`/`true`/`yes` in strings). |
| Invert Y     | `invertY`, `InvertY`     | `boolean` | `true`    | Same parsing.                                                  |


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

Public API status omits serial `**port_name**`. The `**GET /api/cmd/status**` response adds `**printer_connected**` (same meaning as internal `is_open` on the server). Remaining keys are **snake_case** and match `[GET /api/cmd/status](#get-apicmdstatus)`, including `void_after_print_pending`.

### RequestLog (as JSON)


| Field              | Type      |
| ------------------ | --------- |
| `id`               | `string`  |
| `requestId`        | `string`  |
| `status`           | `string`  |
| `statusValue`      | `integer` |
| `approvalResponse` | `string   |
| `errorMessage`     | `string   |
| `createdAt`        | `string`  |
| `updatedAt`        | `string`  |
| `completedAt`      | `string   |


---

## API index (endpoints in this document)

Quick checklist of every HTTP surface **documented above** (method + path). All `/api/`* routes require `**[X-API-Key](#authentication-all-api-routes)`**, except `**GET /api/config/scanner/stream.mjpg`** which may use query `**token**` as documented there.

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


**Pen maintenance**


| Method | Path                            |
| ------ | ------------------------------- |
| `POST` | `/api/config/change-pen/start`  |
| `POST` | `/api/config/change-pen/finish` |
| `POST` | `/api/config/change-pen`        |
| `POST` | `/api/config/pen-distance`      |


**Scanner proxy** (forwards to upstream scanner HTTP service)


| Method | Path                              |
| ------ | --------------------------------- |
| `GET`  | `/api/config/scanner/stream.mjpg` |


**Capture** (scanner + latest image)


| Method | Path                                   |
| ------ | -------------------------------------- |
| `GET`  | `/api/config/capture/latest`           |
| `GET`  | `/api/config/capture/latest/image`     |
| `POST` | `/api/config/scanner/capture/oneshot` |


**Print history**


| Method | Path                        |
| ------ | --------------------------- |
| `GET`  | `/api/config/print-history` |


**Total:** 2 static routes + Flask JSON/binary API routes under `/api/`* (see tables above).

---

## Source

Implemented in `[app.py](../plotter-signature/plotter_signature/web/flask_app/app.py)`; domain types in `[contracts.py](../plotter-signature/plotter_signature/domain/contracts.py)`; config in `[config.py](../plotter-signature/plotter_signature/web/flask_app/config.py)`.