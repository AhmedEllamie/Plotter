# POST /api/print/bulk

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Same as /api/print plus copies (JSON/form/query integer 1..100)

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: svgFileName, copies, commandCount, result, bulkProgress, status

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PRINTER_STATE_ERROR (409), EMPTY_SVG (400), SVG_NOT_UPLOADED (400), PRINT_VALIDATION_ERROR (400), PRINT_RUNTIME_ERROR (400), BULK_PRINT_FAILED (500)
