#!/usr/bin/env bash
# Allow LAN access to plotter Flask, scanner HTTP, and SSH. Keeps ufw enabled.
set -euo pipefail

sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 5001/tcp comment 'plotter-signature-flask'
sudo ufw allow 8008/tcp comment 'a4-scanner'
sudo ufw --force enable
sudo ufw reload
sudo ufw status
