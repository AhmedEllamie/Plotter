# Plotter Signature — Postman testing guide

This guide describes how to call every **Flask** JSON/binary API from **Postman**. Paths match the live app (`plotter_signature/web/flask_app/routes/`). For deeper field-level detail, see [API_REFERENCE.md](API_REFERENCE.md).

---

## 1. Before you start

### Base URL

Use a Postman environment variable, for example:

| Variable   | Example value        |
| ---------- | -------------------- |
| `baseUrl`  | `http://127.0.0.1:5000` |

All request URLs below are `{baseUrl}` + path (e.g. `{baseUrl}/api/cmd/health`).

### Authentication (`X-API-Key`)

**`PLOTTER_API_KEY` is mandatory.** The server refuses to start if it is unset or blank, so every `/api/*` request must send that value:

- **Postman → Headers:** `X-API-Key` = your key  
- **Or** Collection / Environment auth: type **API Key**, key name `X-API-Key`, value = server's key, add to **Header**.

There is no anonymous / development bypass.

**Scanner stream in a browser:** `GET /api/config/scanner/stream.mjpg` also accepts query **`token`** (must match **`PLOTTER_API_KEY`**, or **`PLOTTER_STREAM_TOKEN`** if set) because `<img src="...">` cannot send `X-API-Key`. The configuration page appends **`token`** from the saved API key. In Postman, keep sending **`X-API-Key`** on all requests.

Invalid or missing key → **HTTP 401** and JSON:

```json
{
  "success": false,
  "message": "[UNAUTHORIZED] Invalid X-API-Key header.",
  "data": null,
  "errorCode": 1035,
  "details": null
}
```

### Standard JSON envelope

Most endpoints return **JSON** with this shape:

