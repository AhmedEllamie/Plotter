# POST /api/void

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- None

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data **idle:** `{}`; use **`message`** for the outcome.
- Success data **while printing (`is_printing`):** `{ "voidQueued": true, "voidAfterPrintPending": true }` — void runs automatically after the job (no immediate cancel).

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: **VOID_BUSY** (409) if a void is already in progress; VOID_RUNTIME_ERROR (409), VOID_FAILED (500)
