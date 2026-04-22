# POST /api/upload

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Multipart file: svg (or file)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- 201 success data: fileName, sizeBytes, uploadedAt

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: SVG_REQUIRED (400), EMPTY_SVG (400)
