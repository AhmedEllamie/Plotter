# POST /api/scanner/focus-adjust

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON body required for focus adjustment

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: adjust_response from scanner service

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_CONFIG_REQUIRED (400), SCANNER_HTTP_ERROR (502), SCANNER_UNREACHABLE (502), SCANNER_CONFIG_FAILED (500)
