from pathlib import Path


OPENAI_API_KEY_PATH = Path.home() / ".openai.stephanos.key"


def load_api_key() -> str:
    """Load the Stephanos-specific OpenAI API key."""
    if not OPENAI_API_KEY_PATH.exists():
        raise FileNotFoundError(f"API key file not found: {OPENAI_API_KEY_PATH}")
    return OPENAI_API_KEY_PATH.read_text().strip()
