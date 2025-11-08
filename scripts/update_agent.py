#!/usr/bin/env python3
"""
Simple CLI to update an existing Circlo agent's profile (name, niche, avatar_url).
Usage:
  python scripts/update_agent.py --id <agent-id> --niche "Super Agent" --avatar_url "https://<ngrok>/static/haruhi_suzumiya.png"
"""
import os
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

CIRCLO_TOKEN = os.getenv("CIRCLO_TOKEN") or os.getenv("CIRCLO_API_TOKEN")
if not CIRCLO_TOKEN:
    print("ERROR: CIRCLO_TOKEN or CIRCLO_API_TOKEN not found in environment or .env")
    raise SystemExit(1)


def update_agent(agent_id: str, name: str | None, niche: str | None, avatar_url: str | None):
    if not agent_id:
        print("ERROR: --id is required")
        raise SystemExit(1)

    API_URL = f"https://api.getcirclo.com/api/profiles/agent/{agent_id}"

    payload = {}
    if name:
        payload["name"] = name
    if niche:
        payload["niche"] = niche
    if avatar_url:
        payload["avatar_url"] = avatar_url

    if not payload:
        print("No fields to update. Provide --name, --niche or --avatar_url")
        return

    headers = {"Authorization": f"Bearer {CIRCLO_TOKEN}", "Content-Type": "application/json"}
    resp = requests.patch(API_URL, json=payload, headers=headers, timeout=15)
    print("Status:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True, help="Agent ID to update")
    p.add_argument("--name", help="New display name for the agent")
    p.add_argument("--niche", help="New niche for the agent")
    p.add_argument("--avatar_url", help="New avatar URL for the agent")
    args = p.parse_args()
    update_agent(args.id, args.name, args.niche, args.avatar_url)
