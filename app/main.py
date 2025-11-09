from fastapi import FastAPI
import os
from fastapi.responses import Response
import logging
from app.api.routers import circlo
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.openapi.utils import get_openapi
from typing import Dict

# Enable basic logging so our client logger messages appear in the uvicorn console
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Circlo API Integration")
app.include_router(circlo.router)


# Convenience redirects for usability on deployed instances
@app.get("/openapi")
async def openapi_redirect():
	"""Redirect /openapi to the OpenAPI JSON produced by FastAPI."""
	return RedirectResponse(url="/openapi.json")


@app.get("/")
async def root_redirect():
	"""Redirect root to the Swagger UI for quick exploration."""
	return RedirectResponse(url="/docs")


# Ensure certain Pydantic models are present in OpenAPI components.
def _ensure_extra_schemas(openapi_schema: Dict):
	comps = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
	try:
		# Import the small, dependency-free schema definitions
		from app.api.schemas import SendOAuthPayload, MarketingRequest

		# Add schemas if missing
		if "SendOAuthPayload" not in comps:
			comps["SendOAuthPayload"] = SendOAuthPayload.schema(ref_template="#/components/schemas/{model}")
		if "MarketingRequest" not in comps:
			comps["MarketingRequest"] = MarketingRequest.schema(ref_template="#/components/schemas/{model}")
	except Exception:
		# if imports fail, don't crash OpenAPI generation
		pass


def custom_openapi():
	if app.openapi_schema:
		return app.openapi_schema
	openapi_schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
	_ensure_extra_schemas(openapi_schema)
	app.openapi_schema = openapi_schema
	return app.openapi_schema


app.openapi = custom_openapi

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

# include coordinator router (provides HTML aggregation views)
try:
	from app.api.routers import coordinator
	app.include_router(coordinator.router)
except Exception:
	logging.getLogger(__name__).warning("Coordinator router not available (yet)")

# include orchestrator/router for high-level orchestration
try:
	from app.api.routers import orchestrator
	app.include_router(orchestrator.router)
except Exception:
	logging.getLogger(__name__).warning("Orchestrator router not available (yet)")

# include websearch and gcal routers
try:
	from app.api.routers import websearch
	app.include_router(websearch.router)
except Exception:
	logging.getLogger(__name__).warning("WebSearch router not available (yet)")

try:
	from app.api.routers import gcal
	app.include_router(gcal.router)
except Exception:
	logging.getLogger(__name__).warning("GCal router not available (yet)")

try:
	from app.api.routers import marketing
	app.include_router(marketing.router)
except Exception:
	logging.getLogger(__name__).warning("Marketing router not available (yet)")
