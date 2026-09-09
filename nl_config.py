# nl_config.py
"""Configuración persistente de NitroLink.

Se guarda en un archivo .dat (JSON simple adentro) junto al ejecutable/script,
para que el usuario pueda:
  1. Usar su propio bot/app de Discord para el Rich Presence (opcional).
  2. Desactivar el Rich Presence por completo, por privacidad (opcional).

Nada de esto se escribe en el código fuente ni es obligatorio: si el archivo
no existe, se usan los valores por defecto tal cual funcionaba antes.
"""

import json
import os

from nl_paths import resource_path
from nl_gui_queue import queue_log

CONFIG_FILE = resource_path("nitrolink_config.dat")

DEFAULT_CLIENT_ID = "Your ID here"
DEFAULT_RICH_PRESENCE_ENABLED = True


def load_config():
    """Lee CONFIG_FILE y devuelve (client_id, rich_presence_enabled).
    Si el archivo no existe o está corrupto, devuelve los valores por defecto
    sin lanzar excepciones (solo deja un aviso en el log).
    """
    client_id = DEFAULT_CLIENT_ID
    rp_enabled = DEFAULT_RICH_PRESENCE_ENABLED
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cid = str(data.get("discord_client_id", "")).strip()
            if cid:
                client_id = cid
            if "rich_presence_enabled" in data:
                rp_enabled = bool(data["rich_presence_enabled"])
    except Exception as e:
        queue_log(f"[CONFIG] No se pudo leer {CONFIG_FILE}: {e}")
    return client_id, rp_enabled


def save_config(client_id, rich_presence_enabled):
    """Guarda el Client ID y el estado de Rich Presence. Devuelve True/False."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "discord_client_id": client_id,
                "rich_presence_enabled": rich_presence_enabled,
            }, f)
        return True
    except Exception as e:
        queue_log(f"[CONFIG] No se pudo guardar {CONFIG_FILE}: {e}")
        return False


def clear_config():
    """Borra el archivo de configuración (para volver a los valores por
    defecto). Devuelve True/False."""
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        return True
    except Exception as e:
        queue_log(f"[CONFIG] No se pudo borrar {CONFIG_FILE}: {e}")
        return False
