# Flask APIs (Pre-Security, Single File)

This document consolidates all /api/* endpoint docs before API key enforcement.

---

# GET /api/capture/latest

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional query: includeDataUri (bool)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: fileName, contentType, sizeBytes, capturedAt, imageUrl, optional dataUri

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_NOT_FOUND (404)

---

# GET /api/capture/latest/image

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Binary image response of latest captured image

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_NOT_FOUND (404)

---

# GET /api/config

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: defaultComPort, defaultBaudRate, captureResetConfigured, captureResetMethod, scannerServiceConfigured, scannerServiceBaseUrl

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: none specific from handler

---

# GET /api/health

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: printerConnected, printerBusy, captureResetConfigured

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: none specific from handler

---

# GET /api/requests

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Query: count optional integer, clamped to 1..100 (default 10)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: list of recent request logs

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: INVALID_COUNT (400)

---

# GET /api/requests/<request_id>

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Path: request_id UUID required

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: request log object

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: INVALID_REQUEST_ID (400), REQUEST_NOT_FOUND (404)

---

# GET /api/scanner/capture/<capture_id>/result

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Path: capture_id required

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Binary image response (send_file). Also stores result in runtime captured image state.

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CAPTURE_FAILED (500)

---

# GET /api/scanner/capture/<capture_id>/status

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Path: capture_id required

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: captureId, capture object

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CAPTURE_FAILED (500)

---

# GET /api/scanner/stream.mjpg

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Query: fps (default 10), width (default 0), fisheye (default 1)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Streams MJPEG from scanner service with scanner content-type

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_STREAM_HTTP_ERROR (502), SCANNER_STREAM_UNREACHABLE (502), SCANNER_STREAM_FAILED (500)

---

# GET /api/serial-port-check

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Query: device required (COMx or /dev/... path)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: device, exists, readable, writable, resolvedTarget

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SERIAL_DEVICE_REQUIRED (400), SERIAL_DEVICE_INVALID (400)

---

# GET /api/serial-ports

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: ports array where each item has device, description, manufacturer

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SERIAL_LIST_UNAVAILABLE (503), SERIAL_LIST_FAILED (500)

---

# GET /api/status

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: full printer status model

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: none specific from handler

---

# POST /api/capture

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Image input accepted as multipart file (photo/image/file/capture), imageBase64, or raw image binary body

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- 201 success data: fileName, contentType, sizeBytes, capturedAt, imageUrl

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_PAYLOAD_INVALID (400), CAPTURE_UPLOAD_FAILED (500)

---

# POST /api/capture/request

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON payload forwarded to capture reset endpoint

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: statusCode and responseBody from capture reset endpoint

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_NOT_CONFIGURED (400), CAPTURE_TRIGGER_HTTP_ERROR (502), CAPTURE_TRIGGER_UNREACHABLE (502), CAPTURE_TRIGGER_FAILED (500)

---

# POST /api/change-pen

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON/form: mode = start or finish (default start)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Delegates to /api/change-pen/start or /api/change-pen/finish response

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: INVALID_PEN_MODE (400) plus delegated endpoint errors

---

# POST /api/change-pen/finish

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: pen change finish result

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PEN_CHANGE_STATE_ERROR (409), PEN_CHANGE_FINISH_FAILED (500)

---

# POST /api/change-pen/start

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: pen change start result

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PEN_CHANGE_STATE_ERROR (409), PEN_CHANGE_START_FAILED (500)

---

# POST /api/connect

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON or query: comPort/com_port optional, baudRate/baud_rate optional

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: printer status model after connection

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: ALREADY_CONNECTED (409), INVALID_BAUD_RATE (400), CONNECT_FAILED (400)

---

# POST /api/disconnect

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: printer status model after disconnect

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: NOT_CONNECTED (409), PRINTER_BUSY (409)

---

# POST /api/pen-max-distance

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON/form: meters or maxPenDistanceM required

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: stats

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PEN_MAX_DISTANCE_REQUIRED (400), PEN_MAX_DISTANCE_INVALID (400), PEN_MAX_DISTANCE_FAILED (500)

---

# POST /api/print

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Either multipart svg file or previously uploaded SVG. Print settings via JSON body, printRequest object, printRequestJson form, or form fields.

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: svgFileName, commandCount, result, status

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), EMPTY_SVG (400), SVG_NOT_UPLOADED (400), PRINT_VALIDATION_ERROR (400), PRINT_RUNTIME_ERROR (400), PRINT_FAILED (500)

---

# POST /api/print/bulk

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Same as /api/print plus copies (JSON/form/query integer 1..100)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: svgFileName, copies, commandCount, result, bulkProgress, status

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), EMPTY_SVG (400), SVG_NOT_UPLOADED (400), PRINT_VALIDATION_ERROR (400), PRINT_RUNTIME_ERROR (400), BULK_PRINT_FAILED (500)

---

# POST /api/print/bulk/stop

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: status after stop request

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), PRINTER_NOT_BUSY (409), BULK_STOP_FAILED (500)

---

# POST /api/reset

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON: maxPenDistanceM (number), clearUploadedSvg (bool)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: stats, clearedUploadedSvg

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_BUSY (409), RESET_VALIDATION_ERROR (400), RESET_FAILED (500)

---

# POST /api/scanner/capture-manual

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON body required; includes manual scanner config (quad_points required)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: captureId, fileName, contentType, capturedAt, imageUrl

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CAPTURE_FAILED (500)

---

# POST /api/scanner/capture/start

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON: readability_required (bool, default true), timeout_seconds (int, default 15)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: captureId, capture object

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CAPTURE_FAILED (500)

---

# POST /api/scanner/focus-adjust

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON body required for focus adjustment

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: adjust_response from scanner service

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CONFIG_FAILED (500)

---

# POST /api/scanner/manual-config

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON body required; manual scanner config payload (autofocus_enabled/manual_focus_value/quad_points optional)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: scanner service response plus remembered manual_config

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CONFIG_FAILED (500)

---

# POST /api/upload

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Multipart file: svg (or file)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- 201 success data: fileName, sizeBytes, uploadedAt

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SVG_REQUIRED (400), EMPTY_SVG (400)

---

# POST /api/void

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: printer void result

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: VOID_RUNTIME_ERROR (409), VOID_FAILED (500)
