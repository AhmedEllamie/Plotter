#!/usr/bin/env bash
# Rewrite install paths in systemd/desktop templates (in place).
set -euo pipefail

PLOTTER_INSTALL_ROOT="${PLOTTER_INSTALL_ROOT:-/opt/Automated_Signature/plotter-signature}"
A4_INSTALL_ROOT="${A4_INSTALL_ROOT:-/opt/Automated_Signature/a4-flating}"
A4_SERVICE_USER="${A4_SERVICE_USER:-diwan}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

plotter_only=false
scanner_only=false
user_kiosk_only=false
for arg in "$@"; do
  case "$arg" in
    --plotter-only) plotter_only=true ;;
    --scanner-only) scanner_only=true ;;
    --user-kiosk-only) user_kiosk_only=true ;;
  esac
done

if ! $plotter_only && ! $scanner_only && ! $user_kiosk_only; then
  plotter_only=true
  scanner_only=true
  user_kiosk_only=true
fi

replace_plotter_paths() {
  local file="$1"
  sed -i \
    -e "s|/opt/Automated_Signature/plotter-signature|${PLOTTER_INSTALL_ROOT}|g" \
    -e "s|/opt/plotter-signature|${PLOTTER_INSTALL_ROOT}|g" \
    "$file"
}

replace_a4_paths() {
  local file="$1"
  sed -i \
    -e "s|/opt/Automated_Signature/a4-flating|${A4_INSTALL_ROOT}|g" \
    -e "s|/opt/a4-flating|${A4_INSTALL_ROOT}|g" \
    -e "s|^User=.*|User=${A4_SERVICE_USER}|" \
    "$file"
}

if $plotter_only; then
  replace_plotter_paths plotter-signature-flask.service
fi

if $scanner_only; then
  a4_unit="${A4_INSTALL_ROOT}/deploy/ubuntu/scanner-service.service"
  if [[ -f "$a4_unit" ]]; then
    replace_a4_paths "$a4_unit"
    echo "Patched ${a4_unit}"
  else
    echo "WARN: scanner unit not found at ${a4_unit}" >&2
    echo "      Clone a4-flating or set A4_INSTALL_ROOT." >&2
  fi
fi

if $user_kiosk_only; then
  replace_plotter_paths plotter-pen-kiosk.service
  replace_plotter_paths plotter-pen-kiosk.desktop
fi

echo "PLOTTER_INSTALL_ROOT=${PLOTTER_INSTALL_ROOT}"
echo "A4_INSTALL_ROOT=${A4_INSTALL_ROOT}"
echo "A4_SERVICE_USER=${A4_SERVICE_USER}"
