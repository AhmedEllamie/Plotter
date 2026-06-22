# POST /api/print

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Multipart **SVG** on each request: form file field **`svg`** or **`file`** only.
- Print settings come **only** from the server configuration file (`ui-profile.json` → `printRequestJson.printRequest`).
- Requires `initialized: true` in the profile (set via Send scanner config on `/configuration`).
- Sending `printRequestJson` or print form fields in the request returns `PRINT_SETTINGS_NOT_ALLOWED` (400).

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: slim job result (e.g. **svgFileName**, **commandCount**, **result**); use **`GET /api/cmd/status`** for live state — no duplicate nested full **status**

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CONFIG_NOT_INITIALIZED (409), PRINT_SETTINGS_NOT_ALLOWED (400), PRINTER_STATE_ERROR (409), EMPTY_SVG (400), PRINT_VALIDATION_ERROR (400), PRINT_RUNTIME_ERROR (400), PRINT_FAILED (500)
