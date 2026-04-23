# POST /api/scanner/capture/run

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Optional JSON:
  - `readability_required` (bool, default `true`)
  - `timeout_seconds` (int, default `15`)

## Response
- Success envelope (JSON APIs):
  - `success`: true
  - `message`: success message
  - `data`: endpoint-specific payload
  - `errorCode`: null
- Success data:
  - `jobId`: orchestration job identifier
  - `state`: `pending`
- Returns HTTP `202 Accepted`.

## Error Response
- Error envelope:
  - `success`: false
  - `message`: error message
  - `data`: null
  - `errorCode`: endpoint error code
  - `details`: optional extra details
- Errors: none specific from handler input path.
