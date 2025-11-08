import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lightweight wrapper for OpenAI Chat completions. If OPENAI_API_KEY is not set,
# the helper returns None so callers can fallback to canned replies.
try:
    import openai
except Exception:
    openai = None


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        if self.api_key and openai:
            openai.api_key = self.api_key
        elif self.api_key and not openai:
            logger.warning("openai package not installed but OPENAI_API_KEY provided")

    def available(self) -> bool:
        return bool(self.api_key and openai)

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 300, temperature: float = 0.7) -> Optional[str]:
        """Send chat messages to the LLM. Messages should follow OpenAI chat format.

        Returns the assistant reply string, or None if LLM not available.
        """
        if not self.available():
            logger.info("LLM not available; skipping chat")
            return None
        try:
            resp = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = resp.choices[0].message.content
            return text
        except Exception as e:
            logger.exception("LLM chat failed: %s", e)
            return None


# Helper to create system prompt for persona and instructions
def build_system_prompt(persona: str = "You are Haruhi, a helpful assistant.") -> str:
    return persona + "\nRespond concisely and helpfully. If a user asks to perform an action (booking, searching), ask clarifying questions when necessary and provide options with prices and links when available." 

