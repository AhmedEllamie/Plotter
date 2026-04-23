# Plotter Signature API Documentation

This site is generated with Doxygen from the markdown files under:

- `docs/api-grouped`

## Scope

- Flask grouped endpoints under `/api/cmd/*` and `/api/config/*` (legacy `/api/*` remains for compatibility)
- Group-first endpoint reference for command and configuration workflows

## Authentication

All protected endpoints require the API key header:

- `X-API-Key: <PLOTTER_API_KEY>`

The server key is configured through:

- `PLOTTER_API_KEY`

## Navigation

- Start from `Grouped Flask API Docs`.
- Open `CMD APIs` and `Config APIs` pages from the sidebar.
- Use search for paths like `/api/cmd/print` or `/api/config/scanner/capture/run`.
