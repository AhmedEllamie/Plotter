# Plotter Signature API Documentation

This site is generated with Doxygen from the markdown files under:

- `docs/api-pre-security`

## Scope

- Flask endpoints under `/api/*`
- FastAPI printer endpoints under `/printer/*`
- Request/response examples and notes for local integration

## Authentication

All protected endpoints require the API key header:

- `X-API-Key: <PLOTTER_API_KEY>`

The server key is configured through:

- `PLOTTER_API_KEY`

## Navigation

- Use the sidebar tree to browse each endpoint page.
- Use the search box to quickly locate paths like `/api/print` or `/api/status`.
