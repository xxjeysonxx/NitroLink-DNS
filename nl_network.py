# nl_network.py
"""Utilidades de red usadas por el servidor DNS y la lista de clientes."""

import os
import re
import socket

from nl_gui_queue import queue_log


def get_ip():
    """IP local de esta máquina en la red (la que se usará como DNS primario)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


# Se calcula una sola vez al importar el módulo, igual que en la versión
# original; todos los demás módulos que necesiten la IP local importan
# nl_network y usan nl_network.MY_IP.
MY_IP = get_ip()


def get_mac_address(ip):
    """Intenta resolver la MAC de una IP vía `arp -a` (best-effort)."""
    try:
        with os.popen(f"arp -a {ip}") as f:
            data = f.read()
        mac = re.search(r"(([a-f\d]{1,2}[:\-]){5}[a-f\d]{1,2})", data, re.I)
        return mac.group(0).upper().replace("-", ":") if mac else "Desconocida"
    except Exception as e:
        queue_log(f"[WARN] No se pudo obtener MAC de {ip}: {e}")
        return "Desconocida"
