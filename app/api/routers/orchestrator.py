from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio
import re
from typing import Dict, Any
import httpx

from app.core import memory
from app.core.circlo_client import CircloClient
from app.api.routers.circlo import get_circlo_client
from app.core.config import settings

# coordinator/agent name (who orchestrates)
COORDINATOR_NAME = "Haruhi Agent - Super Agent"

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


async def _search_flights(destination: str, when: str) -> Dict[str, Any]:
    # Mocked flight search - in real integration call an API
    await asyncio.sleep(0.2)
    return {
        "provider": "MockAir",
        "price": "Rp 3.200.000",
        "route": f"Jakarta -> {destination}",
        "details_url": f"https://travel.example/flights?to={destination}&when={when}",
    }


async def _search_hotels(destination: str, when: str, nights: int = 1) -> Dict[str, Any]:
    # Mocked hotel search
    await asyncio.sleep(0.2)
    return {
        "provider": "MockLodging",
        "price": "Rp 1.650.000 / malam",
        "name": f"{destination} Seaside Hotel",
        "details_url": f"https://travel.example/hotels?at={destination}&when={when}",
    }


def _parse_intent(message: str) -> Dict[str, Any]:
    m = message.lower()
    wants_flight = any(k in m for k in ("flight", "pesawat", "terbang"))
    wants_hotel = any(k in m for k in ("hotel", "penginapan", "kamar", "booking"))
    # rough date extraction - look for 'besok' or next week
    when = "besok" if "besok" in m else "next week" if "next week" in m or "minggu depan" in m else "soon"
    dest_match = re.search(r"bali|ubud|kuta|seminyak|canggu|nusa dua", m)
    destination = dest_match.group(0).title() if dest_match else "Bali"
    return {"flight": wants_flight, "hotel": wants_hotel, "destination": destination, "when": when}


@router.post("/execute", response_class=HTMLResponse)
async def orchestrate(request: Request, client: CircloClient = None):
    """High-level orchestrator: accept a natural-language command, break into subtasks,
    spawn helper agents, persist results to memory, and return an aggregated HTML result
    with CTA links for user to proceed to external booking pages.
    """
    payload = await request.json()
    message = payload.get("message", "")
    user = payload.get("user", {})
    user_id = user.get("id") or user.get("name") or "anon"

    intent = _parse_intent(message)
    destination = intent["destination"]
    when = intent["when"]

    # allow caller to request auto-scheduling of quick meetings
    body_auto = (await request.json())
    auto_schedule = bool(body_auto.get("auto_schedule", False))

    tasks = []
    if intent["flight"]:
        tasks.append(_search_flights(destination, when))
    if intent["hotel"]:
        tasks.append(_search_hotels(destination, when))

    # run helpers concurrently
    results = await asyncio.gather(*tasks)

    # If the message asks to 'find experts' we'll try to call the websearch sub-agent
    experts = []
    if "expert" in message.lower() or "ai expert" in message.lower() or "find 3" in message.lower():
        try:
            async with httpx.AsyncClient(timeout=10.0) as hc:
                resp = await hc.post(f"http://127.0.0.1:8000/websearch/query", json={"q": "AI expert Singapore", "num": 3})
                if resp.status_code == 200:
                    experts = resp.json().get("results", [])
        except Exception:
            experts = []

    # persist a simple booking record in memory
    memory.init_db()
    memory.save_booking(user_id, "itinerary", str(results))

    # If auto_schedule requested and user has gcal credentials, try to create events for each expert
    if auto_schedule and experts:
        creds_json = memory.get_pref(user_id, "gcal_credentials")
        if creds_json:
            # schedule simple 30-min events (no attendees) as placeholders
            try:
                async with httpx.AsyncClient(timeout=15.0) as hc:
                    for i, e in enumerate(experts):
                        summary = f"Intro: {e.get('title', 'Expert') }"
                        start_iso = body_auto.get("start_iso") or None
                        end_iso = body_auto.get("end_iso") or None
                        # if not provided, skip scheduling precise time
                        if not (start_iso and end_iso):
                            continue
                        ev_body = {"user_id": user_id, "summary": summary, "start_iso": start_iso, "end_iso": end_iso}
                        try:
                            await hc.post(f"http://127.0.0.1:8000/gcal/create-event", json=ev_body)
                        except Exception:
                            pass
            except Exception:
                pass

    # Build HTML response summarizing the actions
    html = ["<html><head><meta charset='utf-8'><title>Super Agent Result</title></head><body style='font-family:Arial,Helvetica,sans-serif;padding:20px;'>"]
    html.append(f"<h2>{COORDINATOR_NAME} — Hasil untuk: {message}</h2>")
    html.append(f"<p>Koordinator: <strong>{COORDINATOR_NAME}</strong></p>")
    html.append("<p>Berikut ringkasan yang saya temukan. Klik tombol untuk membuka detail di platform eksternal.</p>")

    # show spawned helper agents
    helper_agents = [
        {"name": "FlightFinder", "role": "search and compare flights"},
        {"name": "HotelFinder", "role": "search and compare hotels"},
    ]
    html.append("<p><strong>Spawned helper agents:</strong></p>")
    html.append("<ul>")
    for ha in helper_agents:
        html.append(f"<li><strong>{ha['name']}</strong>: {ha['role']}</li>")
    html.append("</ul>")

    for r in results:
        if 'route' in r:
            html.append("<div style='border:1px solid #ddd;padding:12px;margin-bottom:10px;border-radius:6px;'>")
            html.append(f"<h3>Penerbangan — {r['route']}</h3>")
            html.append(f"<p>Harga estimasi: {r['price']}</p>")
            html.append(f"<p><a href='{r['details_url']}' target='_blank'>Lihat detail & booking</a></p>")
            html.append("</div>")
        else:
            html.append("<div style='border:1px solid #ddd;padding:12px;margin-bottom:10px;border-radius:6px;'>")
            html.append(f"<h3>Hotel — {r.get('name')}</h3>")
            html.append(f"<p>Harga: {r.get('price')}</p>")
            html.append(f"<p><a href='{r['details_url']}' target='_blank'>Lihat Ketersediaan & Booking</a></p>")
            html.append("</div>")

    # CTA button linking to a combined itinerary page (mock external link)
    cta_url = f"https://travel.example/itinerary?user={user_id}&agent={COORDINATOR_NAME.replace(' ', '%20')}"
    html.append(f"<p><a href='{cta_url}' target='_blank' style='background:#007acc;color:#fff;padding:10px 14px;border-radius:6px;text-decoration:none;'>Open itinerary & confirmation</a></p>")

    # Optionally post a summary to Circlo (if client provided)
    if client:
        try:
            summary_text = f"Super Agent found {len(results)} items for {user_id}: {results}"
            await client.create_post({"title": "Itinerary result", "body": summary_text})
        except Exception:
            pass

    html.append("</body></html>")
    return HTMLResponse(content='\n'.join(html))
