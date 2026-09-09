# nl_updater.py
"""Chequeo de actualizaciones y auto-actualización contra GitHub Releases.

Dos modos, según cómo se esté corriendo la app:

- Compilada como .exe en Windows: se puede descargar el nuevo .exe (con
  barra de progreso) y auto-reemplazar el actual. Un .exe no puede
  sobrescribirse a sí mismo mientras está corriendo, así que se usa la
  técnica estándar: descargar aparte, lanzar un script .bat/.ps1 separado que
  espera a que este proceso termine, recién ahí reemplaza el archivo y
  vuelve a abrir la app.
- Corriendo como script .py, o en otro sistema operativo: no se puede
  auto-reemplazar de forma segura. En ese caso solo se abre la página de
  la release en el navegador para que el usuario la descargue a mano.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
import zipfile

import requests

from nl_paths import resource_path
from nl_gui_queue import queue_log

# Repo de GitHub donde se publican los releases (usuario/repositorio).
GITHUB_REPO = "xxjeysonxx/NitroLink-DNS"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Registro de qué versión ya se descargó y aplicó vía auto-actualización.
UPDATE_STATE_FILE = resource_path("nitrolink_update_state.dat")


def leer_ultima_version_instalada():
    """Devuelve el tag de la última versión aplicada por auto-actualización
    en este equipo, o "" si nunca se usó esa función."""
    try:
        if os.path.exists(UPDATE_STATE_FILE):
            with open(UPDATE_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_installed_tag", "")
    except Exception as e:
        queue_log(f"[UPDATE] No se pudo leer el estado de actualización: {e}")
    return ""


def marcar_version_como_instalada(tag):
    """Registra que `tag` ya se descargó y aplicó, para no volver a
    ofrecerla como "nueva" automáticamente al reabrir la app."""
    try:
        with open(UPDATE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_installed_tag": tag}, f)
    except Exception as e:
        queue_log(f"[UPDATE] No se pudo guardar el estado de actualización: {e}")


def _parse_version(texto):
    """Convierte 'v1.2.3', '1.2.3' o similar en (1, 2, 3) para comparar
    numéricamente (así 1.10.0 se reconoce bien como mayor que 1.2.0).
    """
    numeros = re.findall(r"\d+", texto or "")
    return tuple(int(n) for n in numeros) if numeros else (0,)


def check_for_update(current_version, timeout=10, ignorar_ya_instalada=True):
    """Consulta la última release en GitHub."""
    try:
        resp = requests.get(
            GITHUB_API_LATEST,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        queue_log(f"[UPDATE] No se pudo consultar actualizaciones: {e}")
        return None

    latest_tag = data.get("tag_name", "")
    if not latest_tag:
        return None

    if _parse_version(latest_tag) <= _parse_version(current_version):
        return None

    if ignorar_ya_instalada and latest_tag == leer_ultima_version_instalada():
        queue_log(f"[UPDATE] {latest_tag} ya se instaló antes en este equipo; no se vuelve a pedir sola.")
        return None

    asset_exe = None
    asset_zip = None
    for asset in data.get("assets", []):
        nombre = asset.get("name", "").lower()
        if nombre.endswith(".exe") and asset_exe is None:
            asset_exe = asset
        elif nombre.endswith(".zip") and asset_zip is None:
            asset_zip = asset

    elegido, tipo = (asset_exe, "exe") if asset_exe else (asset_zip, "zip") if asset_zip else (None, None)

    info = {
        "tag": latest_tag,
        "name": data.get("name") or latest_tag,
        "url": data.get("html_url", GITHUB_RELEASES_URL),
        "notes": (data.get("body") or "").strip(),
        "asset_url": None,
        "asset_name": None,
        "asset_size": None,
        "asset_type": None,
    }
    if elegido:
        info["asset_url"] = elegido.get("browser_download_url")
        info["asset_name"] = elegido.get("name")
        info["asset_size"] = elegido.get("size")
        info["asset_type"] = tipo
    return info


def abrir_pagina_release(url=None):
    """Abre la página de la release en el navegador por defecto."""
    webbrowser.open(url or GITHUB_RELEASES_URL)


def puede_autoactualizar():
    """La auto-actualización solo es segura si estamos en Windows Y corriendo como .exe compilado."""
    return os.name == "nt" and getattr(sys, "frozen", False)


def descargar_actualizacion(asset_url, destino, progress_callback=None, chunk_size=65536):
    """Descarga asset_url a destino, en streaming, reportando el progreso."""
    resp = requests.get(asset_url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("Content-Length", 0))
    descargado = 0

    tmp_destino = destino + ".part"
    with open(tmp_destino, "wb") as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            f.write(chunk)
            descargado += len(chunk)
            if progress_callback:
                progress_callback(descargado, total)

    if total and descargado != total:
        try:
            os.remove(tmp_destino)
        except Exception:
            pass
        raise RuntimeError(
            f"Descarga incompleta: se esperaban {total} bytes y se recibieron {descargado}."
        )

    os.replace(tmp_destino, destino)
    queue_log(f"[UPDATE] Descarga verificada: {descargado} bytes.")
    return destino


def extraer_exe_de_zip(zip_path, extract_dir=None):
    """Descomprime zip_path y busca el primer .exe adentro."""
    extract_dir = extract_dir or os.path.join(tempfile.gettempdir(), "nitrolink_update_extract")
    if os.path.isdir(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    for carpeta, _subcarpetas, archivos in os.walk(extract_dir):
        for nombre in archivos:
            if nombre.lower().endswith(".exe"):
                return os.path.join(carpeta, nombre)

    raise RuntimeError("El .zip descargado no contiene ningún archivo .exe.")


UPDATE_RESULT_FILE = os.path.join(tempfile.gettempdir(), "nitrolink_update_result.json")


def leer_resultado_actualizacion_pendiente():
    """Lee el resultado del script de auto-actualización si existe."""
    if not os.path.exists(UPDATE_RESULT_FILE):
        return None
    try:
        with open(UPDATE_RESULT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        queue_log(f"[UPDATE] No se pudo leer el resultado de la actualización: {e}")
        return None
    finally:
        try:
            os.remove(UPDATE_RESULT_FILE)
        except Exception:
            pass


def aplicar_actualizacion_y_reiniciar(nuevo_exe_path, tag):
    """Lanza el script de PowerShell totalmente desvinculado del proceso principal."""
    exe_actual = os.path.abspath(sys.executable)
    pid_actual = os.getpid()
    exe_viejo = os.path.splitext(exe_actual)[0] + ".old"

    ps1_path = os.path.join(tempfile.gettempdir(), "nitrolink_update.ps1")

    contenido_ps1 = f"""
