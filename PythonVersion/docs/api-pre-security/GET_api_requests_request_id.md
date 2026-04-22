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
