# POST /api/print

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Multipart **SVG** on each request: form file field **`svg`** or **`file`**.
- Required per job: **`xPosition`**, **`yPosition`** (placement offset mm from config home).
- Optional: **`scale`** (decimal multiplier `> 0`; overrides profile default).
- Config profile (`ui-profile.json` → `printRequestJson.printRequest`) provides **home** x/y, rotation, invert, and default scale.
- Effective plot offset: `home + api_placement + scaled SVG coordinates`.
- Requires `initialized: true` in the profile (set via Send scanner config on `/configuration`).
- Sending `printRequestJson` or print fields other than x/y/scale returns `PRINT_SETTINGS_NOT_ALLOWED` (400).

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