try {{
    Write-Output "=== NitroLink updater: $(Get-Date) ==="

    $pidActual = {pid_actual}
    $nuevo = '{nuevo_exe_path}'
    $actual = '{exe_actual}'
    $viejo = '{exe_viejo}'
    $resultPath = '{UPDATE_RESULT_FILE}'
    $tag = '{tag}'

    Write-Output "Ejecutable actual: $actual"
    Write-Output "Respaldo: $viejo"
    Write-Output "Nuevo ejecutable: $nuevo"

    # ---------------------------------------------------------
    # 1. Esperar a que NitroLink termine totalmente
    # ---------------------------------------------------------

    Write-Output "Esperando a que cierre el proceso PID $pidActual..."

    while (Get-Process -Id $pidActual -ErrorAction SilentlyContinue) {{
        Start-Sleep -Milliseconds 500
    }}

    Write-Output "Proceso cerrado. Esperando liberación de handles de PyInstaller..."
    Start-Sleep -Seconds 3

    # ---------------------------------------------------------
    # 2. Eliminar un .old anterior si existe
    # ---------------------------------------------------------

    if (Test-Path -LiteralPath $viejo) {{
        Write-Output "Existe un respaldo anterior. Eliminándolo..."
        for ($intento = 1; $intento -le 20; $intento++) {{
            try {{
                Remove-Item -LiteralPath $viejo -Force -ErrorAction Stop
                Write-Output "Respaldo anterior eliminado."
                break
            }} catch {{
                Start-Sleep -Milliseconds 500
            }}
        }}
    }}

    # ---------------------------------------------------------
    # 3. Renombrar NitroLink.exe -> NitroLink.old
    # ---------------------------------------------------------

    $viejoRenombrado = $false
    $errorViejo = ""

    Write-Output "Renombrando ejecutable anterior a NitroLink.old..."

    for ($intento = 1; $intento -le 60; $intento++) {{
        try {{
            if (Test-Path -LiteralPath $actual) {{
                Move-Item -LiteralPath $actual -Destination $viejo -Force -ErrorAction Stop
                $viejoRenombrado = $true
                Write-Output "NitroLink.exe -> NitroLink.old OK."
                break
            }} else {{
                $viejoRenombrado = $true
                Write-Output "El ejecutable anterior ya no existe."
                break
            }}
        }} catch {{
            $errorViejo = $_.Exception.Message
            if ($intento % 10 -eq 0) {{
                Write-Output "Intento $intento para renombrar el viejo fallo: $errorViejo"
            }}
            Start-Sleep -Milliseconds 500
        }}
    }}

    # ---------------------------------------------------------
    # 4. Colocar el nuevo ejecutable
    # ---------------------------------------------------------

    $reemplazado = $false
    $errorNuevo = ""

    if ($viejoRenombrado) {{
        if (-not (Test-Path -LiteralPath $nuevo)) {{
            $errorNuevo = "No existe el ejecutable descargado: $nuevo"
            Write-Output $errorNuevo
        }} else {{
            Write-Output "Renombrando nuevo ejecutable a NitroLink.exe..."

            for ($intento = 1; $intento -le 40; $intento++) {{
                try {{
                    Move-Item -LiteralPath $nuevo -Destination $actual -Force -ErrorAction Stop
                    $reemplazado = $true
                    Write-Output "NitroLink_update_download.exe -> NitroLink.exe OK."
                    break
                }} catch {{
                    $errorNuevo = $_.Exception.Message
                    if ($intento % 10 -eq 0) {{
                        Write-Output "Intento $intento para colocar nuevo exe fallo: $errorNuevo"
                    }}
                    Start-Sleep -Milliseconds 750
                }}
            }}
        }}
    }} else {{
        $errorNuevo = "No se pudo renombrar NitroLink.exe a NitroLink.old: $errorViejo"
    }}

    # ---------------------------------------------------------
    # 5. Si falló, intentar restaurar NitroLink.old
    # ---------------------------------------------------------

    if (-not $reemplazado) {{
        Write-Output "La actualización falló."
        if ((Test-Path -LiteralPath $viejo) -and (-not (Test-Path -LiteralPath $actual))) {{
            Write-Output "Intentando restaurar NitroLink.old..."
            try {{
                Move-Item -LiteralPath $viejo -Destination $actual -Force -ErrorAction Stop
                Write-Output "Restauración completada."
            }} catch {{
                Write-Output "ERROR: No se pudo restaurar NitroLink.old."
            }}
        }}
    }}

    # ---------------------------------------------------------
    # 6. Preparar resultado
    # ---------------------------------------------------------

    $errorParaJson = $null
    if (-not $reemplazado) {{
        $errorParaJson = "No se pudo completar la actualización. Error: $errorNuevo"
    }}

    $resultado = [PSCustomObject]@{{
        tag = $tag
        success = $reemplazado
        error = $errorParaJson
    }}

    $resultado | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    Write-Output "Resultado guardado."

    # ---------------------------------------------------------
    # 7. Notificar y abrir NitroLink de forma 100% independiente
    # ---------------------------------------------------------

    if (Test-Path -LiteralPath $actual) {{
        if ($reemplazado) {{
            # Cuadro de diálogo de confirmación antes de iniciar la app
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show(
                "NitroLink DNS se ha actualizado con exito a la version $tag!",
                "Actualización Completada",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information
            )
        }}

        Write-Output "Abriendo NitroLink de forma independiente: $actual"
        
        # Invocar a través de explorer.exe rompe la relación padre-hijo de Windows/PyInstaller
        Start-Process -FilePath "explorer.exe" -ArgumentList "`"$actual`""

        if (Test-Path -LiteralPath $viejo) {{
            Start-Sleep -Seconds 3
            Remove-Item -LiteralPath $viejo -Force -ErrorAction SilentlyContinue
        }}
    }} elseif (Test-Path -LiteralPath $viejo) {{
        Write-Output "NitroLink.exe no existe. Abriendo respaldo: $viejo"
        Start-Process -FilePath "explorer.exe" -ArgumentList "`"$viejo`""
    }} else {{
        Write-Output "ERROR: No existe NitroLink.exe ni NitroLink.old."
    }}

    Write-Output "=== Fin del updater ==="

}} catch {{
    Write-Output "ERROR INESPERADO: $_"
}}

Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""

    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(contenido_ps1)

    # CAMBIO: Se remueve -WindowStyle Hidden y se ajusta 'start' para mostrar la ventana
    cmd_comando = f'cmd.exe /c start "NitroLink Updater" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{ps1_path}"'

    try:
        subprocess.Popen(
            cmd_comando,
            shell=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except Exception as e:
        queue_log(f"[UPDATE] Error lanzando actualizador: {e}")