# Ubuntu Release Guide (Flask UI + API + Kiosk)

Production deployment on Ubuntu with **systemd**, for standalone **`/opt/plotter-signature`** or meta-repo **`/opt/Automated_Signature/plotter-signature`**.

Bundled templates default to the **meta-repo** paths. Adjust with `deploy/ubuntu/configure-units.sh` or edit units before `systemctl enable`.

| Component | Port | systemd unit |
|-----------|------|----------------|
| Plotter Flask | 5001 | `plotter-signature-flask` |
| Pen kiosk (GUI) | — | `plotter-pen-kiosk` (user) |
| A4 scanner (sibling repo) | 8008 | `a4-scanner` — see `a4-flating/UBUNTU_RELEASE_GUIDE.md` |

## 1) Install OS packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-tk git
```

- **`python3-tk`** — required for the pen kiosk (Tkinter).
- USB serial (plotter): `sudo usermod -aG dialout $USER` then log out/in.

## 2) Clone, ownership, and Python environment

**Do not use `sudo` for `python3 -m venv` or `pip install`** (avoids root-owned `.venv` and permission errors).

```bash
sudo mkdir -p /opt
cd /opt

# Option A — meta repo (plotter + scanner):
sudo git clone --recurse-submodules https://github.com/AhmedEllamie/Automated_Signature.git
sudo chown -R $USER:$USER /opt/Automated_Signature
cd /opt/Automated_Signature/plotter-signature

# Option B — standalone plotter only:
# sudo git clone https://github.com/AhmedEllamie/Plotter.git plotter-signature
# sudo chown -R $USER:$USER /opt/plotter-signature
# cd /opt/plotter-signature

export PLOTTER_INSTALL_ROOT="$(pwd)"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### Linux serial port (`appsettings.json`)

Default **`Printer.ComPort`** is empty so startup **AutoConnect** scans `/dev/ttyUSB*` and `/dev/ttyACM*`.

On Windows dev machines, set `"ComPort": "COM5"` (or your port) in `appsettings.json`.

