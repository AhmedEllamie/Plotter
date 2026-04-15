# PythonVersion

Python port of the selected printer workflow files from the C# project.

## What is included

- Printer contract and implementation (`IPrinterService`, `PrinterService`)
- SVG to G-code converter (`SvgConverter`) with path parsing and curve flattening
- Printer API controller parity via FastAPI routes
- Flask API + simple HTML/JS frontend (`Capture`, `Print`, `Upload`, `ChangePen`, `Status`)
- Dependency wiring module
- Printer settings model
- Print-approval workflow service
- In-memory request-log store (mock parity, no database)
- CLI entrypoint (`main.py`) for project operations

## Folder layout

- `api/` - FastAPI app and printer routes
- `models/` - DTOs/contracts/settings
- `services/printer/` - serial printer + SVG converter
- `services/approval/` - mock approval service
- `services/print_approval/` - approval orchestration
- `stores/` - in-memory request log backend
- `flask_app/` - Flask backend + static frontend
- `main.py` - CLI

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r PythonVersion/requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r PythonVersion\requirements.txt
```

## Run API

FastAPI version:

```bash
python -m PythonVersion.main serve-api --host 0.0.0.0 --port 5000
```

Routes are available under `/printer`, for example:

- `POST /printer/connect`
- `POST /printer/disconnect`
- `GET /printer/status`
- `POST /printer/generate`
- `POST /printer/print`
- `POST /printer/print/bulk`
- `POST /printer/print-with-approval`
- `GET /printer/requests/{request_id}`

Flask + frontend version:

```bash
python -m PythonVersion.main serve-flask --host 0.0.0.0 --port 5001
```

Open:
- `http://localhost:5001/` for the frontend page.
- `http://localhost:5001/configuration` for connection and printer settings.

Frontend notes:
- Main page uses a visual status dashboard and main actions (`Capture`, `Print`, `Upload`, `Void`, `Status`).
- Main page also supports `Bulk Print` with a copies prompt (1-100) using the same uploaded SVG workflow.
- Connection and print settings are saved in browser localStorage and reused for printing.

Flask APIs are available under `/api`, including:
- `POST /api/connect`
- `POST /api/disconnect`
- `GET /api/status`
- `POST /api/upload`
- `POST /api/print`
- `POST /api/print/bulk`
- `POST /api/void`
- `POST /api/change-pen/start`
- `POST /api/change-pen/finish`
- `POST /api/change-pen` (body mode: `start` or `finish`)
- `POST /api/reset`
- `POST /api/pen-max-distance` (set pen max distance meters without resetting distance)
- `POST /api/capture/request`
- `POST /api/capture`
- `GET /api/capture/latest`
- `GET /api/capture/latest/image`
- `GET /api/requests/{request_id}`
- `GET /api/requests?count=10`
- `GET /api/health`
- `GET /api/config`
- `GET /api/serial-ports` (lists USB/COM devices via pyserial; used by Configuration “Scan ports”)

### Capture integration environment variables (Flask)

- `CAPTURE_RESET_URL` (required for `POST /api/capture/request`)
- `CAPTURE_RESET_TOKEN` (optional bearer token)
- `CAPTURE_RESET_TIMEOUT_SECONDS` (optional, default `8.0`)
- `CAPTURE_RESET_METHOD` (optional, default `POST`)

## Run CLI

```bash
python -m PythonVersion.main --help
```

Examples:

```bash
python -m PythonVersion.main connect --com-port /dev/ttyUSB0 --baud-rate 250000
python -m PythonVersion.main status
python -m PythonVersion.main generate --svg ./signature.svg --print-request-json '{"scale":1,"rotation":0,"invertY":true}'
python -m PythonVersion.main print --svg ./signature.svg --print-request-json ./print_request.json --auto-connect
python -m PythonVersion.main bulk-print --svg ./signature.svg --print-request-json ./print_request.json --copies 3 --auto-connect
python -m PythonVersion.main distance-stats
python -m PythonVersion.main reset-distance
python -m PythonVersion.main set-pen-max-distance --meters 2.5
python -m PythonVersion.main pen-change-start --auto-connect
python -m PythonVersion.main pen-change-finish --auto-connect
python -m PythonVersion.main print-with-approval --signature-svg ./signature.svg --request-json ./approval_request.json --paper-image ./paper.jpg --auto-connect
python -m PythonVersion.main get-request --request-id 11111111-1111-1111-1111-111111111111
```

`generate` now includes `svgTotalDistanceMm`, and print responses include:
- `svg_total_distance_mm` (planned SVG travel)
- `executed_distance_mm` (actual executed SVG travel)
- `execution_percent` (actual/plan, excludes reset/eject commands)
- `cumulative_distance_mm` (persisted total across jobs, reset with `reset-distance`)
- `status` includes `remaining_pen_percent`, computed as:
  - `((max_pen_distance_m - (cumulative_distance_mm / 1000)) / max_pen_distance_m) * 100`

## Linux Ubuntu notes

- Serial ports are typically `/dev/ttyUSB0` or `/dev/ttyACM0` (not `COM5`).
- Add your user to `dialout` so Python can access serial devices:

```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

- Confirm the printer device:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

- Update port settings in command arguments or in config loading.

## Ubuntu release with systemd

Release/deployment assets are included:

- Service template: `PythonVersion/deploy/ubuntu/diwan-signature-flask.service`
- Environment template: `PythonVersion/deploy/ubuntu/diwan-signature.env.example`
- Full step-by-step guide: `PythonVersion/UBUNTU_RELEASE_GUIDE.md`

Quick start:

```bash
sudo cp PythonVersion/deploy/ubuntu/diwan-signature-flask.service /etc/systemd/system/diwan-signature-flask.service
sudo mkdir -p /etc/diwan-signature
sudo cp PythonVersion/deploy/ubuntu/diwan-signature.env.example /etc/diwan-signature/diwan-signature.env
sudo systemctl daemon-reload
sudo systemctl enable diwan-signature-flask
sudo systemctl start diwan-signature-flask
```

## Config source

`dependency_injection.py` attempts to read defaults from `UUNATEK.API/appsettings.json` if present, then builds Python service instances from those values.

## Current parity scope

- Approval behavior uses mock approval service.
- Request logs are stored in memory only (no SQL persistence).
- Core printer protocol and SVG conversion logic follow the C# implementation.

