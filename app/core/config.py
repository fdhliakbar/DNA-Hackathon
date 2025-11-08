# ...existing code...
import os
import logging
from pydantic import BaseModel, AnyHttpUrl

# optional: load .env if python-dotenv available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

class Settings(BaseModel):
    CIRCLO_BASE_URL: AnyHttpUrl = "https://api.getcirclo.com"
    # token can be provided as CIRCLO_TOKEN or CIRCLO_API_TOKEN in .env
    CIRCLO_TOKEN: str = ""


def _get_token_from_env() -> str:
    # prefer CIRCLO_TOKEN, fallback to CIRCLO_API_TOKEN
    token = os.getenv("CIRCLO_TOKEN") or os.getenv("CIRCLO_API_TOKEN") or ""
    if not token:
        logger.warning("No Circlo token found in environment (CIRCLO_TOKEN or CIRCLO_API_TOKEN)")
        return ""

    # If the token was stored as "Bearer <token>", strip the prefix to keep a clean token value
    if isinstance(token, str) and token.lower().startswith("bearer "):
        return token.split(None, 1)[1].strip()

    return token.strip()


settings = Settings(
    CIRCLO_BASE_URL=os.getenv("CIRCLO_BASE_URL", "https://api.getcirclo.com"),
    CIRCLO_TOKEN=_get_token_from_env(),
)
