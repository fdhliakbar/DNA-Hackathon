# ...existing code...
from fastapi import APIRouter
from pydantic import BaseModel
from app.core.llm import LLMClient
from typing import List, Dict, Any
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx

from app.core.circlo_client import CircloClient

router = APIRouter()
llm = LLMClient()

APP_BASE = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")


class MessageIn(BaseModel):
    message: str
    user_id: str = "demo-user"


def next_tuesday_slot(tz: str = "Asia/Singapore") -> Dict[str, str]:
    """Compute next Tuesday 14:00-14:30 in given timezone and return ISO strings."""
    tzinfo = ZoneInfo(tz)
    now = datetime.now(tzinfo)
    # find next Tuesday (weekday=1 where Monday=0)
    days_ahead = (1 - now.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target = (now + timedelta(days=days_ahead)).replace(hour=14, minute=0, second=0, microsecond=0)
    start_iso = target.isoformat()
    end_iso = (target + timedelta(minutes=30)).isoformat()
    return {"start_iso": start_iso, "end_iso": end_iso}


async def execute_action(step: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Execute a single action by calling local sub-agent endpoints or Circlo API.

    The function expects the app to be reachable at APP_BASE_URL; set that env var in deployment
    if the service is not running on localhost:8000.
    """
    action = step.get("action")
    args = step.get("args", {}) or {}
    result: Dict[str, Any] = {"action": action, "ok": False, "details": None}

    async with httpx.AsyncClient(timeout=20.0) as hc:
        try:
            if action == "search_experts":
                query = args.get("query") or args.get("q") or "AI expert Singapore"
                resp = await hc.post(f"{APP_BASE}/websearch/query", json={"q": query, "num": 3})
                if resp.status_code == 200:
                    result["ok"] = True
                    result["details"] = resp.json().get("results", [])
                else:
                    result["details"] = {"status": resp.status_code, "text": resp.text}

            elif action == "schedule_meetings":
                attendees = args.get("attendees", [])
                start_iso = args.get("start_iso")
                end_iso = args.get("end_iso")
                # if times not provided, compute a default next-Tuesday slot
                if not (start_iso and end_iso):
                    slot = next_tuesday_slot()
                    start_iso = slot["start_iso"]
                    end_iso = slot["end_iso"]

                events = []
                for a in attendees:
                    ev_body = {"user_id": user_id, "summary": f"Intro meeting with {a}", "start_iso": start_iso, "end_iso": end_iso, "attendees": [a]}
                    try:
                        resp = await hc.post(f"{APP_BASE}/gcal/create-event", json=ev_body, timeout=20.0)
                        if resp.status_code in (200, 201):
                            events.append({"attendee": a, "status": "created", "resp": resp.json()})
                        else:
                            events.append({"attendee": a, "status": "failed", "status_code": resp.status_code, "text": resp.text})
                    except Exception as e:
                        events.append({"attendee": a, "status": "error", "error": str(e)})

                result["ok"] = True
                result["details"] = events

            elif action == "post_summary":
                summary = args.get("summary") or args.get("body") or "No summary provided"
                c = CircloClient()
                try:
                    post_resp = await c.create_post({"title": "Haruhi — Summary", "body": summary})
                    result["ok"] = post_resp.get("status_code", 500) in (200, 201)
                    result["details"] = post_resp
                finally:
                    try:
                        await c.close()
                    except Exception:
                        pass

            else:
                result["details"] = {"error": "unknown action"}

        except Exception as e:
            result["details"] = {"exception": str(e)}

    return result


def build_final_text(summary: str, execution_results: List[Dict[str, Any]]) -> str:
    parts = [f"Ringkasan: {summary}"]
    for er in execution_results:
        act = er.get("step", {}).get("action")
        parts.append(f"Action: {act}")
        parts.append(f"Result: {json.dumps(er.get('result', {}), ensure_ascii=False)}")
    return "\n\n".join(parts)


@router.post("/agents/haruhi/hook")
async def haruhi_hook(body: MessageIn):
    user_id = body.user_id or "demo-user"
    user_text = body.message.strip()

    # 1) Ask LLM to produce a structured plan (JSON)
    system_prompt = """
You are Haruhi, a concise, helpful Indonesian assistant that turns one user instruction into a small executable plan.
Return ONLY a JSON object matching this schema:

{
  "plan": [
    {"action": "search_experts", "args": {"query": "<query string>"}},
    {"action": "schedule_meetings", "args": {"attendees": ["email1","email2"], "start_iso":"...", "end_iso":"..."}},
    {"action": "post_summary", "args": {"summary":"..."}}
  ],
  "summary": "short Indonesian sentence summarizing what you will do"
}

If the user input is a simple greeting, return:
{"greeting": "Halo... (Indonesian greeting text)"}

Respond only with valid JSON. Do not include any additional text.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]

    # ask LLM for a plan
    plan_text = llm.chat(messages)
    # if the LLM client returned no text, include diagnostic if available
    if not plan_text:
        err = getattr(llm, "last_error", None)
        if err:
            # do not expose secrets; provide actionable hint
            return {"response": f"Haruhi: LLM tidak tersedia (error: {err}). Silakan periksa konfigurasi OPENAI_API_KEY dan OPENAI_PROJECT_ID."}
        return {"response": f"Haruhi di sini — saya menerima pesan Anda: {user_text}"}

    parsed = None
    try:
        parsed = json.loads(plan_text) if plan_text else None
    except Exception:
        # retry once asking for strict JSON
        retry_msgs = messages + [{"role": "assistant", "content": plan_text or ""}, {"role":"system","content":"Previous response was not valid JSON. Please respond ONLY with valid JSON that matches the schema exactly."}]
        try:
            plan_text = llm.chat(retry_msgs)
            parsed = json.loads(plan_text) if plan_text else None
        except Exception:
            parsed = None

    if not parsed:
        # fallback: return a friendly acknowledgement
        return {"response": f"Haruhi di sini — saya menerima pesan Anda: {user_text}"}

    if "greeting" in parsed:
        return {"response": parsed["greeting"]}

    plan = parsed.get("plan", [])
    summary = parsed.get("summary", "Saya akan membantu menyelesaikan permintaan Anda.")

    # 2) Execute each step synchronously and collect results
    execution_results = []
    for step in plan:
        res = await execute_action(step, user_id)
        execution_results.append({"step": step, "result": res})

    # 3) Build a plain summary of results (structured)
    final_structured = build_final_text(summary, execution_results)

    # 4) Ask LLM to render a polished Indonesian confirmation message including CTAs
    polish_system = "You are Haruhi, an Indonesian assistant. Rephrase the following execution summary into a friendly, professional Indonesian confirmation message. Include clear CTAs for the user to verify calendar invites and next steps. Keep it concise (3-6 sentences)."
    polish_msgs = [
        {"role": "system", "content": polish_system},
        {"role": "user", "content": final_structured}
    ]

    try:
        polished_reply = llm.chat(polish_msgs)
    except Exception:
        polished_reply = final_structured

    # return polished reply and execution details (CTA links included in polished text if any)
    return {"response": polished_reply, "details": execution_results}