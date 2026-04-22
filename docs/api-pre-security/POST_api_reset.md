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
