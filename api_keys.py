import os
from pathlib import Path


OPENAI_API_KEY_PATH = Path.home() / ".openai.stephanos.key"


def load_api_key() -> str:
    """Load the Stephanos-specific OpenAI API key."""
    for env_name in ("STEPHANOS_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(env_name)
        if value:
            return value.strip()

    for env_name in ("STEPHANOS_OPENAI_API_KEY_FILE", "OPENAI_API_KEY_FILE"):
        value = os.environ.get(env_name)
        if value:
            path = Path(value).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"API key file not found: {path}")
            return path.read_text().strip()

    if not OPENAI_API_KEY_PATH.exists():
        raise FileNotFoundError(f"API key file not found: {OPENAI_API_KEY_PATH}")
    return OPENAI_API_KEY_PATH.read_text().strip()
