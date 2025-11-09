import os
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import asyncio

from app.core.circlo_client import CircloClient
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

from app.core import memory

router = APIRouter(prefix="/gcal", tags=["gcal"])

# Scopes needed to create events
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# CLIENT config will be taken from env variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")  # e.g. https://<ngrok>/gcal/callback


def _client_config():
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def _build_oauth_url_for_user(user_id: str = "anon"):
    """Return (auth_url, state) and persist mapping state->user_id in memory."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes=True)
    # store mapping state -> user_id in memory
    memory.set_pref(state, "oauth_user", user_id)
    return auth_url, state


@router.get("/oauth/start")
def oauth_start(user_id: str = "anon"):
    """Return an authorization URL for the user to consent to Google Calendar access.
    Provide user_id so we can map the OAuth state to a user in callback.
    """
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="Google OAuth client_id/client_secret/redirect_uri not configured in env")

    try:
        auth_url, state = _build_oauth_url_for_user(user_id)
        return JSONResponse(content={"auth_url": auth_url, "state": state})
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start OAuth flow")
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth flow: {e}")


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    """OAuth callback endpoint. Exchanges code for credentials and stores them in memory keyed by user_id.
    Expects `state` param to find the user mapping.
    """
    params = dict(request.query_params)
    state = params.get("state")
    if not state:
        return HTMLResponse(content="Missing state", status_code=400)

    # find user_id mapped to this state (we stored it under the state key)
    user_id = memory.get_pref(state, "oauth_user")
    if not user_id:
        # fallback: store under 'anon'
        user_id = "anon"

    try:
        flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
        full_url = str(request.url)
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials
    except Exception as e:
        logging.getLogger(__name__).exception("OAuth callback failed")
        return HTMLResponse(content=f"OAuth callback failed: {e}", status_code=500)
    # store credentials JSON in memory
    memory.set_pref(user_id, "gcal_credentials", creds.to_json())

    return HTMLResponse(content=f"Google Calendar connected for user {user_id}. You can close this window.")


@router.post("/create-event")
async def create_event(request: Request):
    """Create a calendar event for the user. Body: { user_id, summary, start_iso, end_iso, attendees: [emails] }
    Requires that the user previously completed OAuth and credentials are stored under user_id.
    """
    body = await request.json()
    user_id = body.get("user_id") or "anon"
    creds_json = memory.get_pref(user_id, "gcal_credentials")
    if not creds_json:
        raise HTTPException(status_code=400, detail="No Google credentials found for this user. Start OAuth at /gcal/oauth/start")

    creds = Credentials.from_authorized_user_info(json.loads(creds_json), scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": body.get("summary", "Meeting"),
        "start": {"dateTime": body.get("start_iso")},
        "end": {"dateTime": body.get("end_iso")},
    }
    attendees = body.get("attendees")
    if attendees:
        event["attendees"] = [{"email": e} for e in attendees]

    # create and send invitations
    created = service.events().insert(calendarId="primary", body=event, sendUpdates="all").execute()
    # store created event id in memory
    memory.save_booking(user_id, "gcal_event", json.dumps(created))
    return JSONResponse(content={"status": "created", "event": created})


from app.api.schemas import SendOAuthPayload


@router.post("/send-oauth")
async def send_oauth(payload: SendOAuthPayload):
    """Create an oauth auth_url for `user_id` and send it to the user via Circlo create_post.
    This is useful when users do not have email and need an in-app link to click.
    Body: { user_id, message (optional) }
    """
    user_id = payload.user_id or "anon"
    # early validation
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    try:
        auth_url, state = _build_oauth_url_for_user(user_id)
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to build oauth url")
        raise HTTPException(status_code=500, detail=f"Failed to build oauth url: {e}")

    # Compose a Circlo post payload
    post_payload = {
        "user_id": user_id,
        "title": "Connect your Google Calendar",
        "body": payload.message or f"Untuk menyambungkan Google Calendar Anda, silakan klik: {auth_url}",
        "meta": {"auth_url": auth_url},
    }

    client = CircloClient()
    try:
        resp = await client.create_post(post_payload)
    finally:
        await client.close()

    if resp.get("status_code", 0) >= 400:
        raise HTTPException(status_code=502, detail={"error": resp.get("error"), "status": resp.get("status_code")})

    return JSONResponse(content={"sent": True, "circlo": resp})
