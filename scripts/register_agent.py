#!/usr/bin/env python3
"""
Simple CLI to register the Haruhi Agent on Circlo.
Usage:
  python scripts/register_agent.py --endpoint https://<your-ngrok>/agents/haruhi/hook
"""
import os
import time
import argparse
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

CIRCLO_TOKEN = os.getenv("CIRCLO_TOKEN") or os.getenv("CIRCLO_API_TOKEN")
if not CIRCLO_TOKEN:
    print("ERROR: CIRCLO_TOKEN or CIRCLO_API_TOKEN not found in environment or .env")
    raise SystemExit(1)

API_URL = "https://api.getcirclo.com/api/profiles/agent"


def register(endpoint: str | None, username: str | None, niche: str | None, avatar_url: str | None):
    uname = username or f"haruhi-agent-{int(time.time())}"
    # ensure avatar_url is present (Circlo requires it); if not provided, use a simple generated avatar
    # allow generated avatar to include the provided name when available
    default_name = "Haruhi Agent"
    default_avatar = f"https://ui-avatars.com/api/?name={quote_plus(default_name)}&background=0D8ABC&color=fff"
    payload = {
        "name": default_name,
        "username": uname,
        "niche": niche or "General",
        "avatar_url": avatar_url or default_avatar,
    }
    if endpoint:
        payload["endpoint"] = endpoint

    headers = {"Authorization": f"Bearer {CIRCLO_TOKEN}", "Content-Type": "application/json"}
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=15)
    print("Status:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", help="Public HTTPS endpoint for your agent webhook (ngrok URL)")
    p.add_argument("--name", help="Display name for the agent (e.g. 'Haruhi Agent')")
    p.add_argument("--username", help="Username for the agent (must be unique)")
    p.add_argument("--niche", help="Niche for the agent", default="General")
    p.add_argument("--avatar_url", help="Avatar URL for the agent", default="")
    args = p.parse_args()
    # If --name provided, override the default name in the payload
    if args.name:
        # create a small wrapper to pass name through; easiest is to set module-level default via kwargs
        def register_with_name(endpoint, username, niche, avatar_url):
            uname = username or f"haruhi-agent-{int(time.time())}"
            default_avatar = f"https://ui-avatars.com/api/?name={quote_plus(args.name)}&background=0D8ABC&color=fff"
            payload = {
                "name": args.name,
                "username": uname,
                "niche": niche or "General",
                "avatar_url": avatar_url or default_avatar,
            }

            if endpoint:
                payload["endpoint"] = endpoint

            headers = {"Authorization": f"Bearer {CIRCLO_TOKEN}", "Content-Type": "application/json"}
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=15)
            print("Status:", resp.status_code)
            try:
                print(resp.json())
            except Exception:
                print(resp.text)

        register_with_name(args.endpoint, args.username, args.niche, args.avatar_url)
    else:
        register(args.endpoint, args.username, args.niche, args.avatar_url)
