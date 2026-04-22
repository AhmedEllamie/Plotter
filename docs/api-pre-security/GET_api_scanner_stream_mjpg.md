# GET /api/scanner/stream.mjpg

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Query: fps (default 10), width (default 0), fisheye (default 1)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Streams MJPEG from scanner service with scanner content-type

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SCANNER_STREAM_HTTP_ERROR (502), SCANNER_STREAM_UNREACHABLE (502), SCANNER_STREAM_FAILED (500)
