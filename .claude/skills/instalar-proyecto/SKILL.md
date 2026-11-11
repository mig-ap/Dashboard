---
name: instalar-proyecto
description: Instala el dashboard de confort térmico (proyecto SECIHTI, Puebla) en una computadora con Windows, macOS o Linux, incluido Python y sus librerías, guiando paso a paso a alguien que nunca ha programado. Úsala cuando pidan instalar, configurar o abrir el proyecto o el dashboard en su computadora, o cuando la instalación falle.
---

# Instalar el dashboard de confort térmico

Esta skill sirve **solo para instalar** el proyecto y dejarlo listo para abrir con doble clic. La persona que la usa **probablemente nunca ha programado**: tu trabajo es que termine con el dashboard abierto sin tener que entender nada técnico.

El trabajo pesado lo hace `instalar.py`, que está en la carpeta principal del proyecto y también en `scripts/` de esta skill. Ese script:
- revisa Python;
- crea un entorno propio en `.venv` (no toca el resto de la computadora);
- instala pandas y numpy;
- comprueba que el cálculo y el dashboard funcionan;
- crea el acceso de doble clic.

Se puede repetir sin riesgo.

## 1. Cómo hablarle a la persona

- **Un paso a la vez.** Da una instrucción, di qué debería ver en pantalla y espera a que confirme antes de seguir.
- **Sin jerga.** Si tienes que decir "terminal", explica que es una ventana donde se escriben órdenes. No digas "PATH", "venv", "pip" ni "repositorio" sin explicarlos; mejor, no los digas.
- **Que copie y pegue, no que escriba.** Da los comandos completos en un bloque, uno por mensaje.
- **Errores en lenguaje normal.** Si algo falla, pide que copie y pegue lo que salió en pantalla, o que te comparta `instalacion.log`. Explica qué pasó en palabras simples antes de dar la solución.
- **Tranquiliza.** Nada de lo que hace el instalador daña la computadora. Todo queda dentro de la carpeta del proyecto, y borrarla lo desinstala.

## 2. Reglas de seguridad

- **Pide permiso** antes de instalar programas en el sistema (Python, Git) y di qué instalarás, de dónde y por qué.
- **Solo fuentes oficiales:** python.org, el gestor de paquetes del sistema (winget, apt, dnf, Homebrew) y la página del proyecto en GitHub.
- **Nunca** instales librerías fuera del entorno del proyecto: nada de `pip install` suelto ni `sudo pip`.
- **`sudo`** (Linux) solo para instalar Python con el gestor del sistema, explicando que pedirá la contraseña de la computadora.
- No cambies configuraciones del sistema a mano. La única excepción es la casilla "Add python.exe to PATH" del instalador de Python en Windows.

## 3. Antes de empezar: ¿dónde corren tus comandos?

Pregunta qué sistema tiene la persona: Windows, Mac o Linux.

Si puedes ejecutar comandos, comprueba con `python -c "import platform; print(platform.platform())"` (o `python3`, o `py`) que estás en **su** computadora y no en un entorno aparte:

- **Coinciden** (p. ej. en Claude Code en su equipo): haz tú los pasos y cuéntale en una línea qué hiciste en cada uno.
- **No coinciden** (p. ej. un entorno en la nube o aislado), o no puedes ejecutar comandos: **guíala** para que lo haga ella, con los pasos de abajo.

## 4. Paso 1 — Tener Python 3.10 o más reciente

Comprueba la versión. Si responde 3.10 o más, sigue al paso 2.

| Sistema | Comprobar | Si falta o es menor a 3.10 |
|---|---|---|
| Windows | `py --version` | Opción fácil: en python.org/downloads, botón amarillo "Download Python", abrir el archivo y **marcar "Add python.exe to PATH"** en la primera pantalla, luego "Install Now". Alternativa en una terminal: `winget install -e --id Python.Python.3.12`. Después, **cerrar y volver a abrir** la terminal. |
| macOS | `python3 --version` | python.org/downloads, botón amarillo, abrir el `.pkg` y seguir el instalador. Si aparece una ventana para instalar "herramientas de línea de comandos", es la versión de Apple, normalmente vieja: mejor la de python.org. |
| Linux | `python3 --version` | Ubuntu/Debian: `sudo apt install python3 python3-venv`. Fedora: `sudo dnf install python3`. |

En Windows, si `py` no existe pero `python` abre la Microsoft Store, Python no está instalado: usa la opción fácil de arriba.

## 5. Paso 2 — Tener el proyecto en la computadora

Si ya tiene la carpeta del proyecto (con `README.md`, `dashboard`, `backend`, …), sigue al paso 3.

Si no:
1. Pídele que entre a **https://github.com/SanMoF/Dashboard**, pulse el botón verde **Code → Download ZIP** y guarde el archivo.
2. Que lo **descomprima**:
   - Windows: clic derecho → "Extraer todo".
   - Mac: doble clic.
   - Linux: clic derecho → "Extraer aquí".
