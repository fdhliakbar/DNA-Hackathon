#!/usr/bin/env python3
"""
Quick test script to call local FastAPI proxy for Circlo.
Usage:
  python scripts/test_circlo.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("LOCAL_BASE") or "http://127.0.0.1:8000"


def list_prefs(page=1, limit=2):
    url = f"{BASE}/circlo/user-preferences?page={page}&limit={limit}"
    r = requests.get(url, timeout=15)
    print("LIST status:", r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)


def get_user(user_id):
    url = f"{BASE}/circlo/user-preferences/{user_id}"
    r = requests.get(url, timeout=15)
    print("USER status:", r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)


if __name__ == '__main__':
    list_prefs()
    # if you want to test per-user, paste a UUID from list_prefs output below
    # get_user("0011e388-35dd-4ebb-aa58-5c373cc20c5f")
