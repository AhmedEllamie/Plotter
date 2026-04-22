# POST /api/capture

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Image input accepted as multipart file (photo/image/file/capture), imageBase64, or raw image binary body

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- 201 success data: fileName, contentType, sizeBytes, capturedAt, imageUrl

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: CAPTURE_PAYLOAD_INVALID (400), CAPTURE_UPLOAD_FAILED (500)
