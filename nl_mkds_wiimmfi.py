# nl_mkds_wiimmfi.py
"""Lista de jugadores online de Mario Kart DS en Wiimmfi.

NitroLink NO scrapea wiimmfi.de directamente (Cloudflare lo bloquea incluso
con Puppeteer en modo headless, según el propio proyecto de referencia). En
su lugar, consulta la API ya alojada por itshichabk (forkeada por
xxjeysonxx), que corre un Chrome real del lado del servidor y sí logra pasar
la protección.

Endpoint confirmado manualmente (curl mkdsapi.itshichabk.io):
    GET https://mkdsapi.itshichabk.io/
    -> [{"fc":"1852-8731-1745","status":3,"name":"Baris"}, ...]
"""

import requests

MKDS_API_URL = "https://mkdsapi.itshichabk.io/"

# status : estado actual del jugador, según la documentación del proyecto.
MKDS_STATUS_MAP = {
    "0": "Conectando",
    "1": "En lobby",
    "2": "Buscando (mundial/regional/rivales)",
    "3": "Jugando (mundial/regional/rivales)",
    "4": "Buscando en amigos",
    "5": "Jugando con amigos",
}


def fetch_mkds_players():
    """Devuelve [{'fc', 'status_raw', 'name'}, ...] o lanza RuntimeError."""
    resp = requests.get(MKDS_API_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise RuntimeError(f"Respuesta inesperada de la API (no es una lista): {data!r}")

    players = []
    for p in data:
        if not isinstance(p, dict):
            continue
        players.append({
            "fc": p.get("fc", ""),
            "status_raw": str(p.get("status", "")),
            "name": p.get("name", ""),
        })
    return players
