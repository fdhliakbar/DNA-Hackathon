# Haruhi Agent — Super Agent (Creator of Swarms) deliverables

This repo was extended with a minimal Haruhi agent implementation and helper scripts to satisfy the Challenge 1 mandatory requirements.

Files added

- `app/api/routers/agent.py` — FastAPI router with:
  - `POST /agents/haruhi/hook` — webhook endpoint Circlo will call with conversation payload.
  - `POST /agents/register` — convenience register endpoint that uses the repo's `CircloClient` to call Circlo `create_agent`.
- `scripts/register_agent.py` — CLI script that registers Haruhi Agent via Circlo API. Accepts `--endpoint` (ngrok HTTPS url), `--username`, `--niche`.
- `scripts/test_circlo.py` — quick smoke tests that call local FastAPI proxy endpoints.

Quick steps to run locally (Windows / PowerShell)

1. Install dependencies (if not already):

```powershell
pip install -r requirements.txt
```

2. Put your Circlo token in `.env` at repo root. Use either:

```
CIRCLO_TOKEN=eyJ...yourtoken...
# or
CIRCLO_API_TOKEN=eyJ...yourtoken...
```

3. Start the FastAPI server (keep this running):

```powershell
python -m uvicorn app.main:app --reload
```

4. Expose your local server with ngrok (so Circlo can POST HTTPS to it). Install ngrok and run:

```powershell
ngrok http 8000
```

Note the HTTPS forwarding URL (e.g. `https://abcd1234.ngrok.io`).

5. Register Haruhi Agent on Circlo (use the script) — point endpoint to your ngrok URL plus the webhook path:

```powershell
python scripts/register_agent.py --endpoint https://abcd1234.ngrok.io/agents/haruhi/hook --username haruhi-agent-01
```

The script will print the Circlo API response (201 Created and agent JSON) if successful.

6. Test webhook flow

- Open Postman or use curl to POST to Circlo (Circlo will call your webhook when conversation routed), or simulate by calling the webhook directly:

```powershell
# simulate a call from Circlo to your webhook
Invoke-RestMethod -Uri "https://abcd1234.ngrok.io/agents/haruhi/hook" -Method POST -Body (ConvertTo-Json @{ message = 'Hello Haruhi'; user = @{ id = 'u1'; name = 'Tester' } } ) -ContentType 'application/json'
```

The webhook returns JSON like:

```json
{ "response": "Haruhi Agent here — I received your message: Hello Haruhi" }
```

7. Verify agent on getCirclo Agent Page

- Log into getCirclo admin (or whatever UI you use) and look for the new agent username you registered (e.g. `haruhi-agent-01`).

What to hand in for the challenge

- Agent ID and username created on Circlo (the script prints the JSON returned by Circlo). Include these in submission.
- Public webhook URL (ngrok) you used.
- Short README (this file) describing how to run and test.

Notes & next steps

- The webhook here returns a canned response. For stronger submission, implement logic to call an LLM or your decision engine and return richer replies.
- Ensure your ngrok session is stable at submission time (or deploy webhook to a public HTTPS host).
- If you want, I can add example code to call OpenAI or a lightweight local model to generate dynamic replies.