3. Que deje la carpeta en un lugar fácil, como Documentos. **No debe trabajar dentro del .zip sin descomprimir.**

Si en la carpeta no aparece `instalar.py` (una versión anterior del proyecto), copia ahí `scripts/instalar.py` de esta skill, o pídele que lo descargue de la misma página.

Si la persona ya usa Git, también sirve `git clone https://github.com/SanMoF/Dashboard.git`, pero no lo propongas a quien no lo conoce.

## 6. Paso 3 — Abrir una terminal dentro de la carpeta del proyecto

| Sistema | Cómo |
|---|---|
| Windows | Abrir la carpeta del proyecto en el Explorador, hacer clic en la barra de dirección (arriba), escribir `cmd` y pulsar Enter |
| macOS | Abrir la app **Terminal** (Cmd + Espacio, escribir "Terminal"), escribir `cd ` con un espacio, **arrastrar la carpeta** a la ventana y pulsar Enter |
| Linux | Clic derecho dentro de la carpeta → "Abrir en una terminal" |

Para comprobar que está en el lugar correcto, que escriba `dir` (Windows) o `ls` (Mac, Linux): debe ver `instalar.py` en la lista.

## 7. Paso 4 — Ejecutar el instalador

| Sistema | Comando |
|---|---|
| Windows | `py instalar.py` |
| macOS y Linux | `python3 instalar.py` |

Si lo ejecutas tú, agrega `--sin-pausa`. Debe ver cinco pasos con ✓ (u "OK") y al final **"Listo. El dashboard está instalado."**:

1. Python;
2. el entorno;
3. las librerías;
4. la comprobación del cálculo y del dashboard;
5. el acceso de doble clic.

La primera vez tarda unos minutos y descarga unos 60 MB.

Si sale "No se pudo completar", el mismo mensaje dice **qué pasó y qué hacer**. Explícaselo con tus palabras, ayúdala con esa solución y vuelvan a ejecutar el instalador.

## 8. Paso 5 — Abrir el dashboard

| Sistema | Cómo |
|---|---|
| Windows | Doble clic en **"Abrir dashboard.bat"**, en la carpeta del proyecto |
| macOS | Doble clic en **"Abrir dashboard.command"**. La primera vez, si macOS dice que no puede abrirlo: clic derecho → Abrir → Abrir |
| Linux | En la terminal, `./abrir_dashboard.sh`, o doble clic → "Ejecutar en terminal" |

Se abre una ventana negra (el servidor) y el navegador con el dashboard. **Mientras use el dashboard, esa ventana debe quedar abierta**; al cerrarla, el dashboard se apaga. Si el navegador no se abre solo, que copie la dirección que muestra la ventana (`http://localhost:8000/` o similar).

Confirma con la persona que ve el título "Confort térmico" y la tabla de escenarios.

## 9. Problemas frecuentes

| Lo que pasa | Qué hacer |
|---|---|
| Windows: "py no se reconoce como un comando" | Python no está instalado, o se instaló sin "Add python.exe to PATH". Reinstalarlo marcando esa casilla, cerrar la terminal y abrir otra. |
| Windows: el `.bat` se cierra solo de inmediato | Abrir una terminal en la carpeta y ejecutar `"Abrir dashboard.bat"` para leer el mensaje. Casi siempre falta correr el instalador. |
| macOS: "no se puede abrir porque es de un desarrollador no identificado" | Clic derecho sobre el archivo → Abrir → Abrir (solo la primera vez). |
| Linux: "No module named venv" o "ensurepip" | `sudo apt install python3-venv` y volver a ejecutar el instalador. |
| "no hay conexión con el repositorio de librerías" | Revisar internet. En redes de oficina o escuela puede haber un proxy: pedir los datos a sistemas. |
| Python demasiado viejo | Instalar uno nuevo (paso 1) y usar `py` (Windows) o `python3` (Mac, Linux). |
| "este archivo no está dentro de la carpeta del proyecto" | Descomprimir el proyecto completo y ejecutar desde su carpeta principal. |
| El dashboard abre pero sin gráficas | Las gráficas se cargan de internet: revisar la conexión. |
| Otro programa ya usa el puerto 8000 | No hay que hacer nada: el dashboard usa el siguiente libre y lo muestra en la ventana. |

## 10. Al terminar

Resume en 3 o 4 líneas:
- qué quedó instalado (Python, si lo instalaste, y las librerías dentro de la carpeta del proyecto);
- dónde está la carpeta;
- cómo abrir el dashboard la próxima vez (el doble clic).

Para **desinstalar** basta con borrar la carpeta del proyecto (y, si se quiere, desinstalar Python como cualquier programa).

Si la persona quiere además **generar datos** o importar archivos de Revit, eso es otra tarea: la skill `esquema-confort-termico` y el `README.md` del proyecto lo explican.
