# POST /api/print

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Either multipart svg file or previously uploaded SVG. Print settings via JSON body, printRequest object, printRequestJson form, or form fields.

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: svgFileName, commandCount, result, status

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), EMPTY_SVG (400), SVG_NOT_UPLOADED (400), PRINT_VALIDATION_ERROR (400), PRINT_RUNTIME_ERROR (400), PRINT_FAILED (500)
