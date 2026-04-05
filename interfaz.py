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

# ----------------- GUI Funciones -----------------

def show_about():
    about_text = (
        "NitroLink DNS by SooraMaru\n\n"
        "Fork of RiiConnect24 DNS Server (based on sudomemoDNS)\n\n"
        "Original authors: Austin Burk / RiiConnect24 team\n\n"
        "Modified with GUI, ConnTest fix, startup delay, logging improvements, "
        "client tracking (IP + MAC), log clearing and button state logic."
    )
    messagebox.showinfo("Acerca de NitroLink", about_text)

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
        client_list_box.configure(state="normal")
        client_list_box.insert("end", f"[{connected_clients[ip]}] {ip} | MAC: {mac} | Nintendo DS {connected_clients[ip]}\n")
        client_list_box.configure(state="disabled")
        client_list_box.yview("end")
        client_counter += 1

log_box = scrolledtext.ScrolledText(main_frame, state="disabled", bg="black", fg="#00ff00", font=("Consolas", 9), height=15)
log_box.pack(fill="both", expand=True, pady=5)

def gui_log(text):
    log_box.configure(state="normal")
    log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
    log_box.configure(state="disabled")
    log_box.yview("end")

def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")
    gui_log("Log limpiado.")

# ----------------- Lógica de Registros DNS Original -----------------

ZONES = {}
try:
    get_zones = requests.get("https://raw.githubusercontent.com/RiiConnect24/DNS-Server/master/dns_zones.json", timeout=10)
    zones_data = json.loads(get_zones.text)
    for z in zones_data:
        if z["type"] == "a":
            ZONES[z["name"]] = z["value"]
    gui_log("[INFO] Zonas DNS cargadas correctamente.")
except:
    gui_log("[ERROR] No se pudieron cargar las zonas externas.")

class Resolver:
    def resolve(self, request, handler):
        qname = str(request.q.qname).strip('.')
        client_ip = handler.client_address[0]
        reply = request.reply()
        
        # Prueba de conexión Nintendo (ConnTest)
        if "conntest.nintendowifi.net" in qname:
            reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(MY_IP), ttl=60))
            return reply

        # Redirección a Wiimmfi/RiiConnect24
        found = False
        for zone_name, target_ip in ZONES.items():
            if zone_name in qname:
                reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(target_ip), ttl=300))
                found = True
                break
        
        # Si no está en las zonas, resolver mediante DNS del sistema
        if not found:
            if "nintendowifi.net" in qname:
                reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A("95.217.77.151"), ttl=60))
            else:
                try:
                    real_ip = socket.gethostbyname(qname)
                    reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(real_ip), ttl=60))
                except:
                    pass
        return reply

# ----------------- HTTP & Control -----------------

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
dnsLogger = RiiConnect24DNSLogger() if 'RiiConnect24DNSLogger' in locals() else None
# Creamos un logger simple si el anterior falló
if not dnsLogger:
    class SimpleLogger:
        def log_request(self, handler, request):
            update_client_list(handler.client_address[0])
            gui_log(f"[DNS] Req: {request.q.qname} desde {handler.client_address[0]}")
        def __getattr__(self, name): return lambda *a, **k: None
    dnsLogger = SimpleLogger()

servers = []
running = False

def start_server():
    global servers, running
    if running: return
    btn_start.config(state="disabled")
    btn_stop.config(state="normal")
    gui_log("[INFO] Iniciando NitroLink en 5 segundos...")
    
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
            gui_log("[OK] NitroLink DNS Online.")
        except Exception as e:
            gui_log(f"[ERROR] {e}")
            stop_server()
            
    threading.Thread(target=delayed_start, daemon=True).start()

def stop_server():
    global servers, running
    for s in servers: s.stop()
    servers = []; running = False
    btn_start.config(state="normal")
    btn_stop.config(state="disabled")
    gui_log("[INFO] Servidor detenido.")

# ----------------- Botones -----------------

btn_frame = tk.Frame(main_frame, bg="black")
btn_frame.pack(side="bottom", fill="x", pady=10)

btn_start = tk.Button(btn_frame, text="Iniciar", bg="#222", fg="#00ff00", width=12, command=start_server)
btn_start.pack(side="left", padx=5)

btn_stop = tk.Button(btn_frame, text="Detener", bg="#222", fg="#00ff00", width=12, command=stop_server, state="disabled")
btn_stop.pack(side="left", padx=5)

tk.Button(btn_frame, text="Limpiar Log", bg="#222", fg="#00ff00", width=12, command=clear_log).pack(side="left", padx=5)

tk.Button(btn_frame, text="Acerca de", bg="#222", fg="#00ff00", width=12, command=show_about).pack(side="right", padx=5)

gui_log("==============================================")
gui_log(" NitroLink DNS Console v1.0 Ready ")
gui_log("==============================================")

root.mainloop()