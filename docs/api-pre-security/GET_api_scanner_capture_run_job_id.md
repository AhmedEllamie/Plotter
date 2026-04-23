# GET /api/scanner/capture/run/&lt;job_id&gt;

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- Path: `job_id` required.

## Response
- Success envelope (JSON APIs):
  - `success`: true
  - `message`: success message
  - `data`: endpoint-specific payload
  - `errorCode`: null
- Success data includes:
  - `jobId`
  - `state`: `pending|running|succeeded|failed|timeout`
  - `captureId` when available
  - `scannerStatus` and `attempts`
  - `error` and `errorCode` when failed/timeout
  - On success: `fileName`, `contentType`, `capturedAt`, `imageUrl`

## Error Response
- Error envelope:
  - `success`: false
  - `message`: error message
  - `data`: null
  - `errorCode`: endpoint error code
  - `details`: optional extra details
- Errors:
  - `SCANNER_CONFIG_REQUIRED` (400) when `job_id` missing
  - `CAPTURE_JOB_NOT_FOUND` (404) when job does not exist
