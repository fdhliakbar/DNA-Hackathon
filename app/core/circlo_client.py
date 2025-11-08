# ...existing code...
import httpx
import logging
from .config import settings

logger = logging.getLogger(__name__)

class CircloClient:
    def __init__(self, base_url: str = None, token: str = None, timeout: float = 10.0):
        # ensure base_url is a plain string (settings.CIRCLO_BASE_URL may be a pydantic AnyHttpUrl)
        self.base_url = str(base_url) if base_url else str(settings.CIRCLO_BASE_URL)
        # prefer explicit token param, fallback to settings
        self.token = token or settings.CIRCLO_TOKEN
        self._timeout = timeout

        # Build Authorization header robustly: if token already contains 'Bearer ' prefix, don't double-prefix
        if isinstance(self.token, str) and self.token.lower().startswith("bearer "):
            auth_value = self.token
        else:
            auth_value = f"Bearer {self.token}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"Authorization": auth_value},
        )

    async def _request(self, method: str, path: str, params: dict | None = None, json: dict | None = None):
        try:
            resp = await self._client.request(method, path, params=params, json=json)
            resp.raise_for_status()
            # try parse JSON, otherwise return text
            try:
                return {"status_code": resp.status_code, "data": resp.json()}
            except Exception:
                return {"status_code": resp.status_code, "data": resp.text}
        except httpx.HTTPStatusError as e:
            # return structured error for router to convert to HTTPException
            content = None
            try:
                content = e.response.json()
            except Exception:
                content = e.response.text
            # log upstream response body for debugging
            logger.error("Circlo HTTPStatusError %s %s", e.response.status_code, content)
            return {"status_code": e.response.status_code, "error": content}
        except Exception as e:
            logger.exception("Circlo request failed: %s", e)
            return {"status_code": 502, "error": str(e)}

    async def get_user_preferences(self, user_id: str):
        return await self._request("GET", f"/api/user-preferences/user/{user_id}")

    async def get_all_user_preferences(self, page: int = 1, limit: int = 10):
        return await self._request("GET", "/api/user-preferences", params={"page": page, "limit": limit})

    async def get_posts_by_keywords(self, keywords: str, page: int = 1, limit: int = 10):
        return await self._request("GET", "/api/posts/by-keywords", params={"keywords": keywords, "page": page, "limit": limit})

    async def create_post(self, payload: dict):
        return await self._request("POST", "/api/user-preferences/recommend/create-post", json=payload)

    async def create_agent(self, payload: dict):
        return await self._request("POST", "/api/profiles/agent", json=payload)

    async def update_agent(self, agent_id: str, payload: dict):
        """Update an existing agent. Uses PATCH against the agent resource."""
        # Try PATCH first; some APIs expect PUT for full updates.
        patch_resp = await self._request("PATCH", f"/api/profiles/agent/{agent_id}", json=payload)
        status = patch_resp.get("status_code", 0)
        if status in (404, 405):
            # fallback to PUT
            logger.info("PATCH not supported, retrying with PUT for agent %s", agent_id)
            put_resp = await self._request("PUT", f"/api/profiles/agent/{agent_id}", json=payload)
            return put_resp
        return patch_resp

    async def close(self):
        await self._client.aclose()
# ...existing code...