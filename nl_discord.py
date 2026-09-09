# nl_discord.py
"""Discord Rich Presence: detección de juego (vía DNS) y actualización de
estado en Discord.

Privacidad: el Rich Presence es 100% opcional. Si el usuario lo desactiva
desde la ventana "Opciones" de la GUI, este módulo NUNCA abre una conexión
con la app de Discord (ni intenta reconectar) hasta que se vuelva a activar.
"""

import json
import os
import threading
import time

from pypresence import Presence

from nl_paths import resource_path
from nl_gui_queue import queue_log
from nl_config import load_config, save_config, clear_config, DEFAULT_CLIENT_ID

# Estado cargado desde disco al importar el módulo (o los valores por
# defecto si no hay nada guardado).
CLIENT_ID, RICH_PRESENCE_ENABLED = load_config()

RPC = None
start_time = time.time()
current_game = "Ninguno"
GAME_IDS = {}

# Protege el acceso a current_game desde varios hilos DNS (TCP/UDP) a la vez.
_game_lock = threading.Lock()

# Señal para que el hilo update_discord() salga limpiamente al cerrar la app.
shutdown_event = threading.Event()


def cargar_game_ids():
    """Carga game_ids.json (mapa dominio -> nombre de juego) para la
    detección automática vía consultas DNS."""
    global GAME_IDS
    archivo = resource_path("game_ids.json")
    try:
        if os.path.exists(archivo):
            with open(archivo, "r", encoding="utf-8") as f:
                GAME_IDS = json.load(f)
            queue_log(f"[SISTEMA] Se cargaron {len(GAME_IDS)} juegos del JSON.")
        else:
            queue_log(f"[ERROR] No se encontró el archivo {archivo}")
            GAME_IDS = {"mariokartds": "Mario Kart DS"}  # Diccionario de respaldo
    except Exception as e:
        queue_log(f"[ERROR] Al leer el JSON: {e}")
        GAME_IDS = {"mariokartds": "Mario Kart DS"}


def detectar_juego_por_qname(qname):
    """Revisa una consulta DNS contra GAME_IDS y actualiza current_game si
    cambió. Pensado para llamarse desde el Resolver DNS (nl_dns_server.py).
    Devuelve el nombre del juego detectado solo si hubo un cambio real
    (para que quien llama decida si loguearlo), o None si no cambió nada.
    """
    global current_game
    for key, name in GAME_IDS.items():
        if key in qname:
            with _game_lock:
                if current_game != name:
                    current_game = name
                    return name
            return None
    return None


def _disconnect_rpc():
    global RPC
    if RPC is not None:
        try:
            RPC.close()
        except Exception:
            pass
        RPC = None


def set_client_id(nuevo_id):
    """Cambia el Client ID en memoria y fuerza una reconexión con el nuevo
    ID en el siguiente ciclo de update_discord()."""
    global CLIENT_ID
    CLIENT_ID = nuevo_id
    _disconnect_rpc()


def set_rich_presence_enabled(enabled):
    """Activa/desactiva el Rich Presence. Al desactivarlo, corta la conexión
    con Discord de inmediato: no se manda ningún dato más hasta reactivarlo."""
    global RICH_PRESENCE_ENABLED
    RICH_PRESENCE_ENABLED = enabled
    if not enabled:
        _disconnect_rpc()


def persist_settings(nuevo_client_id, rich_presence_enabled):
    """Guarda en disco y aplica de inmediato el Client ID y el estado de
    Rich Presence. Devuelve True/False según si se pudo guardar."""
    ok = save_config(nuevo_client_id, rich_presence_enabled)
    if ok:
        set_client_id(nuevo_client_id)
        set_rich_presence_enabled(rich_presence_enabled)
    return ok


def restore_defaults():
    """Vuelve al Client ID por defecto, deja Rich Presence activado, y borra
    el archivo de configuración guardado."""
    clear_config()
    set_client_id(DEFAULT_CLIENT_ID)
    set_rich_presence_enabled(True)


def update_discord(get_running, get_client_count):
    """Hilo de fondo: mantiene el Rich Presence de Discord al día, si está
    habilitado.

    `get_running` y `get_client_count` son funciones sin argumentos que
    consultan el estado del servidor DNS desde el módulo principal (evita
    acoplar este módulo a la GUI / variables globales de otro archivo).
    """
    global RPC
    cargar_game_ids()

    while not shutdown_event.is_set():
        if not RICH_PRESENCE_ENABLED:
            # Por privacidad: mientras esté desactivado, no se conecta a
            # Discord bajo ninguna circunstancia.
            _disconnect_rpc()
            shutdown_event.wait(5)
            continue

        try:
            if RPC is None:
                RPC = Presence(CLIENT_ID)
                RPC.connect()
                queue_log("[DISCORD] ¡CONECTADO CON ÉXITO!")

            is_running = get_running()
            n_clients = get_client_count()

            if not is_running:
                status_text = "Servidor Detenido"
                state_text = f"Clientes: {n_clients}"
            else:
                status_text = f"Jugando: {current_game}"
                state_text = f"Online | Clientes: {n_clients}"

            RPC.update(
                state=state_text,
                details=status_text,
                large_image="icono2",
                start=start_time,
            )
        except Exception as e:
            queue_log(f"[DISCORD] Error: {e}")
            RPC = None
        shutdown_event.wait(15)

    # Al salir (cierre de la app), desconectar con prolijidad.
    _disconnect_rpc()
