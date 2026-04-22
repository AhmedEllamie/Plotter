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
