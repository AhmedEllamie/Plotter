# GET /api/scanner/capture/&lt;capture_id&gt;/status

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Path: capture_id required

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: captureId, capture object

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CAPTURE_FAILED (500)

