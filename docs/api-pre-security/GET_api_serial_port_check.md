# GET /api/serial-port-check

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Query: device required (COMx or /dev/... path)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: device, exists, readable, writable, resolvedTarget

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SERIAL_DEVICE_REQUIRED (400), SERIAL_DEVICE_INVALID (400)
