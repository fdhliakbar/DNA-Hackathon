from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
import logging
import re
import time
from typing import Optional

from app.api.routers.circlo import get_circlo_client
from app.core.circlo_client import CircloClient
from app.core import llm as llm_module

# Try to import langdetect; if not installed we'll fall back to a tiny detector
try:
    from langdetect import detect
except Exception:
    def detect(text: str) -> str:  # type: ignore
        if not text:
            return "en"
        t = text.lower()
        if any(k in t for k in ("halo", "apa", "bagaimana", "terima", "kamu", "saya")):
            return "id"
        if any(k in t for k in ("hola", "gracias")):
            return "es"
        if any(k in t for k in ("bonjour", "merci")):
            return "fr"
        return "en"


router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

# LLM client (no-op if OPENAI_API_KEY not configured)
_llm = llm_module.LLMClient()


def _detect_language(text: str) -> str:
    try:
        return detect(text or "")
    except Exception:
        return "en"


def _is_booking_intent(text: str) -> bool:
    t = (text or "").lower()
    keywords = ["book", "booking", "pesan", "pesan kamar", "booking kamar", "reserve", "kamar", "hotel"]
    return any(k in t for k in keywords)


def _mock_search(platform: str, destination: str) -> list:
    if platform == "PlatformA":
        return [
            {"name": f"{destination} Seaside Hotel A", "price": 50, "currency": "USD", "link": "https://platform-a.example/offer/1"},
            {"name": f"{destination} Budget Inn A", "price": 30, "currency": "USD", "link": "https://platform-a.example/offer/2"},
        ]
    return [
        {"name": f"{destination} Luxury Suites B", "price": 70, "currency": "USD", "link": "https://platform-b.example/offer/1"},
        {"name": f"{destination} Cozy Stay B", "price": 35, "currency": "USD", "link": "https://platform-b.example/offer/2"},
    ]


