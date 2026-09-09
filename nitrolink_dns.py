# NitroLink DNS
# Fork of RiiConnect24 DNS Server (based on sudomemoDNS)

from datetime import datetime
import threading
import ctypes
import os
import shutil
import sys

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk

from nl_paths import resource_path
from nl_gui_queue import gui_queue, queue_log
from nl_network import MY_IP, get_mac_address
import nl_discord
import nl_dns_server
import nl_mkds_wiimmfi
import nl_updater

CURRENT_VERSION = "1.0.0"

# ----------------- Estado de la GUI -----------------

connected_clients = {}
client_counter = 1
state_lock = threading.Lock()

servers = []
running = False


def get_running():
    with state_lock:
        return running


def get_client_count():
    with state_lock:
        return len(connected_clients)


# ----------------- Procesamiento de la cola de la GUI -----------------

def process_gui_queue():
    try:
        while True:
            kind, payload = gui_queue.get_nowait()
            if kind == "log":
                _gui_log_direct(payload)
            elif kind == "client":
                _update_client_list_direct(payload)
    except Exception:
        pass
    finally:
        root.after(100, process_gui_queue)


# ----------------- GUI Principal -----------------

root = tk.Tk()

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nitrolink.dns.server.v1")
except Exception as e:
    print(f"[WARN] No se pudo aplicar AppUserModelID: {e}")

try:
    icon_path = resource_path("icono.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print(f"[WARN] No se encontró icono.ico en: {icon_path}")
except Exception as e:
    print(f"[WARN] No se pudo aplicar el icono de la ventana: {e}")

root.title("NitroLink DNS - Server Console")
root.geometry("800x640")
root.configure(bg="black")
root.resizable(False, False)


def aplicar_icono_ventana(ventana):
    try:
        icon_path = resource_path("icono.ico")
        if os.path.exists(icon_path):
            ventana.iconbitmap(icon_path)
    except Exception:
        pass


main_frame = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True, padx=10, pady=5)

ip_label = tk.Label(main_frame, text=f"Primary DNS: {MY_IP}    Secondary DNS: 1.1.1.1", font=("Arial", 11, "bold"), bg="black", fg="#00ff00")
ip_label.pack(pady=8)

client_frame = tk.LabelFrame(main_frame, text=" Clientes Conectados (IP & MAC) ", bg="black", fg="#00ff00", font=("Arial", 9, "bold"))
client_frame.pack(fill="x", pady=5)

client_list_box = tk.Text(client_frame, height=5, bg="black", fg="#00ff00", state="disabled", font=("Consolas", 10), borderwidth=0)
client_list_box.pack(fill="x", padx=5, pady=5)


def _update_client_list_direct(ip):
    global client_counter
    with state_lock:
        if ip in connected_clients:
            return
        mac = get_mac_address(ip)
        connected_clients[ip] = client_counter
        label_id = client_counter
        client_counter += 1

    client_list_box.configure(state="normal")
    client_list_box.insert("end", f"[{label_id}] {ip} | MAC: {mac} | Nintendo DS {label_id}\n")
    client_list_box.configure(state="disabled")
    client_list_box.yview("end")


log_box = scrolledtext.ScrolledText(main_frame, state="disabled", bg="black", fg="#00ff00", font=("Consolas", 9), height=15)
log_box.pack(fill="both", expand=True, pady=5)


def _gui_log_direct(text):
    log_box.configure(state="normal")
    log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
    log_box.configure(state="disabled")
    log_box.yview("end")


def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")
    _gui_log_direct("Log limpiado.")
    _gui_log_direct("==============================================")
    _gui_log_direct(" NitroLink DNS Console v1.0 Ready ")
    _gui_log_direct("==============================================")


# ----------------- Control del servidor DNS -----------------

def start_server():
    global servers, running
    with state_lock:
        if running:
            return
    btn_start.config(state="disabled")
    btn_stop.config(state="normal")
    queue_log("[INFO] Iniciando NitroLink en 5 segundos...")

    def delayed_start():
        global servers, running
        try:
            import time
            time.sleep(5)
            servers = nl_dns_server.crear_servidores_dns()
            for s in servers:
                s.start_thread()
            threading.Thread(target=nl_dns_server.start_conntest_server, daemon=True).start()
            with state_lock:
                running = True
            queue_log("[OK] NitroLink DNS Online.")
        except Exception as e:
            queue_log(f"[ERROR] {e}")
            root.after(0, stop_server)

    threading.Thread(target=delayed_start, daemon=True).start()


