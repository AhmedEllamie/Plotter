# Ubuntu Release Guide (Flask UI + API)

This guide prepares the `plotter_signature` package for production-style deployment on Ubuntu using `systemd`.

## 1) Install OS packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

If you use USB serial printer access:

```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

## 2) Clone project and install Python dependencies

```bash
sudo mkdir -p /opt
cd /opt
# Standalone plotter repo:
sudo git clone https://github.com/AhmedEllamie/Plotter.git plotter-signature
# Or: full stack (plotter + scanner submodules) — then use .../Automated_Signature/plotter-signature
# git clone --recurse-submodules https://github.com/AhmedEllamie/Automated_Signature.git
sudo chown -R $USER:$USER /opt/plotter-signature
cd /opt/plotter-signature

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Create runtime environment file

```bash
sudo mkdir -p /etc/plotter-signature
sudo cp deploy/ubuntu/plotter-signature.env.example /etc/plotter-signature/plotter-signature.env
sudo nano /etc/plotter-signature/plotter-signature.env
```

At minimum set:

- `PLOTTER_API_KEY` to a long random shared secret. **This variable is mandatory** — the Flask service refuses to start (`RuntimeError`) if it is unset or blank, and every `/api/*` request must send the matching value as `X-API-Key`. Changing the key after deployment: edit the env file, `sudo systemctl restart plotter-signature-flask`, then update browsers/kiosk/integration clients.
- `CAPTURE_RESET_URL` to your reset endpoint.
- Optional `PLOTTER_SERIAL_DEVICE_MATCH` to a stable USB serial identifier for the plotter, such as `CH340`, `CP210x`, or `VID:PID=1A86:7523`.

Serial scan/check/connect/disconnect config APIs are removed. Use the Desktop App local USB panel or CLI direct serial flow instead. The CLI scans Ubuntu `/dev/ttyUSB*` and `/dev/ttyACM*` devices, matches `PLOTTER_SERIAL_DEVICE_MATCH` / `--device-match` against USB metadata (`device`, `name`, `description`, `manufacturer`, `hwid`), and opens the matching plotter directly.

```bash
python -m plotter_signature.cli scan-serial --device-match "CH340"
python -m plotter_signature.cli connect --device-match "CH340"
python -m plotter_signature.cli disconnect
```

The Desktop App uses the same direct serial resolver for its local USB connect/disconnect controls.

Unless you are on a machine **without** USB serial hardware (or CI), rely on the default: **AutoConnect runs once** when Flask/FastAPI start (same as `POST /api/config/auto-connect` with `{}`; failures are logged and the service still listens). To **disable** that probing, set **`AUTO_CONNECT_ON_STARTUP`** to `0`, `false`, `no`, or `off`.

If scanner integration is used, also set:

- `SCANNER_SERVICE_BASE_URL`
- `SCANNER_SERVICE_BEARER_TOKEN` (if required)

## 4) Install systemd service

```bash
sudo cp deploy/ubuntu/plotter-signature-flask.service /etc/systemd/system/plotter-signature-flask.service
```

Edit service user/group/path if needed:

```bash
sudo nano /etc/systemd/system/plotter-signature-flask.service
```

Important fields:

- `User` should be your deployment user (the example unit uses `root`; many sites override to a dedicated account).
- When not `root`, ensure **serial access**: user in **`dialout`** and the unit sets **`SupplementaryGroups=dialout`** (already present in the bundled service files).
- `WorkingDirectory` should be your repo path.
- `ExecStart` should point to that repo `.venv` Python.

## 5) Start and enable service

```bash
sudo systemctl daemon-reload
sudo systemctl enable plotter-signature-flask
sudo systemctl start plotter-signature-flask
sudo systemctl status plotter-signature-flask
```

## 6) Verify application

Local health check:

```bash
curl -H "X-API-Key: <PLOTTER_API_KEY>" http://127.0.0.1:5001/api/cmd/health
```

UI:

- `http://<SERVER_IP>:5001/`
- `http://<SERVER_IP>:5001/configuration`

## 7) Logs and troubleshooting

Follow logs:

```bash
sudo journalctl -u plotter-signature-flask -f
```

Common checks:

- Service does not start:
  - verify `WorkingDirectory` and `ExecStart` paths.
  - verify `.venv` exists and dependencies installed.
