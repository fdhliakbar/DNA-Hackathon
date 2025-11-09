from pydantic import BaseModel
from typing import List


class SendOAuthPayload(BaseModel):
    user_id: str
    message: str | None = None


class MarketingRequest(BaseModel):
    goal: str
    user_id: str | None = None
    register_agents: bool = False
