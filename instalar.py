#!/usr/bin/env python3
"""
instalar.py — Instala el dashboard de confort térmico en esta computadora (Windows, macOS o Linux).

Qué hace, paso a paso (se puede repetir sin problema; lo que ya está hecho no se rehace):
  1. Revisa que Python sea 3.10 o más reciente.
  2. Crea un entorno propio del proyecto en la carpeta .venv (no toca el resto de la computadora).
  3. Instala ahí las librerías que necesita el proyecto (backend/requirements.txt).
  4. Comprueba que todo funciona: genera datos de prueba y levanta el dashboard un momento.
  5. Crea un archivo para abrir el dashboard con doble clic.
Deja el detalle en instalacion.log, junto a este archivo.

Uso:  Windows:        py instalar.py
      macOS y Linux:  python3 instalar.py
Opciones: --dev (también instala lo necesario para las pruebas de fórmulas), --sin-pausa
"""
import os, platform, re, shutil, subprocess, sys, tempfile, time

try:
    sys.stdout.reconfigure(errors="backslashreplace")   # consolas que no admiten todos los caracteres
except AttributeError:
    pass

RAIZ = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(RAIZ, ".venv")
LOG = os.path.join(RAIZ, "instalacion.log")
WINDOWS, MAC = os.name == "nt", sys.platform == "darwin"
PY_VENV = os.path.join(VENV, "Scripts", "python.exe") if WINDOWS else os.path.join(VENV, "bin", "python")
MINIMO = (3, 10)
registro = []

def _admite(simbolo):
    try:
        simbolo.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False
# en consolas que no muestran ✓ o ✗ se escribe la palabra
SI, NO = ("✓", "✗") if _admite("✓✗") else ("OK", "ERROR")

def decir(texto=""):
    texto = texto.replace("✓", SI).replace("✗", NO)
    print(texto, flush=True)
    registro.append(texto)

