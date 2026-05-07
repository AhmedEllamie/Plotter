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
- Success data: printer status fields for clients (**`port_name` is omitted** from this JSON; use connect/auto-connect responses or local COM override for port context)

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: none specific from handler
