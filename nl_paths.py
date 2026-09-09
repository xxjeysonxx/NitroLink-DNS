# nl_paths.py
"""Resolución de rutas de recursos (icono, JSON de juegos, config, etc.),
compatible tanto con `python nitrolink_dns.py` como con un ejecutable
empaquetado con PyInstaller.

IMPORTANTE: estos archivos (game_ids.json, icono.ico, nitrolink_config.dat)
son EXTERNOS y editables por el usuario, no recursos empaquetados dentro
del .exe. Por eso NO usamos sys._MEIPASS (la carpeta temporal donde
PyInstaller descomprime el .exe en cada ejecución y que se borra al
cerrar) — si la usáramos, nitrolink_config.dat jamás persistiría entre
ejecuciones y game_ids.json/icono.ico habría que reempaquetarlos para
poder editarlos. En su lugar, siempre usamos la carpeta donde está el
.exe (o el .py, si se corre sin compilar).
"""

import os
import sys


def resource_path(filename):
    """Devuelve la ruta absoluta de un recurso que vive junto al .exe/.py."""
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

