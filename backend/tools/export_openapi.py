"""Export public API schemas only; never settings, keys or access tokens."""
from pathlib import Path
import json

from app.config import Settings
from app.main import create_app

if __name__ == "__main__":
    app = create_app(Settings(_env_file=None, environment="test"))
    output = Path(__file__).resolve().parents[2] / "docs/openapi.json"
    schema = app.openapi()
    output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Exported OpenAPI with {len(schema['paths'])} paths; no settings or credentials included")
