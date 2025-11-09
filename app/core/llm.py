import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
try:
    # modern SDK exposes OpenAI client class
    from openai import OpenAI as OpenAIClient  # type: ignore
except Exception:
    OpenAIClient = None  # type: ignore

try:
    import openai as openai_legacy
except Exception:
    openai_legacy = None


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        # support explicit organization/project id env var
        self.organization = os.getenv("OPENAI_ORGANIZATION") or os.getenv("OPENAI_ORG") or os.getenv("OPENAI_PROJECT_ID")
        self.model = model
        self._client = None
        self._uses_new_sdk = False
        # store last error (string) to help diagnostics
        self.last_error: Optional[str] = None

        if self.api_key and OpenAIClient:
            try:
                # instantiate the new SDK client; pass organization if provided
                if self.organization:
                    try:
                        # some SDK versions accept organization param in constructor
                        self._client = OpenAIClient(api_key=self.api_key, organization=self.organization)
                    except TypeError:
                        # fallback to passing only api_key and set org later via header param
                        self._client = OpenAIClient(api_key=self.api_key)
                else:
                    self._client = OpenAIClient(api_key=self.api_key)
                self._uses_new_sdk = True
            except Exception:
                logger.exception("Failed to initialize OpenAI OpenAIClient; will try legacy client")
                self._client = None

        if not self._uses_new_sdk and self.api_key and openai_legacy:
            try:
                openai_legacy.api_key = self.api_key
                # set organization for legacy client if provided
                org = self.organization
                if org:
                    try:
                        setattr(openai_legacy, "organization", org)
                    except Exception:
                        logger.debug("Could not set legacy openai.organization")
            except Exception:
                logger.exception("Failed to set legacy openai.api_key")

    def available(self) -> bool:
        return bool(self.api_key and (self._uses_new_sdk or openai_legacy))

    def _messages_to_text(self, messages: List[Dict[str, str]]) -> str:
        # Convert chat-format messages to a single textual prompt for Responses API.
        parts: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"[{role}] {content}")
        return "\n".join(parts)

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 300, temperature: float = 0.7) -> Optional[str]:
        """Send chat messages to the LLM.

        Supports the modern Responses API (preferred) and falls back to
        the legacy ChatCompletion interface when available.
        Returns the assistant reply string, or None if LLM not available.
        """
        if not self.available():
            logger.info("LLM not available; skipping chat")
            return None

        try:
            if self._uses_new_sdk and self._client:
                prompt = self._messages_to_text(messages)
                # modern Responses API uses max_output_tokens instead of max_tokens
                create_kwargs = dict(model=self.model, input=prompt, max_output_tokens=max_tokens, temperature=temperature)
                # include organization header if not set at client construction
                if getattr(self, "organization", None):
                    # some versions accept organization as kwarg; pass it if supported
                    try:
                        create_kwargs["organization"] = self.organization
                    except Exception:
                        pass
                resp = self._client.responses.create(**create_kwargs)
                # modern SDK provides output_text helper
                text = getattr(resp, "output_text", None)
                if text:
                    self.last_error = None
                    return text
                # fallback parse
                try:
                    outputs = getattr(resp, "output", None)
                    if outputs and isinstance(outputs, list) and outputs:
                        # each output may contain 'content' list with dicts
                        first = outputs[0]
                        content = first.get("content") if isinstance(first, dict) else None
                        if content and isinstance(content, list) and content:
                            # join any text fragments
                            parts = [c.get("text") for c in content if isinstance(c, dict) and c.get("type") == "output_text"]
                            if parts:
                                self.last_error = None
                                return "".join(parts)
                except Exception:
                    pass

            # legacy fallback (pre-1.0 openai package)
            if openai_legacy:
                resp = openai_legacy.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                text = resp.choices[0].message.content
                self.last_error = None
                return text

        except Exception as e:
            # record error for diagnostics and return None so callers can fallback
            try:
                self.last_error = str(e)
            except Exception:
                self.last_error = "LLM error"
            logger.exception("LLM chat failed: %s", e)
            return None


# Helper to create system prompt for persona and instructions
def build_system_prompt(persona: str = "You are Haruhi, a helpful assistant.") -> str:
    return persona + "\nRespond concisely and helpfully. If a user asks to perform an action (booking, searching), ask clarifying questions when necessary and provide options with prices and links when available." 

