# POST /api/config/auto-connect

## Behavior

- When `PLOTTER_API_KEY` is unset or empty, `X-API-Key` is not required; when set, all `/api/*` routes require a valid key (see `API_REFERENCE.md`).

**Startup:** The Flask/FastAPI processes also run the same AutoConnect logic **once at boot** (unless `AUTO_CONNECT_ON_STARTUP` is `0`/`false`/`no`/`off`); this POST still works for manual retries or a forced `comPort`.

**Desktop / CLI:** You can also use direct serial from the machine: `python -m plotter_signature.cli scan-serial --device-match "CH340"` and `connect --device-match "CH340"` (matches `device`, `name`, `description`, `manufacturer`, `hwid`).

## What It Takes

- JSON body **{}** or query only: server tries **default COM** from config, then **filtered serial enumeration** (same rules as `GET /api/config/serial-ports`) until a port opens.
- Optional `comPort` / `com_port` (or query): try **only** that device (plus optional `baudRate` / `baud_rate`).

## Response

- Success envelope (JSON APIs):
  - success: true
  - message: success message
  - data: endpoint-specific payload
  - errorCode: null
- Success data: printer status after connection (includes `port_name` where applicable; **public** `GET /api/cmd/status` omits `port_name` / `is_open`; exposes **`printer_connected`**).

## Error Response

- Error envelope:
  - success: false
  - message: error message
  - data: null
  - errorCode: endpoint error code
  - details: optional extra details (e.g. `attemptedPorts` for `AUTO_CONNECT_FAILED`)
- Errors: **ALREADY_CONNECTED** (409), **INVALID_BAUD_RATE** (400), **AUTO_CONNECT_FAILED** (400), connect/open failures surfaced as **400** with stable `errorCode`
