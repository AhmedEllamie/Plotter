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