- Capture endpoints fail:
  - verify `CAPTURE_RESET_URL` and connectivity.
- Scanner endpoints fail:
  - verify scanner base URL/token in env file.
- Printer connect fails:
  - verify `/dev/ttyUSB0` or `/dev/ttyACM0`.
  - verify user/group has `dialout`.
  - see **USB serial permissions** below.

### USB serial permissions (`Permission denied`)

USB serial devices are usually owned by **`root:dialout`** with mode **`660`**. The account that runs Flask, the CLI, or the Desktop App must be able to read/write that node.

1. **One-time (persistent across reboot):** `sudo usermod -aG dialout <service_user>` then log out/in, or restart the service. Group membership is stored in `/etc/group`, not lost on reboot.
2. **systemd:** the bundled [`plotter-signature-flask.service`](../deploy/ubuntu/plotter-signature-flask.service) and [`plotter-pen-kiosk.service`](../deploy/ubuntu/plotter-pen-kiosk.service) include **`SupplementaryGroups=dialout`** so the service process receives the `dialout` group without relying on a login shell. After editing a unit: `sudo systemctl daemon-reload` and restart the service (user units: `systemctl --user daemon-reload`).
3. **Checks:** `ls -l /dev/ttyUSB* /dev/ttyACM*`; ensure another process is not holding the port (`sudo lsof /dev/ttyUSB0`).

The example Flask unit ships **`User=root`** (root bypasses `dialout`), but production often overrides **`User=`** to a non-root account; then **`dialout`** + **`SupplementaryGroups`** matter.

## 8) Update deployment (new release)

```bash
cd /opt/plotter-signature
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart plotter-signature-flask
```

## 9) Install fullscreen Pen Config kiosk app (Raspberry Pi)

This app is a native fullscreen UI for:
- status monitoring (including bulk status)
- changing pen (`PenDown` / `PenUp`)
- max pen distance input and distance reset

### 9.1 Install both startup methods

Use both methods for reliability:
- `systemd --user` service
- desktop autostart entry

```bash
mkdir -p ~/.config/systemd/user
cp deploy/ubuntu/plotter-pen-kiosk.service ~/.config/systemd/user/plotter-pen-kiosk.service

mkdir -p ~/.config/autostart
cp deploy/ubuntu/plotter-pen-kiosk.desktop ~/.config/autostart/plotter-pen-kiosk.desktop
```

### 9.2 Enable and start user service

```bash
systemctl --user daemon-reload
systemctl --user enable plotter-pen-kiosk.service
systemctl --user start plotter-pen-kiosk.service
systemctl --user status plotter-pen-kiosk.service
```

To keep user services active even when no session is open (optional):

```bash
sudo loginctl enable-linger $USER
```

### 9.3 Verify startup on login

1. Ensure Flask API service is running (`plotter-signature-flask` on port `5001`).
2. Log out and log in again.
3. Confirm kiosk app opens fullscreen automatically.
4. Press `F11` to toggle fullscreen for debugging; `Esc` opens exit confirmation.

### 9.4 Raspberry Pi HDMI / UX recommendations

- Use a resolution that matches your small HDMI panel native mode.
- Use system font scaling (if needed) so labels remain readable from operator distance.
- Keep Ubuntu auto-login enabled for dedicated kiosk devices.
- Avoid screen sleep/blanking in kiosk setup.

### 9.5 Kiosk troubleshooting

- Kiosk window does not open:
  - `systemctl --user status plotter-pen-kiosk.service`
  - `journalctl --user -u plotter-pen-kiosk.service -f`
- API errors in kiosk feedback area:
  - verify Flask service is reachable with API key header:
    - `curl -H "X-API-Key: <PLOTTER_API_KEY>" http://127.0.0.1:5001/api/health`
  - the kiosk reads `PLOTTER_API_KEY` from `/etc/plotter-signature/plotter-signature.env` on **every** request when that file exists and is readable by the logged-in user (`PLOTTER_API_KEY_FILE` overrides the path); otherwise it uses the `PLOTTER_API_KEY` environment variable from the user service.
  - after rotating the key in that file, **restart Flask** so the server picks up the new secret; the kiosk will pick it up on the next poll without restarting.
  - verify API key is set in `/configuration` page on the kiosk browser profile (browser UI only).
- Opens but not fullscreen:
  - use `F11` and check desktop environment fullscreen restrictions