def stop_server():
    global servers, running
    for s in servers:
        try:
            s.stop()
        except Exception as e:
            queue_log(f"[WARN] Error al detener un servidor DNS: {e}")
    servers = []
    with state_lock:
        running = False

    nl_dns_server.stop_conntest_server()

    btn_start.config(state="normal")
    btn_stop.config(state="disabled")
    queue_log("[INFO] Servidor detenido.")


def on_close():
    try:
        if get_running():
            stop_server()
    except Exception:
        pass
    try:
        close_mkds_window()
    except Exception:
        pass
    nl_discord.shutdown_event.set()
    root.after(200, root.destroy)


# ----------------- Ventana: Mario Kart DS -----------------

mkds_window = None
mkds_tree = None
mkds_status_label = None
mkds_after_id = None

import queue as _queue_module
mkds_queue = _queue_module.Queue()


def open_mkds_window():
    global mkds_window, mkds_tree, mkds_status_label

    if mkds_window is not None and mkds_window.winfo_exists():
        mkds_window.lift()
        mkds_window.focus_force()
        return

    mkds_window = tk.Toplevel(root)
    mkds_window.title("Mario Kart DS - Jugadores Online (Wiimmfi)")
    mkds_window.geometry("560x440")
    mkds_window.configure(bg="black")
    aplicar_icono_ventana(mkds_window)
    mkds_window.protocol("WM_DELETE_WINDOW", close_mkds_window)

    top_bar = tk.Frame(mkds_window, bg="black")
    top_bar.pack(fill="x", padx=8, pady=6)

    mkds_status_label = tk.Label(top_bar, text="Cargando...", bg="black", fg="#00ff00", font=("Consolas", 9))
    mkds_status_label.pack(side="left")

    auto_var = tk.BooleanVar(value=True)
    mkds_window.auto_var = auto_var

    chk_auto = tk.Checkbutton(
        top_bar, text="Auto (30s)", variable=auto_var, bg="black", fg="#00ff00",
        selectcolor="black", activebackground="black", activeforeground="#00ff00",
    )
    chk_auto.pack(side="right", padx=4)

    btn_refresh = tk.Button(top_bar, text="Actualizar", bg="#222", fg="#00ff00", command=request_mkds_refresh)
    btn_refresh.pack(side="right", padx=4)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("MKDS.Treeview", background="black", fieldbackground="black", foreground="#00ff00", font=("Consolas", 10), rowheight=22)
    style.configure("MKDS.Treeview.Heading", background="#222", foreground="#00ff00", font=("Consolas", 10, "bold"))

    columns = ("name", "fc", "status")
    mkds_tree = ttk.Treeview(mkds_window, columns=columns, show="headings", height=15, style="MKDS.Treeview")
    mkds_tree.heading("name", text="Nombre")
    mkds_tree.heading("fc", text="Friend Code")
    mkds_tree.heading("status", text="Estado")
    mkds_tree.column("name", width=200)
    mkds_tree.column("fc", width=150, anchor="center")
    mkds_tree.column("status", width=190)
    mkds_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    process_mkds_queue()
    request_mkds_refresh()
    schedule_mkds_auto_refresh()


def close_mkds_window():
    global mkds_window, mkds_after_id
    if mkds_window is not None and mkds_after_id is not None:
        try:
            mkds_window.after_cancel(mkds_after_id)
        except Exception:
            pass
    mkds_after_id = None
    if mkds_window is not None:
        mkds_window.destroy()
    mkds_window = None


def request_mkds_refresh():
    if mkds_status_label is not None and mkds_status_label.winfo_exists():
        mkds_status_label.config(text="Actualizando...")
    threading.Thread(target=_mkds_fetch_worker, daemon=True).start()


def _mkds_fetch_worker():
    try:
        players = nl_mkds_wiimmfi.fetch_mkds_players()
        mkds_queue.put(("ok", players))
    except Exception as e:
        mkds_queue.put(("error", str(e)))


def process_mkds_queue():
    if mkds_window is None or not mkds_window.winfo_exists():
        return
    try:
        while True:
            kind, payload = mkds_queue.get_nowait()
            if kind == "ok":
                _populate_mkds_tree(payload)
            elif kind == "error":
                if mkds_status_label is not None and mkds_status_label.winfo_exists():
                    mkds_status_label.config(text=f"Error al obtener datos: {payload}")
                queue_log(f"[MKDS] Error al obtener jugadores: {payload}")
    except Exception:
        pass
    if mkds_window is not None and mkds_window.winfo_exists():
        mkds_window.after(200, process_mkds_queue)


