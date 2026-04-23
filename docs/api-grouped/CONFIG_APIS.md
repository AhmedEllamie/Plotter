# Config APIs (`/api/config/*`)

The `config` group contains setup, scanner, capture, and operational configuration endpoints.

## Runtime and device config
- `GET /api/config`
- `GET /api/config/serial-ports`
- `GET /api/config/serial-port-check`
- `POST /api/config/connect`
- `POST /api/config/disconnect`
- `POST /api/config/upload`
- `POST /api/config/change-pen/start`
- `POST /api/config/change-pen/finish`
- `POST /api/config/change-pen`
- `POST /api/config/reset`
- `POST /api/config/pen-max-distance`

## Capture storage and reset integration
- `POST /api/config/capture/request`
- `POST /api/config/capture`
- `GET /api/config/capture/latest`
- `GET /api/config/capture/latest/image`

## Scanner stream and configuration
- `GET /api/config/scanner/stream.mjpg`
- `POST /api/config/scanner/manual-config`
- `POST /api/config/scanner/focus-adjust`

## Scanner capture endpoints
- `POST /api/config/scanner/capture/start`
- `GET /api/config/scanner/capture/<capture_id>/status`
- `GET /api/config/scanner/capture/<capture_id>/result`
- `POST /api/config/scanner/capture/run`
- `GET /api/config/scanner/capture/run/<job_id>`
- `POST /api/config/scanner/capture-manual`

### One-call orchestration flow
- Start async run via `POST /api/config/scanner/capture/run`.
- Poll orchestration state via `GET /api/config/scanner/capture/run/<job_id>`.
- Terminal states:
  - `succeeded`
  - `failed`
  - `timeout`
- On success, response includes `imageUrl` pointing to latest capture image.

## Request logs
- `GET /api/config/requests/<request_id>`
- `GET /api/config/requests`
