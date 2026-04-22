import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_policy():
    with open(BASE_DIR / "data/policy_terms.json") as f:
        return json.load(f)


POLICY = load_policy()