| Field       | Meaning |
| ----------- | ------- |
| `success`   | `true` / `false` |
| `message`   | Human-readable summary |
| `data`      | Payload object/array, or `null` on many errors |
| `errorCode` | Integer machine code on failure (`null` on success); legacy string tokens are folded into `message` as `[TOKEN] ...`. See [API_REFERENCE.md](API_REFERENCE.md#api-error-code-registry). |
| `details`   | Extra context (optional) |

**Postman tip:** open the **Pretty** JSON view and check **status code** (200, 202, 400, 401, 409, 502, …) together with `success` and `errorCode`.

---

## 2. Postman mechanics by pattern

### GET (query parameters)

Example: **Params** tab → key `device`, value `COM3` for serial port check.

### POST JSON

**Body → raw → JSON.** Set header `Content-Type: application/json` (Postman usually sets it when you pick JSON).

Empty body where noted: use `{}` or no body; if the server requires JSON, prefer `{}`.

### POST `multipart/form-data` (print)

**Body → form-data:**

- Row type **File**: key `svg` (or `file`) → choose your `.svg` file.
- Optional row type **Text**: key `printRequestJson`, value = stringified JSON, e.g.  
  `{"printRequest":{"paper":"A4","scale":1,"rotation":0,"invertY":true}}`
- Optional: other [PrintRequest](API_REFERENCE.md#printrequest-fields) keys as separate text fields (`scale`, `xPosition`, …).

**Do not** set `Content-Type` manually for multipart; let Postman set the boundary.

### Binary responses (image / MJPEG)

- **`GET .../capture/latest/image`**: response is image bytes; use **Send and Download** or view in **Preview** if supported.
- **`GET .../scanner/stream.mjpg`**: continuous **multipart MJPEG**; Postman may show a raw stream — a browser or VLC is often easier for long previews.

---

## 3. Command APIs (`/api/cmd/*`)

| Method | Path | Body / params | Typical success HTTP | What to expect in `data` |
| ------ | ---- | ------------- | -------------------- | -------------------------- |
| GET | `/api/cmd/health` | — | 200 | `printerConnected`, `printerBusy`, `captureResetConfigured` |
| GET | `/api/cmd/status` | — | 200 | Public printer status (no `port_name`; includes **`printer_connected`**) |
| POST | `/api/cmd/print` | `multipart/form-data`: file field **`svg`** or **`file`** (required); optional `printRequestJson` or JSON / form print settings | 200 = completed; **202** = queued | 200: `queued`, `jobId`, `jobType`, `svgFileName`, `commandCount`, slim `result` (see [API_REFERENCE](API_REFERENCE.md#post-apicmdprint)). 202: `queued: true`, `jobId`, `queuePosition`, … |
| POST | `/api/cmd/print/bulk` | Same as print + **`copies`** (1–100) in form, JSON, or query | 200 / 202 | Like print, plus `bulkProgress`; no top-level `copies` on 200; `result` is slim bulk summary |
| POST | `/api/cmd/bulk/stop` | JSON `{}` recommended | 200 | `{ "status": { … } }` — graceful bulk stop after current copy |
| POST | `/api/cmd/void` | JSON `{}` recommended | 200 | Idle: `data` is `{}` (use `message`). Busy: `{ "status": … }` |

### Common command error codes (non-exhaustive)

| `errorCode` | Typical HTTP |
| ----------- | ------------ |
| `PRINTER_STATE_ERROR` | 409 (e.g. not connected for print) |
| `EMPTY_SVG` / `SVG_REQUIRED` / `PRINT_VALIDATION_ERROR` / `PRINT_RUNTIME_ERROR` | 400 |
| `PRINT_FAILED` / `BULK_PRINT_FAILED` | 500 |
| `UNAUTHORIZED` | 401 |

---

## 4. Config — runtime & UI profile

| Method | Path | Body / params | Typical success | `data` (summary) |
| ------ | ---- | ------------- | --------------- | ------------------ |
| GET | `/api/config` | — | 200 | Scanner/capture flags, `scannerServiceBaseUrl`, … |
| GET | `/api/config/ui-profile` | — | 200 | `print`, `capture`, `updatedAt` — default shape includes paper/settings and `capture.quad_points` |
| POST | `/api/config/ui-profile` | JSON **root** object with `print` + `capture` only — **not** the full GET envelope (do not nest under top-level `data`); see [API_REFERENCE](API_REFERENCE.md) “Config — UI profile” | 200 | Full saved profile; `capture` applied to scanner when configured; may include `scannerApplyWarning` |

**POST errors:** `UI_PROFILE_REQUIRED` (400), `UI_PROFILE_SAVE_FAILED` (500).

---

## 5. Serial & connection are not API routes

The serial scan/check/connect/disconnect config APIs were removed. On Ubuntu, use the Desktop App local USB panel or CLI direct serial commands instead:

```bash
python -m plotter_signature.cli scan-serial --device-match "CH340"
python -m plotter_signature.cli connect --device-match "CH340"
python -m plotter_signature.cli disconnect
```

`--device-match` is matched against USB serial metadata (`device`, `name`, `description`, `manufacturer`, `hwid`) so the plotter can still be found if Ubuntu changes `/dev/ttyUSB0` to another device path.

---

## 6. Config — pen & distance

| Method | Path | Body / params | Typical success |
| ------ | ---- | ------------- | --------------- |
| POST | `/api/config/change-pen/start` | `{}` | 200 — `data` is `{}` (use `message`) |
| POST | `/api/config/change-pen/finish` | `{}` | 200 — same |
| POST | `/api/config/change-pen` | JSON `{"mode":"start"}` or `{"mode":"finish"}` | 200 — delegates to start/finish (`data` `{}`) |
| POST | `/api/config/pen-distance` | `{"resetCumulative":true}`, `{"meters":2.75}`, or both | 200 — slim `data`: `maxPenDistanceM`, `remainingPenPercent`, optional `cumulativeDistanceMm` after reset |

---

## 7. Config — upload capture (dashboard image)

| Method | Path | Body | Typical success |
| ------ | ---- | ---- | --------------- |
| POST | `/api/config/capture` | **`multipart` file** (`photo` / `image` / `file` / `capture`) and/or **JSON** `imageBase64`, or raw image body | **201** — `fileName`, `contentType`, `sizeBytes`, `capturedAt`, `imageUrl` |

**Errors:** `CAPTURE_PAYLOAD_INVALID` (400), `CAPTURE_UPLOAD_FAILED` (500).

---

## 8. Config — latest capture (JSON vs raw image)

| Method | Path | Params | Typical success |
| ------ | ---- | ------ | --------------- |
| GET | `/api/config/capture/latest` | Optional query **`includeDataUri`** (bool) | 200 — metadata + URL + optional `dataUri` |
| GET | `/api/config/capture/latest/image` | — | **200 binary image** (not JSON envelope) |

**Errors:** `CAPTURE_NOT_FOUND` (404).

---

## 9. Config — scanner proxy & session

| Method | Path | Params / body | Typical success |
| ------ | ---- | ------------- | --------------- |
| GET | `/api/config/scanner/stream.mjpg` | Query: `fps` (default 10), `width` (default 0), `fisheye` (default 1); plus header `X-API-Key` **or** query `token` (must match `PLOTTER_STREAM_TOKEN` if set, otherwise `PLOTTER_API_KEY`) | **200** MJPEG stream (binary) |

Scanner manual config is embedded in `POST /api/config/ui-profile` under the `capture` section. Scanner-related legacy tokens (see numeric codes in [API_REFERENCE.md](API_REFERENCE.md#api-error-code-registry)): `SCANNER_CONFIG_REQUIRED`, `SCANNER_HTTP_ERROR`, `SCANNER_UNREACHABLE`, `SCANNER_CAPTURE_FAILED`, stream: `SCANNER_STREAM_*`.

---

## 10. Config — scanner capture (async steps)

Use **`captureId`** from **start** for **status** and **result**.

| Method | Path | Body / params | Typical success |
| ------ | ---- | ------------- | --------------- |
| POST | `/api/config/scanner/capture/start` | Optional JSON: `readability_required`, `timeout_seconds` | 200 — `captureId`, capture metadata |
| GET | `/api/config/scanner/capture/{capture_id}/status` | Path: real `capture_id` | 200 — `captureId`, `capture` object |
| GET | `/api/config/scanner/capture/{capture_id}/result` | Path: `capture_id` | **200** often **image file** (binary) per implementation |

### Orchestration: `run` + poll job

| Method | Path | Body / params | Typical success |
| ------ | ---- | ------------- | --------------- |
| POST | `/api/config/scanner/capture/run` | Optional JSON: `readability_required`, `timeout_seconds` | **202** — `jobId`, `state` (e.g. `pending`) |
| GET | `/api/config/scanner/capture/run/{job_id}` | Path: `job_id` from previous step | 200 — `state`: `pending` \| `running` \| `succeeded` \| `failed` \| `timeout`; on success includes capture metadata / image fields |

**Job errors:** `CAPTURE_JOB_NOT_FOUND` (404); missing id → `SCANNER_CONFIG_REQUIRED` (400) in some paths.

---

## 11. Config — manual / oneshot capture (JSON → rectified PNG)

Same handler is registered for both paths (use whichever you prefer in Postman).

| Method | Path | Body | Typical success |
| ------ | ---- | ---- | --------------- |
| POST | `/api/config/scanner/capture-manual` | JSON: **`quad_points`** required (4 corners); optional focus/autofocus; optional `includeDataUri` | 200 — `captureId`, `fileName`, `imageUrl`, … |
| POST | `/api/config/scanner/capture/oneshot` | Same as above | 200 — same |

---

## 12. Config — print history

| Method | Path | Query | Typical success |
| ------ | ---- | ----- | --------------- |
| GET | `/api/config/print-history` | `days` (default **30**), `limit` (default **500**), optional `compact=1` | 200 — `items[]`, `days`, `limit`; compact mode trims rows and unwraps slim `result` / `bulkProgress` |

Invalid integers → `INVALID_QUERY` (400).

---

## 13. Suggested Postman collection folder layout

1. **Env:** `baseUrl` and `apiKey` (required) → header `X-API-Key: {{apiKey}}` on every `/api/*` request.  
2. **01 Health & config:** `GET health`, `GET config`, `GET ui-profile`.  
3. **02 Status:** `GET status`.  
4. **03 Print:** `POST print`, `POST print/bulk`, `POST bulk/stop`, `POST void`.  
5. **04 Pen / stats:** change-pen, **`pen-distance`**.  
6. **05 Capture upload & latest:** `POST capture`, `GET capture/latest`, `GET capture/latest/image`.  
7. **06 Scanner:** `capture/start`, `capture/{id}/status`, `capture/{id}/result`, `capture/run`, `capture/run/{job_id}`, `stream.mjpg`.  
8. **07 History:** `GET print-history`.

---

## 14. Optional: FastAPI surface (`/printer`)

Some deployments expose a **FastAPI** controller (see [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) § FastAPI). Serial connect/disconnect is handled by Desktop App/CLI direct serial code; API status and print routes assume that the process already has the plotter serial link open.

---

## 15. Quick reference — all Flask routes in this guide

**Commands**

- `GET /api/cmd/health`
- `GET /api/cmd/status`
- `POST /api/cmd/print`
- `POST /api/cmd/print/bulk`
- `POST /api/cmd/bulk/stop`
- `POST /api/cmd/void`

**Config**

- `GET /api/config`
- `GET /api/config/ui-profile` — `POST /api/config/ui-profile`
- `POST /api/config/change-pen/start` — `POST /api/config/change-pen/finish` — `POST /api/config/change-pen`
- `POST /api/config/pen-distance`
- `POST /api/config/capture` — `GET /api/config/capture/latest` — `GET /api/config/capture/latest/image`
- `GET /api/config/scanner/stream.mjpg`
- `POST /api/config/scanner/capture/start`
- `GET /api/config/scanner/capture/{capture_id}/status` — `GET /api/config/scanner/capture/{capture_id}/result`
- `POST /api/config/scanner/capture/run` — `GET /api/config/scanner/capture/run/{job_id}`
- `POST /api/config/scanner/capture-manual` — `POST /api/config/scanner/capture/oneshot`
- `GET /api/config/print-history`
