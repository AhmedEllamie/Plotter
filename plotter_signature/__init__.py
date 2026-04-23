"""Plotter Signature - printer automation package.

Layered architecture:

- `domain` : pure data contracts and value objects.
- `services` : application-level business services.
- `infrastructure` : cross-cutting stores, security, and adapters.
- `web` : HTTP delivery surfaces (Flask UI/API, FastAPI).
- `desktop` : native operator kiosk UIs.
"""

__version__ = "1.0.0"