After the plotter USB adapter appears:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
python -m plotter_signature scan-serial --device-match "CH340"
```

Optionally set `"ComPort": "/dev/ttyUSB0"` in `appsettings.json`, then restart Flask.

## 3) Runtime environment file

Run from the **plotter-signature** repo root (paths below assume meta-repo layout):

```bash
sudo mkdir -p /etc/plotter-signature
sudo cp deploy/ubuntu/plotter-signature.env.example /etc/plotter-signature/plotter-signature.env
sudo nano /etc/plotter-signature/plotter-signature.env
sudo chmod 644 /etc/plotter-signature/plotter-signature.env
```

Set at minimum:

- **`PLOTTER_API_KEY`** — mandatory; every `/api/*` request needs header **`X-API-Key`**.
- **`CAPTURE_RESET_URL`** — if capture flow is used.
- **`SCANNER_SERVICE_BASE_URL=http://127.0.0.1:8008`** and **`SCANNER_SERVICE_TOKEN`** — must match `/etc/default/a4-scanner` when using the scanner service.

Optional: **`PLOTTER_SERIAL_DEVICE_MATCH=CH340`** (CLI / device metadata). **`AUTO_CONNECT_ON_STARTUP=0`** disables serial probe at Flask start.

## 4) Install systemd units (paths)

```bash
cd /opt/Automated_Signature/plotter-signature   # or your install root
export PLOTTER_INSTALL_ROOT="$(pwd)"
./deploy/ubuntu/configure-units.sh --plotter-only

sudo cp deploy/ubuntu/plotter-signature-flask.service /etc/systemd/system/
sudo nano /etc/systemd/system/plotter-signature-flask.service   # verify User, paths
```

Important:

- **`WorkingDirectory`** and **`ExecStart`** must point at your repo **`.venv`** (same directory).
- **`User=root`** + **`SupplementaryGroups=dialout`** in the Flask unit is fine; if **`User=diwan`**, add `dialout` to that user.
- **`--host 0.0.0.0 --port 5001`** — required for LAN access.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now plotter-signature-flask
sudo systemctl status plotter-signature-flask
```

Confirm listen:

```bash
sudo ss -tlnp | grep 5001    # expect 0.0.0.0:5001
```

## 5) Firewall (LAN access from laptop / other PCs)

If **`ufw`** is active, allow services (recommended vs disabling firewall):

```bash
cd /opt/Automated_Signature/plotter-signature
chmod +x deploy/ubuntu/ufw-services.sh
./deploy/ubuntu/ufw-services.sh
```

Or manually:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 5001/tcp
sudo ufw allow 8008/tcp
sudo ufw enable
```

From another machine: `http://<ubuntu-ip>:5001/` and `curl -H "X-API-Key: <key>" http://<ubuntu-ip>:5001/api/cmd/health`.

## 6) Verify application

```bash
curl -H "X-API-Key: <PLOTTER_API_KEY>" http://127.0.0.1:5001/api/cmd/health
curl -H "X-API-Key: <PLOTTER_API_KEY>" http://127.0.0.1:5001/api/cmd/status
```

`printer_connected: true` requires plotter USB serial visible (`lsusb`, `/dev/ttyUSB*`) **before** Flask start; then `sudo systemctl restart plotter-signature-flask`.

## 7) Desktop auto-login (kiosk HDMI)

So the pen kiosk starts without a login password (SSH can still require a password):

```bash
sudo nano /etc/gdm3/custom.conf
```

```ini
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=diwan
```

Or **Settings → Users → Automatic Login**. Reboot and confirm the desktop loads.

## 8) Pen kiosk (user systemd + autostart)

The kiosk is a **GUI** on the Ubuntu monitor — not over SSH with X11 forwarding.

```bash
cd /opt/Automated_Signature/plotter-signature
export PLOTTER_INSTALL_ROOT="$(pwd)"
chmod +x deploy/ubuntu/configure-units.sh
./deploy/ubuntu/configure-units.sh --user-kiosk-only

mkdir -p ~/.config/systemd/user ~/.config/autostart
cp deploy/ubuntu/plotter-pen-kiosk.service ~/.config/systemd/user/
cp deploy/ubuntu/plotter-pen-kiosk.desktop ~/.config/autostart/
```

Edit the user unit if needed — **do not** add `SupplementaryGroups=dialout` (causes exit **216/GROUP**). Serial is opened by **Flask**, not the kiosk.

On the **local desktop** (or SSH with `XDG_RUNTIME_DIR` + `DBUS_SESSION_BUS_ADDRESS`):

```bash
systemctl --user daemon-reload
systemctl --user enable --now plotter-pen-kiosk.service
systemctl --user status plotter-pen-kiosk.service
```

Optional: `sudo loginctl enable-linger $USER`

Test Tk once: `python -m plotter_signature.desktop.pen_kiosk` from a terminal on the HDMI session.

## 9) Logs and troubleshooting

```bash
sudo journalctl -u plotter-signature-flask -f
journalctl --user -u plotter-pen-kiosk.service -f
```

| Symptom | Fix |
|---------|-----|
| **203/EXEC** or **200/CHDIR** | Wrong `ExecStart` / `WorkingDirectory`; run `configure-units.sh` |
| **`externally-managed-environment`** | Never `sudo pip`; use venv as normal user |
| **`No serial ports to try`** | Plotter USB not plugged / not in `lsusb`; fix hardware, restart Flask |
| **`could not open port COM5`** | Set `"ComPort": ""` or `/dev/ttyUSB0` in `appsettings.json` |
| Kiosk **Server unreachable** | Flask down or wrong IP; check `ss` and `ufw` |
| Kiosk **Plotter Disconnected** | `printer_connected: false` — serial not open (see Flask logs / AutoConnect) |
| **`216/GROUP`** on kiosk | Remove `SupplementaryGroups` from **user** kiosk unit |
| LAN cannot reach :5001 | `ufw allow 5001/tcp`; confirm `0.0.0.0:5001` |

### USB serial

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
sudo journalctl -u plotter-signature-flask | grep -i autoconnect
python -m plotter_signature scan-serial --device-match "CH340"
```

On Raspberry Pi, if CH340 appears in `lsusb` but no `ttyUSB*`: `sudo apt remove -y brltty`.

## 10) Update deployment

```bash
cd /opt/Automated_Signature/plotter-signature
git pull
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
sudo systemctl restart plotter-signature-flask
```

## 11) Full stack checklist

- [ ] Plotter: venv, `pip install -e .`, env file, Flask unit paths, `active`, `0.0.0.0:5001`
- [ ] Scanner: see `a4-flating/UBUNTU_RELEASE_GUIDE.md`, `curl :8008/health`
- [ ] `SCANNER_SERVICE_TOKEN` matches on plotter + scanner
- [ ] `ufw` allows 22 / 5001 / 8008 (or documented alternative)
- [ ] Auto-login + pen kiosk on HDMI
- [ ] Plotter USB → `printer_connected: true` after Flask restart

See also: `deploy/ubuntu/README.md`.
