# POST /api/pen-max-distance

**Current server:** This path is **not** implemented. Use **`POST /api/config/pen-distance`** with `{"meters":...}` when setting max distance. Below is historical pre-security documentation only.

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON/form: `meters` required when setting max distance

## Response
- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: stats

## Error Response
- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details
- Errors: PEN_MAX_DISTANCE_REQUIRED (400), PEN_MAX_DISTANCE_INVALID (400), PEN_MAX_DISTANCE_FAILED (500)
