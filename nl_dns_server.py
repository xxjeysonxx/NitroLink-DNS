# nl_dns_server.py
"""Lógica de resolución DNS de NitroLink: carga de zonas, el Resolver que
usa dnslib, y el pequeño servidor HTTP que responde a conntest.nintendowifi.net.
"""

import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dnslib import QTYPE, RR, A
from dnslib.server import DNSServer

from nl_gui_queue import queue_log, queue_client_update
from nl_network import MY_IP
import nl_discord

ZONES = {}


def cargar_zonas():
    """Descarga la lista de zonas DNS personalizadas desde sooramaru.xyz."""
    global ZONES
    try:
        resp = requests.get("https://sooramaru.xyz/dns_zones.json", timeout=10)
        resp.raise_for_status()
        zones_data = json.loads(resp.text)
        for z in zones_data:
            if z["type"] == "a":
                ZONES[z["name"]] = z["value"]
        queue_log("[INFO] Zonas DNS cargadas correctamente.")
    except Exception as e:
        queue_log(f"[ERROR] No se pudieron cargar las zonas externas: {e}")


# Se cargan una sola vez al importar el módulo (igual que en la versión
# original de un solo archivo).
cargar_zonas()


class Resolver:
    """Resolver de dnslib: responde conntest, zonas personalizadas, el
    dominio de Wiimmfi, o reenvía a la resolución DNS normal del sistema."""

    def resolve(self, request, handler):
        qname = str(request.q.qname).strip('.')
        reply = request.reply()

        # Detección de juego por consulta DNS (delegada a nl_discord).
        juego = nl_discord.detectar_juego_por_qname(qname)
        if juego:
            queue_log(f"[INFO] Juego detectado: {juego}")

        if "conntest.nintendowifi.net" in qname:
            reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(MY_IP), ttl=60))
            return reply

        found = False
        for zone_name, target_ip in ZONES.items():
            if zone_name in qname:
                reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(target_ip), ttl=300))
                found = True
                break

        if not found:
            if "nintendowifi.net" in qname:
                reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A("95.217.77.151"), ttl=60))
            else:
                try:
                    real_ip = socket.gethostbyname(qname)
                    reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(real_ip), ttl=60))
                except Exception as e:
                    queue_log(f"[WARN] No se pudo resolver {qname}: {e}")
        return reply


class ConnTestHandler(BaseHTTPRequestHandler):
    """Responde OK a las peticiones HTTP de conntest de las consolas."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>OK</body></html>")

    def log_message(self, format, *args):
        return  # silenciar el log por defecto de BaseHTTPRequestHandler


class SimpleLogger:
    """Logger mínimo para dnslib: cada request se encola hacia la GUI."""

    def log_request(self, handler, request):
        queue_client_update(handler.client_address[0])
        queue_log(f"[DNS] Req: {request.q.qname} desde {handler.client_address[0]}")

    def __getattr__(self, name):
        return lambda *a, **k: None


resolver = Resolver()
dnsLogger = SimpleLogger()

_conntest_httpd = None


def start_conntest_server():
    """Arranca el servidor HTTP de conntest (bloqueante; llamar en un hilo)."""
    global _conntest_httpd
    try:
        _conntest_httpd = HTTPServer((MY_IP, 80), ConnTestHandler)
        _conntest_httpd.serve_forever()
    except Exception as e:
        queue_log(f"[ERROR] No se pudo iniciar servidor ConnTest en puerto 80: {e}")


def stop_conntest_server():
    """Detiene el servidor HTTP de conntest si está corriendo."""
    global _conntest_httpd
    if _conntest_httpd is not None:
        try:
            _conntest_httpd.shutdown()
        except Exception:
            pass
        _conntest_httpd = None


def crear_servidores_dns():
    """Crea (sin iniciar) las instancias DNSServer TCP y UDP en el puerto 53."""
    return [
        DNSServer(resolver=resolver, port=53, address=MY_IP, tcp=True, logger=dnsLogger),
        DNSServer(resolver=resolver, port=53, address=MY_IP, tcp=False, logger=dnsLogger),
    ]