def _summarize_offers_with_llm(destination: str, offers_a: list, offers_b: list, lang: str, persona: str = "You are Haruhi, a helpful travel assistant.") -> str:
    system = llm_module.build_system_prompt(persona)
    offers_text = "\n\n".join([
        "Offers from Platform A:\n" + "\n".join([f"- {o['name']} ({o['price']} {o['currency']}) - {o['link']}" for o in offers_a]),
        "Offers from Platform B:\n" + "\n".join([f"- {o['name']} ({o['price']} {o['currency']}) - {o['link']}" for o in offers_b]),
    ])

    prompt = (
        f"User asked to find accommodations in {destination}. Compare the offers below and recommend the top 2 options overall and one budget pick.\n\n"
        f"{offers_text}\n\nRespond in {lang}. Keep the answer concise and include reasons (price, location, value)."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    reply = _llm.chat(messages) if _llm.available() else None
    if reply:
        return reply

    # fallback summary
    fallback_lines = [f"Comparison for {destination}:"]
    fallback_lines.append("Platform A top: " + offers_a[0]["name"] + f" ({offers_a[0]['price']} {offers_a[0]['currency']})")
    fallback_lines.append("Platform B top: " + offers_b[0]["name"] + f" ({offers_b[0]['price']} {offers_b[0]['currency']})")
    fallback_lines.append("Budget pick: " + offers_a[1]["name"] + f" ({offers_a[1]['price']} {offers_a[1]['currency']})")
    return "\n".join(fallback_lines)


@router.post("/haruhi/hook")
async def haruhi_hook(request: Request):
    """Webhook endpoint.

    - Default (JSON): returns {"response": "..."} for Circlo API.
    - If client requests HTML (Accept: text/html) or uses ?format=html,
      responds with a rendered HTML page with clarifying questions and
      mocked offers. The HTML mode accepts form submissions (application/x-www-form-urlencoded)
      where users can submit `area`, `budget`, and `guests` and receive an updated HTML result.
    """
    # determine whether caller wants HTML
    wants_html = ("text/html" in request.headers.get("accept", "")) or (request.query_params.get("format") == "html")

    # read payload (support JSON and form posts)
    payload = {}
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith("multipart/form-data"):
        form = await request.form()
        payload = dict(form)
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    message = (payload or {}).get("message") or ""
    user = (payload or {}).get("user") or {}
    if isinstance(user, str):
        user = {"name": user}
    user_name = user.get("name") or user.get("id") or "Pengguna"

    area = payload.get("area") or payload.get("destination")
    budget = payload.get("budget")
    guests = payload.get("guests")

    lang = _detect_language(message)

    # booking / search flow
    if _is_booking_intent(message) or area:
        dest_match = re.search(r"bali|ubud|kuta|seminyak|canggu|nusa dua", (message or "").lower())
        destination = (area or (dest_match.group(0).title() if dest_match else "Bali"))

        offers_a = _mock_search("PlatformA", destination)
        offers_b = _mock_search("PlatformB", destination)

        if wants_html:
            # render an HTML reply with clarifying questions and offers
            html_parts = [
                "<html><head><meta charset='utf-8'><title>Haruhi — Rekomendasi Hotel</title></head>",
                "<body style='font-family:Arial,Helvetica,sans-serif;padding:20px;'>",
                f"<h2>Halo {user_name}, tentu, dengan senang hati saya akan membantu Anda.</h2>",
                "<p>Sebelum saya memberikan rekomendasi yang paling sesuai, boleh saya tahu beberapa detail?</p>",
                "<ul><li>Area (mis. Seminyak, Ubud, Canggu, Nusa Dua)</li><li>Perkiraan anggaran per malam</li><li>Untuk berapa orang?</li></ul>",
                "<form method='post' action='?format=html'>",
                "<label>Area: <input name='area' value='" + (destination or "Bali") + "'></label><br>",
                "<label>Anggaran per malam (IDR): <input name='budget' value='" + (budget or "") + "'></label><br>",
                "<label>Jumlah tamu: <input name='guests' value='" + (guests or "") + "'></label><br>",
                "<input type='hidden' name='message' value='" + (message or "") + "'>",
                "<button type='submit'>Kirim detail</button></form>",
                "<p>Sambil menunggu jawaban Anda, berikut beberapa pilihan cepat untuk besok:</p>",
                "<div>",
            ]
            for o in offers_a + offers_b:
                price_text = f"Rp {int(o['price'] * 28000):,}" if isinstance(o.get('price'), (int, float)) else o.get('price')
                source = "Booking.com" if 'PlatformA' in o.get('link', '') else "Agoda"
                html_parts.append(
                    f"<div style='border:1px solid #eee;padding:10px;margin-bottom:10px;border-radius:6px;'><h3>{o['name']}</h3><p><strong>Lokasi:</strong> {destination}</p><p>Mulai dari {price_text} / malam</p><p><em>Source: {source}</em></p><p><a href='{o['link']}' target='_blank' rel='noopener'>Lihat Ketersediaan</a></p></div>"
                )
            html_parts.extend(["</div>", "</body></html>"])
            return HTMLResponse(content='\n'.join(html_parts))

        # default JSON response
        reply = _summarize_offers_with_llm(destination, offers_a, offers_b, lang)
        return {"response": reply}

    # general message -> LLM or fallback
    persona = "You are Haruhi, a helpful and slightly playful assistant who provides clear answers."
    system = llm_module.build_system_prompt(persona)
    user_prompt = f"Reply concisely in {lang}. The user said: {message}. Keep tone helpful and give one actionable suggestion if appropriate."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]

    reply = _llm.chat(messages) if _llm.available() else None
    if wants_html:
        # render html reply
        html = reply or (f"Haruhi Agent di sini - saya menerima pesan Anda: {message}" if lang == 'id' else f"Haruhi Agent here - I received your message: {message}")
        body = f"<html><body style='font-family:Arial,Helvetica,sans-serif;padding:20px;'><p>{html}</p></body></html>"
        return HTMLResponse(content=body)

    if reply:
        return {"response": reply}

    responses = {
        "en": f"Haruhi Agent here - I received your message: {message}",
        "id": f"Haruhi Agent di sini - saya menerima pesan Anda: {message}",
        "es": f"Agente Haruhi aquí - recibí tu mensaje: {message}",
        "fr": f"Agent Haruhi ici - j'ai reçu votre message: {message}",
    }
    return {"response": responses.get(lang, responses["en"])}


