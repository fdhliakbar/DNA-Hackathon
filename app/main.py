from fastapi import FastAPI
import os
from fastapi.responses import Response
import logging
from app.api.routers import circlo
from fastapi.staticfiles import StaticFiles

# Enable basic logging so our client logger messages appear in the uvicorn console
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Circlo API Integration")
app.include_router(circlo.router)

# If the user hasn't placed a haruhi.jpg into app/static, provide a small
# fallback SVG served at the same path so the avatar URL is reachable immediately.
HARUHI_PATH = os.path.join("app", "static", "haruhi.jpg")

if not os.path.exists(HARUHI_PATH):
	@app.get("/static/haruhi.jpg")
	async def _haruhi_fallback():
		svg = (
			"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 1067'>"
			"<rect width='100%' height='100%' fill='#f8f0ff'/>"
			"<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle'"
			" font-family='Arial, Helvetica, sans-serif' font-size='48' fill='#333'>Haruhi</text>"
			"</svg>"
		)
		return Response(content=svg, media_type="image/svg+xml")

# Serve static files (put images like haruhi.jpg in app/static)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# include agent router (Haruhi)
try:
	from app.api.routers import agent
	app.include_router(agent.router)
except Exception:
	# if agent router is not present yet, ignore; it will be picked up on reload
	logging.getLogger(__name__).warning("Agent router not available (yet)")
