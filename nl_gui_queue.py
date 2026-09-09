# nl_gui_queue.py
"""Cola thread-safe para actualizar la GUI desde hilos de fondo.

Tkinter no es thread-safe: solo el hilo principal debe tocar los widgets.
Cualquier otro hilo (servidor DNS, HTTP de conntest, Discord Rich Presence)
llama a queue_log()/queue_client_update() para encolar lo que quiere mostrar;
el módulo principal (nitrolink_dns.py) es el único que lee gui_queue, vía
root.after(...), y aplica los cambios reales a los widgets.
"""

import queue

# Cola global: (tipo, payload). tipo es "log" o "client".
gui_queue = queue.Queue()


def queue_log(text):
    """Encola una línea de texto para el log de la consola."""
    gui_queue.put(("log", text))


def queue_client_update(ip):
    """Encola una IP de cliente recién visto, para la lista de clientes."""
    gui_queue.put(("client", ip))
