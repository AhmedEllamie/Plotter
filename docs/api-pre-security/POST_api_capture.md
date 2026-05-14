# POST /api/capture (removed)

The live Flask route **`POST /api/config/capture`** (multipart / `imageBase64` / raw image upload) was **removed**.

Use **`POST /api/config/scanner/capture/oneshot`** or other scanner capture routes to populate the latest image, then **`GET /api/config/capture/latest`** / **`GET /api/config/capture/latest/image`** to read it.

See [API_REFERENCE.md](../API_REFERENCE.md) — Config — Capture.
