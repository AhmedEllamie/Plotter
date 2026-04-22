# POST /api/pen-max-distance

## Pre-Security Behavior
- Authentication: Not required (before API key enforcement was added).

## What It Takes
- JSON/form: meters or maxPenDistanceM required

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