@router.post("/register")
async def register_haruhi(request: Request, client: CircloClient = Depends(get_circlo_client)):
    """Register a Haruhi Agent on Circlo using the server's CircloClient.

    Optional JSON body accepted:
      { "username": "haruhi-agent-1", "niche": "Business", "avatar_url": "...", "endpoint": "https://..." }
    """
    payload = await request.json() if request._body else {}
    username = payload.get("username") or f"haruhi-agent-{int(time.time())}"
    body = {
        "name": payload.get("name", "Haruhi Agent"),
        "username": username,
        "niche": payload.get("niche", "General"),
        "avatar_url": payload.get("avatar_url", ""),
    }
    if payload.get("endpoint"):
        body["endpoint"] = payload.get("endpoint")

    resp = await client.create_agent(body)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]


@router.post("/{agent_id}/update")
async def update_agent_route(agent_id: str, request: Request, client: CircloClient = Depends(get_circlo_client)):
    """Update agent fields (name, niche, avatar_url) using CircloClient.update_agent."""
    payload = await request.json() if request._body else {}
    # only pass known fields
    body = {}
    for k in ("name", "niche", "avatar_url"):
        if k in payload:
            body[k] = payload[k]

    if not body:
        raise HTTPException(status_code=400, detail="No update fields provided")

    resp = await client.update_agent(agent_id, body)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]

    responses = {
        "en": f"Haruhi Agent here - I received your message: {message}",
        "id": f"Haruhi Agent di sini - saya menerima pesan Anda: {message}",
        "es": f"Agente Haruhi aquí - recibí tu mensaje: {message}",
        "fr": f"Agent Haruhi ici - j'ai reçu votre message: {message}",
    }

    reply = responses.get(lang, responses["en"])
    return {"response": reply}


@router.post("/register")
async def register_haruhi(request: Request, client: CircloClient = Depends(get_circlo_client)):
    """Register a Haruhi Agent on Circlo using the server's CircloClient.

    Optional JSON body accepted:
      { "username": "haruhi-agent-1", "niche": "Business", "avatar_url": "...", "endpoint": "https://..." }
    """
    payload = await request.json() if request._body else {}
    username = payload.get("username") or f"haruhi-agent-{int(time.time())}"
    body = {
        "name": payload.get("name", "Haruhi Agent"),
        "username": username,
        "niche": payload.get("niche", "General"),
        "avatar_url": payload.get("avatar_url", ""),
    }
    if payload.get("endpoint"):
        body["endpoint"] = payload.get("endpoint")

    resp = await client.create_agent(body)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]


@router.post("/{agent_id}/update")
async def update_agent_route(agent_id: str, request: Request, client: CircloClient = Depends(get_circlo_client)):
    """Update agent fields (name, niche, avatar_url) using CircloClient.update_agent."""
    payload = await request.json() if request._body else {}
    # only pass known fields
    body = {}
    for k in ("name", "niche", "avatar_url"):
        if k in payload:
            body[k] = payload[k]

    if not body:
        raise HTTPException(status_code=400, detail="No update fields provided")

    resp = await client.update_agent(agent_id, body)
    if resp.get("error"):
        raise HTTPException(status_code=resp.get("status_code", 502), detail=resp["error"])
    return resp["data"]