def _populate_mkds_tree(players):
    if mkds_tree is None or not mkds_tree.winfo_exists():
        return
    for item in mkds_tree.get_children():
        mkds_tree.delete(item)
    for p in players:
        status_txt = nl_mkds_wiimmfi.MKDS_STATUS_MAP.get(
            str(p.get("status_raw", "")).strip(), p.get("status_raw", "?")
        )
        mkds_tree.insert("", "end", values=(p.get("name", ""), p.get("fc", ""), status_txt))
    if mkds_status_label is not None and mkds_status_label.winfo_exists():
        now = datetime.now().strftime("%H:%M:%S")
        mkds_status_label.config(text=f"{len(players)} jugador(es) | actualizado {now}")


def schedule_mkds_auto_refresh():
    global mkds_after_id
    if mkds_window is None or not mkds_window.winfo_exists():
        return
    if getattr(mkds_window, "auto_var", None) is not None and mkds_window.auto_var.get():
        request_mkds_refresh()
    mkds_after_id = mkds_window.after(30000, schedule_mkds_auto_refresh)


# ----------------- Actualizaciones -----------------

import queue as _updater_queue_module
_update_result_queue = _updater_queue_module.Queue()


def check_for_updates(manual=False):
    if manual:
        queue_log("[UPDATE] Buscando actualizaciones...")
    threading.Thread(target=_check_updates_worker, args=(manual,), daemon=True).start()


def _check_updates_worker(manual):
    info = nl_updater.check_for_update(CURRENT_VERSION, ignorar_ya_instalada=not manual)
    _update_result_queue.put((manual, info))
    root.after(0, _process_update_result)


def _process_update_result():
    try:
        manual, info = _update_result_queue.get_nowait()
    except Exception:
        return

    if info is not None:
        queue_log(f"[UPDATE] Nueva versión disponible: {info['tag']}")
        _mostrar_dialogo_actualizacion(info)
    elif manual:
        queue_log("[UPDATE] Ya tienes la última versión.")
        messagebox.showinfo("Buscar actualizaciones", "Ya tienes la última versión de NitroLink DNS.")


def _mostrar_dialogo_actualizacion(info):
    ventana = tk.Toplevel(root)
    ventana.title("Actualización disponible")
    ventana.geometry("440x300")
    ventana.configure(bg="black")
    ventana.resizable(False, False)
    aplicar_icono_ventana(ventana)

    tk.Label(
        ventana, text=f"Hay una nueva versión: {info['tag']}",
        bg="black", fg="#00ff00", font=("Arial", 11, "bold"),
    ).pack(pady=(16, 4))

    tk.Label(
        ventana, text=f"Versión actual instalada: {CURRENT_VERSION}",
        bg="black", fg="#888888", font=("Consolas", 9),
    ).pack(pady=(0, 8))

    notas = info.get("notes", "")
    if notas:
        notas_box = tk.Text(ventana, height=6, width=48, bg="#111", fg="#00ff00", font=("Consolas", 8), wrap="word")
        notas_box.insert("1.0", notas)
        notas_box.configure(state="disabled")
        notas_box.pack(padx=10, pady=4)

    auto_disponible = nl_updater.puede_autoactualizar() and info.get("asset_url")

    aviso_lbl = tk.Label(ventana, text="", bg="black", fg="#888888", font=("Consolas", 8))
    if not auto_disponible:
        if not nl_updater.puede_autoactualizar():
            aviso_lbl.config(text="(Actualización automática no disponible al correr como script .py)")
        else:
            aviso_lbl.config(text="(No se encontró un .exe adjunto en la release; descarga manual)")
        aviso_lbl.pack(pady=(2, 0))

    btns = tk.Frame(ventana, bg="black")
    btns.pack(pady=14)

    def descargar_manual():
        nl_updater.abrir_pagina_release(info["url"])
        ventana.destroy()

    def descargar_automatico():
        ventana.destroy()
        iniciar_actualizacion_automatica(info)

    if auto_disponible:
        tk.Button(btns, text="Actualizar automáticamente", bg="#222", fg="#00ff00", width=22, command=descargar_automatico).pack(side="left", padx=6)

    tk.Button(btns, text="Descargar manual", bg="#222", fg="#00ff00", width=16, command=descargar_manual).pack(side="left", padx=6)
    tk.Button(btns, text="Más tarde", bg="#222", fg="#00ff00", width=12, command=ventana.destroy).pack(side="left", padx=6)


