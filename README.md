# Diwan Signature

Printer automation for the Diwan signature workflow. The project exposes the same service graph through three delivery surfaces - Flask (UI + REST), FastAPI (REST only), and a CLI - and ships with a Tkinter-based operator kiosk.

## Repository layout

```
.
├── diwan_signature/           # Main Python package
│   ├── __init__.py
│   ├── __main__.py            # `python -m diwan_signature`
│   ├── cli.py                 # Command-line entrypoint
│   ├── dependency_injection.py
│   ├── domain/                # Pure contracts and value objects
│   ├── services/              # Business services (printer, approval, print_approval)
│   ├── infrastructure/        # Stores and security adapters
│   │   ├── security/
│   │   └── stores/
│   ├── web/                   # HTTP delivery surfaces
│   │   ├── flask_app/         # Flask UI + /api/*
│   │   └── fastapi_app/       # FastAPI /printer/*
│   └── desktop/               # Tkinter pen config kiosk
├── deploy/ubuntu/             # systemd units and env templates
├── docs/                      # Design docs, API reference, Doxygen config
│   ├── api-pre-security/
│   └── doxygen/
├── samples/                   # Sample SVGs and print-request JSON
├── appsettings.json           # Optional runtime defaults
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Architecture

Layered, single-direction dependencies from top to bottom:

- `web`, `desktop`, `cli` depend on `services`.
- `services` depend on `domain` and `infrastructure`.
- `infrastructure` depends on `domain`.
- `domain` depends on nothing else in the package.

## Install

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or install as an editable package:

```bash
pip install -e .
```

## Run

CLI help:

```bash
python -m diwan_signature --help
```

Flask UI + API (port 5001):

```bash
python -m diwan_signature serve-flask --host 0.0.0.0 --port 5001
```

Open:

- `http://localhost:5001/` - operator UI
- `http://localhost:5001/configuration` - connection and API key

FastAPI printer endpoints (port 5000):

```bash
python -m diwan_signature serve-api --host 0.0.0.0 --port 5000
```

Pen config kiosk (Linux/X11):

```bash
python -m diwan_signature.desktop.pen_kiosk
```

## Authentication

All HTTP APIs require a shared API key:

- Server: set `PLOTTER_API_KEY=<secret>`
- Clients: send header `X-API-Key: <same-secret>`

## Configuration

Optional defaults can be set in `appsettings.json` at the repo root:

```json
{
  "Printer": { "ComPort": "COM5", "BaudRate": 250000 },
  "PrintRetry": { "MaxRetries": 3, "RetryDelayMs": 1000 },
  "ApprovalService": {
    "Endpoint": "",
    "ApiKey": "",
    "TimeoutSeconds": 30,
    "UseMockService": true
  }
}
```

Additional runtime environment variables are documented in `docs/TECHNICAL_DOCUMENTATION.md` and `deploy/ubuntu/diwan-signature.env.example`.

## Documentation

- Deployment: `docs/UBUNTU_RELEASE_GUIDE.md`
- Technical reference: `docs/TECHNICAL_DOCUMENTATION.md`
- Scanner HTTP integration: `docs/FLASK_SCANNER_HTTP_INTEGRATION.md`
- Pen change command: `docs/CHANGE_PEN_COMMAND.md`
- API reference (markdown): `docs/api-pre-security/`
- Generate HTML docs site: `doxygen docs/doxygen/Doxyfile` -> `docs/generated/html/index.html`