def guardar_log():
    with open(LOG, "w", encoding="utf-8", newline="\n") as f:
        f.write("Instalación del dashboard de confort térmico — " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write("Sistema: {} {} · Python {} ({})\n\n".format(platform.system(), platform.release(), platform.python_version(), sys.executable))
        f.write("\n".join(registro) + "\n")

def terminar(codigo, pausa):
    guardar_log()
    if pausa and sys.stdin and sys.stdin.isatty():
        try:
            input("\nPulsa Enter para cerrar esta ventana…")
        except EOFError:
            pass
    sys.exit(codigo)

def fallo(paso, explicacion, solucion, pausa, detalle=""):
    decir("")
    decir("✗ No se pudo completar: " + paso)
    decir("  Qué pasó: " + explicacion)
    decir("  Qué hacer: " + solucion)
    if detalle:
        registro.append("\n--- detalle técnico ---\n" + detalle.strip()[-4000:])
    decir("  (El detalle técnico quedó en instalacion.log; compártelo si pides ayuda.)")
    terminar(1, pausa)

def correr(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)

def como_instalar_python():
    if WINDOWS:
        return ("instala Python desde https://www.python.org/downloads/ (botón amarillo «Download Python») y, en la primera "
                "pantalla del instalador, marca la casilla «Add python.exe to PATH». Luego cierra esta ventana y vuelve a ejecutar «py instalar.py».")
    if MAC:
        return ("instala Python desde https://www.python.org/downloads/ (botón amarillo «Download Python», archivo .pkg) y sigue el "
                "instalador. Luego abre una Terminal nueva y vuelve a ejecutar «python3 instalar.py».")
    return ("instala Python 3.10 o más reciente con el gestor de tu sistema, por ejemplo en Ubuntu/Debian: "
            "«sudo apt install python3 python3-venv»; en Fedora: «sudo dnf install python3». Luego vuelve a ejecutar «python3 instalar.py».")

def paso_python(pausa):
    decir("1/5  Revisando Python…")
    v = sys.version_info
    if (v.major, v.minor) < MINIMO:
        fallo("Python es demasiado viejo", "este proyecto necesita Python {}.{} o más reciente y tienes {}.{}.{}.".format(MINIMO[0], MINIMO[1], v.major, v.minor, v.micro),
              como_instalar_python(), pausa)
    decir("     ✓ Python {} ({})".format(platform.python_version(), platform.system()))

def paso_venv(pausa):
    decir("2/5  Preparando el entorno del proyecto (.venv)…")
    if os.path.exists(PY_VENV) and correr([PY_VENV, "-c", "import sys; print(sys.version)"]).returncode == 0:
        decir("     ✓ Ya existía; se reutiliza")
        return
    if os.path.exists(VENV):
        shutil.rmtree(VENV, ignore_errors=True)   # un .venv roto (p. ej. copiado de otra computadora) se rehace
    r = correr([sys.executable, "-m", "venv", VENV])
    if r.returncode != 0 or not os.path.exists(PY_VENV):
        texto = (r.stderr or "") + (r.stdout or "")
        if not WINDOWS and not MAC and ("ensurepip" in texto or "venv" in texto.lower()):
            fallo("crear el entorno", "a este Python le falta el módulo para crear entornos (venv).",
                  "en Ubuntu/Debian ejecuta «sudo apt install python3-venv» (o «python3.X-venv» con tu versión) y vuelve a ejecutar el instalador.", pausa, texto)
        fallo("crear el entorno", "Python no pudo crear la carpeta .venv.",
              "revisa que la carpeta del proyecto no esté dentro de un .zip (descomprímela primero) y que tengas permiso de escritura en ella.", pausa, texto)
    decir("     ✓ Entorno creado")

def paso_librerias(dev, pausa):
    decir("3/5  Instalando librerías (pandas, numpy{}). La primera vez puede tardar unos minutos y descarga unos 60 MB…".format(", pythermalcomfort" if dev else ""))
    req = os.path.join(RAIZ, "backend", "requirements-dev.txt" if dev else "requirements.txt")
    r = correr([PY_VENV, "-m", "pip", "install", "--disable-pip-version-check", "-r", req])
    if r.returncode != 0:
        texto = r.stdout + r.stderr
        if re.search(r"(?i)connection|network|resolve|timed out|proxy|SSL", texto):
            fallo("instalar librerías", "no hay conexión con el repositorio de librerías de Python (pypi.org).",
                  "revisa tu conexión a internet; si estás en una red de oficina o escuela con proxy, pide la dirección del proxy a sistemas.", pausa, texto)
        fallo("instalar librerías", "pip no pudo instalar las librerías.", "vuelve a ejecutar el instalador; si se repite, comparte instalacion.log.", pausa, texto)
    r = correr([PY_VENV, "-c", "import pandas, numpy; print(pandas.__version__, numpy.__version__)"])
    if r.returncode != 0:
        fallo("comprobar librerías", "las librerías se instalaron pero no se pueden usar.", "borra la carpeta .venv y vuelve a ejecutar el instalador.", pausa, r.stderr)
    pd_v, np_v = r.stdout.split()
    decir("     ✓ pandas {} y numpy {}".format(pd_v, np_v))

def paso_prueba(pausa):
    decir("4/5  Comprobando que todo funciona…")
    with tempfile.TemporaryDirectory() as tmp:
        r = correr([PY_VENV, os.path.join(RAIZ, "backend", "mock", "crear_mock.py"), "--vivienda", "PUE-01"])
        if r.returncode != 0:
            fallo("crear datos de prueba", "el programa de datos de prueba falló.", "comparte instalacion.log.", pausa, r.stdout + r.stderr)
        ent = os.path.join(RAIZ, "backend", "mock", "entradas", "PUE-01")
        salida = os.path.join(tmp, "prueba.csv")
        r = correr([PY_VENV, os.path.join(RAIZ, "backend", "generar_csv_confort.py"), "--escenarios", os.path.join(ent, "escenarios.csv"),
                    "--config", os.path.join(ent, "config.csv"), "--clima", os.path.join(ent, "clima.csv"), "--salida", salida])
        if r.returncode != 0 or not os.path.exists(salida):
            fallo("generar el CSV de prueba", "el cálculo de confort no terminó.", "comparte instalacion.log.", pausa, r.stdout + r.stderr)
    decir("     ✓ Cálculo de confort (CSV de prueba con 75 filas)")
    srv = subprocess.Popen([PY_VENV, "-u", os.path.join(RAIZ, "dashboard", "servidor.py"), "--sin-navegador", "--puerto", "8765"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        url, inicio = None, time.time()
        for linea in srv.stdout:
            m = re.search(r"http://localhost:\d+/", linea)
            if m:
                url = m.group(0); break
            if time.time() - inicio > 30:
                break
        if not url:
            fallo("abrir el dashboard", "el servidor del dashboard no arrancó.", "comparte instalacion.log.", pausa)
        import urllib.request
        lista = urllib.request.urlopen(url.replace("localhost", "127.0.0.1") + "api/csv", timeout=10).read().decode("utf-8")
        if ".csv" not in lista:
            fallo("abrir el dashboard", "el dashboard arrancó pero no encontró datos en la carpeta datos/.",
                  "revisa que la carpeta datos/ del proyecto tenga archivos .csv.", pausa, lista)
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()
    decir("     ✓ Dashboard (servidor local y datos)")

def paso_acceso():
    decir("5/5  Creando el acceso para abrir el dashboard…")
    if WINDOWS:
        ruta = os.path.join(RAIZ, "Abrir dashboard.bat")
        contenido = ('@echo off\r\ncd /d "%~dp0"\r\necho Abriendo el dashboard de confort termico. No cierres esta ventana mientras lo usas.\r\n'
                     '".venv\\Scripts\\python.exe" dashboard\\servidor.py\r\npause\r\n')
    elif MAC:
        ruta = os.path.join(RAIZ, "Abrir dashboard.command")
        contenido = ('#!/bin/bash\ncd "$(dirname "$0")"\necho "Abriendo el dashboard de confort térmico. No cierres esta ventana mientras lo usas."\n'
                     './.venv/bin/python dashboard/servidor.py\n')
    else:
        ruta = os.path.join(RAIZ, "abrir_dashboard.sh")
        contenido = ('#!/bin/bash\ncd "$(dirname "$0")"\necho "Abriendo el dashboard de confort térmico. No cierres esta ventana mientras lo usas."\n'
                     './.venv/bin/python dashboard/servidor.py\n')
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(contenido)
    if not WINDOWS:
        os.chmod(ruta, 0o755)
    decir("     ✓ {}".format(os.path.basename(ruta)))
    return ruta

def main():
    pausa = "--sin-pausa" not in sys.argv
    decir("Instalación del dashboard de confort térmico")
    decir("Carpeta: " + RAIZ)
    decir("")
    if not os.path.exists(os.path.join(RAIZ, "backend", "requirements.txt")):
        fallo("encontrar el proyecto", "este archivo no está dentro de la carpeta del proyecto (no se encuentra backend/requirements.txt).",
              "descomprime el proyecto completo y ejecuta instalar.py desde su carpeta principal.", pausa)
    paso_python(pausa)
    paso_venv(pausa)
    paso_librerias("--dev" in sys.argv, pausa)
    paso_prueba(pausa)
    acceso = paso_acceso()
    decir("")
    decir("✓ Listo. El dashboard está instalado.")
    decir("")
    decir("Para abrirlo:")
    if WINDOWS:
        decir("  Dale doble clic a «{}» en la carpeta del proyecto.".format(os.path.basename(acceso)))
    elif MAC:
        decir("  Dale doble clic a «{}» en la carpeta del proyecto.".format(os.path.basename(acceso)))
        decir("  La primera vez, si macOS lo bloquea: clic derecho → Abrir → Abrir.")
    else:
        decir("  Ejecuta «./abrir_dashboard.sh» en la carpeta del proyecto, o dale doble clic y elige «Ejecutar en terminal».")
    decir("  Se abre el navegador con el dashboard. Para cerrarlo, cierra esa ventana (o pulsa Ctrl+C en ella).")
    terminar(0, pausa)

if __name__ == "__main__":
    main()
