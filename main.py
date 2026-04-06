# NitroLink DNS
# Fork of RiiConnect24 DNS Server (based on sudomemoDNS)
# All original features restored + MAC Detection & GUI

from datetime import datetime
import time
import threading
import ctypes
import os
import re

from dnslib import DNSLabel, QTYPE, RD, RR
from dnslib import A, AAAA, CNAME, MX, NS, SOA, TXT
from dnslib.server import DNSServer

import socket
import requests
import json
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- NUEVO IMPORT PARA DISCORD ---
from pypresence import Presence

# ----------------- CONFIGURACIÓN WEBHOOK -----------------
WEBHOOK_URL = "https://discord.com/api/webhooks/1490513733657563238/vareLAHpy37mToNpFHaFZkwqnpktL3xptCTPGcD_myu3pRNNMK9cNrm-ZoavP5pvZ_W1"

def send_to_discord(message):
    try:
        if not WEBHOOK_URL or "webhooks" not in WEBHOOK_URL:
            return
    except NameError:
        return
    
    def dispatch():
        time.sleep(0.1)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NitroLink-DNS-Logger"
        }
        data = {"content": f"**[NitroLink Log]** {message}"}
        try:
            requests.post(WEBHOOK_URL, json=data, headers=headers, timeout=10)
        except:
            pass

    threading.Thread(target=dispatch, daemon=True).start()

# ----------------- Utilidades -----------------

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

MY_IP = get_ip()
connected_clients = {} 
client_counter = 1

def get_mac_address(ip):
    try:
        with os.popen(f"arp -a {ip}") as f:
            data = f.read()
        mac = re.search(r"(([a-f\d]{1,2}[:\-]){5}[a-f\d]{1,2})", data, re.I)
        return mac.group(0).upper().replace("-", ":") if mac else "Desconocida"
    except:
        return "Desconocida"

# ----------------- Lógica Discord RPC & Detección -----------------

CLIENT_ID = "1119796944181678112" 
RPC = None
start_time = time.time()
current_game = "Ninguno"
GAME_IDS = {} 

def cargar_game_ids():
    global GAME_IDS
    archivo = "game_ids.json"
    try:
        if os.path.exists(archivo):
            with open(archivo, "r", encoding="utf-8") as f:
                GAME_IDS = json.load(f)
        else:
            GAME_IDS = {"mariokartds": "Mario Kart DS"} 
    except:
        pass

def update_discord():
    global RPC
    cargar_game_ids()
    while True:
        try:
            if RPC is None:
                RPC = Presence(CLIENT_ID)
                RPC.connect()
            
            if not running:
                status_text = "Servidor Detenido"
                state_text = f"Clientes: {len(connected_clients)}"
            else:
                status_text = f"Jugando: {current_game}"
                state_text = f"Online | Clientes: {len(connected_clients)}"

            RPC.update(state=state_text, details=status_text, large_image="icono2", start=start_time)
        except:
            RPC = None
        time.sleep(15)

# ----------------- GUI Principal -----------------

root = tk.Tk()

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nitrolink.dns.server.v1")
    if os.path.exists("icono.ico"):
        root.iconbitmap("icono.ico")
except:
    pass

root.title("NitroLink DNS - Server Console")
root.geometry("800x640")
root.configure(bg="black")
root.resizable(False, False)

# Mensaje de inicio limpio para Discord
send_to_discord("🚀 NitroLink Iniciado - Webhook Activo")

main_frame = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True, padx=10, pady=5)

ip_label = tk.Label(main_frame, text=f"Primary DNS: {MY_IP}    Secondary DNS: 1.1.1.1", font=("Arial", 11, "bold"), bg="black", fg="#00ff00")
ip_label.pack(pady=8)

client_frame = tk.LabelFrame(main_frame, text=" Clientes Conectados (IP & MAC) ", bg="black", fg="#00ff00", font=("Arial", 9, "bold"))
client_frame.pack(fill="x", pady=5)

client_list_box = tk.Text(client_frame, height=5, bg="black", fg="#00ff00", state="disabled", font=("Consolas", 10), borderwidth=0)
client_list_box.pack(fill="x", padx=5, pady=5)

def update_client_list(ip):
    global client_counter
    if ip not in connected_clients:
        mac = get_mac_address(ip)
        connected_clients[ip] = client_counter
        
        # Muestra IP y MAC solo en tu pantalla
        client_list_box.configure(state="normal")
        client_list_box.insert("end", f"[{connected_clients[ip]}] {ip} | MAC: {mac} | Nintendo DS {connected_clients[ip]}\n")
        client_list_box.configure(state="disabled")
        client_list_box.yview("end")
        
        # OCULTA IP Y MAC EN DISCORD
        send_to_discord(f"📡 Nueva conexión detectada: Nintendo DS {client_counter}")
        
        client_counter += 1

log_box = scrolledtext.ScrolledText(main_frame, state="disabled", bg="black", fg="#00ff00", font=("Consolas", 9), height=15)
log_box.pack(fill="both", expand=True, pady=5)

