"""Load the sample videos and comments into Cosmos DB, once.

Run from the backend folder (with COSMOS_URI and COSMOS_KEY set in .env):
    python -m app.seed
"""
import json

from .config import load_settings
from .cosmos_store import CosmosStore
from .store import SEED_PATH


def main() -> None:
    settings = load_settings()
    if not settings.use_cosmos:
        raise SystemExit("Set COSMOS_URI and COSMOS_KEY in backend/.env first.")

    store = CosmosStore(settings.cosmos_uri, settings.cosmos_key, settings.cosmos_database)
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if store.seed(data):
        print("Loaded sample videos and comments into Cosmos DB.")
    else:
        print("The videos container already has data, so nothing was changed.")


if __name__ == "__main__":
    main()
