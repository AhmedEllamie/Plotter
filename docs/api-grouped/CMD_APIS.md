# CMD APIs (`/api/cmd/*`)

The `cmd` group contains action/execution endpoints only.

## `GET /api/cmd/health`
- Purpose: service health snapshot.
- Response data:
  - `printerConnected`
  - `printerBusy`
  - `captureResetConfigured`

## `GET /api/cmd/status`
- Purpose: current printer runtime status.
- Response data: full printer status model.

## `POST /api/cmd/print`
- Purpose: print one SVG payload or previously uploaded SVG.
- Typical inputs:
  - `printRequest` object in JSON, form, or multipart flow.
- Response data:
  - `svgFileName`, `commandCount`, `result`, `status`.

## `POST /api/cmd/print/bulk`
- Purpose: print multiple copies.
- Typical inputs:
  - print payload + `copies` (1..100).
- Response data:
  - `svgFileName`, `copies`, `commandCount`, `result`, `bulkProgress`, `status`.

## `POST /api/cmd/bulk/stop`
- Purpose: request stop for active bulk print job.
- Response data:
  - updated `status`.

## `POST /api/cmd/void`
- Purpose: execute void/eject-safe sequence without drawing.
- Response data:
  - printer void operation result.