def gui_log(text, send_discord=True):
    log_box.configure(state="normal")
    log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
    log_box.configure(state="disabled")
    log_box.yview("end")
    if send_discord:
        send_to_discord(text)

def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")
    gui_log("Log limpiado.", send_discord=True)
    gui_log("==============================================", send_discord=False)
    gui_log(" NitroLink DNS Console v2.0.0 Ready ", send_discord=False)
    gui_log("==============================================", send_discord=False)

def show_about():
    about_text = (
        "NitroLink DNS by SooraMaru\n\n"
        "Fork of RiiConnect24 DNS Server (based on sudomemoDNS)\n\n"
        "Original authors: Austin Burk / RiiConnect24 team\n\n"
    )
    messagebox.showinfo("Acerca de NitroLink", about_text)

# ----------------- Lógica DNS -----------------

ZONES = {}
try:
    get_zones = requests.get("https://sooramaru.xyz/dns_zones.json", timeout=10)
    zones_data = json.loads(get_zones.text)
    for z in zones_data:
        if z["type"] == "a": ZONES[z["name"]] = z["value"]
    gui_log("[INFO] Zonas DNS cargadas correctamente.", send_discord=True)
except:
    gui_log("[ERROR] No se pudieron cargar las zonas externas.", send_discord=True)

class Resolver:
    def resolve(self, request, handler):
        global current_game
        qname = str(request.q.qname).strip('.')
        reply = request.reply()
        for key, name in GAME_IDS.items():
            if key in qname:
                if current_game != name:
                    current_game = name
                    gui_log(f"[INFO] Juego detectado: {name}", send_discord=True)
                break
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
                except: pass
        return reply

class ConnTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/html"); self.end_headers()
        self.wfile.write(b"<html><body>OK</body></html>")
    def log_message(self, format, *args): return

def start_conntest_server():
    try:
        httpd = HTTPServer((MY_IP, 80), ConnTestHandler)
        httpd.serve_forever()
    except: pass

resolver = Resolver()
class SimpleLogger:
    def log_request(self, handler, request):
        client_ip = handler.client_address[0]
        update_client_list(client_ip)
        
        # Muestra IP en el log de tu PC
        log_text_local = f"[DNS] Req: {request.q.qname} desde {client_ip}"
        
        # OCULTA IP EN DISCORD (Usa el ID de consola)
        ds_id = connected_clients.get(client_ip, "?")
        log_text_discord = f"[DNS] Req: {request.q.qname} | Nintendo DS {ds_id}"
        
        gui_log(log_text_local, send_discord=False)
        send_to_discord(log_text_discord)
        
    def __getattr__(self, name): return lambda *a, **k: None

dnsLogger = SimpleLogger()
servers = []
running = False

def start_server():
    global servers, running
    if running: return
    btn_start.config(state="disabled")
    btn_stop.config(state="normal")
    gui_log("[INFO] Iniciando NitroLink en 5 segundos...", send_discord=True)
    def delayed_start():
        global servers, running
        try:
            time.sleep(5)
            servers = [
                DNSServer(resolver=resolver, port=53, address=MY_IP, tcp=True, logger=dnsLogger),
                DNSServer(resolver=resolver, port=53, address=MY_IP, tcp=False, logger=dnsLogger),
            ]
            for s in servers: s.start_thread()
            threading.Thread(target=start_conntest_server, daemon=True).start()
            running = True
            gui_log("[OK] NitroLink DNS Online.", send_discord=True)
        except Exception as e:
            gui_log(f"[ERROR] {e}", send_discord=True)
            stop_server()
    threading.Thread(target=delayed_start, daemon=True).start()

def stop_server():
    global servers, running
    for s in servers: s.stop()
    servers = []; running = False
    btn_start.config(state="normal")
    btn_stop.config(state="disabled")
    gui_log("[INFO] Servidor detenido.", send_discord=True)

# ----------------- Botones -----------------

btn_frame = tk.Frame(main_frame, bg="black")
btn_frame.pack(side="bottom", fill="x", pady=10)

btn_start = tk.Button(btn_frame, text="Iniciar", bg="#222", fg="#00ff00", width=12, command=start_server)
btn_start.pack(side="left", padx=5)

btn_stop = tk.Button(btn_frame, text="Detener", bg="#222", fg="#00ff00", width=12, command=stop_server, state="disabled")
btn_stop.pack(side="left", padx=5)

tk.Button(btn_frame, text="Limpiar Log", bg="#222", fg="#00ff00", width=12, command=clear_log).pack(side="left", padx=5)
tk.Button(btn_frame, text="Acerca de", bg="#222", fg="#00ff00", width=12, command=show_about).pack(side="right", padx=5)

gui_log("==============================================", send_discord=False)
gui_log(" NitroLink DNS Console v2.0.0 Ready ", send_discord=False)
gui_log("==============================================", send_discord=False)

threading.Thread(target=update_discord, daemon=True).start()
root.mainloop()