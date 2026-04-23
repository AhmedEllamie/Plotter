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
sudo git clone <YOUR_REPO_URL> plotter-signature
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

- `PLOTTER_API_KEY` to a long random shared secret (required for all `/api/*` and `/printer/*` calls).
- `CAPTURE_RESET_URL` to your reset endpoint.

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

- `User` should be your deployment user.
- `Group` should usually be `dialout` for serial access.
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
curl -H "X-API-Key: <PLOTTER_API_KEY>" http://127.0.0.1:5001/api/health
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
  - verify API key is set in `/configuration` page on the kiosk browser profile.
- Opens but not fullscreen:
  - use `F11` and check desktop environment fullscreen restrictions
