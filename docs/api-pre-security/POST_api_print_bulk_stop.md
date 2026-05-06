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
- Success data: minimal stop acknowledgment (e.g. **jobStopped**); **`GET /api/cmd/status`** for live state — not full nested status blob

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), PRINTER_NOT_BUSY (409), BULK_STOP_FAILED (500)
