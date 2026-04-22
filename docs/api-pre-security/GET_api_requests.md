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