# ----------------- Descarga automática con barra de progreso -----------------

_download_progress_queue = _updater_queue_module.Queue()


def _formatear_mb(bytes_valor):
    return f"{bytes_valor / (1024 * 1024):.1f} MB"


def iniciar_actualizacion_automatica(info):
    progreso_win = tk.Toplevel(root)
    progreso_win.title("Actualizando NitroLink DNS")
    progreso_win.geometry("380x150")
    progreso_win.configure(bg="black")
    progreso_win.resizable(False, False)
    progreso_win.protocol("WM_DELETE_WINDOW", lambda: None)
    aplicar_icono_ventana(progreso_win)

    tk.Label(
        progreso_win, text=f"Descargando {info['tag']}...",
        bg="black", fg="#00ff00", font=("Arial", 10, "bold"),
    ).pack(pady=(16, 8))

    style = ttk.Style()
    style.configure("Update.Horizontal.TProgressbar", troughcolor="#111", background="#00ff00", bordercolor="#111")
    barra = ttk.Progressbar(
        progreso_win, style="Update.Horizontal.TProgressbar",
        orient="horizontal", length=320, mode="determinate", maximum=100,
    )
    barra.pack(pady=6)

    detalle_lbl = tk.Label(progreso_win, text="Preparando descarga...", bg="black", fg="#888888", font=("Consolas", 8))
    detalle_lbl.pack(pady=(4, 0))

    exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    asset_type = info.get("asset_type") or "exe"
    extension = ".zip" if asset_type == "zip" else ".exe"
    
    # Destino estándar que espera el script updater
    destino_final_exe = os.path.join(exe_dir, "NitroLink_update_download.exe")
    temp_download = os.path.join(exe_dir, f"NitroLink_temp_dl{extension}")

    def worker():
        def on_progress(descargado, total):
            _download_progress_queue.put(("progress", descargado, total))

        try:
            nl_updater.descargar_actualizacion(info["asset_url"], temp_download, progress_callback=on_progress)

            if asset_type == "zip":
                _download_progress_queue.put(("extracting", None, None))
                exe_extraido = nl_updater.extraer_exe_de_zip(temp_download)
                
                # Mover el ejecutable extraído a la carpeta destino final
                if os.path.exists(destino_final_exe):
                    os.remove(destino_final_exe)
                shutil.move(exe_extraido, destino_final_exe)

                try:
                    os.remove(temp_download)
                except Exception:
                    pass
                _download_progress_queue.put(("done", destino_final_exe, None))
            else:
                if os.path.exists(destino_final_exe):
                    os.remove(destino_final_exe)
                os.replace(temp_download, destino_final_exe)
                _download_progress_queue.put(("done", destino_final_exe, None))
        except Exception as e:
            _download_progress_queue.put(("error", str(e), None))

    threading.Thread(target=worker, daemon=True).start()
    _poll_download_progress(progreso_win, barra, detalle_lbl, info["tag"])


def _poll_download_progress(progreso_win, barra, detalle_lbl, tag):
    try:
        while True:
            item = _download_progress_queue.get_nowait()
            tipo = item[0]
            if tipo == "progress":
                _, descargado, total = item
                if total:
                    pct = min(100, int(descargado * 100 / total))
                    barra["value"] = pct
                    detalle_lbl.config(text=f"{pct}%  ({_formatear_mb(descargado)} / {_formatear_mb(total)})")
                else:
                    detalle_lbl.config(text=f"{_formatear_mb(descargado)} descargados...")
            elif tipo == "extracting":
                barra["value"] = 100
                detalle_lbl.config(text="Descarga completa. Extrayendo...")
                queue_log("[UPDATE] Descarga completa, extrayendo el .zip...")
            elif tipo == "done":
                _, nuevo_exe_path, _ = item
                barra["value"] = 100
                detalle_lbl.config(text="Listo. Reiniciando...")
                queue_log(f"[UPDATE] Descarga lista: {nuevo_exe_path}. Reiniciando para aplicar el reemplazo...")
                progreso_win.after(800, lambda: _reiniciar_para_actualizar(nuevo_exe_path, tag))
                return
            elif tipo == "error":
                _, mensaje, _ = item
                queue_log(f"[UPDATE] Error al actualizar: {mensaje}")
                messagebox.showerror("Error al actualizar", f"No se pudo completar la actualización:\n{mensaje}")
                progreso_win.destroy()
                return
    except Exception:
        pass
    progreso_win.after(150, lambda: _poll_download_progress(progreso_win, barra, detalle_lbl, tag))


