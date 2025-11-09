from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import re
from typing import List

from app.api.routers import agent as agent_module

router = APIRouter(prefix="/coordinator", tags=["coordinator"])


def _render_offer_html(name: str, location: str, desc: str, price: str, source: str, link: str) -> str:
    return f"""
    <div class='offer'>
      <h3>{name}</h3>
      <p><strong>Lokasi:</strong> {location}</p>
      <p>{desc}</p>
      <p><strong>Mulai dari</strong> {price}</p>
      <p><em>Source: {source}</em></p>
      <p><a href='{link}' target='_blank' rel='noopener'>Lihat Ketersediaan</a></p>
    </div>
    """


@router.post("/task", response_class=HTMLResponse)
async def coordinator_task(request: Request):
    """Accepts a JSON payload with a `message` and optional `agents` list.

    Responds with an HTML page containing a friendly intro, clarifying
    questions, and a set of mocked hotel recommendations (aggregated).
    This is intentionally HTML so it can be rendered directly in a browser or
    embedded in Circlo if desired.
    """
    payload = await request.json()
    message = (payload or {}).get("message", "")
    user = (payload or {}).get("user", {})
    user_name = user.get("name") or user.get("id") or "Pengguna"

    # detect destination if present
    dest_match = re.search(r"bali|ubud|kuta|seminyak|canggu|nusa dua", (message or "").lower())
    destination = dest_match.group(0).title() if dest_match else payload.get("destination", "Bali")

    # Gather mocked offers from the agent module's helper
    offers_a = agent_module._mock_search("PlatformA", destination)
    offers_b = agent_module._mock_search("PlatformB", destination)

    # Build HTML
    html_parts: List[str] = []
    html_parts.append("""
    <html>
    <head>
      <meta charset='utf-8'>
      <title>Rekomendasi Hotel — Coordinator</title>
      <style>
        body { font-family: Arial, Helvetica, sans-serif; line-height: 1.5; padding: 24px; }
        .intro { margin-bottom: 16px; }
        .questions { background:#f4f6fb; padding:12px; border-radius:6px; margin-bottom:18px }
        .offer { border:1px solid #eee; padding:12px; border-radius:6px; margin-bottom:12px }
      </style>
    </head>
    <body>
    """)

    html_parts.append(f"<div class='intro'><h2>Halo {user_name}, saya akan bantu cari penginapan di {destination} untuk besok</h2>")
    html_parts.append("<p>Sebelum saya memberikan rekomendasi yang paling sesuai, boleh saya tahu beberapa detail?</p>")
    html_parts.append("<div class='questions'><ol><li>Area mana di Bali yang paling Anda minati (misalnya Seminyak, Ubud, Canggu, Nusa Dua)?</li><li>Berapa perkiraan anggaran Anda per malam?</li><li>Untuk berapa orang penginapan ini?</li></ol></div>")

    html_parts.append("<p>Sambil menunggu jawaban Anda, berikut adalah beberapa pilihan populer yang tersedia untuk besok di berbagai area dan rentang harga, berdasarkan pencarian cepat yang saya lakukan.</p>")
    html_parts.append("<h3>Pilihan Awal Hotel di {}</h3>".format(destination))

    # Present offers (mix A and B)
    for o in offers_a + offers_b:
        # create simple localized price string
        price_text = f"Rp {int(o['price'] * 28000):,}" if isinstance(o.get('price'), (int, float)) else o.get('price')
        location = destination
        desc = "Pilihan populer untuk relaksasi dan kenyamanan." if 'Ubud' in o['name'] or 'Seaside' in o['name'] else "Hotel modern dengan akses mudah ke area wisata."
        source = "Booking.com" if 'PlatformA' in o.get('link', '') else "Agoda"
        html_parts.append(_render_offer_html(o['name'], location, desc, price_text + " / malam", source, o['link']))

    html_parts.append("<p>Jika Anda ingin, saya bisa cek ketersediaan dan mengamankan opsi terbaik setelah Anda memberi detail area, anggaran, dan jumlah tamu.</p>")
    html_parts.append("</body></html>")

    html = "\n".join(html_parts)
    return HTMLResponse(content=html)
