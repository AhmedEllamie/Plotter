# GET /api/capture/latest

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional query: includeDataUri (bool)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: fileName, contentType, sizeBytes, capturedAt, imageUrl, optional dataUri

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_NOT_FOUND (404)
