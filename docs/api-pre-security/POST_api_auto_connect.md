# POST /api/config/auto-connect

> Removed. Use Desktop App / CLI direct serial connect instead.

## Behavior

Serial connect/disconnect config APIs were removed from Flask/FastAPI. The Desktop App and CLI now scan Ubuntu `/dev/ttyUSB*` / `/dev/ttyACM*`, match USB metadata (`device`, `name`, `description`, `manufacturer`, `hwid`), and open the plotter directly.

## What It Takes

- CLI example:
  - `python -m plotter_signature.cli scan-serial --device-match "CH340"`
  - `python -m plotter_signature.cli connect --device-match "CH340"`

## Response

- This HTTP route is no longer available.

## Error Response

- This HTTP route is no longer available.
