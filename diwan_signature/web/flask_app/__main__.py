from __future__ import annotations

from diwan_signature.web.flask_app.app import app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
