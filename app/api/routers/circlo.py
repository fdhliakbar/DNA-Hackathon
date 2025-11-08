# ...existing code...
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import AsyncGenerator
import logging
from app.core.circlo_client import CircloClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/circlo", tags=["circlo"])

async def get_circlo_client() -> AsyncGenerator[CircloClient, None]:
    # create client defensively so we can return a meaningful HTTP error if something fails
    try:
        client = CircloClient()
    except Exception as exc:
        logger.exception("Failed to create CircloClient: %s", exc)
        # raise HTTPException so FastAPI returns a JSON error instead of bare 500
        raise HTTPException(status_code=500, detail=f"Failed to initialize Circlo client: {exc}")

    try:
        yield client
    finally:
        try:
            await client.close()
        except Exception:
            logger.exception("Error closing Circlo client")

@router.get("/user-preferences/{user_id}")
async def read_user_preferences(user_id: str, client: CircloClient = Depends(get_circlo_client)):
    resp = await client.get_user_preferences(user_id)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]

@router.get("/user-preferences")
async def list_user_preferences(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
                                client: CircloClient = Depends(get_circlo_client)):
    resp = await client.get_all_user_preferences(page=page, limit=limit)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]

@router.get("/posts/by-keywords")
async def posts_by_keywords(keywords: str = Query(..., description="comma separated"), page: int = 1, limit: int = 10,
                            client: CircloClient = Depends(get_circlo_client)):
    resp = await client.get_posts_by_keywords(keywords=keywords, page=page, limit=limit)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]

@router.post("/posts/create")
async def create_post(payload: dict, client: CircloClient = Depends(get_circlo_client)):
    resp = await client.create_post(payload)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]

@router.post("/agents")
async def create_agent(payload: dict, client: CircloClient = Depends(get_circlo_client)):
    resp = await client.create_agent(payload)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]


@router.get("/_debug")
async def debug_info(client: CircloClient = Depends(get_circlo_client)):
    """Debug endpoint (dev only): show masked token presence and try a small upstream call.

    Returns:
      - token_masked: token with middle masked (or not set)
      - upstream: result of calling /api/user-preferences?page=1&limit=1 using the same client
    """
    token = getattr(client, "token", None)
    if not token:
        token_masked = None
    else:
        # mask token: keep first 4 and last 4 chars
        t = str(token)
        if len(t) > 8:
            token_masked = f"{t[:4]}...{t[-4:]}"
        else:
            token_masked = "****"

    # attempt a small upstream call using the same client to reproduce the error
    try:
        resp = await client.get_all_user_preferences(page=1, limit=1)
    except Exception as exc:
        # If an unexpected exception bubbles up, return its type/message for debugging
        import traceback
        tb = traceback.format_exc()
        return {"token_masked": token_masked, "upstream": {"status_code": 502, "error": str(exc), "trace": tb}}

    return {"token_masked": token_masked, "upstream": resp}
# ...existing code...