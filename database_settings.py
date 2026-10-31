"""Resolve nonsecret connection metadata consistently for Python and shell tools."""

import os
from pathlib import Path

KEYS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_EXPECTED_SERVER_MAJOR")
ALIASES = dict(zip(KEYS[:4], ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")))


def read_profile(path):
    values = {}
    if not path.exists():
        return values
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in KEYS or not value or key in values:
            raise ValueError(f"Invalid nonsecret database profile line {number}")
        values[key] = value
    return values


def resolve(legacy=None, *, environ=None, home=None):
    env = os.environ if environ is None else environ
    path = Path(env.get("STEPHANOS_DATABASE_CONFIG") or
                (Path.home() if home is None else Path(home)) /
                ".config/stephanos/database.conf")
    if env.get("STEPHANOS_DATABASE_CONFIG") and not path.is_file():
        raise ValueError("Explicit database profile does not exist")
    profile = read_profile(path)
    legacy = legacy or {}
    defaults = {"DB_PORT": 5432, "DB_NAME": "stephanos", "DB_USER": "stephanos"}
    result = {}
    for key in KEYS:
        result[key] = (env.get(key) or env.get(ALIASES.get(key, "")) or
                       profile.get(key) or legacy.get(key) or defaults.get(key))
    result["DB_PORT"] = int(result["DB_PORT"])
    if not 0 < result["DB_PORT"] < 65536:
        raise ValueError("Invalid database port")
    if result["DB_EXPECTED_SERVER_MAJOR"]:
        result["DB_EXPECTED_SERVER_MAJOR"] = int(result["DB_EXPECTED_SERVER_MAJOR"])
    return result