def _reiniciar_para_actualizar(nuevo_exe_path, tag):
    try:
        if get_running():
            stop_server()
    except Exception:
        pass
    nl_discord.shutdown_event.set()
    try:
        nl_updater.aplicar_actualizacion_y_reiniciar(nuevo_exe_path, tag)
    except Exception as e:
        queue_log(f"[UPDATE] No se pudo iniciar el reemplazo automático: {e}")
        messagebox.showerror(
            "Error al actualizar",
            f"Se descargó la actualización pero no se pudo aplicar sola:\n{e}\n\n"
            f"El instalador quedó en:\n{nuevo_exe_path}",
        )
        return
    root.after(300, root.destroy)


def procesar_resultado_actualizacion_pendiente():
    resultado = nl_updater.leer_resultado_actualizacion_pendiente()
    if resultado is None:
        return

    tag = resultado.get("tag", "")
    if resultado.get("success"):
        nl_updater.marcar_version_como_instalada(tag)
        queue_log(f"[UPDATE] Actualización a {tag} aplicada correctamente.")
    else:
        error = resultado.get("error") or "motivo desconocido"
        queue_log(f"[UPDATE] La actualización automática a {tag} NO se pudo aplicar: {error}")
        messagebox.showwarning(
            "Actualización no aplicada",
            f"Se descargó la versión {tag}, pero no se pudo reemplazar el "
            f"programa automáticamente:\n\n{error}\n\n"
            "Se abrió la versión anterior. Puedes intentar de nuevo desde "
            "'Acerca de' → 'Buscar actualizaciones', o descargarla manualmente.",
        )


# ----------------- Ventana: Opciones -----------------

options_window = None


def show_about():
    ventana = tk.Toplevel(root)
    ventana.title("Acerca de NitroLink")
    ventana.geometry("440x300")
    ventana.configure(bg="black")
    ventana.resizable(False, False)
    aplicar_icono_ventana(ventana)

    about_text = (
        "NitroLink DNS by SooraMaru\n\n"
        f"Versión: {CURRENT_VERSION}\n\n"
        "Fork of RiiConnect24 DNS Server (based on sudomemoDNS)\n\n"
        "Original authors: Austin Burk / RiiConnect24 team\n\n"
    )
    tk.Label(
        ventana, text=about_text, bg="black", fg="#00ff00",
        font=("Consolas", 9), justify="left", wraplength=400,
    ).pack(padx=14, pady=14, fill="both", expand=True)

    btns = tk.Frame(ventana, bg="black")
    btns.pack(pady=10)

    tk.Button(
        btns, text="Buscar actualizaciones", bg="#222", fg="#00ff00", width=20,
        command=lambda: check_for_updates(manual=True),
    ).pack(side="left", padx=6)
    tk.Button(btns, text="Cerrar", bg="#222", fg="#00ff00", width=12, command=ventana.destroy).pack(side="left", padx=6)


