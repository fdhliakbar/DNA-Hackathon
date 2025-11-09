from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import requests

router = APIRouter(prefix="/websearch", tags=["websearch"])

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
if not SERPAPI_KEY:
    # allow a fallback env name
    SERPAPI_KEY = os.getenv("SECHAPI_KEY") or os.getenv("SEARCH_API_KEY")


@router.post("/query")
async def query_search(request: Request):
    """Query a web-search provider (SerpApi) and return top results.

    Body: { "q": "search terms", "num": 3 }
    """
    body = await request.json()
    q = body.get("q")
    num = int(body.get("num", 3))
    if not q:
        raise HTTPException(status_code=400, detail="Missing 'q' in request body")

    if not SERPAPI_KEY:
        # fallback: return a mocked set (so system still works without key)
        mocked = []
        for i in range(num):
            mocked.append({"title": f"Mock Expert {i+1}", "link": f"https://example.com/expert/{i+1}", "snippet": f"Expert {i+1} profile"})
        return JSONResponse(content={"results": mocked})

    # Call SerpApi
    params = {"q": q, "api_key": SERPAPI_KEY, "num": num}
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        # extract organic results
        organic = data.get("organic_results") or data.get("organic") or []
        results = []
        for item in organic[:num]:
            results.append({
                "title": item.get("title") or item.get("position"),
                "link": item.get("link") or item.get("url"),
                "snippet": item.get("snippet") or item.get("snippet") or "",
            })
        return JSONResponse(content={"results": results})
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
