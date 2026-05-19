# Ubuntu systemd templates

Templates assume the **meta-repo** layout:

| Service | Default install root |
|---------|----------------------|
| Plotter Flask + kiosk | `/opt/Automated_Signature/plotter-signature` |
| A4 scanner | `/opt/Automated_Signature/a4-flating` |

For a **standalone** clone use `/opt/plotter-signature` and `/opt/a4-flating` instead.

## Quick install (plotter)

```bash
cd /opt/Automated_Signature/plotter-signature   # your repo root

export PLOTTER_INSTALL_ROOT="/opt/Automated_Signature/plotter-signature"
./deploy/ubuntu/configure-units.sh

sudo cp deploy/ubuntu/plotter-signature-flask.service /etc/systemd/system/
sudo mkdir -p /etc/plotter-signature
sudo cp deploy/ubuntu/plotter-signature.env.example /etc/plotter-signature/plotter-signature.env
# edit env, appsettings.json (ComPort), then:
sudo systemctl daemon-reload
sudo systemctl enable --now plotter-signature-flask
```

## Quick install (scanner)

```bash
cd /opt/Automated_Signature/a4-flating

export A4_INSTALL_ROOT="/opt/Automated_Signature/a4-flating"
export A4_SERVICE_USER="diwan"    # user in video group
./deploy/ubuntu/configure-units.sh --scanner-only

sudo cp deploy/ubuntu/scanner-service.service /etc/systemd/system/a4-scanner.service
sudo cp deploy/ubuntu/a4-scanner.env.example /etc/default/a4-scanner
sudo systemctl daemon-reload
sudo systemctl enable --now a4-scanner
```

## User kiosk (after graphical login)

```bash
export PLOTTER_INSTALL_ROOT="/opt/Automated_Signature/plotter-signature"
./deploy/ubuntu/configure-units.sh --user-kiosk-only

mkdir -p ~/.config/systemd/user ~/.config/autostart
cp deploy/ubuntu/plotter-pen-kiosk.service ~/.config/systemd/user/
cp deploy/ubuntu/plotter-pen-kiosk.desktop ~/.config/autostart/
systemctl --user daemon-reload
systemctl --user enable --now plotter-pen-kiosk.service
```

See [docs/UBUNTU_RELEASE_GUIDE.md](../../docs/UBUNTU_RELEASE_GUIDE.md) for firewall, auto-login, serial, and troubleshooting.
