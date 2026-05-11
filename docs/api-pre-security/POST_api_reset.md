# POST /api/reset

**Current server:** This path is **not** implemented. Use **`POST /api/config/pen-distance`** with `{"resetCumulative":true}` (and optional `meters`). Below is historical pre-security documentation only.

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON: **`meters`** (number). Legacy **`clearUploadedSvg`** is ignored if sent.

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: **`data`** includes **`maxPenDistanceM`**; full distance stats: **`GET /api/cmd/status`** (no **clearedUploadedSvg**).

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_BUSY (409), RESET_VALIDATION_ERROR (400), RESET_FAILED (500)
