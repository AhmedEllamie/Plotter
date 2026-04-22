# POST /api/capture/request

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON payload forwarded to capture reset endpoint

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: statusCode and responseBody from capture reset endpoint

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_NOT_CONFIGURED (400), CAPTURE_TRIGGER_HTTP_ERROR (502), CAPTURE_TRIGGER_UNREACHABLE (502), CAPTURE_TRIGGER_FAILED (500)
