from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.api.schemas import MarketingRequest
from app.core.circlo_client import CircloClient
import asyncio

router = APIRouter(prefix="/marketing", tags=["marketing"])


@router.post("/generate")
async def generate_marketing_workflow(req: MarketingRequest):
    """Generate a simple role-based marketing workflow (planner, copywriter, designer, scheduler).
    If register_agents=True, attempt to create agents on Circlo for each role and return their IDs.
    """
    steps = [
        {"role": "planner", "task": f"Define audience, channels, KPIs for goal: {req.goal}"},
        {"role": "copywriter", "task": "Draft 3 ad copies and email subject lines"},
        {"role": "designer", "task": "Create 2 hero images / social assets"},
        {"role": "scheduler", "task": "Create posting schedule and calendar invites"},
    ]

    agents_created = []
    if req.register_agents:
        client = CircloClient()
        try:
            for s in steps:
                payload = {
                    "name": f"{s['role'].title()} for {req.user_id or 'campaign'}",
                    "username": f"{s['role']}-{int(asyncio.get_event_loop().time())}",
                    "niche": "Marketing",
                    "avatar_url": "https://ui-avatars.com/api/?name=Agent&background=0D8ABC&color=fff",
                    "endpoint": "",
                }
                resp = await client.create_agent(payload)
                agents_created.append(resp)
        finally:
            await client.close()

    return JSONResponse(content={"workflow": steps, "agents": agents_created})