def open_options_window():
    global options_window

    if options_window is not None and options_window.winfo_exists():
        options_window.lift()
        options_window.focus_force()
        return

    options_window = tk.Toplevel(root)
    options_window.title("Opciones - NitroLink DNS")
    options_window.geometry("500x330")
    options_window.configure(bg="black")
    options_window.resizable(False, False)
    aplicar_icono_ventana(options_window)

    rp_var = tk.BooleanVar(value=nl_discord.RICH_PRESENCE_ENABLED)

    tk.Label(
        options_window,
        text="Discord Rich Presence",
        bg="black", fg="#00ff00", font=("Arial", 10, "bold"),
    ).pack(pady=(16, 2))

    chk_rp = tk.Checkbutton(
        options_window,
        text="Mostrar mi actividad en Discord (Rich Presence)",
        variable=rp_var,
        bg="black", fg="#00ff00", selectcolor="black",
        activebackground="black", activeforeground="#00ff00",
        font=("Consolas", 9),
        command=lambda: _actualizar_estado_entry(),
    )
    chk_rp.pack(pady=(0, 4))

    tk.Label(
        options_window,
        text=(
            "Si lo desactivas, NitroLink no se conecta a Discord en absoluto\n"
            "(por privacidad). Dejar el campo vacío usa el bot por defecto de\n"
            "la app; solo escribe algo aquí si quieres usar tu propia app/bot\n"
            "de Discord."
        ),
        bg="black", fg="#888888", font=("Consolas", 8), justify="center",
    ).pack(pady=(0, 10))

    usando_id_por_defecto = (nl_discord.CLIENT_ID == nl_discord.DEFAULT_CLIENT_ID)
    entry_var = tk.StringVar(value="" if usando_id_por_defecto else nl_discord.CLIENT_ID)
    entry = tk.Entry(
        options_window, textvariable=entry_var, width=30,
        bg="#111", fg="#00ff00", insertbackground="#00ff00",
        font=("Consolas", 11), justify="center",
    )
    entry.pack(pady=4)

    tk.Label(
        options_window,
        text="(vacío = usar el bot por defecto de la app)",
        bg="black", fg="#555555", font=("Consolas", 7),
    ).pack()

    def _actualizar_estado_entry():
        entry.config(state="normal" if rp_var.get() else "disabled")

    _actualizar_estado_entry()

    status_lbl = tk.Label(options_window, text="", bg="black", fg="#ff5555", font=("Consolas", 9))
    status_lbl.pack(pady=(6, 0))

    def guardar():
        nuevo_id = entry_var.get().strip()
        if not nuevo_id:
            nuevo_id = nl_discord.DEFAULT_CLIENT_ID
        elif not nuevo_id.isdigit():
            status_lbl.config(text="El Client ID debe contener solo números.")
            return
        if nl_discord.persist_settings(nuevo_id, rp_var.get()):
            estado = "activado" if rp_var.get() else "desactivado"
            queue_log(f"[CONFIG] Discord Rich Presence {estado}. Configuración guardada.")
            options_window.destroy()
        else:
            status_lbl.config(text="No se pudo guardar la configuración (ver log).")

    def usar_por_defecto():
        nl_discord.restore_defaults()
        queue_log("[CONFIG] Se restauraron los valores de Discord por defecto.")
        options_window.destroy()

    btns = tk.Frame(options_window, bg="black")
    btns.pack(pady=16)

    tk.Button(btns, text="Guardar", bg="#222", fg="#00ff00", width=12, command=guardar).pack(side="left", padx=6)
    tk.Button(btns, text="Usar el de por defecto", bg="#222", fg="#00ff00", width=20, command=usar_por_defecto).pack(side="left", padx=6)
    tk.Button(btns, text="Cancelar", bg="#222", fg="#00ff00", width=12, command=options_window.destroy).pack(side="left", padx=6)


# ----------------- Botones -----------------

btn_frame = tk.Frame(main_frame, bg="black")
btn_frame.pack(side="bottom", fill="x", pady=10)

btn_start = tk.Button(btn_frame, text="Iniciar", bg="#222", fg="#00ff00", width=12, command=start_server)
btn_start.pack(side="left", padx=5)

btn_stop = tk.Button(btn_frame, text="Detener", bg="#222", fg="#00ff00", width=12, command=stop_server, state="disabled")
btn_stop.pack(side="left", padx=5)

tk.Button(btn_frame, text="Limpiar Log", bg="#222", fg="#00ff00", width=12, command=clear_log).pack(side="left", padx=5)

tk.Button(btn_frame, text="Mario Kart DS", bg="#222", fg="#00ff00", width=14, command=open_mkds_window).pack(side="left", padx=5)

tk.Button(btn_frame, text="Opciones", bg="#222", fg="#00ff00", width=12, command=open_options_window).pack(side="left", padx=5)

tk.Button(btn_frame, text="Acerca de", bg="#222", fg="#00ff00", width=12, command=show_about).pack(side="right", padx=5)

_gui_log_direct("==============================================")
_gui_log_direct(" NitroLink DNS Console v1.0 Ready ")
_gui_log_direct("==============================================")
if not nl_discord.RICH_PRESENCE_ENABLED:
    _gui_log_direct("[INFO] Discord Rich Presence está desactivado (ver Opciones).")

root.protocol("WM_DELETE_WINDOW", on_close)

root.after(100, process_gui_queue)

threading.Thread(
    target=nl_discord.update_discord,
    args=(get_running, get_client_count),
    daemon=True,
).start()

root.after(300, procesar_resultado_actualizacion_pendiente)
root.after(1500, lambda: check_for_updates(manual=False))

root.mainloop()